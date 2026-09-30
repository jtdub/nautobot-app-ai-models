"""Create fixtures for tests."""

from datetime import timedelta

from django.utils import timezone
from nautobot.extras.models import ExternalIntegration

from nautobot_ai_models.choices import (
    AIAgentPatternChoices,
    AIAgentThreadStatusChoices,
    AIModelKindChoices,
    AIProviderTypeChoices,
    AIToolKindChoices,
    MCPTransportChoices,
    SubagentInputModeChoices,
)
from nautobot_ai_models.models import (
    AIAgent,
    AIAgentSkill,
    AIAgentSubagent,
    AIAgentThread,
    AIAgentTool,
    AIModel,
    AIProvider,
    AISkill,
    AITool,
    AIToolApproval,
    AIUsageRecord,
    MCPPrompt,
    MCPResource,
    MCPServer,
    MCPTool,
)
from nautobot_ai_models.services import usage

INTEGRATIONS = (
    ("Test Integration One", "https://llm.example.com"),
    ("Test Integration Two", "https://llm2.example.com"),
    ("Test Integration Three", "https://llm3.example.com"),
)

PROVIDERS = (
    ("Test One", "First provider", AIProviderTypeChoices.OPENAI),
    ("Test Two", "Second provider", AIProviderTypeChoices.ANTHROPIC),
    ("Test Three", "Third provider", AIProviderTypeChoices.OLLAMA),
)

AI_MODELS = (
    ("Test One", "Test One", "First model", AIModelKindChoices.CHAT),
    ("Test Two", "Test Two", "Second model", AIModelKindChoices.CHAT),
    ("Test Three", "Test Three", "Third model", AIModelKindChoices.EMBEDDING),
)


def create_external_integration(name=INTEGRATIONS[0][0], remote_url=INTEGRATIONS[0][1], **kwargs):
    """Return one ExternalIntegration, creating it if it does not exist.

    Args:
        name: The integration's name.
        remote_url: Its remote URL.
        **kwargs: Further defaults for creation.

    Returns:
        ExternalIntegration: The existing or new record.
    """
    integration, _ = ExternalIntegration.objects.get_or_create(
        name=name,
        defaults={"remote_url": remote_url, "verify_ssl": True, "timeout": 30, **kwargs},
    )
    return integration


def create_ai_provider():
    """Fixture to create the necessary number of AIProvider objects for tests."""
    for (name, description, provider_type), (integration_name, remote_url) in zip(PROVIDERS, INTEGRATIONS):
        AIProvider.objects.create(
            name=name,
            description=description,
            provider_type=provider_type,
            external_integration=create_external_integration(integration_name, remote_url),
        )


def create_aimodel():
    """Fixture to create the necessary number of AIModel objects for tests."""
    create_ai_provider()
    for provider_name, name, description, kind in AI_MODELS:
        AIModel.objects.create(
            provider=AIProvider.objects.get(name=provider_name),
            name=name,
            description=description,
            kind=kind,
        )


SERVER_SPECS = (
    ("Test One", MCPTransportChoices.TYPE_STREAMABLE_HTTP),
    ("Test Two", MCPTransportChoices.TYPE_SSE),
    ("Test Three", MCPTransportChoices.TYPE_STDIO),
)


def create_mcpserver():
    """Create one MCPServer per transport, each with its own integration.

    Returns:
        list[MCPServer]: The three servers.
    """
    servers = []
    for index, (label, transport) in enumerate(SERVER_SPECS, start=1):
        integration = create_external_integration(
            name=f"Integration {label}",
            remote_url=f"https://mcp{index}.example.com/mcp",
        )
        server, _ = MCPServer.objects.get_or_create(
            name=label,
            defaults={
                "description": f"{label} description",
                "external_integration": integration,
                "transport": transport,
            },
        )
        servers.append(server)
    return servers


def create_mcptool():
    """Create three MCPTool records, one per server and one per annotation state.

    Returns:
        list[MCPTool]: A read-only tool, a writable one, and one the server did not annotate.
    """
    servers = create_mcpserver()
    return [
        MCPTool.objects.create(
            mcp_server=servers[0],
            name="get_device",
            title="Get Device",
            description="Read one device.",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            writable=False,
            advertised_read_only=True,
        ),
        MCPTool.objects.create(
            mcp_server=servers[1],
            name="set_interface",
            title="Set Interface",
            description="Change one interface.",
            input_schema={"type": "object", "properties": {"id": {"type": "string"}}},
            writable=True,
            advertised_read_only=False,
        ),
        MCPTool.objects.create(
            mcp_server=servers[2],
            name="run_report",
            title="Run Report",
            description="A tool the server annotated with nothing at all.",
            input_schema={"type": "object"},
            enabled=False,
            advertised_read_only=None,
        ),
    ]


REGISTERED_TOOLS = (
    ("lookup_device", "Look up one device by hostname. Returns vendor, site, and platform.", False),
    ("reboot_device", "Reboot one device by hostname. Returns nothing.", True),
    ("unreviewed_tool", "A tool discovery found and nobody has looked at yet.", True),
)


def register_test_tools():
    """Register the suite's tools, so `AITool` rows of kind `registered` validate.

    This is idempotent. The same callable may register twice under one name, and the suite calls
    this from more than one `setUpTestData`.
    """
    from nautobot_ai_models import tools  # pylint: disable=import-outside-toplevel

    for name, description, writable in REGISTERED_TOOLS:
        if tools.get_registered_tool(name) is not None:
            continue

        def placeholder(hostname: str) -> str:
            return hostname

        placeholder.__name__ = name
        tools.register_ai_tool(placeholder, name=name, description=description, writable=writable)


def create_mcpresource(**kwargs):
    """Return the suite's MCP resources, creating them if they do not exist.

    Returns:
        list: Four MCPResource records. One is a template, and one URI is offered by two servers.
    """
    if MCPResource.objects.exists():
        return list(MCPResource.objects.all())

    servers = create_mcpserver()
    return [
        MCPResource.objects.create(
            mcp_server=servers[0],
            uri="nautobot://devices/inventory",
            name="inventory",
            title="Device inventory",
            description="Every device this Nautobot knows about.",
            mime_type="application/json",
            **kwargs,
        ),
        MCPResource.objects.create(
            mcp_server=servers[0],
            uri="nautobot://sites/{site_code}",
            name="site",
            description="One site, by its code.",
            mime_type="application/json",
            is_template=True,
            **kwargs,
        ),
        MCPResource.objects.create(
            mcp_server=servers[1],
            uri="nautobot://devices/inventory",
            name="inventory",
            description="The same URI under another server.",
            **kwargs,
        ),
        MCPResource.objects.create(
            mcp_server=servers[1],
            uri="nautobot://circuits/summary",
            name="circuits",
            description="Every circuit and its provider.",
            mime_type="text/csv",
            **kwargs,
        ),
    ]


def create_mcpprompt(**kwargs):
    """Return the suite's MCP prompts, creating them if they do not exist.

    Returns:
        list: Four MCPPrompt records. One name is offered by two servers.
    """
    if MCPPrompt.objects.exists():
        return list(MCPPrompt.objects.all())

    servers = create_mcpserver()
    return [
        MCPPrompt.objects.create(
            mcp_server=servers[0],
            name="triage_device",
            title="Triage a device",
            description="Walk through a device that is down.",
            arguments=[{"name": "hostname", "description": "The device name.", "required": True}],
            **kwargs,
        ),
        MCPPrompt.objects.create(
            mcp_server=servers[0],
            name="summarise_site",
            description="Summarise one site.",
            arguments=[{"name": "site_code", "required": False}],
            **kwargs,
        ),
        MCPPrompt.objects.create(
            mcp_server=servers[1],
            name="triage_device",
            description="The same name under another server.",
            **kwargs,
        ),
        MCPPrompt.objects.create(
            mcp_server=servers[1],
            name="explain_circuit",
            description="Explain one circuit in plain words.",
            **kwargs,
        ),
    ]


def create_aitool(**kwargs):
    """Return the suite's AI Tools, creating them if they do not exist.

    Returns:
        list: Three AITool records: a read-only registered tool, a writable one, and one that is
            disabled the way `new_tools_enabled: False` leaves a newly discovered tool.
    """
    register_test_tools()
    if AITool.objects.exists():
        return list(AITool.objects.all())

    from nautobot_ai_models import tools  # pylint: disable=import-outside-toplevel

    records = []
    for name, description, writable in REGISTERED_TOOLS:
        registered = tools.get_registered_tool(name)
        records.append(
            AITool.objects.create(
                name=name,
                description=description,
                argument_schema=registered.argument_schema,
                kind=AIToolKindChoices.REGISTERED,
                module=registered.module,
                writable=writable,
                advertised_read_only=not writable,
                definition_fingerprint=registered.definition_fingerprint,
                **kwargs,
            )
        )
    records[-1].enabled = False
    records[-1].module = "nautobot_ai_models.tests.other_module"
    records[-1].save()
    return records


def create_aiagent(**kwargs):
    """Return the suite's AI Agents, creating them if they do not exist.

    Returns:
        list: Three AIAgent records: a supervisor, a specialist, and a skills agent.
    """
    if AIAgent.objects.exists():
        return list(AIAgent.objects.all())

    if not AIModel.objects.exists():
        create_aimodel()
    chat = list(AIModel.objects.filter(kind=AIModelKindChoices.CHAT))

    return [
        AIAgent.objects.create(
            name="Test Supervisor",
            description="Answers network operations questions by asking specialists.",
            system_prompt="You answer network operations questions. Never state a fact you did not get from a tool.",
            model=chat[0],
            pattern=AIAgentPatternChoices.SINGLE,
            **kwargs,
        ),
        AIAgent.objects.create(
            name="Test Inventory Specialist",
            description="Looks up a network device by hostname. Give it a hostname.",
            system_prompt="You look up device records. Never state a fact you did not get from the tool.",
            model=chat[0],
            **kwargs,
        ),
        AIAgent.objects.create(
            name="Test Skills Agent",
            description="One agent that loads its rules as it needs them.",
            system_prompt="You start with no domain rules loaded. Call load_skill before any other tool.",
            model=chat[1],
            **kwargs,
        ),
    ]


def create_aiagenttool(**kwargs):
    """Return the suite's tool bindings, and create them if they do not exist.

    One binding per source, so a test that reads `wire_name` or `writable` off a binding gets both
    kinds without a build of its own.

    Returns:
        list: Two AIAgentTool records, one MCP and one registered.
    """
    if AIAgentTool.objects.exists():
        return list(AIAgentTool.objects.all())

    agents = create_aiagent()
    mcp_tools = create_mcptool()
    ai_tools = create_aitool()
    return [
        AIAgentTool.objects.create(agent=agents[0], mcp_tool=mcp_tools[0], **kwargs),
        AIAgentTool.objects.create(
            agent=agents[0],
            ai_tool=ai_tools[0],
            name_override="find_device",
            description_override="Look up a device. Send it one hostname.",
            **kwargs,
        ),
        AIAgentTool.objects.create(agent=agents[1], mcp_tool=mcp_tools[1], weight=200, **kwargs),
        AIAgentTool.objects.create(agent=agents[1], ai_tool=ai_tools[1], weight=300, **kwargs),
    ]


def create_aitoolapproval(**kwargs):
    """Return the suite's approvals, creating them if they do not exist.

    One approval stands, one is withdrawn, and one has expired. Every question the model answers
    then has a row behind it.

    Returns:
        list: Three AIToolApproval records.
    """
    if AIToolApproval.objects.exists():
        return list(AIToolApproval.objects.all())

    bindings = create_aiagenttool()
    now = timezone.now()
    return [
        AIToolApproval.objects.create(
            binding=bindings[0],
            fingerprint=bindings[0].fingerprint,
            approved_by_name="reviewer",
            note="Read-only lookup. Nothing to review.",
            **kwargs,
        ),
        AIToolApproval.objects.create(
            binding=bindings[1],
            fingerprint=bindings[1].fingerprint,
            approved_by_name="reviewer",
            approved_at=now - timedelta(days=2),
            revoked_at=now - timedelta(days=1),
            revoked_by_name="reviewer",
            note="Withdrawn while the description was rewritten.",
            **kwargs,
        ),
        AIToolApproval.objects.create(
            binding=bindings[2],
            fingerprint=bindings[2].fingerprint,
            approved_by_name="reviewer",
            expires_at=now - timedelta(days=1),
            approved_at=now - timedelta(days=30),
            note="A quarterly review that nobody renewed.",
            **kwargs,
        ),
    ]


def create_aiagentsubagent(**kwargs):
    """Return the suite's subagent bindings, creating them if they do not exist.

    Returns:
        list: One AIAgentSubagent record.
    """
    if AIAgentSubagent.objects.exists():
        return list(AIAgentSubagent.objects.all())

    agents = create_aiagent()
    return [
        AIAgentSubagent.objects.create(
            parent=agents[0],
            subagent=agents[1],
            tool_name="inventory_expert",
            tool_description="Look up a network device by hostname. Returns the vendor and the site code.",
            input_mode=SubagentInputModeChoices.TASK_ONLY,
            **kwargs,
        ),
        AIAgentSubagent.objects.create(
            parent=agents[0],
            subagent=agents[2],
            tool_name="policy_expert",
            tool_description="Answer a policy question. Give it the area of work.",
            input_mode=SubagentInputModeChoices.TASK_AND_CONTEXT,
            weight=200,
            **kwargs,
        ),
        AIAgentSubagent.objects.create(parent=agents[2], subagent=agents[1], weight=300, **kwargs),
    ]


def create_aiskill(**kwargs):
    """Return the suite's AI Skills, creating them if they do not exist.

    Returns:
        list: Two AISkill records.
    """
    if AISkill.objects.exists():
        return list(AISkill.objects.all())

    return [
        AISkill.objects.create(
            name="device_records",
            description="looking up devices",
            body="Call lookup_device for every hostname. Report the vendor and the site code.",
            **kwargs,
        ),
        AISkill.objects.create(
            name="maintenance_windows",
            description="approved change windows",
            body="If the request gives you a hostname instead of a site code, ask for the site code.",
            **kwargs,
        ),
        AISkill.objects.create(
            name="escalation",
            description="who to tell, and when",
            body="Escalate to the on-call engineer when a change window has already closed.",
            enabled=False,
            **kwargs,
        ),
    ]


def create_aiagentskill(**kwargs):
    """Return the suite's skill bindings, creating them if they do not exist.

    Returns:
        list: Two AIAgentSkill records.
    """
    if AIAgentSkill.objects.exists():
        return list(AIAgentSkill.objects.all())

    agents = create_aiagent()
    skills = create_aiskill()
    return [
        AIAgentSkill.objects.create(agent=agents[2], skill=skills[0], **kwargs),
        AIAgentSkill.objects.create(agent=agents[2], skill=skills[1], weight=200, **kwargs),
        AIAgentSkill.objects.create(agent=agents[0], skill=skills[0], weight=300, **kwargs),
    ]


def create_aiagentthread(**kwargs):
    """Return the suite's threads, creating them if they do not exist.

    Returns:
        list: Three AIAgentThread records, one per interesting status.
    """
    if AIAgentThread.objects.exists():
        return list(AIAgentThread.objects.all())

    agents = create_aiagent()
    return [
        AIAgentThread.objects.create(agent=agents[0], **kwargs),
        AIAgentThread.objects.create(
            agent=agents[0],
            status=AIAgentThreadStatusChoices.WAITING,
            interrupt_payload={"question": "Approve the reboot?"},
            **kwargs,
        ),
        AIAgentThread.objects.create(
            agent=agents[1],
            status=AIAgentThreadStatusChoices.COMPLETED,
            finished_at=timezone.now(),
            **kwargs,
        ),
    ]


def create_aiusagerecord(**kwargs):
    """Return the suite's usage records, creating them if they do not exist.

    One priced model and one unpriced one, so the "nobody recorded a price" case has a row.

    Returns:
        list: Three AIUsageRecord records.
    """
    if AIUsageRecord.objects.exists():
        return list(AIUsageRecord.objects.all())

    threads = create_aiagentthread()
    priced = AIModel.objects.filter(input_cost_per_million__isnull=False).first()
    if priced is None:
        priced = AIModel.objects.filter(kind=AIModelKindChoices.CHAT).first()
        priced.input_cost_per_million = "2.5000"
        priced.output_cost_per_million = "10.0000"
        priced.validated_save()
    unpriced = AIModel.objects.filter(kind=AIModelKindChoices.CHAT).exclude(pk=priced.pk).first()

    return [
        usage.record(
            threads[0],
            threads[0].agent,
            priced,
            input_tokens=1200,
            output_tokens=340,
            usage_payload={"prompt_tokens": 1200, "completion_tokens": 340},
            **kwargs,
        ),
        usage.record(
            threads[0],
            threads[0].agent,
            priced,
            input_tokens=800,
            output_tokens=210,
            cached_input_tokens=600,
            **kwargs,
        ),
        usage.record(
            threads[2],
            threads[2].agent,
            unpriced,
            input_tokens=95,
            output_tokens=40,
            **kwargs,
        ),
    ]


def age_agent_threads(days=365):
    """Move every thread's timestamps back, so the retention window has passed.

    `expired_threads` measures from `finished_at` and falls back to `started_at`, so both columns
    have to move. A thread that never finished keeps its empty `finished_at`.

    Args:
        days: How far back to move the timestamps.

    Returns:
        datetime: The timestamp written.
    """
    old = timezone.now() - timezone.timedelta(days=days)
    AIAgentThread.objects.update(started_at=old)
    AIAgentThread.objects.filter(finished_at__isnull=False).update(finished_at=old)
    return old
