# AI Models

<p align="center">
  <img src="https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/icon-ai-models.png" class="logo" height="200px">
  <br>
  <a href="https://github.com/jtdub/nautobot-app-ai-models/actions"><img src="https://github.com/jtdub/nautobot-app-ai-models/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="https://nautobot-ai-models.readthedocs.io/en/latest/"><img src="https://readthedocs.org/projects/nautobot-ai-models/badge/"></a>
  <a href="https://pypi.org/project/nautobot-ai-models/"><img src="https://img.shields.io/pypi/v/nautobot-ai-models"></a>
  <a href="https://pypi.org/project/nautobot-ai-models/"><img src="https://img.shields.io/pypi/dm/nautobot-ai-models"></a>
  <br>
  An <a href="https://networktocode.com/nautobot-apps/">App</a> for <a href="https://nautobot.com/">Nautobot</a>.
</p>

## Overview

AI Models makes Nautobot the source of truth for your LLM estate. It records which providers
exist, how to reach each one, and which models each provider offers. Access control, change
logging, custom fields, and the REST API all come from Nautobot.

The app is a data catalog. It has no AI or LLM client code and it does no inference. Another app, a
Job, or an external system reads these records and does the work. This keeps the question *what is
available and allowed* apart from the question *how do I call it*.

The app keeps no URL and no credential of its own. Each **AI Provider** points at a Nautobot
External Integration. That integration gives the remote URL, the HTTP headers, the SSL
verification, the CA file path, the timeout, and the Secrets Group. A provider also records its
API dialect, so that a consuming app knows how to address the endpoint.

Each **AI Model** belongs to a provider. It carries a name, a description, and a kind of `chat` or
`embedding`. It also carries an enabled flag, the cost of a million tokens, and the parameters to
send with a call. `num_predict` and `temperature` fall back to the provider default.

The **Discover AI Models** Job reads `GET /v1/models` from each enabled, OpenAI-compatible provider
and keeps the model list current. It creates and updates records. It never deletes one.

A second pair of models does the same for MCP. An **MCP Server** records one server and what it
reported about itself. An **MCP Tool** records one tool that a server advertises, with both
advertised JSON Schemas and the two flags that a person owns.

### Screenshots

The AI Providers list. Each provider points at an External Integration. The Provider Type column
says how a consuming app addresses the endpoint.

![AI Providers list](https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/ai-providers-list-light.png)

The provider detail view lists each model that the provider offers.

![AI Provider detail](https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/ai-provider-detail-light.png)

The **Discover AI Models** job reads `GET /v1/models` and records what it finds. It never deletes a
record.

![Discovery job result](https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/ai-discovery-job-result-light.png)

If the External Integration that you need does not exist, create it in a modal. You do not leave
the provider form.

![Create an External Integration from a modal](https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/embedded-create-modal-light.png)

The MCP Servers list, and one server with what it advertised.

![MCP Servers list](https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/mcp-servers-list-light.png)

![MCP Server detail](https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/mcp-server-detail-light.png)

For more screenshots, read the [Using the App](https://nautobot-ai-models.readthedocs.io/en/latest/user/app_use_cases/) page.

## Documentation

The full documentation for this app is on [Read the Docs](https://nautobot-ai-models.readthedocs.io/en/latest/):

- [User Guide](https://nautobot-ai-models.readthedocs.io/en/latest/user/app_overview/) - Overview, Using the App, Getting Started.
- [Administrator Guide](https://nautobot-ai-models.readthedocs.io/en/latest/admin/install/) - How to Install, Configure, Upgrade, or Uninstall the App.
- [Developer Guide](https://nautobot-ai-models.readthedocs.io/en/latest/dev/contributing/) - Extending the App, Code Reference, Contribution Guide.
- [Release Notes / Changelog](https://nautobot-ai-models.readthedocs.io/en/latest/admin/release_notes/).
- [Frequently Asked Questions](https://nautobot-ai-models.readthedocs.io/en/latest/user/faq/).

### Contributing to the Documentation

The Markdown source of the documentation is in the [`docs`](https://github.com/jtdub/nautobot-app-ai-models/tree/develop/docs) folder of this repository. For a simple edit, a Markdown editor is enough. Clone the repository and make the change.

To see the generated documentation site, build it with [MkDocs](https://www.mkdocs.org/). The `invoke` commands start a container that hosts the documentation on [http://localhost:8001](http://localhost:8001). The [Development Environment Guide](https://nautobot-ai-models.readthedocs.io/en/latest/dev/dev_environment/#docker-development-environment) gives the details. The container rebuilds a page when you save a change, and your browser reloads it.

Pull requests with fixes or improvements are welcome.

## Questions

For a question or a comment, read the [FAQ](https://nautobot-ai-models.readthedocs.io/en/latest/user/faq/) first. You can also use the [Network to Code Slack](https://networktocode.slack.com/), in the `#nautobot` channel. If you have no account, sign up [here](http://slack.networktocode.com/).
