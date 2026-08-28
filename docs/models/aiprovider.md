# AI Provider

An AI Provider records one remote LLM endpoint. It does not keep a URL, a header, a TLS setting, or
a credential. A related Nautobot [External Integration](https://docs.nautobot.com/projects/core/en/stable/user-guide/platform-functionality/externalintegration/)
owns all of those. This app does no inference. It only makes a catalog of what is available.

Each AI Provider owns zero or more [AI Models](aimodel.md).

The class is `AIProvider`, not `Provider`. Nautobot core already has `circuits.Provider`. One
unqualified name for two things confuses a reader and an import.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | The unique name of the provider. |
| `description` | string | no | Free text. |
| `external_integration` | foreign key to `extras.ExternalIntegration` | yes | Gives the remote URL, the headers, the TLS settings, the timeout, and the credentials. Protected: Nautobot refuses to delete an External Integration that a provider uses. |
| `provider_type` | choice | yes | The API dialect of this endpoint: `openai`, `anthropic`, `openai_compatible`, or `ollama`. The default is `openai`. A consuming app reads this field to find out how to address the provider. |
| `openai_compatible` | boolean | yes | The endpoint gives the OpenAI API shape, which includes `GET /v1/models`. The default is `True`. The **Discover AI Models** job runs only against a provider that has this flag set. |
| `enabled` | boolean | yes | Whether this provider is in service. The default is `True`. Discovery skips a disabled provider. An app that reads this registry must also skip one. |
| `num_predict` | integer | no | The default maximum number of tokens to generate. `-1` means unlimited. An AI Model can override it. |
| `temperature` | decimal | no | The default sampling temperature, from 0 to 2. An AI Model can override it. |

## Provider type and OpenAI-compatible

The two fields answer different questions. You need both.

- `openai_compatible` answers **can this app discover models here**. The **Discover AI Models** job
  reads it, because `GET /v1/models` is the only discovery endpoint this app knows.
- `provider_type` answers **how does a client address this endpoint**. A consuming app reads it
  before the app sends anything.

Ollama shows the difference. Ollama gives an OpenAI-compatibility layer, so `openai_compatible` is
a true statement about Ollama. But that layer does not return tool calls in the `tool_calls` field.
A model that gets a request for a tool writes the JSON call into the message content, where nothing
can act on it. The native Ollama API returns tool calls correctly. An app that reads only the
boolean addresses Ollama through the compatibility layer and loses tool calling silently. Set
`provider_type` to `ollama` and `openai_compatible` to `True`. This records both facts.

Two of the four types are an address, not a service:

| Type | Needs a remote URL |
|---|---|
| `openai` | no |
| `anthropic` | no |
| `openai_compatible` | yes |
| `ollama` | yes |

A self-hosted vLLM or llama.cpp endpoint has no well-known address.

WARNING: A client with no URL for one of these two types goes to a default endpoint. That endpoint
is another company's API, and the client sends this provider's credential to it. Give an
`openai_compatible` or an `ollama` provider an External Integration with a remote URL. The app
refuses to save one without a URL.

### Providers that existed before this field

The migration that added `provider_type` fills it in from `openai_compatible`. A provider that gave
the OpenAI shape becomes `openai_compatible`. A provider that did not is **left empty**. The boolean
records only that the endpoint is not OpenAI-shaped. It says nothing about what the endpoint is
instead. The app refuses to save an empty value. Thus an operator must answer the next time the
operator edits the record.

## How to take a provider out of service

Clear the **Enabled** checkbox. Each of these is a provider-level event, and this field records it:
a contract that ends, a machine that goes down for maintenance, a key that changes, or spend that
must stop now.

CAUTION: The **Discover AI Models** job creates a model with **Enabled** set. A provider that you
take out of service one model at a time comes back on the next discovery run. Do not disable each
model. Clear the flag on the provider.

CAUTION: `AIModel.provider` cascades. If you delete a provider, you also delete each model record
on it, together with the cost data. Do not delete a provider that you want to keep. Clear the flag
on it.

To find out if one model is on offer, read [`AIModel.is_available`](aimodel.md#availability). It
asks one question in place of two.

## Credentials

Attach a Secrets Group to the External Integration. Keep the API key as a secret with the access
type `HTTP(S)` and the secret type `token`. The app reads the key at the point of use. It never
keeps the value.
