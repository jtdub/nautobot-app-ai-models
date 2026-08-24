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

AI Models turns Nautobot into the source of truth for your LLM estate. It records which
providers exist, how to reach each one, and which models each provider offers. Access control,
change logging, custom fields, and the REST API all come from Nautobot.

The app is a data catalog. It contains no AI or LLM client code and performs no inference.
Another app, a Job, or an external system reads these records and does the work. That keeps the
question of *what is available and allowed* separate from the question of *how to call it*.

The app never stores a URL or a credential of its own. Each **AI Provider** points at a Nautobot
External Integration, which supplies the remote URL, HTTP headers, SSL verification, CA file
path, timeout, and Secrets Group. Each **AI Model** belongs to a provider and carries a name, a
description, an enabled flag, and optional `num_predict` and `temperature` overrides that fall
back to the provider default. A **Discover AI Models** Job reads `GET /v1/models` from every
OpenAI-compatible provider and keeps the model list current. It creates and updates records, and
never deletes one.

### Screenshots

The AI Providers list. Each provider points at an External Integration, and the OpenAI-compatible
column tells you whether the discovery job can read its model catalog.

![AI Providers list](https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/ai-providers-list-light.png)

The provider detail view lists every model the provider offers.

![AI Provider detail](https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/ai-provider-detail-light.png)

The **Discover AI Models** job reads `GET /v1/models` and records what it finds. It never deletes a
record.

![Discovery job result](https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/ai-discovery-job-result-light.png)

If the External Integration you need does not exist yet, create it from a modal without leaving the
provider form.

![Create an External Integration from a modal](https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/embedded-create-modal-light.png)

The MCP Servers list, and one server showing what it advertised.

![MCP Servers list](https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/mcp-servers-list-light.png)

![MCP Server detail](https://raw.githubusercontent.com/jtdub/nautobot-app-ai-models/develop/docs/images/mcp-server-detail-light.png)

More screenshots can be found in the [Using the App](https://nautobot-ai-models.readthedocs.io/en/latest/user/app_use_cases/) page in the documentation.

## Documentation

Full documentation for this App can be found on [Read the Docs](https://nautobot-ai-models.readthedocs.io/en/latest/):

- [User Guide](https://nautobot-ai-models.readthedocs.io/en/latest/user/app_overview/) - Overview, Using the App, Getting Started.
- [Administrator Guide](https://nautobot-ai-models.readthedocs.io/en/latest/admin/install/) - How to Install, Configure, Upgrade, or Uninstall the App.
- [Developer Guide](https://nautobot-ai-models.readthedocs.io/en/latest/dev/contributing/) - Extending the App, Code Reference, Contribution Guide.
- [Release Notes / Changelog](https://nautobot-ai-models.readthedocs.io/en/latest/admin/release_notes/).
- [Frequently Asked Questions](https://nautobot-ai-models.readthedocs.io/en/latest/user/faq/).

### Contributing to the Documentation

You can find all the Markdown source for the App documentation under the [`docs`](https://github.com/jtdub/nautobot-app-ai-models/tree/develop/docs) folder in this repository. For simple edits, a Markdown capable editor is sufficient: clone the repository and edit away.

If you need to view the fully-generated documentation site, you can build it with [MkDocs](https://www.mkdocs.org/). A container hosting the documentation can be started using the `invoke` commands (details in the [Development Environment Guide](https://nautobot-ai-models.readthedocs.io/en/latest/dev/dev_environment/#docker-development-environment)) on [http://localhost:8001](http://localhost:8001). Using this container, as your changes to the documentation are saved, they will be automatically rebuilt and any pages currently being viewed will be reloaded in your browser.

Any PRs with fixes or improvements are very welcome!

## Questions

For any questions or comments, please check the [FAQ](https://nautobot-ai-models.readthedocs.io/en/latest/user/faq/) first. Feel free to also swing by the [Network to Code Slack](https://networktocode.slack.com/) (channel `#nautobot`), sign up [here](http://slack.networktocode.com/) if you don't have an account.
