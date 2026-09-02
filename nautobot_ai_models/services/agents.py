"""Build a LangChain agent from the registry rows. This module calls no model.

`build_agent()` returns a configured agent and stops. The consuming app runs the agent, and it
decides the checkpointer, the timeout, and what to record.

This module keeps these rules:

* **G1** - a build runs nothing. `build_agent()` opens no socket, writes no row, and calls no
  model. A subagent wrapper holds a call to its specialist, and that call happens at run time.
* **G2** - this module imports LangChain lazily, behind the `agents` extra.
* **G3** - a build refuses a disabled agent, model, or provider before it assembles anything. It
  also refuses a model registered for the other job.
* **G4** - the name and the description a model reads come from the binding, never from the target
  alone. An operator override wins.
* **G5** - a wire name is unique within one agent. Two sources can offer one name, and a model
  given both cannot say which it meant.
* **G6** - a Job tool starts a Job as a named user and reports. It never waits.
* **G7** - this module builds no MCP tool. An MCP call needs an approval gate that belongs to the
  consuming app. This module returns the binding, and the consuming app pairs it with its own
  caller and passes the result back as `extra_tools`.
"""

import logging
import re

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.urls import reverse
from nautobot.apps.choices import SecretsGroupAccessTypeChoices, SecretsGroupSecretTypeChoices

from nautobot_ai_models.choices import (
    AIAgentPatternChoices,
    AIModelKindChoices,
    AIProviderTypeChoices,
    MCPTransportChoices,
    SubagentInputModeChoices,
)
from nautobot_ai_models.constants import ADDRESSED_PROVIDER_TYPES
from nautobot_ai_models.integrations import integration_timeout, integration_verify, render_field
from nautobot_ai_models.secrets import read_secret
from nautobot_ai_models.tools import get_registered_tool

logger = logging.getLogger(__name__)

WIRE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9_-]")
WIRE_NAME_MAX = 64

CALLABLE_TRANSPORTS = (MCPTransportChoices.TYPE_STREAMABLE_HTTP,)

LOAD_SKILL_TOOL = "load_skill"


class AgentBuildError(Exception):
    """The agent could not be assembled. Nothing ran, because nothing was built."""


def wire_safe(raw, fallback):
    """Cut one string down to what a tool schema will accept as a name.

    Args:
        raw: The name as an operator wrote it.
        fallback: What to use when nothing usable is left.

    Returns:
        str: A name a model can call.
    """
    return WIRE_NAME_PATTERN.sub("_", raw)[:WIRE_NAME_MAX] or fallback


def wire_unique(raw, fallback, taken):
    """A usable name that nothing in `taken` already claims (G5).

    Args:
        raw: The name as an operator wrote it.
        fallback: What to use when nothing usable is left.
        taken: The names already allocated for this agent.

    Returns:
        str: A name a model can call, and that means one tool.
    """
    base = wire_safe(raw, fallback)
    name, suffix = base, 2
    while name in taken:
        name = f"{base[: WIRE_NAME_MAX - len(str(suffix)) - 1]}_{suffix}"
        suffix += 1
    return name


def require_langchain():
    """Import LangChain, or raise a configuration error that names the extra.

    Callers call this up front, so a missing extra fails at startup instead of mid-build.

    Returns:
        tuple: ``(create_agent, tool)`` from LangChain.

    Raises:
        ImproperlyConfigured: LangChain is not installed.
    """
    try:
        from langchain.agents import create_agent  # pylint: disable=import-outside-toplevel
        from langchain.tools import tool  # pylint: disable=import-outside-toplevel
    except ImportError as error:
        raise ImproperlyConfigured(
            "LangChain could not be imported, so no agent can be built: "
            f"{type(error).__name__}: {error}. "
            "Install the app with the 'agents' extra: nautobot-ai-models[agents]."
        ) from error
    return create_agent, tool


def chat_model_for(ai_model, *, ai_agent=None):
    """Build the LangChain chat model for one registry row.

    This function reads the provider's ExternalIntegration on every build, so a rotated credential
    reaches the next build.

    The dialect decides the client class. An OpenAI-compatible endpoint and a native Ollama endpoint
    can share a host, but the compatibility layer returns no tool calls. `AIProvider.provider_type`
    answers this.

    Args:
        ai_model: The AIModel to build a client for.
        ai_agent: The agent under build, or None. Its generation overrides beat the model's, which is
            the third level of the chain provider -> model -> agent.

    Returns:
        A LangChain chat model.

    Raises:
        AgentBuildError: The dialect has no client here, or it needs a remote URL that the
            integration does not carry.
        ImproperlyConfigured: LangChain is not installed.
    """
    provider = ai_model.provider
    integration = provider.external_integration

    url = render_field(integration, "render_remote_url", provider, AgentBuildError, include_error=False)
    if not url and provider.provider_type in ADDRESSED_PROVIDER_TYPES:
        raise AgentBuildError(
            f"AI provider '{provider}' speaks {provider.get_provider_type_display()}, which is an "
            "address rather than a service, and its external integration carries no remote URL."
        )

    builder = _CHAT_MODEL_BUILDERS.get(provider.provider_type)
    if builder is None:
        raise AgentBuildError(
            f"Provider type '{provider.provider_type}' has no chat model class here. "
            "Add one to _CHAT_MODEL_BUILDERS beside the choice."
        )

    parameters = {**ai_model.resolved_parameters, **_generation_overrides(ai_model, ai_agent)}
    parameters.setdefault("timeout", integration_timeout(integration))

    return builder(
        ai_model,
        url=url,
        token=_token_for(integration),
        parameters=parameters,
        verify=integration_verify(integration),
    )


def _generation_overrides(ai_model, ai_agent):
    """Return the two tuning values the resolution chain settles, ready to send.

    `AIModel.resolved_parameters` folds in the model's temperature and stops, so `num_predict` and an
    agent's overrides reach a client only here. `max_tokens` is the neutral key, and the Ollama builder
    renames it to `num_predict`.

    Args:
        ai_model: The model under build.
        ai_agent: The agent under build, or None.

    Returns:
        dict: The parameters to apply on top of the model's own.
    """
    source = ai_agent if ai_agent is not None else ai_model
    overrides = {}

    if source.resolved_temperature is not None:
        overrides["temperature"] = float(source.resolved_temperature)
    if source.resolved_num_predict is not None:
        overrides["max_tokens"] = int(source.resolved_num_predict)
    return overrides


def _token_for(integration):
    """Return the credential on an integration's secrets group, or None.

    The search order matches `discovery.build_headers`: HTTP access type first, then generic, and
    token before secret. The two must agree, or discovery finds a model that no agent can reach.

    Args:
        integration: The ExternalIntegration to read.

    Returns:
        str | None: The credential, or None when there is not one.
    """
    for access_type in (SecretsGroupAccessTypeChoices.TYPE_HTTP, SecretsGroupAccessTypeChoices.TYPE_GENERIC):
        for secret_type in (SecretsGroupSecretTypeChoices.TYPE_TOKEN, SecretsGroupSecretTypeChoices.TYPE_SECRET):
            token = read_secret(integration, secret_type, access_type=access_type)
            if token:
                return token
    return None


def _ollama_chat_model(ai_model, *, url, token, parameters, verify=True):
    """The native Ollama client, which is the one that returns tool calls."""
    from langchain_ollama import ChatOllama  # pylint: disable=import-outside-toplevel

    del token
    settings = dict(parameters)
    if "max_tokens" in settings:
        settings["num_predict"] = settings.pop("max_tokens")
    if verify is not True:
        settings.setdefault("client_kwargs", {"verify": verify})
    return ChatOllama(model=ai_model.name, base_url=url, **settings)


def _openai_chat_model(ai_model, *, url, token, parameters, verify=True):
    """OpenAI itself, and anything speaking its API shape at another address."""
    import httpx  # pylint: disable=import-outside-toplevel
    from langchain_openai import ChatOpenAI  # pylint: disable=import-outside-toplevel

    parameters = dict(parameters)
    if verify is not True:
        parameters.setdefault("http_client", httpx.Client(verify=verify))
        parameters.setdefault("http_async_client", httpx.AsyncClient(verify=verify))

    return ChatOpenAI(
        model=ai_model.name,
        base_url=url or None,
        api_key=token or "not-required",
        **parameters,
    )


def _anthropic_chat_model(ai_model, *, url, token, parameters, verify=True):
    """Build the Anthropic chat model.

    `ChatAnthropic` exposes no HTTP client, so this function cannot apply the integration's TLS
    settings. It reports that instead. Verification stays on, and an operator who set a CA file learns
    that the file did nothing.
    """
    from langchain_anthropic import ChatAnthropic  # pylint: disable=import-outside-toplevel

    if verify is not True:
        logger.warning(
            "AI model %s is on Anthropic, whose client takes no TLS settings. The integration's "
            "SSL verification and CA file path were not applied; verification stays on.",
            ai_model,
        )
    return ChatAnthropic(model=ai_model.name, base_url=url or None, api_key=token, **parameters)


_CHAT_MODEL_BUILDERS = {
    AIProviderTypeChoices.OLLAMA: _ollama_chat_model,
    AIProviderTypeChoices.OPENAI: _openai_chat_model,
    AIProviderTypeChoices.OPENAI_COMPATIBLE: _openai_chat_model,
    AIProviderTypeChoices.ANTHROPIC: _anthropic_chat_model,
}


def wire_names(bindings):
    """Map each binding to the unique name its agent offers it under (G5).

    Two sources can hold a tool of one name, and a model given both cannot say which it meant. The
    second name gets a numbered suffix. This function builds the names per agent and never looks one
    up in the database.

    Args:
        bindings: An iterable of AIAgentTool rows.

    Returns:
        dict: Wire name to binding, in the order the bindings came.
    """
    by_name = {}
    for binding in bindings:
        by_name[wire_unique(binding.wire_name, "tool", by_name)] = binding
    return by_name


def tool_bindings(ai_agent):
    """Return every available tool binding on this agent, in weight order.

    This function leaves out a binding whose tool or server is disabled, because a model that hears
    about no tool cannot ask for it.

    Args:
        ai_agent: The agent to read.

    Returns:
        list: Available AIAgentTool rows.
    """
    bindings = ai_agent.tool_bindings.select_related(
        "agent",
        "mcp_tool__mcp_server",
        "ai_tool__job",
    ).order_by("weight", "pk")
    return [binding for binding in bindings if binding.target.is_available]


def named_bindings(ai_agent):
    """Return every available tool binding on this agent, keyed by the name a model calls it (G5).

    One place allocates the names. `mcp_bindings` and `resolve_tools` both partition this result, so
    G5 does not depend on two runs that agree.

    Args:
        ai_agent: The agent to read.

    Returns:
        dict: Wire name to AIAgentTool row.
    """
    return wire_names(tool_bindings(ai_agent))


def mcp_bindings(ai_agent):
    """Return the bindings a consuming app has to build itself (G7).

    This module cannot build an MCP tool, because an MCP call needs a gate that this app does not own.
    It settles everything the model is told: the wire name, the description, and the schema. The
    consuming app pairs each binding with its own caller and passes the results to `build_agent` as
    `extra_tools`.

    Args:
        ai_agent: The agent to read.

    Returns:
        dict: Wire name to AIAgentTool row, for the MCP bindings only. `resolve_tools` allocated the
            same names, so the two sets cannot collide.

    Raises:
        AgentBuildError: A bound server is on a transport that Nautobot cannot reach.
    """
    named = {}
    for name, binding in named_bindings(ai_agent).items():
        if binding.mcp_tool_id is None:
            continue
        server = binding.mcp_tool.mcp_server
        if server.transport not in CALLABLE_TRANSPORTS:
            raise AgentBuildError(
                f"MCP server '{server}' is registered on the '{server.transport}' transport, which "
                "cannot be reached from Nautobot. Only streamable HTTP can."
            )
        named[name] = binding
    return named


def resolve_tools(ai_agent, *, user=None):
    """Turn this agent's non-MCP bindings into LangChain tools (G4, G5, G6, G7).

    This function returns no MCP tool. Read those from `mcp_bindings()`, pair each one with your own
    gated caller, then pass the results to `build_agent` as `extra_tools`.

    Args:
        ai_agent: The agent to build tools for.
        user: Who a Job tool starts its Job as. Required if the agent binds one.

    Returns:
        list: LangChain tools, one for each available non-MCP binding.

    Raises:
        AgentBuildError: A binding names a registered tool that nothing registered, or a Job tool is
            bound and no user was given.
        ImproperlyConfigured: LangChain is not installed.
    """
    _, tool = require_langchain()

    resolved = []
    for name, binding in named_bindings(ai_agent).items():
        if binding.mcp_tool_id is not None:
            continue
        if binding.ai_tool.job_id is not None:
            resolved.append(_job_tool(binding, name, tool, user))
        else:
            resolved.append(_registered_tool(binding, name, tool))
    return resolved


def _registered_tool(binding, name, tool):
    """Build a tool from a Python callable that an app or a Git repository registered.

    An installed app registers its tools when Nautobot imports its module at start. A Git repository
    registers per process, on demand, so a miss here is the first use in this process.

    Args:
        binding: The AIAgentTool row.
        name: The unique wire name for this agent.
        tool: LangChain's `tool` decorator.

    Returns:
        A LangChain tool.

    Raises:
        AgentBuildError: Nothing registered a tool under that name in this process.
    """
    registered = get_registered_tool(binding.ai_tool.name)
    if registered is None:
        from nautobot_ai_models.datasources import load_tool  # pylint: disable=import-outside-toplevel

        registered = load_tool(binding.ai_tool)
    if registered is None:
        raise AgentBuildError(
            f"Agent '{binding.agent}' is bound to '{binding.ai_tool.name}', which nothing "
            "registered in this process. Either the app that declares it is not installed, the "
            "repository it came from no longer declares it, or the row outlived its code."
        )
    return tool(name, description=binding.wire_description)(registered.callable)


def _job_tool(binding, name, tool, user):
    """Build a tool that starts a Nautobot Job and reports (G6).

    The tool enqueues and returns. It does not wait, and it does not read the result. A wait inside a
    bounded agent loop spends the whole budget of the loop on a queue.

    WARNING: A model decides when to call this, and it can read text that somebody else wrote. The
    gate cannot be the operator's binding alone. `_job_refusal` re-checks the permission, the enabled
    flag, and the approval workflow on every call, because `JobResult.enqueue_job` checks none of them.

    Args:
        binding: The AIAgentTool row.
        name: The unique wire name for this agent.
        tool: LangChain's `tool` decorator.
        user: Who the Job runs as. Their `extras.run_job` permission decides whether it starts.

    Returns:
        A LangChain tool.

    Raises:
        AgentBuildError: No user was given, so the Job would have nobody to run as.
    """
    job = binding.ai_tool.job
    if user is None:
        raise AgentBuildError(
            f"Agent '{binding.agent}' binds the Job '{job}', and a Job has to run as somebody. "
            "Pass user= to build_agent."
        )

    def start_job(arguments: dict = None) -> str:
        refusal = _job_refusal(job, user)
        if refusal is not None:
            return refusal
        return _start_or_submit(job, user, arguments or {})

    return tool(name, description=binding.wire_description)(start_job)


def _job_refusal(job, user):
    """Return why this user may not start this Job now, or None when they may.

    `JobResult.enqueue_job` is the raw execution primitive. It checks no `run_job` permission, no
    `Job.enabled` flag, and no approval workflow. Nautobot's `JobRunView` holds all three, and this
    path does not go through that view.

    This check runs at call time, not at build time, because an operator can disable a Job or revoke a
    permission after the build.

    Args:
        job: The Job the tool would start.
        user: Who it would run as.

    Returns:
        str | None: What to tell the model, or None to go ahead.
    """
    if not job.runnable:
        return f"'{job.name}' cannot be run: it is disabled or not installed. A person has to enable it."
    if not user.has_perm("extras.run_job", job):
        return f"You do not have permission to run '{job.name}'."
    if job.has_sensitive_variables:
        return f"'{job.name}' takes sensitive variables and is not startable this way."
    return None


def _start_or_submit(job, user, arguments):
    """Start the Job, or submit it for approval, the way Nautobot's own run view decides.

    A `ScheduledJob` answers whether a Job needs approval, so this function makes one first, which is
    what `JobRunView` also does. If approval applies, the schedule stays and waits for a person. If it
    does not, this function deletes the schedule and enqueues the Job.

    Args:
        job: The Job to run.
        user: Who it runs as.
        arguments: The Job's own variables, as a mapping.

    Returns:
        str: What to tell the model.
    """
    from nautobot.extras.choices import JobExecutionType  # pylint: disable=import-outside-toplevel
    from nautobot.extras.models import JobResult, ScheduledJob  # pylint: disable=import-outside-toplevel

    with transaction.atomic():
        scheduled = ScheduledJob.create_schedule(
            job, user, interval=JobExecutionType.TYPE_IMMEDIATELY, job_kwargs=arguments
        )
        if scheduled.has_approval_workflow_definition():
            url = reverse("extras:scheduledjob_approvalworkflow", kwargs={"pk": scheduled.pk})
            return (
                f"'{job.name}' needs a person to approve it, so it was submitted rather than "
                f"started. Somebody can approve it at {url}."
            )
        scheduled.delete()

    job_result = JobResult.enqueue_job(job, user, job_kwargs=arguments)
    url = reverse("extras:jobresult", kwargs={"pk": job_result.pk})
    return (
        f"Started '{job.name}' as job result {job_result.pk}. It is queued, and this tool does "
        f"not wait for it. A person can watch it at {url}."
    )


def build_agent(ai_agent, *, extra_tools=(), checkpointer=None, user=None):
    """Assemble one LangChain agent from its rows. Nothing runs here (G1).

    For `pattern=subagents` this function wraps each specialist as a tool. The name and the description
    come from the binding, because those two strings decide whether a specialist is called at all.

    For `pattern=skills` this function adds a `load_skill` tool over the agent's skills. A rule that
    arrives that way is weaker than the same rule in a system prompt. Put anything that must hold in
    the prompt.

    Args:
        ai_agent: The AIAgent to build.
        extra_tools: Tools the consuming app supplies, appended after the agent's own. Gated MCP
            callers and retrievers arrive here.
        checkpointer: A LangGraph checkpointer, or None. This app never makes one.
        user: Who a Job tool starts its Job as, and who a specialist's Job tools run as.

    Returns:
        A configured LangChain agent.

    Raises:
        AgentBuildError: The agent, its model, or its provider is unavailable, or a binding cannot be
            resolved.
        ImproperlyConfigured: LangChain is not installed.
    """
    _check_available(ai_agent)
    create_agent, _ = require_langchain()

    tools = [*resolve_tools(ai_agent, user=user), *extra_tools]
    taken = {getattr(each, "name", "") for each in tools}

    if ai_agent.pattern == AIAgentPatternChoices.SUBAGENTS:
        tools.extend(_subagent_tools(ai_agent, user, taken))
    elif ai_agent.pattern == AIAgentPatternChoices.SKILLS:
        tools.append(_load_skill_tool(ai_agent))

    _check_names_are_unique(ai_agent, tools)

    return create_agent(
        model=chat_model_for(ai_agent.model, ai_agent=ai_agent),
        tools=tools,
        system_prompt=ai_agent.system_prompt,
        checkpointer=checkpointer,
    )


def _check_names_are_unique(ai_agent, tools):
    """Refuse a tool list that offers one name twice (G5).

    The allocator keeps this module's own names unique, so this last check catches a collision between
    sources: an `extra_tools` entry, or `load_skill` on an agent that binds a tool of that name. This
    function refuses rather than renames, because the operator's name decides whether a tool is called.

    Args:
        ai_agent: The agent under build.
        tools: The assembled tool list.

    Raises:
        AgentBuildError: Two tools share a name.
    """
    seen = set()
    for each in tools:
        name = getattr(each, "name", "")
        if name in seen:
            raise AgentBuildError(
                f"Agent '{ai_agent}' was given two tools called '{name}'. A model offered both has "
                "no way to say which it meant. Set a name override on one of them, or rename the "
                "tool the consuming app passed in."
            )
        seen.add(name)


def run_config(ai_agent):
    """Return the runtime config to invoke this agent with.

    `create_agent` takes no bound on how far the graph may go. A wrapper that added one would return
    something that is no longer a `CompiledStateGraph`, which a checkpointer, a replay, and an
    interrupt all need. So the consuming app passes the bound instead::

        agent.invoke(payload, config=run_config(ai_agent))

    Args:
        ai_agent: The agent about to run.

    Returns:
        dict: A LangGraph runtime config that carries `max_iterations` as the recursion limit.
    """
    return {"recursion_limit": ai_agent.max_iterations}


def _check_available(ai_agent):
    """Refuse a build that could not run (G3).

    Args:
        ai_agent: The agent to check.

    Raises:
        AgentBuildError: The agent, its model or its provider is disabled.
    """
    if not ai_agent.enabled:
        raise AgentBuildError(f"AI agent '{ai_agent}' is disabled.")
    if ai_agent.model.kind != AIModelKindChoices.CHAT:
        raise AgentBuildError(
            f"AI agent '{ai_agent}' is on '{ai_agent.model}', which is registered as "
            f"{ai_agent.model.get_kind_display()} rather than a chat model."
        )
    if not ai_agent.model.enabled:
        raise AgentBuildError(f"AI model '{ai_agent.model}' is disabled.")
    if not ai_agent.model.provider.enabled:
        raise AgentBuildError(f"AI provider '{ai_agent.model.provider}' is disabled.")


def _subagent_tools(ai_agent, user, taken):
    """Wrap every specialist this supervisor may delegate to as a tool (G4).

    A specialist is a whole agent, so a specialist may have specialists of its own.
    `AIAgentSubagent.clean()` refuses a cycle, which keeps this build finite.

    Args:
        ai_agent: The supervisor.
        user: Passed down, so a specialist's Job tools have somebody to run as.
        taken: The wire names this agent's tools already claim.

    Returns:
        list: One LangChain tool for each available specialist.
    """
    _, tool = require_langchain()

    wrapped = []
    bindings = ai_agent.subagent_bindings.select_related("subagent__model__provider").order_by("weight", "pk")
    for binding in bindings:
        if not binding.subagent.is_available:
            logger.warning(
                "Agent %s delegates to %s, which is not available. Leaving it out.",
                ai_agent,
                binding.subagent,
            )
            continue
        name = wire_unique(binding.wire_name, "specialist", taken)
        taken.add(name)
        wrapped.append(_subagent_tool(binding, name, tool, user))
    return wrapped


def _subagent_tool(binding, name, tool, user):
    """Wrap one specialist so its supervisor can call it.

    The build of the specialist happens at call time, not at supervisor build time, so an edit to the
    specialist's prompt reaches the next call. That inner call is the one place in this module where a
    model runs, and it runs only because the consuming app ran the supervisor (G1).

    A specialist starts with no memory. The binding decides what it receives: the task alone by
    default, or the task plus the user's question. The default is the measured-safe one, because extra
    text can activate a rule in the specialist's own prompt. The two modes are two signatures, so a
    `task_only` binding advertises no argument the supervisor could fill.

    Args:
        binding: The AIAgentSubagent row.
        name: The unique wire name allocated for this specialist.
        tool: LangChain's `tool` decorator.
        user: Passed through to the specialist's own build.

    Returns:
        A LangChain tool.
    """

    def call_specialist(task, question=None):
        specialist = build_agent(binding.subagent, user=user)
        content = task if question is None else f"{task}\n\nThe user asked: {question}"
        answer = specialist.invoke(
            {"messages": [{"role": "user", "content": content}]},
            config=run_config(binding.subagent),
        )
        return answer["messages"][-1].content

    if binding.input_mode == SubagentInputModeChoices.TASK_AND_CONTEXT:

        def delegate(task: str, question: str) -> str:
            return call_specialist(task, question)

    else:

        def delegate(task: str) -> str:
            return call_specialist(task)

    return tool(name, description=binding.wire_description)(delegate)


def _load_skill_tool(ai_agent):
    """Build the tool a skills agent loads its rules with.

    The description lists every skill on one line. A measurement showed that a bulleted, multi-line
    description stopped every call to the tool.

    Args:
        ai_agent: The agent whose skills these are.

    Returns:
        A LangChain tool.
    """
    _, tool = require_langchain()

    bindings = [
        binding
        for binding in ai_agent.skill_bindings.select_related("skill").order_by("weight", "pk")
        if binding.skill.enabled
    ]
    bodies = {binding.skill.name: binding.skill.body for binding in bindings}
    listed = ", ".join(f"{binding.skill.name} ({binding.skill.description})" for binding in bindings)
    description = f"Load the rules for one area of work. Skills: {listed}."

    def load_skill(skill_name: str) -> str:
        return bodies.get(
            skill_name,
            f"There is no skill called '{skill_name}'. Skills: {', '.join(bodies)}.",
        )

    return tool(LOAD_SKILL_TOOL, description=description)(load_skill)
