# AI Usage Budget

A permitted spend over one scope and one calendar period.

An [AI Usage Record](aiusagerecord.md) shows what a call spent. A budget records how much a
scope may spend in a period, and the app reports the spend for the current period beside the
limit. The app that runs the agent reads `exceeded_budgets()` before a call and refuses the call
when a limit is reached; this app records and reports, it does not stop a call.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | String | Yes | The name the operator reads this budget by. |
| `description` | String | No | What this limit is for. |
| `enabled` | Boolean | Yes | A disabled budget is not offered to a consuming app. |
| `agent` | AI Agent | No | Set exactly one of the agent, the model, or the tenant. |
| `model` | AI Model | No | Set exactly one of the agent, the model, or the tenant. |
| `tenant` | Tenant | No | Set exactly one of the agent, the model, or the tenant. |
| `period` | Choice | Yes | `day`, `week`, or `month`. Calendar periods in the server time zone. |
| `cost_limit` | Decimal | No | The most the scope may spend in the period. |
| `token_limit` | Integer | No | The most tokens the scope may spend in the period. |

A budget needs exactly one scope and at least one limit.

## The period and the retention

The period counts the usage records that survived pruning. Pruning deletes usage records after
`checkpoint_retention_days`, so a budget whose period is longer than the retention is refused: it
would count less spend than occurred. With the default 30-day retention, a `month` budget is
refused until the administrator raises the retention.

## The spend

`spent_cost` and `spent_tokens` report what the scope spent since the start of the current period.
A usage record with no recorded cost counts as zero.

## Currency

Costs use each provider's billing currency. A tenant budget over two providers can add two
currencies; the recorded costs are the sums of what each provider charged.