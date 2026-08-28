# Using the App

This document describes common use-cases and scenarios for this App.

## General Usage

The app holds two registries under one **AI Tools** menu.

- **AI Tools → AI Models** lists **AI Providers** and **AI Models**, the LLM endpoints and the
  models each one offers.
- **AI Tools → MCP Models** lists **MCP Servers** and **MCP Tools**, the MCP servers and what
  each one advertises.

Neither registry calls anything. Both record what exists so that other apps read one place.

![The AI Tools navigation tab](../images/ai-tools-navigation-light.png#only-light)
![The AI Tools navigation tab](../images/ai-tools-navigation-dark.png#only-dark)

![The AI Providers list](../images/ai-providers-list-light.png#only-light)
![The AI Providers list](../images/ai-providers-list-dark.png#only-dark)

## AI providers and models

### Add a provider

1. Go to **AI Tools → AI Models → AI Providers**, then select **Add**.
2. Enter a **Name**.
3. Choose an **External Integration**. If the one you need does not exist yet, select the **+**
   button beside the field. A modal opens, you create the External Integration in place, and the new
   record is selected for you. You never leave the provider form.
4. Choose a **Provider type**: the API dialect a consuming app uses to address this endpoint. An
   `openai_compatible` or `ollama` provider needs an External Integration with a remote URL, because
   those two are an address rather than a service.
5. Leave **OpenAI-compatible** checked if the endpoint serves `GET /v1/models`. This is a separate
   question from the provider type, and Ollama answers yes to both.
6. Optionally set a default **num_predict** and **temperature**.

![Add an AI Provider](../images/ai-provider-add-form-light.png#only-light)
![Add an AI Provider](../images/ai-provider-add-form-dark.png#only-dark)

The **+** button beside the field opens this modal. Fill it in, select **Create**, and the new
External Integration is selected on the provider form behind it.

![Creating an External Integration without leaving the page](../images/embedded-create-modal-light.png#only-light)
![Creating an External Integration without leaving the page](../images/embedded-create-modal-dark.png#only-dark)

### Discover the models a provider offers

Run **Jobs → AI Models → Discover AI Models**.

The job reads `GET <remote_url>/v1/models` from each OpenAI-compatible provider and syncs the
result. It is safe to run repeatedly:

- A model in the response that is not in the database is created.
- A model already in the database keeps every column an operator owns: `enabled`, `kind`,
  `num_predict`, `temperature`, both costs, and `default_parameters`. A user may have set any of
  them by hand, so the job never overwrites them.
- A model in the database that the provider no longer offers is **logged and kept**. The job never
  deletes a record.

Leave **AI Provider** empty to run against every enabled provider. Uncheck **Enable new models** to
create new records in the disabled state for review.

A provider that is not OpenAI-compatible is skipped, and the job says so. No standard discovery
endpoint exists for those.

A disabled provider is skipped too, whether it was named directly or picked up by an all-providers
run. A provider taken out of service does not come back the next time discovery runs.

Every new model is created with **Kind** set to `chat`. `GET /v1/models` returns chat models and
embedding models mixed together and says nothing about which is which, so correct the embedding
models by hand after a first run.

![The Discover AI Models job result](../images/ai-discovery-job-result-light.png#only-light)
![The Discover AI Models job result](../images/ai-discovery-job-result-dark.png#only-dark)

The provider detail view lists everything the job found.

![An AI Provider after discovery](../images/ai-provider-detail-light.png#only-light)
![An AI Provider after discovery](../images/ai-provider-detail-dark.png#only-dark)

### Override an inference parameter for one model

`num_predict` and `temperature` exist on both models. The provider value is the default. The model
value is an override. Leave the model value empty to inherit.

Read the effective value from the ORM:

```python
ai_model.resolved_num_predict
ai_model.resolved_temperature
```

### Send a parameter that has no field of its own

Put it in **Default parameters** on the model, as a JSON object. `seed` for a deterministic run,
`reasoning_effort` for a reasoning model, `top_k` and `top_p` for a local model, and `extra_body`
for anything a unified client has no name for.

Only the keys on the app's allowlist are accepted, and nothing that decides which host answers is
on it. Read the whole set through `ai_model.resolved_parameters`, which applies the allowlist again
and folds the resolved temperature in. See [AI Model](../models/aimodel.md#default-parameters).

### Retire a model without deleting it

Clear the **Enabled** checkbox. The record stays, its history stays, and the discovery job leaves
the flag alone. Consumers should skip a disabled model.

### Take a whole provider out of service

Clear the **Enabled** checkbox on the provider. Discovery skips it, and any app reading this
registry should skip every model on it.

Do not disable each model instead: the discovery job creates models with **Enabled** set, so a
provider retired that way quietly comes back on the next run. Do not delete the provider either,
because that deletes every model record on it along with the cost metadata.

Ask `ai_model.is_available` rather than checking both flags.

### Record what a model costs

Set **Input cost per million tokens** and **Output cost per million tokens** on the model, so
that a consumer can price a call before it makes one, or account for one afterwards. Output is
usually several times dearer than input, which is why the two are separate fields.

An empty price means nobody has recorded one. Treat it as unknown, not as free.

![An AI Model detail view](../images/ai-model-detail-light.png#only-light)
![An AI Model detail view](../images/ai-model-detail-dark.png#only-dark)

### Browse every model at once

The AI Models list shows every model across every provider. Filter it by provider, by enabled
state, or by name.

![The AI Models list](../images/ai-models-list-light.png#only-light)
![The AI Models list](../images/ai-models-list-dark.png#only-dark)

## MCP servers and tools

### Register a server

1. Go to **AI Tools → MCP Models → MCP Servers** and select **Add**.
2. Give the server a name and pick its **External Integration**.

    If the integration does not exist yet, select the **+** button beside the field. The External
    Integration form opens in a modal over the page. Save it, and the new integration is selected
    without losing anything already typed. This needs the `extras.add_externalintegration`
    permission; without it, Nautobot hides the button.

3. Choose the **Transport**. Almost every remote server is `streamable-http`, which is the only
   transport discovery reads. A `stdio` server runs as a subprocess of its client, so a worker
   cannot reach one; `sse` is deprecated by the MCP specification and this app speaks none of
   it. Discovery skips both and says so, and their tools are entered by hand.
4. Save.

![The MCP Servers list](../images/mcp-servers-list-light.png#only-light)
![The MCP Servers list](../images/mcp-servers-list-dark.png#only-dark)

### Discover what a server offers

Open the server and select **Run Discovery**, or run **Jobs → MCP Models → MCP Server Discovery**
directly. Leave the server blank to discover every enabled server, which is the form to schedule.

Discovery writes down what the server said. It never enables a tool and never sets `writable`.

A discovered server shows what the operator set, what the server reported about itself, its
advertised capabilities, its own instructions, and every tool it offers:

![An MCP Server after discovery](../images/mcp-server-detail-light.png#only-light)
![An MCP Server after discovery](../images/mcp-server-detail-dark.png#only-dark)

### Review the tools

A newly discovered tool arrives enabled and marked `writable=True`. Assume it writes until somebody
has read what it does.

Set `new_tools_enabled` to `False` in `PLUGINS_CONFIG` to have new tools arrive switched off
instead, so nothing is on offer before a person has read it. Set `disable_on_definition_change` to
`True` to have a tool switched off when its definition moves under a review somebody already did.
See [Install](../admin/install.md#optional-settings).

Go to **AI Tools → MCP Models → MCP Tools**, read each new tool's description and input schema, select
the ones that only read, and use **Edit Selected** to clear `writable` on all of them at once.

The **Advertised Read Only** column shows what the server itself claimed. Treat it as a hint from
an unverified party: the MCP specification requires that a client not decide from it. It is there
so a reviewer can compare the claim against the description.

![The MCP Tools list](../images/mcp-tools-list-light.png#only-light)
![The MCP Tools list](../images/mcp-tools-list-dark.png#only-dark)

Opening a tool shows both JSON Schemas the server advertised, and the fingerprint that says whether
its contract has moved since the review:

![An MCP Tool with both advertised schemas](../images/mcp-tool-detail-light.png#only-light)
![An MCP Tool with both advertised schemas](../images/mcp-tool-detail-dark.png#only-dark)

### Register a server Nautobot cannot reach

A `stdio` server has no endpoint for a worker to open. Register the server, then add its tools by
hand from **AI Tools → MCP Models → MCP Tools → Add**. Everything else about the record works normally.

## Reading a registry from another app

This is what the app exists for. Both registries are plain Nautobot models, so another app
reads them through the ORM or the REST API.

### The AI registry

```python
from nautobot_ai_models.models import AIModel

# Every model on offer, with its provider and endpoint ready to read. Both flags, because a model
# on a disabled provider is not on offer however the model itself is flagged.
available = AIModel.objects.filter(
    enabled=True,
    provider__enabled=True,
).select_related("provider__external_integration")

# The same question about one record: ai_model.is_available.

# How to address each endpoint. Ollama is the case to notice: its OpenAI-compatibility layer does
# not return tool calls, so a client that read openai_compatible alone would lose tool calling.
for ai_model in available:
    print(ai_model.name, ai_model.provider.provider_type)

# The chat models and the embedding models, which are not interchangeable.
chat = available.filter(kind="chat")
embedding = available.filter(kind="embedding")

# The effective inference parameters, with the provider default filled in.
for ai_model in available:
    print(ai_model.name, ai_model.resolved_num_predict, ai_model.resolved_temperature)

# Everything else a request needs, checked against the allowlist as it is read.
for ai_model in available:
    print(ai_model.name, ai_model.resolved_parameters)

# What a million tokens cost. None means nobody recorded a price, not that it is free.
priced = available.exclude(input_cost_per_million=None)
```

### The MCP registry

```python
from nautobot_ai_models.models import MCPTool

# Every tool that is on offer, with its server and endpoint ready to read.
available = MCPTool.objects.filter(
    enabled=True,
    mcp_server__enabled=True,
).select_related("mcp_server__external_integration")

# The read-only subset, for a caller that runs without approval.
read_only = available.filter(writable=False)
```

Build the connection from the server's integration. Render the templated fields rather than reading
them raw, because all three support Jinja2:

```python
integration = tool.mcp_server.external_integration
url = integration.render_remote_url({"obj": tool.mcp_server})
headers = integration.render_headers({"obj": tool.mcp_server})
```

### Notice that a tool's contract changed

`definition_fingerprint` is a digest of the tool's title, description, and both schemas. Record it
alongside whatever approval you granted. When it differs from the current value, the server changed
what the tool is after somebody reviewed it, and the review is stale.
