# AI Model

![An AI Model detail view](../images/ai-model-detail-light.png#only-light)
![An AI Model detail view](../images/ai-model-detail-dark.png#only-dark)

An AI Model records one model offered by an [AI Provider](aiprovider.md). It is a catalog entry.
This app performs no inference.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `provider` | foreign key to `AIProvider` | yes | The provider that offers this model. Deleting the provider deletes its models. |
| `name` | string | yes | The model identifier the provider expects, for example `gpt-4o-mini`. Unique within one provider. |
| `description` | string | no | Free-text description. |
| `kind` | choice | yes | What this model is for: `chat` or `embedding`. Default `chat`. Set by a person; discovery cannot tell the two apart. |
| `enabled` | boolean | yes | Consumers should ignore a disabled model. Default `True`. |
| `num_predict` | integer | no | Overrides the provider default. Leave empty to inherit. |
| `temperature` | decimal | no | Overrides the provider default. Leave empty to inherit. |
| `input_cost_per_million` | decimal | no | What a million input tokens cost, in the provider's billing currency. |
| `output_cost_per_million` | decimal | no | What a million output tokens cost. Usually several times the input price. |
| `default_parameters` | JSON object | no | Extra request parameters to send with every call, restricted to an allowlist. Default `{}`. |

## Kind

A chat model and an embedding model are not interchangeable, and they are not even the same
endpoint. The failure this field prevents is not usually calling the wrong endpoint. It is an
operator configuring a retrieval feature with a chat model, or triage with an embedding model, and
getting a provider-side error later, far from the screen where the mistake was made. Recording the
kind turns that into a refusal before any network traffic.

The **Discover AI Models** job leaves `kind` at its default. `GET /v1/models` returns both kinds
mixed together and carries no field saying which is which, so the job records what the endpoint
said and a person owns the judgement. That is the same division of labour `enabled` and `writable`
already use on [MCP Tool](mcptool.md).

## Availability

```python
ai_model.is_available
```

True only when the model and its provider are both enabled. A model on a disabled provider is not
on offer however the model itself is flagged, so a consuming app asks this one question rather than
two. It is exposed as a read-only field on the REST API.

## Cost

The two cost fields record what a million tokens cost, so that a consumer can price a call
before it makes one, or account for one after. They are recorded per model rather than per
provider, because two models on one endpoint rarely cost the same.

Input and output are separate fields because they are separately priced, and output is usually
several times dearer. An empty value means nobody has recorded a price. That is not the same
as free, and a consumer should treat it as unknown.

The app records no currency. A deployment reaching several providers that bill in different
currencies should hold the currency in a custom field on the provider.

## Resolved values

Read the effective values through two properties. Each returns the model's own value when it is
set, and the provider default when it is not.

```python
ai_model.resolved_num_predict
ai_model.resolved_temperature
ai_model.resolved_parameters
```

## Default parameters

`num_predict` and `temperature` cover the two values an operator changes most often. Everything
else a call needs goes in `default_parameters`, as a JSON object.

Only these keys are accepted:

```text
extra_body          logit_bias          seed         timeout
frequency_penalty   n                   stop         top_k
presence_penalty    reasoning_effort    temperature  top_p
```

That is an allowlist, not a denylist, and the difference matters. The keyword surface of a unified
LLM client is wide, aliased, and moves between releases. `base_url` alone overrides `api_base` in
litellm, so a denylist naming `api_base` would never see it. An operator holding only
`change_aimodel` could then redirect a call to a host of their choosing, and the provider's
credential would go with it. An allowlist fails closed on a key nobody has considered.

Every key on the list shapes an answer. None of them decides who answers.

The list is checked when a record is saved and again when the parameters are read. Once is not
enough: a fixture, a data migration, or a direct ORM write never runs model validation, and the
read side is where a key that got past it would be handed to a client. Read the parameters through
`resolved_parameters`, which drops anything off the list:

```python
>>> ai_model.default_parameters
{'seed': 7, 'top_p': 0.9}
>>> ai_model.resolved_parameters
{'seed': 7, 'top_p': 0.9, 'temperature': Decimal('0.70')}
```

### Where temperature comes from

`temperature` is on the allowlist as well as being a column of its own, so it can be set in two
places. The order is most specific first, and `resolved_temperature` and `resolved_parameters`
always agree:

1. `AIModel.temperature`, the column, which is the field an operator sees on the form.
2. `AIModel.default_parameters["temperature"]`.
3. `AIProvider.temperature`, the provider default.

When none of the three is set, `resolved_parameters` leaves `temperature` out rather than sending
a null.

## Discovery

The **Discover AI Models** job creates and updates these records automatically. See
[Using the App](../user/app_use_cases.md). The job never deletes a record, and never changes an
operator's columns on an existing record: `enabled`, `kind`, `num_predict`, `temperature`, either
cost, or `default_parameters`.

The job skips a provider whose `enabled` flag is clear, both when that provider is named directly
and when the job runs against every provider.
