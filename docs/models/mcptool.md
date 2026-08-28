# MCP Tool

One tool that an MCP server advertises. Discovery creates these records. An operator can also add
one by hand. That is the only way to register the tools of a `stdio` server.

![An MCP Tool detail view](../images/mcp-tool-detail-light.png#only-light)
![An MCP Tool detail view](../images/mcp-tool-detail-dark.png#only-dark)

## Two flags, not one

The MCP specification tells a client to treat the annotations of a server as untrusted. Thus this
model keeps the claim of the server apart from the decision of a person.

- **`writable`** is set by a person. This is the field that a consuming app reads. It defaults to
  `True`. A wrong guess in this direction costs a review. A wrong guess the other way tells each
  consuming app that a tool is safe when it is not. Discovery never writes this field.
- **`advertised_read_only`** is a copy of the `readOnlyHint` annotation of the server. It is empty
  when the server claimed nothing. The app shows it so that a reviewer can see the claim. It
  decides nothing.

## Fields that an operator owns

| Field | Type | Description |
| --- | --- | --- |
| `enabled` | boolean | Whether the app offers this tool to the apps that read the registry. Discovery only clears it, and only for a tool that the server stopped advertising. |
| `writable` | boolean | Whether a call to this tool changes something. Defaults to `True`. |

## Fields that the discovery job owns

| Field | Type | Description |
| --- | --- | --- |
| `mcp_server` | foreign key | The server that offers the tool. A tool cannot outlive it. |
| `name` | string | The tool name sent on the wire. Unique in its server, and case sensitive. |
| `title` | string | The name that the server offered for display, if it offered one. |
| `description` | text | What the tool does, as the server advertised it. |
| `input_schema` | JSON | The JSON Schema that the server advertised for the arguments of the tool. |
| `output_schema` | JSON | The JSON Schema that the server advertised for the structured result, if it advertised one. |
| `advertised_read_only` | boolean, nullable | The `readOnlyHint` claim of the server. Empty when it claimed nothing. |
| `definition_fingerprint` | string | A digest of the title, the description, and both schemas. Compare it to find that the contract of a tool changed after a review. |
| `last_seen_at` | datetime | When discovery last saw the tool advertised. An older time means that the server stopped offering it. |

`definition_fingerprint` and `last_seen_at` are read-only over the REST API. `enabled` and
`writable` are not. You can set those two over the API.

## Discovery policy

Two optional settings change what a discovery run puts on offer. Both defaults keep the behavior
of an existing deployment. See [Install](../admin/install.md#optional-settings) for where to put
them.

### `new_tools_enabled`

The default is `True`. A newly discovered tool arrives switched on.

Set it to `False`. Discovery then writes `enabled = False` on a new tool, and a person turns the
tool on.

`writable` and `enabled` answer different questions. That is why the careful default on one does
not cover the other. `writable` says that a tool needs a review before each call. `enabled` says
that the tool is on offer at all. A tool that nobody has read is not only a tool that changes
something. It is a tool whose description nobody has examined.

### `disable_on_definition_change`

The default is `False`. The job log reports a tool whose `definition_fingerprint` moved, and the
tool stays on offer.

Set it to `True`. Discovery then clears `enabled` on such a tool, if the tool was on.

WARNING: A compromised or careless server can rewrite the description of a tool and leave the
arguments alone. In the prompt of an agent, that description is the meaning of the tool. Set this
option to `True` if you want the app to act on such a change instead of only reporting it.

The tool keeps its row, its schemas, its `writable` value, and its `last_seen_at`. One click puts
it back in service. The job log names a tool that the run switched off separately from a tool that
only changed.

## `is_available`

A read-only property. The REST API also gives it. It is `True` when the tool is enabled **and** its
server is enabled. A tool on a disabled server is not on offer, whatever the flag on the tool says.
