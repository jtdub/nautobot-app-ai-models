# AI Agent

One agent: a model, a system prompt, and the tools it may reach. Everything an agent is made of is
a row. The prompt is a column, the tool list is a table, and the specialists it may delegate to are
another table. Nothing about an agent is a constant in Python code.

This app builds an agent from these rows. It does not run one. A consuming app runs it.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | String | Yes | Unique. Also the name a supervisor calls this agent by, unless a binding overrides it. |
| `description` | String | No | What this agent is for. Read the caution below before you write it. |
| `system_prompt` | Text | Yes | The standing instructions of the agent. |
| `model` | AI Model | Yes | The chat model. An embedding model is refused. |
| `pattern` | Choice | Yes | `single`, `subagents`, or `skills`. |
| `enabled` | Boolean | Yes | A disabled agent is not built. |
| `temperature` | Decimal | No | Overrides the model. |
| `num_predict` | Integer | No | Overrides the model. `-1` means unlimited. |
| `max_iterations` | Integer | Yes | How many model calls one run may spend. |
| `tenant` | Tenant | No | |

## The description decides whether the agent is called

CAUTION: A supervisor reads the `description` of a specialist to decide whether to delegate to it.
A description that reads badly to the model produces no error, no exception, and no log line. It
produces silence. When a multi-agent system returns an empty answer, examine the name and the
description first.

Write the description the way you write it for a new colleague on the first day. Say what the agent
does. Say what to send it. Keep it to one or two sentences on one line. A bulleted, multi-line
description stopped a tool being called at all in every measured run.

## Three settings resolve in one chain

`temperature` and `num_predict` are read from the agent first, then the model, then the provider.
The first one that carries a value wins. This lets one model serve a supervisor at temperature 0
and a writer at temperature 0.7.

## Choose a pattern

Start with `single`, and give the agent every tool. Measure it. Most systems stop there.

Move to `subagents` when one prompt can no longer hold every rule. A specialist gets an isolated
context and its own prompt. You pay for that with more model calls, every run.

Move to `skills` when the rules are large and only advisory. See [AI Skill](aiskill.md) for the
measured weakness of that pattern.

## Related

- [AI Agent Tool](aiagenttool.md) binds a tool to an agent.
- [AI Agent Subagent](aiagentsubagent.md) binds a specialist to a supervisor.
- [AI Agent Skill](aiagentskill.md) binds a skill to an agent.
- [AI Agent Thread](aiagentthread.md) records one run.
