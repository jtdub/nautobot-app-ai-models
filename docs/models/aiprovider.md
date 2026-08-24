# AI Provider

An AI Provider records one remote LLM endpoint. It does not store a URL, a header, a TLS setting,
or a credential. A related Nautobot [External Integration](https://docs.nautobot.com/projects/core/en/stable/user-guide/platform-functionality/externalintegration/)
owns all of those. This app performs no inference. It only catalogs what is available.

Each AI Provider owns zero or more [AI Models](aimodel.md).

The model class is `AIProvider`, not `Provider`. Nautobot core already defines
`circuits.Provider`, and one unqualified name for two things confuses both a reader and an
import.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Unique name for the provider. |
| `description` | string | no | Free-text description. |
| `external_integration` | foreign key to `extras.ExternalIntegration` | yes | Supplies the remote URL, headers, TLS settings, timeout, and credentials. Protected: Nautobot refuses to delete an External Integration a Provider still uses. |
| `openai_compatible` | boolean | yes | The endpoint serves the OpenAI API shape, including `GET /v1/models`. Default `True`. The **Discover AI Models** job runs only against providers where this is true. |
| `num_predict` | integer | no | Default maximum number of tokens to generate. `-1` means unlimited. An AI Model may override it. |
| `temperature` | decimal | no | Default sampling temperature, between 0 and 2. An AI Model may override it. |

## Credentials

Attach a Secrets Group to the External Integration. Store the API key as a secret of access type
`HTTP(S)` and secret type `token`. The app reads it at the point of use. It never stores the value.
