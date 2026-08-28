"""Exceptions raised by the service layer."""


class MCPError(Exception):
    """Base class for every error the MCP service raises.

    No exception from the client library escapes ``services.mcp``, so callers catch one family.
    """


class MCPConfigurationError(MCPError):
    """The server is disabled, or unreachable because of how it is configured.

    Nothing left the process.
    """


class MCPCallError(MCPError):
    """The server was reached and would not answer usably, or answered something unstorable."""
