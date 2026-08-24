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
| `enabled` | boolean | yes | Consumers should ignore a disabled model. Default `True`. |
| `num_predict` | integer | no | Overrides the provider default. Leave empty to inherit. |
| `temperature` | decimal | no | Overrides the provider default. Leave empty to inherit. |
| `input_cost_per_million` | decimal | no | What a million input tokens cost, in the provider's billing currency. |
| `output_cost_per_million` | decimal | no | What a million output tokens cost. Usually several times the input price. |

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
```

## Discovery

The **Discover AI Models** job creates and updates these records automatically. See
[Using the App](../user/app_use_cases.md). The job never deletes a record, and never changes
`enabled`, `num_predict`, or `temperature` on an existing record.
