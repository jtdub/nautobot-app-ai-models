"""Choice sets for nautobot_ai_models."""

from nautobot.apps.choices import ChoiceSet


class MCPTransportChoices(ChoiceSet):
    """How a client reaches an MCP server.

    Recorded rather than inferred: a consuming app needs to know which transport to open before it
    reads anything else off the server, and the discovery job needs it to decide whether the server
    is reachable from a Nautobot worker at all.
    """

    TYPE_STREAMABLE_HTTP = "streamable-http"
    TYPE_SSE = "sse"
    TYPE_STDIO = "stdio"

    CHOICES = (
        (TYPE_STREAMABLE_HTTP, "Streamable HTTP"),
        # Deprecated by the MCP specification since revision 2025-03-26, and eligible for removal.
        # Recorded so an existing server can be registered, not because it should be chosen.
        (TYPE_SSE, "HTTP+SSE (deprecated)"),
        # A stdio server is a subprocess of its client. A Nautobot worker cannot reach one over the
        # network, so discovery skips it and the tool list has to be entered by hand.
        (TYPE_STDIO, "stdio (not discoverable from Nautobot)"),
    )


class AIProviderTypeChoices(ChoiceSet):
    """Which API dialect a provider speaks.

    Recorded because `openai_compatible` answers a different question. That boolean says whether the
    endpoint serves `GET /v1/models`, which is what the discovery job needs. This says how a client
    addresses the endpoint, which is what a consuming app needs before it sends anything.

    Ollama is the case that makes the two questions distinct. It serves an OpenAI-compatibility
    layer, so `openai_compatible` is a true statement about it, but that layer does not return tool
    calls in the `tool_calls` field: a model asked for a tool writes the JSON call into the message
    content, where nothing can act on it. Its native API does return them. A consuming app reading
    only the boolean addresses Ollama over the compatibility layer and silently loses tool calling.
    """

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai_compatible"
    OLLAMA = "ollama"

    CHOICES = (
        (OPENAI, "OpenAI"),
        (ANTHROPIC, "Anthropic"),
        # An address rather than a service. A self-hosted vLLM or llama.cpp endpoint serves the
        # OpenAI shape, but a client that falls back to a default endpoint for it reaches
        # somebody else's API, so this type requires a remote URL.
        (OPENAI_COMPATIBLE, "OpenAI-compatible"),
        (OLLAMA, "Ollama (native API)"),
    )


class AIModelKindChoices(ChoiceSet):
    """What a model is for.

    A chat model and an embedding model are not interchangeable, and they are not even the same
    endpoint. Recorded so that configuring retrieval with a chat model is refused at the screen
    where the mistake is made, rather than becoming a provider-side error at a bad hour.

    Discovery cannot infer this. `GET /v1/models` returns both kinds mixed together and carries no
    field saying which is which, so the job leaves every row at the default and a person corrects
    it - the same division of labour `MCPTool.enabled` and `MCPTool.writable` already use.
    """

    CHAT = "chat"
    EMBEDDING = "embedding"

    CHOICES = (
        (CHAT, "Chat"),
        (EMBEDDING, "Embedding"),
    )
