# MCP Resource

![The MCP Resources list](../images/mcp-resources-list-light.png#only-light)
![The MCP Resources list](../images/mcp-resources-list-dark.png#only-dark)

One resource that an [MCP Server](mcpserver.md) advertises.

A server offers three things: tools, resources, and prompts. A resource is content that an
application chooses to put in front of a model. It is not an action the model calls.

## No writable column

An [MCP Tool](mcptool.md) carries `writable` and `advertised_read_only`. This model carries
neither. `resources/read` reads, by protocol. The asymmetry is a decision, not an omission.

CAUTION: A resource is still text that enters a prompt. `enabled` is the lever that keeps one out,
and `definition_fingerprint` still moves when the server rewrites the description.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `mcp_server` | MCP Server | Yes | Deleting the server deletes its resources. |
| `uri` | String | Yes | How a client reads it. Unique within its server. Holds the template when `is_template` is set. |
| `name` | String | No | The name the server gave it. Not the uniqueness key. |
| `title` | String | No | The display name the server offered. |
| `description` | Text | No | What the resource holds, as advertised. |
| `mime_type` | String | No | The content type the server advertised. |
| `is_template` | Boolean | Yes | Whether the URI has parameters in it. |
| `size` | Integer | No | The byte size the server advertised. |
| `annotations` | JSON object | No | The annotations object, stored whole. It decides nothing. |
| `enabled` | Boolean | Yes | A consumer must ignore a disabled resource. |
| `definition_fingerprint` | String | No | The digest of what the server last advertised. |
| `last_seen_at` | Date and time | No | When discovery last saw it advertised. |

## The URI is the key, not the name

The specification does not promise that two resources on one server have different names. It does
promise a distinct URI. So `uri` carries the uniqueness constraint and the natural key, and `name`
is free text.

A template row holds its `uriTemplate` in the same column, and sets `is_template`. The two lists
live in one table because they are one kind of thing to a reviewer.

## Binding one to an agent

A resource is content that an application puts in front of a model, so a person decides which
agents may use which resources. That decision is an [AI Agent Tool](aiagenttool.md) target:
`AIAgentTool.mcp_resource` names the resource, `mcp_kind` returns `resource`, and the app's detail
page shows the agents that may use it. A resource with no `name` needs a `name_override` on the
binding, or the model could not say which resource it meant.

`AIAgentTool.writable` is `False` for a resource binding, because `resources/read` reads by
protocol.

## Discovery

The **MCP Server Discovery** Job writes these rows. It reads `resources/list` and
`resources/templates/list`, and only when the handshake said the server offers resources at all.
An unsupported method raises, and one raised method would fail a whole pass.

The policy is the one that governs tools:

- The Job creates and updates. It never deletes, unless you ask for **Remove stale records**.
- It disables a resource the server stopped advertising.
- `disable_on_definition_change` clears `enabled` when the definition moves.

If a resource list fails on its own, the Job logs it and retires nothing of that kind. A server
having a bad minute must not disable every resource somebody reviewed.

NOTE: The two settings are named for tools and now govern every kind of record an MCP server
advertises. Renaming them would break a deployment's configuration, so the meaning widened and the
names did not.

## Availability

```python
resource.is_available
```

True only when the resource and its server are both enabled.
