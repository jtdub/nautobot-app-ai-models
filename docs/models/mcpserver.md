# MCP Server

An MCP server known to Nautobot. Registering one records that the server exists, how to reach it,
and what it advertises. It does not make anything callable: this app is a registry, and the apps
that read it decide what to do with what they find here.

An MCP server carries no URL and no credential of its own. Both live on the
[External Integration](https://docs.nautobot.com/projects/core/en/stable/user-guide/platform-functionality/externalintegration/)
it points at, which is also where the TLS settings and the timeout come from.

![An MCP Server detail view](../images/mcp-server-detail-light.png#only-light)
![An MCP Server detail view](../images/mcp-server-detail-dark.png#only-dark)

## Fields an operator owns

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | What this server is called in Nautobot. Unique. Not the name the server reports for itself. |
| `description` | string | What the server is for, in an operator's words. |
| `external_integration` | foreign key | The endpoint URL, its headers and TLS settings, and its secrets group. Required. |
| `transport` | choice | `streamable-http`, `sse` (deprecated), or `stdio`. Discovery reads a `streamable-http` server only. It skips the other two and says so, because a stdio server is a subprocess of its client and this app speaks no SSE. Register their tools by hand. |
| `enabled` | boolean | Whether the server is in service. A disabled server is skipped by discovery and is meant to be skipped by any app reading this registry. |
| `tenant` | foreign key | The tenant this server belongs to, if the deployment is divided that way. Optional. |
| `tags` | tags | Standard Nautobot tags. |

## Fields the discovery job owns

Every field below is written by **MCP Server Discovery** and is read-only over the REST API.
All of it is self-reported by the server and none of it is verified.

| Field | Type | Description |
| --- | --- | --- |
| `protocol_version` | string | The MCP protocol revision the last discovery negotiated. |
| `server_name` | string | The name the server reports for itself. |
| `server_version` | string | The version the server reports for itself. |
| `instructions` | text | The server's own guidance on how to use it. |
| `capabilities` | JSON | The capabilities object the server advertised, stored whole. |
| `last_discovered_at` | datetime | When the tool list was last read successfully. Left alone when a run fails, so a stale server is visible. |
