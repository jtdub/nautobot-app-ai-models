# MCP Tool

One tool an MCP server advertises. Discovery creates these; an operator can also add one by hand,
which is the only way to register the tools of a `stdio` server.

![An MCP Tool detail view](../images/mcp-tool-detail-light.png#only-light)
![An MCP Tool detail view](../images/mcp-tool-detail-dark.png#only-dark)

## Two flags, not one

The MCP specification requires that a client treat a server's annotations as untrusted. So this
model keeps what the server claimed apart from what a person decided:

- **`writable`** is set by a person and is what a consuming app should read. It defaults to `True`:
  guessing that a tool writes costs a review, and guessing the other way tells every consuming app
  a tool is safe when it is not. Discovery never writes this field.
- **`advertised_read_only`** mirrors the server's own `readOnlyHint` annotation. It is unset when
  the server claimed nothing. It is shown so a reviewer can see the claim, and it decides nothing.

## Fields an operator owns

| Field | Type | Description |
| --- | --- | --- |
| `enabled` | boolean | Whether this tool is offered to apps reading the registry. Discovery only ever clears it, and only for a tool the server stopped advertising. |
| `writable` | boolean | Whether calling the tool changes something. Defaults to `True`. |

## Fields the discovery job owns

| Field | Type | Description |
| --- | --- | --- |
| `mcp_server` | foreign key | The server offering the tool. A tool cannot outlive it. |
| `name` | string | The tool name sent on the wire. Unique within its server, and case sensitive. |
| `title` | string | The human-readable name the server offered for display, if any. |
| `description` | text | What the tool does, as the server advertised it. |
| `input_schema` | JSON | The JSON Schema the server advertised for the tool's arguments. |
| `output_schema` | JSON | The JSON Schema the server advertised for the tool's structured result, if any. |
| `advertised_read_only` | boolean, nullable | The server's `readOnlyHint` claim. Unset when it claimed nothing. |
| `definition_fingerprint` | string | A digest of the title, description and both schemas. Compare it to detect that a tool's contract changed after somebody reviewed it. |
| `last_seen_at` | datetime | When discovery last saw the tool advertised. An older time means the server stopped offering it. |

`definition_fingerprint` and `last_seen_at` are read-only over the REST API. `enabled` and
`writable` are not: setting those over the API is a supported thing to do.

## `is_available`

A read-only property, also exposed in the REST API. `True` when the tool is enabled **and** its
server is enabled. A tool on a disabled server is not on offer however the tool itself is flagged.
