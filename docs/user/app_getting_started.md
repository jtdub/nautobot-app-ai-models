# Getting Started with the App

This document is a tutorial. It shows how to start the app and how to use it.

## Install the App

To install the app, obey the instructions in the [Installation Guide](../admin/install.md).

## First steps with the App

1. **Create an External Integration.** Go to **Extensibility → External Integrations → Add**. Set
   the **Name** and the **Remote URL** of your LLM endpoint, for example
   `https://ollama.example.com`. If the endpoint needs an API key, attach a Secrets Group.
2. **Create an AI Provider.** Go to **AI Tools → AI Models → AI Providers → Add**. Enter a name and
   select the External Integration from step 1. You can also skip step 1: use the **+** button
   beside the field to create the External Integration in a modal, without leaving this page.
3. **Set the Provider type.** This is the API dialect that a consuming app uses to address the
   endpoint. See [AI Provider](../models/aiprovider.md#provider-type-and-openai-compatible).

    ![Add an AI Provider](../images/ai-provider-add-form-light.png#only-light)
    ![Add an AI Provider](../images/ai-provider-add-form-dark.png#only-dark)

4. **Discover the models.** Go to **Jobs → AI Models → Discover AI Models** and run the job. The
   job reads the model catalog of the provider. It creates one AI Model record for each entry.
5. **Examine the result.** Open the detail page of the provider. The AI Models panel on the right
   lists what the job found.

    ![An AI Provider after discovery](../images/ai-provider-detail-light.png#only-light)
    ![An AI Provider after discovery](../images/ai-provider-detail-dark.png#only-dark)

## What are the next steps?

- Set the **Kind** of each model that does embedding. The job creates every model as `chat`,
  because the catalog endpoint does not say which is which.
- Clear the **Enabled** checkbox on each model that a consumer must not use.
- Set a default **num_predict** and **temperature** on the provider. Override either one on a
  single model that needs a different value.
- Put anything else that a call needs in **Default parameters** on the model.
- Schedule the **Discover AI Models** job, to keep the catalog current.
- Read the catalog from your own code or from the REST API. See
  [External Interactions](external_interactions.md).

## How to register an MCP server

The MCP registry works the same way.

1. Go to **AI Tools → MCP Models → MCP Servers → Add**. Give the server a name, select or create
   its External Integration, and select its transport.
2. Open the server and select **Run Discovery**. The job reads what the server advertises and
   records it.
3. Examine each new tool. A discovered tool arrives with `writable` set, because the app assumes
   that a tool writes until a person has read what it does.

The discovery job needs the optional `discovery` extra. See
[External Interactions](external_interactions.md).

For more examples, read the [Use Cases](app_use_cases.md) section.
