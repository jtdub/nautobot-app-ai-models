# Getting Started with the App

This document provides a step-by-step tutorial on how to get the App going and how to use it.

## Install the App

To install the App, please follow the instructions detailed in the [Installation Guide](../admin/install.md).

## First steps with the App

1. **Create an External Integration.** Go to **Extensibility → External Integrations → Add**. Set
   the **Name** and the **Remote URL** of your LLM endpoint, for example
   `https://ollama.example.com`. Attach a Secrets Group if the endpoint needs an API key.
2. **Create an AI Provider.** Go to **AI Tools → AI Models → AI Providers → Add**. Enter a name and
   choose the External Integration you just made. You can also skip step 1 and use the **+** button
   beside the field to create the External Integration from a modal without leaving this page.

    ![Add an AI Provider](../images/provider-add-form.png)

3. **Discover the models.** Go to **Jobs → AI Models → Discover AI Models** and run it. The job
   reads the provider's model catalog and creates one AI Model record for each entry.
4. **Review the result.** Open the provider's detail page. The AI Models panel on the right lists
   everything the job found.

    ![AI Provider detail](../images/provider-detail.png)


## What are the next steps?

- Clear the **Enabled** checkbox on any model you do not want consumers to use.
- Set a default **num_predict** and **temperature** on the provider, and override either one on a
  single model where it needs to differ.
- Schedule the **Discover AI Models** job so the catalog stays current.
- Read the catalog from your own code or from the REST API. See
  [External Interactions](external_interactions.md).

You can check out the [Use Cases](app_use_cases.md) section for more examples.
