# AI Usage Record

![The AI Usage Records list](../images/ai-usage-records-list-light.png#only-light)
![The AI Usage Records list](../images/ai-usage-records-list-dark.png#only-dark)

What one model call spent, and what it cost at the price of the day.

## This app writes no row here

The app makes no model call, so it has nothing to record. Whatever ran the agent writes these, the
same way it writes the [AI Agent Thread](aiagentthread.md). The app owns the table, the read views,
and the retention.

Write one over the REST API:

```bash
curl -s -X POST -H "Authorization: Token $NAUTOBOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"thread": "<uuid>", "agent": "<uuid>", "model": "<uuid>",
       "input_tokens": 1200, "output_tokens": 340}' \
  "https://nautobot.example.com/api/plugins/ai-models/ai-usage-records/"
```

Post a list to write a whole run at once. Eight rows per run as eight HTTP calls is not viable.

There is no update route. Nothing rewrites a spend that already happened; a wrong row is deleted.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `thread` | AI Agent Thread | Yes | The run this call belongs to. Deleting the thread deletes its usage. |
| `agent` | AI Agent | Yes | Which agent made the call. A subagent call is its own, not the supervisor's. |
| `model` | AI Model | Yes | The model actually called, which is not always the thread agent's model. |
| `input_tokens` | Integer | Yes | Tokens sent. |
| `output_tokens` | Integer | Yes | Tokens returned. |
| `cached_input_tokens` | Integer | Yes | Input tokens the provider served from its cache. |
| `reasoning_tokens` | Integer | Yes | Tokens spent thinking. Usually billed as output. |
| `input_cost` | Decimal | No | What the input cost. Written by the app, read-only over the API. |
| `output_cost` | Decimal | No | What the answer cost. Written by the app, read-only over the API. |
| `usage_payload` | JSON object | No | The usage object the provider returned, stored whole. |
| `recorded_at` | Date and time | Yes | When the call was made. Retention measures from here. |

## The cost is frozen

`AIModel.input_cost_per_million` changes when a vendor changes its price. A cost worked out on read
would then quietly reprice last quarter.

So the cost is worked out once, at the price recorded when the row is written, and stored. A client
cannot set it: the two fields are read-only over the API.

CAUTION: An empty cost means that nobody had recorded a price for that model. It does not mean the
call was free.

The write helper does the arithmetic:

```python
from nautobot_ai_models.services import usage

usage.record(thread, agent, ai_model, input_tokens=1200, output_tokens=340)
```

## Why this model is different

Every other model in this app is an `OrganizationalModel` or a `PrimaryModel`. This one is a
`BaseModel`, and it declares only two `extras_features`.

The volume decides it. [AI Agent Thread](aiagentthread.md) argues the other way in its own
docstring: a thread changes state two or three times in a whole run, so change logging costs a few
rows. A usage row lands on every model call. Change logging every one of them would double the
write cost and fill the log an operator reads for governance. A webhook for each one is a firehose.

What this costs you: no custom fields, no tags, no notes, no relationships, and no change log on
these rows.

## Totals

```python
record.total_tokens
record.total_cost
```

Neither is stored. `total_tokens` adds the input and the output. The provider's own figure is in
`usage_payload`, and it does not always equal the sum.

## Retention

The **Prune Agent Threads** Job deletes these. It deletes the usage of every expired thread whether
or not you ask it to delete the thread rows, because usage is state and the cascade from the thread
only fires when the thread itself goes.

The window is `checkpoint_retention_days`. See [Install and Configure](../admin/install.md).

NOTE: A deployment that reports on cost over years wants a daily roll-up, not a year of rows. Build
that in a reporting system. This table is the record of what happened, not the report.
