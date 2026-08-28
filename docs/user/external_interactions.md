# External Interactions

This document describes the external dependencies of the app: the system requirements, the API
endpoints, and the connections to other applications and services.

## External System Integrations

### From the App to Other Systems

The app makes an outbound request only when you run one of its two discovery jobs. No part of the
app calls an LLM for inference, and no part calls an MCP tool.

#### Discover AI Models

| Property | Value |
|---|---|
| Request | `GET <remote_url>/v1/models` |
| Trigger | The **Discover AI Models** Job, run by a user or on a schedule |
| Target | Each enabled AI Provider where **OpenAI-compatible** is true |
| Response | The OpenAI model catalog, `{"data": [{"id": "...", "owned_by": "..."}]}` |

`GET /v1/models` is the de facto standard endpoint for model discovery. OpenAI, Azure OpenAI, vLLM,
Ollama, LM Studio, llama.cpp server, Groq, Together, and OpenRouter all give it. No equivalent
standard exists for another endpoint, so the job skips a provider that is not OpenAI-compatible.
The job also skips a disabled provider.

The External Integration of the provider gives each request setting:

| External Integration field | Use |
|---|---|
| `remote_url` | The base URL. The app does not duplicate a trailing `/v1`. |
| `headers` | Sent with the request, after Jinja2 rendering. |
| `secrets_group` | Gives the API key. See below. |
| `verify_ssl` | Sent to the HTTP client. |
| `ca_file_path` | Used in place of `verify_ssl` when it has a value. |
| `timeout` | Sent to the HTTP client. |

#### MCP Server Discovery

| Property | Value |
|---|---|
| Request | An MCP `initialize` handshake, then `tools/list`, in pages |
| Trigger | The **MCP Server Discovery** Job, run by a user or on a schedule |
| Target | Each enabled MCP Server whose transport is `streamable-http` |
| Response | The capabilities of the server, its own metadata, and its tool definitions |

A `stdio` server is a subprocess of its client, so a Nautobot worker cannot reach one. This app
does not speak HTTP+SSE. Discovery skips both and says so. Register their tools by hand.

WARNING: A credential belongs to the host that it was configured for, and a redirect is that host
naming a different one. Neither job obeys an HTTP redirect to another origin while it carries the
headers of the integration.

This job needs the optional `discovery` extra, which brings the MCP client library:

```bash
pip install 'nautobot-ai-models[discovery]'
```

Without the extra, the job stops before it contacts anything and names the extra. Each other part
of the app works without it.

The job records what a server advertised. It decides nothing from it. The MCP specification tells a
client to treat the annotations of a server as untrusted. Thus the app keeps and shows
`advertised_read_only`, and `writable` keeps the value that a person set.

### Credentials

Attach a Secrets Group to the External Integration. Define a secret with:

- Access type: **HTTP(S)**
- Secret type: **token**

The job reads that value and sends it as `Authorization: Bearer <token>`. The app never keeps the
value. On a failure the job log records the exception type. It never records a URL, a header, a
token, or a response body.

### From Other Systems to the App

Another system reads the catalog through the REST API. It does not write to the catalog.

## Nautobot REST API endpoints

| Endpoint | Purpose |
|---|---|
| `/api/plugins/ai-models/ai-providers/` | List and manage AI Providers |
| `/api/plugins/ai-models/ai-models/` | List and manage AI Models |
| `/api/plugins/ai-models/mcp-servers/` | List and manage MCP Servers |
| `/api/plugins/ai-models/mcp-tools/` | List and manage MCP Tools |

List each enabled model of one provider:

```bash
curl -s -H "Authorization: Token $NAUTOBOT_TOKEN" \
  "https://nautobot.example.com/api/plugins/ai-models/ai-models/?provider=my-provider&enabled=true"
```

List each chat model that is on offer, on an enabled provider:

```bash
curl -s -H "Authorization: Token $NAUTOBOT_TOKEN" \
  "https://nautobot.example.com/api/plugins/ai-models/ai-models/?kind=chat&enabled=true&provider__enabled=true"
```

An AI Model also gives two read-only fields. `is_available` is true only when the model and its
provider are both enabled. `resolved_parameters` is the checked set of request parameters to send.

The `provider_enabled` filter asks the same question as `is_available` over the API, because a
read-only field cannot be a filter.

Read one provider with its External Integration expanded:

```bash
curl -s -H "Authorization: Token $NAUTOBOT_TOKEN" \
  "https://nautobot.example.com/api/plugins/ai-models/ai-providers/?depth=1"
```

List each MCP tool that a caller can use without an approval:

```bash
curl -s -H "Authorization: Token $NAUTOBOT_TOKEN" \
  "https://nautobot.example.com/api/plugins/ai-models/mcp-tools/?enabled=true&writable=false"
```

Each endpoint accepts the standard Nautobot filters and lookup expressions, for example
`?name__ic=llama`.

The fields that the MCP discovery job owns are read-only over the API. A client that could change
them could make the registry claim that a server reported something it never did.
