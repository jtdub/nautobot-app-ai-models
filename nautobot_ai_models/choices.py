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

    Separate from ``AIProvider.openai_compatible``, which says only whether models can be
    discovered at the endpoint. Ollama is both OpenAI-compatible and its own dialect, because its
    compatibility layer does not return tool calls.
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


ADDRESSED_PROVIDER_TYPES = (
    AIProviderTypeChoices.OPENAI_COMPATIBLE,
    AIProviderTypeChoices.OLLAMA,
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
