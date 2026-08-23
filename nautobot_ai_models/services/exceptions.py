"""Exceptions raised by the service layer."""


class MCPError(Exception):
    """Base class for every error the MCP service raises.

    No exception from the MCP client library escapes `services.mcp`. Callers catch this one family,
    so a change of client library cannot become a change to every call site.
    """


class MCPConfigurationError(MCPError):
    """The server is disabled, or unreachable because of how it is configured.

    Nothing left the process. A missing remote URL, a template that will not render, and a stdio
    transport all land here.
    """


class MCPCallError(MCPError):
    """The server was reached and would not answer usably, or answered something unstorable."""
