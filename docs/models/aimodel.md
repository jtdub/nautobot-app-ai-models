# AI Model

![An AI Model detail view](../images/ai-model-detail-light.png#only-light)
![An AI Model detail view](../images/ai-model-detail-dark.png#only-dark)

An AI Model records one model that an [AI Provider](aiprovider.md) offers. It is a catalog entry.
This app does no inference.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `provider` | foreign key to `AIProvider` | yes | The provider that offers this model. If you delete the provider, you also delete its models. |
| `name` | string | yes | The model identifier that the provider expects, for example `gpt-4o-mini`. Unique in one provider. |
| `description` | string | no | Free text. |
| `kind` | choice | yes | What this model is for: `chat` or `embedding`. The default is `chat`. A person sets it, because discovery cannot tell the two apart. |
| `enabled` | boolean | yes | A consumer must ignore a disabled model. The default is `True`. |
| `num_predict` | integer | no | Overrides the provider default. Leave it empty to inherit. |
| `temperature` | decimal | no | Overrides the provider default. Leave it empty to inherit. |
| `input_cost_per_million` | decimal | no | The cost of a million input tokens, in the billing currency of the provider. |
| `output_cost_per_million` | decimal | no | The cost of a million output tokens. Usually several times the input price. |
| `default_parameters` | JSON object | no | Extra request parameters to send with each call, limited to an allowlist. The default is `{}`. |

## Kind

A chat model and an embedding model are not interchangeable. They are not even the same endpoint.

The usual failure is not a call to the wrong endpoint. It is an operator who configures a retrieval
feature with a chat model, or triage with an embedding model. The provider then gives a confusing
error, at a bad hour, and far from the screen where the mistake occurred. This field turns that
into a refusal before any network traffic.

The **Discover AI Models** job leaves `kind` at its default. `GET /v1/models` returns both kinds
together and has no field that says which is which. Thus the job records what the endpoint said,
and a person makes the decision. `enabled` and `writable` on [MCP Tool](mcptool.md) divide the work
the same way.

## Availability

```python
ai_model.is_available
```

This is `True` only when the model and its provider are both enabled. A model on a disabled
provider is not on offer, whatever the flag on the model says. A consuming app asks this one
question in place of two. The REST API gives it as a read-only field.

## Cost

The two cost fields record the cost of a million tokens. A consumer can then price a call before it
makes one, or account for one afterward. The fields are on the model and not on the provider,
because two models on one endpoint rarely cost the same.

Input and output are separate fields because they have separate prices. Output usually costs
several times more.

CAUTION: An empty value means that nobody recorded a price. It does not mean free. Treat an empty
value as unknown.

The app records no currency. If your deployment reaches several providers that bill in different
currencies, keep the currency in a custom field on the provider.

## Resolved values

Read the effective values through these properties. Each one gives the value of the model when the
model has one, and the provider default when it does not.

```python
ai_model.resolved_num_predict
ai_model.resolved_temperature
ai_model.resolved_parameters
```

## Default parameters

`num_predict` and `temperature` cover the two values that an operator changes most often. Put
everything else that a call needs in `default_parameters`, as a JSON object.

The app accepts only these keys:

```text
extra_body          logit_bias          seed         timeout
frequency_penalty   n                   stop         top_k
presence_penalty    reasoning_effort    temperature  top_p
```

That is an allowlist, not a denylist. The difference is important.

WARNING: The keyword surface of a unified LLM client is wide, it uses aliases, and it moves between
releases. In litellm, `base_url` overrides `api_base`, so a denylist that names `api_base` never
sees `base_url`. An operator who holds only `change_aimodel` could then send a call to a host of
their choice, with the credential of the provider. An allowlist fails closed on a key that nobody
examined. Do not change the allowlist to a denylist.

Each key on the list shapes an answer. No key on the list decides who answers.

The app checks the list when it saves a record, and again when it reads the parameters. Once is not
enough. A fixture, a data migration, or a direct ORM write does not run model validation, and the
read side is where an unchecked key would go to a client. Read the parameters through
`resolved_parameters`, which drops anything that is not on the list:

```python
>>> ai_model.default_parameters
{'seed': 7, 'top_p': 0.9}
>>> ai_model.resolved_parameters
{'seed': 7, 'top_p': 0.9, 'temperature': 0.7}
```

`resolved_parameters` always gives `temperature` as a float, because `json.dumps` refuses a
`Decimal`.

### Where temperature comes from

`temperature` is on the allowlist and it is also a column. Thus you can set it in two places. The
order is most specific first. `resolved_temperature` and `resolved_parameters` always agree:

1. `AIModel.temperature`, the column, which is the field that an operator sees on the form.
2. `AIModel.default_parameters["temperature"]`.
3. `AIProvider.temperature`, the provider default.

If none of the three has a value, `resolved_parameters` leaves `temperature` out. It does not send
a null.

## Discovery

The **Discover AI Models** job creates and updates these records. See
[Using the App](../user/app_use_cases.md).

The job never deletes a record. On an existing record it never changes a column that an operator
owns: `enabled`, `kind`, `num_predict`, `temperature`, either cost, or `default_parameters`.

The job skips a provider whose `enabled` flag is clear. This applies both when you name that
provider directly and when the job runs against every provider.
