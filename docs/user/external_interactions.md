# External Interactions

This document describes external dependencies and prerequisites for this App to operate, including system requirements, API endpoints, interconnection or integrations to other applications or services, and similar topics.

## External System Integrations

### From the App to Other Systems

The app makes outbound requests only when you run one of its two discovery jobs. Nothing in the
app calls an LLM for inference, and nothing calls an MCP tool.

#### Discover AI Models

| Property | Value |
|---|---|
| Request | `GET <remote_url>/v1/models` |
| Trigger | The **Discover AI Models** Job, run by a user or on a schedule |
| Target | Every AI Provider where **OpenAI-compatible** is true |
| Response | The OpenAI model catalog, `{"data": [{"id": "...", "owned_by": "..."}]}` |

`GET /v1/models` is the de facto standard model-discovery endpoint. OpenAI, Azure OpenAI, vLLM,
Ollama, LM Studio, llama.cpp server, Groq, Together, and OpenRouter all serve it. No equivalent
standard exists for other endpoints, so the job skips a provider that is not OpenAI-compatible.

The request settings all come from the provider's External Integration:

| External Integration field | Use |
|---|---|
| `remote_url` | The base URL. A trailing `/v1` is not duplicated. |
| `headers` | Sent with the request, after Jinja2 rendering. |
| `secrets_group` | Supplies the API key. See below. |
| `verify_ssl` | Passed to the HTTP client. |
| `ca_file_path` | Used in place of `verify_ssl` when set. |
| `timeout` | Passed to the HTTP client. |

#### MCP Server Discovery

| Property | Value |
|---|---|
| Request | An MCP `initialize` handshake, then `tools/list`, paged |
| Trigger | The **MCP Server Discovery** Job, run by a user or on a schedule |
| Target | Every enabled MCP Server whose transport a worker can open |
| Response | The server's capabilities, its own metadata, and its tool definitions |

A `stdio` server is a subprocess of its client, so a Nautobot worker cannot reach one. Discovery
skips it and says so. Register its tools by hand.

This job needs the optional `discovery` extra, which brings the MCP client library:

```bash
pip install 'nautobot-ai-models[discovery]'
```

Without it the job stops before it contacts anything and names the extra. Every other part of
the app works without it.

The job records what a server advertised. It decides nothing from it. The MCP specification
requires that a client treat a server's own annotations as untrusted, so `advertised_read_only`
is stored and shown, and `writable` stays whatever a person set.

### Credentials

Attach a Secrets Group to the External Integration. Define a secret with:

- Access type: **HTTP(S)**
- Secret type: **token**

The job reads that value and sends it as `Authorization: Bearer <token>`. The app never stores the
value. The job log records the exception type on a failure, never a URL, a header, a token, or a
response body.

### From Other Systems to the App

Other systems read the catalog through the REST API. They do not write to it.

## Nautobot REST API endpoints

| Endpoint | Purpose |
|---|---|
| `/api/plugins/ai-models/ai-providers/` | List and manage AI Providers |
| `/api/plugins/ai-models/ai-models/` | List and manage AI Models |
| `/api/plugins/ai-models/mcp-servers/` | List and manage MCP Servers |
| `/api/plugins/ai-models/mcp-tools/` | List and manage MCP Tools |

List every enabled model for one provider:

```bash
curl -s -H "Authorization: Token $NAUTOBOT_TOKEN" \
  "https://nautobot.example.com/api/plugins/ai-models/ai-models/?provider=my-provider&enabled=true"
```

Read one provider with its External Integration expanded:

```bash
curl -s -H "Authorization: Token $NAUTOBOT_TOKEN" \
  "https://nautobot.example.com/api/plugins/ai-models/ai-providers/?depth=1"
```

List every MCP tool a caller may use without approval:

```bash
curl -s -H "Authorization: Token $NAUTOBOT_TOKEN" \
  "https://nautobot.example.com/api/plugins/ai-models/mcp-tools/?enabled=true&writable=false"
```

Every endpoint accepts the standard Nautobot filters and lookup expressions, for example
`?name__ic=llama`.

The fields the MCP discovery job owns are read-only over the API. A client that could change
them could make the registry claim a server reported something it never did.
