# AI Agent Tool

One tool that an agent may call, and what the agent is told about it.

A binding names exactly one target: an [MCP Tool](mcptool.md), an [AI Tool](aitool.md), an
[MCP Prompt](mcpprompt.md), or an [MCP Resource](mcpresource.md). The app refuses a row that names
none, and a row that names more than one.

## The overrides are the point

CAUTION: The name of a tool and its description decide whether the model calls it at all, and the
failure when they read badly is silence rather than an error. An operator has to be able to correct
that here, on the binding, without editing the MCP server that advertised the tool or the code that
registered it.

Leave both empty and the binding uses the name and the description of the tool itself.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `agent` | AI Agent | Yes | |
| `mcp_tool` | MCP Tool | No | Set one of the four targets, not more. |
| `ai_tool` | AI Tool | No | Set one of the four targets, not more. |
| `mcp_prompt` | MCP Prompt | No | Set one of the four targets, not more. |
| `mcp_resource` | MCP Resource | No | Set one of the four targets, not more. |
| `name_override` | String | No | What this agent calls the target. |
| `description_override` | Text | No | What this agent is told the target does. |
| `weight` | Integer | Yes | The order targets are offered in. Lower comes first. |

A resource target whose resource has no `name` needs a `name_override`, or the model could not say
which resource it meant.

## Values the model actually reads

These are computed from the binding and its target. They are read-only, and the REST API returns
them.

| Value | How it resolves |
| --- | --- |
| `wire_name` | The override, or the name of the target. |
| `wire_description` | The override, or the description of the target. |
| `writable` | Read from the target. Never stored twice. |
| `fingerprint` | The definition digest of the target. |
| `is_approved` | Whether an [AI Tool Approval](aitoolapproval.md) still answers for this digest. |
| `mcp_kind` | `tool`, `prompt`, or `resource` for an MCP target, `null` for an AI tool. A consuming app reads it to pick the MCP call. |

The gate of a consuming app reads the last two. Because they resolve through the binding, no tool
source can arrive without answering them.

## Approval

`fingerprint` exists so that an approval can be checked against it. The approval itself is an
[AI Tool Approval](aitoolapproval.md) row, and `is_approved` reads it.

The app records the answer and enforces nothing. A consuming app reads `is_approved` before it
wires its caller, and the same app owns the gate that a call passes through.

## Two tools can share a name

An agent may bind an MCP tool and an AI tool that have the same name. The builder gives the second
one a numbered suffix, because a model offered two tools of one name has no way to say which it
meant.
