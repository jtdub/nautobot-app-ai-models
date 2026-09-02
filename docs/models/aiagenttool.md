# AI Agent Tool

One tool that an agent may call, and what the agent is told about it.

A binding names exactly one tool. It is either an [MCP Tool](mcptool.md) or an
[AI Tool](aitool.md). The app refuses a row that names neither, and a row that names both.

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
| `mcp_tool` | MCP Tool | No | Set this or `ai_tool`, not both. |
| `ai_tool` | AI Tool | No | Set this or `mcp_tool`, not both. |
| `name_override` | String | No | What this agent calls the tool. |
| `description_override` | Text | No | What this agent is told the tool does. |
| `weight` | Integer | Yes | The order tools are offered in. Lower comes first. |

## Four values the model actually reads

These are computed from the binding and its tool. They are read-only, and the REST API returns
them.

| Value | How it resolves |
| --- | --- |
| `wire_name` | The override, or the name of the tool. |
| `wire_description` | The override, or the description of the tool. |
| `writable` | Read from the tool. Never stored twice. |
| `fingerprint` | The definition digest of the tool. |

The gate of a consuming app reads the last two. Because they resolve through the binding, no tool
source can arrive without answering them.

## Two tools can share a name

An agent may bind an MCP tool and an AI tool that have the same name. The builder gives the second
one a numbered suffix, because a model offered two tools of one name has no way to say which it
meant.
