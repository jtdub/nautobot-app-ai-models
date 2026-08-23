# AI Model

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
