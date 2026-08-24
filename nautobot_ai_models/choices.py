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
