# AI Skill

A block of domain rules that an agent loads part-way through a run. A skill is a prompt that arrives
as a tool result rather than as a system prompt.

## The measured weakness

WARNING: A rule that arrives as a tool result does not hold as firmly as the same rule in a system
prompt. In a measured comparison, an agent loaded a skill, read a rule in it, and then broke that
rule on every run. The same rule held when it sat in the system prompt of a subagent.

Use a skill where the cost of ignoring the rule is low. A knowledge base fits well. Where a rule
must hold, put it in the system prompt of an [AI Agent](aiagent.md), or give the work to a
specialist whose prompt carries it.

## What a skill is worth

An agent with twenty skills still loads one. The prompt stays small, and the saving grows with the
number of skills. In one measured comparison, skills used 28% less prompt text than a single agent
that carried every policy in its system prompt.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | String | Yes | Unique. The name the agent loads the skill by. |
| `description` | String | No | What area of work this covers, in a few words. |
| `body` | Text | Yes | The rules. This text is handed to the agent when it loads the skill. |
| `enabled` | Boolean | Yes | A disabled skill is not offered. |

## How the agent sees it

An agent with `pattern` set to `skills` gets one extra tool, called `load_skill`. Its description
lists every enabled skill of the agent on one line, with the description of each. The agent reads
that line to choose a skill. Keep each description short.
