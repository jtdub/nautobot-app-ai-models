# AI Agent Skill

One skill that an agent may load. See [AI Skill](aiskill.md) for what a skill is and when to use
one.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `agent` | AI Agent | Yes | |
| `skill` | AI Skill | Yes | |
| `weight` | Integer | Yes | The order skills are listed in. Lower comes first. |

A skill is bound to an agent once. The order decides how the skills appear in the description of
the `load_skill` tool, which is the line the model reads to choose one.
