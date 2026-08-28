# Frequently Asked Questions

## Does this app call an LLM or an MCP tool?

No. The app is a catalog. It records which endpoints, models, servers, and tools exist. Another
app, a Job, or an external system reads these records and makes the call.

## Why is there both a Provider type and an OpenAI-compatible flag?

The two answer different questions. `openai_compatible` says whether the app can discover models at
the endpoint. `provider_type` says how a client addresses the endpoint. Ollama answers yes to the
first and still needs its own dialect, because its compatibility layer does not return tool calls.
See [AI Provider](../models/aiprovider.md#provider-type-and-openai-compatible).

## Why did discovery create every model as a chat model?

`GET /v1/models` returns chat models and embedding models together. It has no field that says which
is which. The job records what the endpoint said. Set the **Kind** of each embedding model by hand.

## How do I take a provider out of service?

Clear the **Enabled** checkbox on the provider. Do not disable each model, and do not delete the
provider. See [AI Provider](../models/aiprovider.md#how-to-take-a-provider-out-of-service).

## Why can I not put `base_url` in Default parameters?

The app accepts only the keys on an allowlist, and no key on that list decides which host answers.
This stops an operator who holds only `change_aimodel` from sending a call, and the credential of
the provider, to a host of their choice. See
[AI Model](../models/aimodel.md#default-parameters).

## Where does the app keep an API key?

In a Nautobot Secret, on the Secrets Group of the External Integration. The app reads the value at
the point of use and never keeps it. See
[External Interactions](external_interactions.md#credentials).

## The MCP Server Discovery job says a library is missing. What do I install?

The optional `discovery` extra:

```bash
pip install 'nautobot-ai-models[discovery]'
```

Each other part of the app works without it.

## Why does discovery skip my MCP server?

Discovery reads a `streamable-http` server only. A `stdio` server is a subprocess of its client, so
a Nautobot worker cannot reach one, and this app does not speak HTTP+SSE. Register the tools of
such a server by hand. Discovery also skips a disabled server.

## A tool came back disabled after a discovery run. Why?

Two settings can do this. `disable_on_definition_change` clears the flag when the definition of a
tool moves. Discovery also disables a tool that the server stopped advertising. See
[MCP Tool](../models/mcptool.md#discovery-policy).
