"""Choice sets for nautobot_ai_models."""

from nautobot.apps.choices import ChoiceSet


class MCPTransportChoices(ChoiceSet):
    """How a client reaches an MCP server."""

    TYPE_STREAMABLE_HTTP = "streamable-http"
    TYPE_SSE = "sse"
    TYPE_STDIO = "stdio"

    CHOICES = (
        (TYPE_STREAMABLE_HTTP, "Streamable HTTP"),
        (TYPE_SSE, "HTTP+SSE (deprecated)"),
        (TYPE_STDIO, "stdio (not discoverable from Nautobot)"),
    )


class AIProviderTypeChoices(ChoiceSet):
    """Which API dialect a provider speaks.

    This is separate from ``AIProvider.openai_compatible``, which says only whether the endpoint
    supports model discovery. Ollama is both OpenAI-compatible and its own dialect, because its
    compatibility layer returns no tool calls.
    """

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai_compatible"
    OLLAMA = "ollama"

    CHOICES = (
        (OPENAI, "OpenAI"),
        (ANTHROPIC, "Anthropic"),
        (OPENAI_COMPATIBLE, "OpenAI-compatible"),
        (OLLAMA, "Ollama (native API)"),
    )


class AIModelKindChoices(ChoiceSet):
    """What a model is for.

    A chat model and an embedding model are not interchangeable and are not the same endpoint.
    Discovery cannot tell them apart, so a person sets this.
    """

    CHAT = "chat"
    EMBEDDING = "embedding"

    CHOICES = (
        (CHAT, "Chat"),
        (EMBEDDING, "Embedding"),
    )


class AIAgentPatternChoices(ChoiceSet):
    """Which multi-agent shape an agent is built into.

    The names come from the LangChain multi-agent guide. Three of its five are here. Handoffs and
    routers are graph code more than configuration, and nothing has asked for them yet.
    """

    SINGLE = "single"
    SUBAGENTS = "subagents"
    SKILLS = "skills"

    CHOICES = (
        (SINGLE, "Single agent"),
        (SUBAGENTS, "Subagents"),
        (SKILLS, "Skills"),
    )


class AIToolKindChoices(ChoiceSet):
    """Where a tool that is not an MCP tool came from.

    MCP tools are not here. They have their own model, because a server discovered them and the
    server owns their definition.
    """

    REGISTERED = "registered"
    GIT = "git"
    JOB = "job"

    CHOICES = (
        (REGISTERED, "Registered in code"),
        (GIT, "Git repository"),
        (JOB, "Nautobot Job"),
    )


class SubagentInputModeChoices(ChoiceSet):
    """What a supervisor sends a specialist.

    ``TASK_ONLY`` is the default, because a wider input is measurably dangerous. Every added string
    can activate a rule in the subagent's own prompt, and the subagent then answers the question it
    saw instead of the task it was given.
    """

    TASK_ONLY = "task_only"
    TASK_AND_CONTEXT = "task_and_context"

    CHOICES = (
        (TASK_ONLY, "The task only"),
        (TASK_AND_CONTEXT, "The task and the user's question"),
    )


class AIAgentThreadStatusChoices(ChoiceSet):
    """Where one LangGraph thread got to.

    ``WAITING`` is the interrupt: the graph paused inside a node, the checkpointer holds everything,
    and a person has to answer before it goes on.
    """

    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"

    CHOICES = (
        (RUNNING, "Running"),
        (WAITING, "Waiting for a person"),
        (COMPLETED, "Completed"),
        (FAILED, "Failed"),
    )
