# AI Agent Fallback

One fallback chat model an agent moves to when its primary model fails.

An [AI Agent](aiagent.md) runs on one primary model. An operator who keeps a backup model records
it here, in advance, so the built agent moves to it on its own instead of waiting for a hand edit
during an outage.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `agent` | AI Agent | Yes | Deleting the agent deletes its fallbacks. |
| `model` | AI Model | Yes | A chat model, protected from deletion while bound. |
| `weight` | Integer | Yes | The order models are tried in. Lower comes first. |

A fallback is bound to an agent once. The order is the point: the built agent tries the primary
model, then each fallback in `weight` order.

## The order and the skip rule

`fallback_models()` returns the available fallbacks in `weight, pk` order. A fallback whose model
or provider is disabled is skipped, the same way a disabled tool is skipped. A model that cannot
answer would fail the same way the primary did.

## The rules

A fallback has to be a chat model, and it cannot be the agent's primary model. If the agent binds
tools or subagents, a fallback recorded as unable to call a tool is refused.

## Usage records

The usage record names the model that answered. If a fallback answered a call, the record says so;
an operator can tell which model cost what.