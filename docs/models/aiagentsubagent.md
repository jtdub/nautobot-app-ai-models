# AI Agent Subagent

One specialist that a supervisor may delegate to, and how the supervisor addresses it.

The supervisor calls the specialist as a tool. The specialist runs with an isolated context. It has
no memory of an earlier call, and it never sees the conversation of the supervisor.

## Three columns, three measured findings

### The name and the description decide everything

CAUTION: These two strings decide whether the specialist is ever called. In one measured test, four
wordings of one tool were tried ten times each. Three of the four never called the tool at all. The
model returned an empty message, the framework read it as the final answer, and the run ended with a
blank reply. There was no error and no log line.

Keep the name plain. Keep the description to one or two sentences on one line. A bulleted,
multi-line description failed even with a working name.

### The input mode is a trap

WARNING: Sending the question of the user along with the task looks like a strict improvement. It is
not. In a measured test it broke the system on every run: the specialist read a word in the added
text, matched it against a rule in its own system prompt, and refused the work.

`task_only` is the default for that reason. Read the system prompt of the specialist before you
widen this, and measure before and after.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `parent` | AI Agent | Yes | The supervisor. |
| `subagent` | AI Agent | Yes | The specialist. |
| `tool_name` | String | No | What the supervisor calls the specialist. |
| `tool_description` | Text | No | What the supervisor reads when it decides to delegate. |
| `input_mode` | Choice | Yes | `task_only` or `task_and_context`. |
| `weight` | Integer | Yes | The order specialists are offered in. |

## Cycles are refused

A specialist may have specialists of its own. The app walks the whole chain of bindings and refuses
a row that would make a cycle, because building an agent follows these rows and a cycle in them is a
build that never returns.
