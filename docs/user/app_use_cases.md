# Using the App

This document describes the common use cases for this app.

## General Usage

The app holds two registries under one **AI Tools** menu.

- **AI Tools → AI Models** lists **AI Providers** and **AI Models**: the LLM endpoints and the
  models that each one offers.
- **AI Tools → MCP Models** lists **MCP Servers** and **MCP Tools**: the MCP servers and what each
  one advertises.

Neither registry calls anything. Both record what exists, so that other apps read one place.

![The AI Tools navigation tab](../images/ai-tools-navigation-light.png#only-light)
![The AI Tools navigation tab](../images/ai-tools-navigation-dark.png#only-dark)

![The AI Providers list](../images/ai-providers-list-light.png#only-light)
![The AI Providers list](../images/ai-providers-list-dark.png#only-dark)

## AI providers and models

### How to add a provider

1. Go to **AI Tools → AI Models → AI Providers**. Select **Add**.
2. Enter a **Name**.
3. Select an **External Integration**. If the integration does not exist, select the **+** button
   beside the field. A modal opens. Create the External Integration there, and the app selects the
   new record for you. You do not leave the provider form.
4. Select a **Provider type**. This is the API dialect that a consuming app uses to address the
   endpoint.
5. Keep **OpenAI-compatible** set if the endpoint gives `GET /v1/models`. This is a different
   question from the provider type. Ollama answers yes to both.
6. Set a default **num_predict** and **temperature**, if you want them.

CAUTION: An `openai_compatible` or an `ollama` provider is an address, not a service. Give one an
External Integration with a remote URL. Without a URL, a client goes to another company's endpoint.

![Add an AI Provider](../images/ai-provider-add-form-light.png#only-light)
![Add an AI Provider](../images/ai-provider-add-form-dark.png#only-dark)

The **+** button beside the field opens this modal. Complete it and select **Create**. The app then
selects the new External Integration on the provider form behind the modal.

![Creating an External Integration without leaving the page](../images/embedded-create-modal-light.png#only-light)
![Creating an External Integration without leaving the page](../images/embedded-create-modal-dark.png#only-dark)

### How to discover the models that a provider offers

Run **Jobs → AI Models → Discover AI Models**.

The job reads `GET <remote_url>/v1/models` from each OpenAI-compatible provider and syncs the
result. You can run it as often as you want:

- The job creates a record for a model in the response that is not in the database.
- A model that is already in the database keeps each column that an operator owns: `enabled`,
  `kind`, `num_predict`, `temperature`, both costs, and `default_parameters`. A user can set any of
  them by hand, so the job never overwrites them.
- The job **logs and keeps** a model in the database that the provider no longer offers. It never
  deletes a record.

Leave **AI Provider** empty to run against each enabled provider. Clear **Enable new models** to
create new records in the disabled state, for a review.

The job skips a provider that is not OpenAI-compatible, and says so. No standard discovery endpoint
exists for such a provider.

The job also skips a disabled provider. This applies both when you name that provider directly and
when the job runs against every provider. A provider that you take out of service does not come
back on the next discovery run.

The job creates each new model with **Kind** set to `chat`. `GET /v1/models` returns chat models
and embedding models together and says nothing about which is which. Correct the embedding models
by hand after the first run.

![The Discover AI Models job result](../images/ai-discovery-job-result-light.png#only-light)
![The Discover AI Models job result](../images/ai-discovery-job-result-dark.png#only-dark)

The provider detail view lists what the job found.

![An AI Provider after discovery](../images/ai-provider-detail-light.png#only-light)
![An AI Provider after discovery](../images/ai-provider-detail-dark.png#only-dark)

### How to override an inference parameter for one model

`num_predict` and `temperature` are on both models. The provider value is the default. The model
value is an override. Leave the model value empty to inherit the default.

Read the effective value from the ORM:

```python
ai_model.resolved_num_predict
ai_model.resolved_temperature
```

### How to send a parameter that has no field of its own

Put it in **Default parameters** on the model, as a JSON object. Use `seed` for a run that must
repeat. Use `reasoning_effort` for a reasoning model. Use `top_k` and `top_p` for a local model.
Use `extra_body` for anything that a unified client has no name for.

The app accepts only the keys on its allowlist. No key on that list decides which host answers.
Read the whole set through `ai_model.resolved_parameters`, which applies the allowlist again and
adds the resolved temperature. See [AI Model](../models/aimodel.md#default-parameters).

### How to record what a model is for

Set **Kind** to `chat` or to `embedding`. The two are not interchangeable and they are not the same
endpoint. This lets a consuming app refuse a wrong configuration before it sends anything.

### How to retire a model without a delete

Clear the **Enabled** checkbox. The record stays, its history stays, and the discovery job does not
change the flag. A consumer must skip a disabled model.

### How to take a whole provider out of service

Clear the **Enabled** checkbox on the provider. Discovery skips it, and an app that reads this
registry must skip each model on it. Ask `ai_model.is_available` in place of a check on both flags.

CAUTION: The discovery job creates a model with **Enabled** set. A provider that you retire one
model at a time comes back on the next run. Do not disable each model.

CAUTION: A delete of the provider also deletes each model record on it, together with the cost
data. Do not delete a provider that you want to keep.

### How to record what a model costs

Set **Input cost per million tokens** and **Output cost per million tokens** on the model. A
consumer can then price a call before it makes one, or account for one afterward. Output usually
costs several times more than input. That is why the two are separate fields.

CAUTION: An empty price means that nobody recorded one. Treat it as unknown, not as free.

![An AI Model detail view](../images/ai-model-detail-light.png#only-light)
![An AI Model detail view](../images/ai-model-detail-dark.png#only-dark)

### How to examine every model at once

The AI Models list shows each model of each provider. Filter it by provider, by kind, by enabled
state, or by name.

![The AI Models list](../images/ai-models-list-light.png#only-light)
![The AI Models list](../images/ai-models-list-dark.png#only-dark)

## MCP servers and tools

### How to register a server

1. Go to **AI Tools → MCP Models → MCP Servers**. Select **Add**.
2. Give the server a name and select its **External Integration**.

    If the integration does not exist, select the **+** button beside the field. The External
    Integration form opens in a modal over the page. Save it, and the app selects the new
    integration without a loss of what you typed. This needs the
    `extras.add_externalintegration` permission. Without that permission, Nautobot hides the
    button.

3. Select the **Transport**. Almost every remote server is `streamable-http`, and that is the only
   transport that discovery reads. A `stdio` server runs as a subprocess of its client, so a worker
   cannot reach one. The MCP specification deprecates `sse`, and this app does not speak it.
   Discovery skips both and says so. Enter their tools by hand.
4. Save.

![The MCP Servers list](../images/mcp-servers-list-light.png#only-light)
![The MCP Servers list](../images/mcp-servers-list-dark.png#only-dark)

### How to discover what a server offers

Open the server and select **Run Discovery**. You can also run
**Jobs → MCP Models → MCP Server Discovery** directly. Leave the server empty to discover each
enabled server. That is the form to schedule.

Discovery records what the server said. It never enables a tool and it never sets `writable`.

A discovered server shows five things: what the operator set, what the server reported about
itself, its advertised capabilities, its own instructions, and each tool that it offers.

![An MCP Server after discovery](../images/mcp-server-detail-light.png#only-light)
![An MCP Server after discovery](../images/mcp-server-detail-dark.png#only-dark)

### How to review the tools

A newly discovered tool arrives enabled, with `writable` set to `True`. Assume that the tool writes
until a person has read what it does.

Two optional settings change this. Set `new_tools_enabled` to `False`, and a new tool arrives
switched off, so nothing is on offer before a person reads it. Set `disable_on_definition_change`
to `True`, and the app switches a tool off when its definition moves after a review. See
[Install](../admin/install.md#optional-settings).

Go to **AI Tools → MCP Models → MCP Tools**. Read the description and the input schema of each new
tool. Select the tools that only read. Use **Edit Selected** to clear `writable` on all of them at
once.

The **Advertised Read Only** column shows the claim of the server.

WARNING: The MCP specification tells a client not to decide from an annotation of a server. Treat
this column as a hint from a party that nothing verified. Use it only to compare the claim against
the description.

![The MCP Tools list](../images/mcp-tools-list-light.png#only-light)
![The MCP Tools list](../images/mcp-tools-list-dark.png#only-dark)

Open a tool to see both advertised JSON Schemas, and the fingerprint that says whether the contract
moved since the review:

![An MCP Tool with both advertised schemas](../images/mcp-tool-detail-light.png#only-light)
![An MCP Tool with both advertised schemas](../images/mcp-tool-detail-dark.png#only-dark)

### How to register a server that Nautobot cannot reach

A `stdio` server has no endpoint for a worker to open. Register the server, then add its tools by
hand from **AI Tools → MCP Models → MCP Tools → Add**. Each other part of the record works normally.

## How to read a registry from another app

This is what the app is for. Both registries are plain Nautobot models, so another app reads them
through the ORM or the REST API.

### The AI registry

Filter on both flags. A model on a disabled provider is not on offer, whatever the flag on the
model says. `ai_model.is_available` asks the same question about one record.

```python
from nautobot_ai_models.models import AIModel

available = AIModel.objects.filter(
    enabled=True,
    provider__enabled=True,
).select_related("provider__external_integration")
```

Read `provider_type` to find out how to address each endpoint.

WARNING: The OpenAI-compatibility layer of Ollama does not return tool calls. A client that reads
`openai_compatible` alone loses tool calling silently. Read `provider_type`.

```python
for ai_model in available:
    print(ai_model.name, ai_model.provider.provider_type)
```

Split the chat models from the embedding models, which are not interchangeable:

```python
chat = available.filter(kind="chat")
embedding = available.filter(kind="embedding")
```

Read the effective inference parameters, with the provider default added:

```python
for ai_model in available:
    print(ai_model.name, ai_model.resolved_num_predict, ai_model.resolved_temperature)
    print(ai_model.resolved_parameters)
```

`resolved_parameters` checks the allowlist again as it reads, so it is safe to send.

Read the price of a million tokens. `None` means that nobody recorded a price. It does not mean
free.

```python
priced = available.exclude(input_cost_per_million=None)
```

### The MCP registry

```python
from nautobot_ai_models.models import MCPTool

available = MCPTool.objects.filter(
    enabled=True,
    mcp_server__enabled=True,
).select_related("mcp_server__external_integration")

read_only = available.filter(writable=False)
```

Build the connection from the integration of the server. Render the templated fields. Do not read
them raw, because all three support Jinja2:

```python
integration = tool.mcp_server.external_integration
url = integration.render_remote_url({"obj": tool.mcp_server})
headers = integration.render_headers({"obj": tool.mcp_server})
```

### How to find that the contract of a tool changed

`definition_fingerprint` is a digest of the title, the description, and both schemas of the tool.
Record it beside the approval that you gave. A difference from the current value means that the
server changed the tool after a person reviewed it. The review is then out of date.
