# MCP Prompt

![The MCP Prompts list](../images/mcp-prompts-list-light.png#only-light)
![The MCP Prompts list](../images/mcp-prompts-list-dark.png#only-dark)

One prompt template that an [MCP Server](mcpserver.md) advertises.

A prompt is a template that a person selects. The model does not choose it. There is no binding
table from an [AI Agent](aiagent.md) to a prompt; when an agent must choose one for itself, that is
a target on [AI Agent Tool](aiagenttool.md).

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `mcp_server` | MCP Server | Yes | Deleting the server deletes its prompts. |
| `name` | String | Yes | The prompt name on the wire. Unique within its server, and case sensitive. |
| `title` | String | No | The display name the server offered. |
| `description` | Text | No | What the prompt is for, as advertised. |
| `arguments` | JSON list | No | The arguments the server advertised. |
| `enabled` | Boolean | Yes | A consumer must ignore a disabled prompt. |
| `definition_fingerprint` | String | No | The digest of what the server last advertised. |
| `last_seen_at` | Date and time | No | When discovery last saw it advertised. |

## The arguments are a list, not a schema

`MCPTool.input_schema` holds a JSON Schema, which is an object. `MCPPrompt.arguments` holds a list,
because the protocol sends a list of `{name, description, required}` here.

WARNING: This is the one place where the two models do not mirror each other. Code that reads
`input_schema` with `.get(...)` breaks on `arguments`. Read the list.

```python
prompt.required_arguments
```

That gives the names the server marked required, in the order it gave them.

## Binding one to an agent

An [AI Agent Tool](aiagenttool.md) exists because the name and the description a model reads decide
whether it calls a tool, and a bad pair fails in silence. An operator has to be able to correct
that on the binding.

A prompt that a person picks from a list has no such pressure, so there is no binding table. When
a consuming app needs an agent to select a prompt for itself, that is a target on `AIAgentTool`
beside the MCP tool and the AI tool, not a second binding table. `AIAgentTool.mcp_kind` returns
`prompt` for such a binding, and the app's detail page shows the agents that may use this prompt.

## Discovery

The **MCP Server Discovery** Job writes these rows. It reads `prompts/list`, and only when the
handshake said the server offers prompts.

The policy is the one that governs [MCP Resources](mcpresource.md) and
[MCP Tools](mcptool.md): create and update, never delete, disable what the server stopped
advertising, and clear `enabled` on a moved definition when the setting says so.

## Availability

```python
prompt.is_available
```

True only when the prompt and its server are both enabled.
