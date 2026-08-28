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
| `provider_type` | choice | yes | Which API dialect this endpoint speaks: `openai`, `anthropic`, `openai_compatible`, or `ollama`. Default `openai`. A consuming app reads this to decide how to address the provider. |
| `openai_compatible` | boolean | yes | The endpoint serves the OpenAI API shape, including `GET /v1/models`. Default `True`. The **Discover AI Models** job runs only against providers where this is true. |
| `enabled` | boolean | yes | Whether this provider is in service. Default `True`. Discovery skips a disabled provider, and any app reading this registry should skip one too. |
| `num_predict` | integer | no | Default maximum number of tokens to generate. `-1` means unlimited. An AI Model may override it. |
| `temperature` | decimal | no | Default sampling temperature, between 0 and 2. An AI Model may override it. |

## Provider type and OpenAI-compatible

The two fields answer different questions, and both are needed.

- `openai_compatible` asks **can models be discovered here**. The **Discover AI Models** job reads
  it, because `GET /v1/models` is the only discovery endpoint this app knows.
- `provider_type` asks **how is this endpoint addressed**. A consuming app reads it before it sends
  anything.

Ollama makes the difference concrete. Ollama serves an OpenAI-compatibility layer, so
`openai_compatible` is a true statement about it. That layer does not return tool calls in the
`tool_calls` field: a model asked for a tool writes the JSON call into the message content, where
nothing can act on it. Its native API does return them. An app that read only the boolean would
address Ollama over the compatibility layer and silently lose tool calling. Recording
`provider_type = ollama` and `openai_compatible = True` states both facts.

Two of the four types are an address rather than a service:

| Type | Needs a remote URL |
|---|---|
| `openai` | no |
| `anthropic` | no |
| `openai_compatible` | yes |
| `ollama` | yes |

A self-hosted vLLM or llama.cpp endpoint has no well-known address. A client that fell back to a
default endpoint for one would reach somebody else's API, with this provider's credential attached.
Saving an `openai_compatible` or `ollama` provider whose External Integration carries no remote URL
is therefore refused.

### Providers that existed before this field

The migration that added `provider_type` fills it in from `openai_compatible`. A provider that
served the OpenAI shape becomes `openai_compatible`. A provider that did not is **left blank**,
because the boolean records only that the endpoint is not OpenAI-shaped and says nothing about
what it is instead. A blank is refused on save, so an operator is asked to answer the next time
they edit the record.

## Taking a provider out of service

Clear `enabled`. A contract lapsing, a self-hosted box going down for maintenance, a rotated key,
or spend that has to stop now are all provider-level events, and this is the field that records
them.

Do not disable each model instead. The **Discover AI Models** job creates models with `enabled`
set, so a provider taken out of service that way quietly comes back the next time discovery runs.
Do not delete the provider either: `AIModel.provider` cascades, so deleting the provider deletes
every model record with it, along with its cost metadata.

Read [`AIModel.is_available`](aimodel.md#availability) to ask whether one model is on offer,
rather than checking both flags.

## Credentials

Attach a Secrets Group to the External Integration. Store the API key as a secret of access type
`HTTP(S)` and secret type `token`. The app reads it at the point of use. It never stores the value.
