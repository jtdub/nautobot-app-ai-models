# MCP Server

An MCP server known to Nautobot. When you register one, you record that the server exists, how to
reach it, and what it advertises. This does not make anything callable. This app is a registry. The
apps that read it decide what to do with what they find.

An MCP server keeps no URL and no credential of its own. Both live on the
[External Integration](https://docs.nautobot.com/projects/core/en/stable/user-guide/platform-functionality/externalintegration/)
that the server points at. The TLS settings and the timeout come from there too.

![An MCP Server detail view](../images/mcp-server-detail-light.png#only-light)
![An MCP Server detail view](../images/mcp-server-detail-dark.png#only-dark)

## Fields that an operator owns

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | The name of this server in Nautobot. Unique. Not the name that the server reports for itself. |
| `description` | string | What the server is for, in the words of an operator. |
| `external_integration` | foreign key | The endpoint URL, its headers and TLS settings, and its secrets group. Required. |
| `transport` | choice | `streamable-http`, `sse` (deprecated), or `stdio`. Discovery reads a `streamable-http` server only. It skips the other two and says so, because a stdio server is a subprocess of its client and this app does not speak SSE. Register their tools by hand. |
| `enabled` | boolean | Whether the server is in service. Discovery skips a disabled server. An app that reads this registry must also skip one. |
| `tenant` | foreign key | The tenant that owns this server, if the deployment is divided that way. Optional. |
| `tags` | tags | Standard Nautobot tags. |

## Fields that the discovery job owns

The **MCP Server Discovery** job writes each field below. Each one is read-only over the REST API.

CAUTION: The server reports all of this data about itself and nothing verifies it. Do not make a
decision from it.

| Field | Type | Description |
| --- | --- | --- |
| `protocol_version` | string | The MCP protocol revision that the last discovery negotiated. |
| `server_name` | string | The name that the server reports for itself. |
| `server_version` | string | The version that the server reports for itself. |
| `instructions` | text | The guidance of the server on how to use it. |
| `capabilities` | JSON | The capabilities object that the server advertised, kept whole. |
| `last_discovered_at` | datetime | When this app last read the tool list correctly. A failed run does not change it, so a stale server is easy to see. |
