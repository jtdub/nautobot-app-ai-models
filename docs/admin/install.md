# Installing the App in Nautobot

This page tells you how to **install** and **configure** the app in your Nautobot environment.

## Prerequisites

- The app works with Nautobot 3.1.0 and later.
- Supported databases: PostgreSQL, MySQL.

!!! note
    For the full compatibility matrix and the deprecation policy, read the
    [dedicated page](compatibility_matrix.md).

### Access Requirements

The app needs no external access. The **Discover AI Models** Job needs outbound HTTPS access from
the Nautobot worker to each provider endpoint that you configure. The endpoint must give
`GET /v1/models`.

The **MCP Server Discovery** Job needs outbound HTTPS access to each MCP server that you register.

## Install Guide

!!! note
    You can install an app from the [Python Package Index](https://pypi.org/) or from a local
    file. For more information, read the
    [Nautobot documentation](https://docs.nautobot.com/projects/core/en/stable/user-guide/administration/installation/app-install/).
    The pip package name for this app is
    [`nautobot-ai-models`](https://pypi.org/project/nautobot-ai-models/).

The app is a Python package on PyPI. Install it with `pip`:

```shell
pip install nautobot-ai-models
```

To install the app again on each future upgrade, list the package in `local_requirements.txt` in
the Nautobot root directory, beside `requirements.txt`. Create the file if it does not exist:

```shell
echo nautobot-ai-models >> local_requirements.txt
```

Next, enable the app in your Nautobot configuration. Make these two changes in `nautobot_config.py`:

- Add `"nautobot_ai_models"` to the `PLUGINS` list.
- Add a `"nautobot_ai_models"` dictionary to `PLUGINS_CONFIG` if you want to change a default.

```python
PLUGINS = ["nautobot_ai_models"]

PLUGINS_CONFIG = {
    "nautobot_ai_models": {},
}
```

Then run the post-upgrade command. It applies the migrations and clears the cache:

```shell
nautobot-server post_upgrade
```

Then restart the Nautobot services. These can include:

- Nautobot
- Nautobot Workers
- Nautobot Scheduler

```shell
sudo systemctl restart nautobot nautobot-worker nautobot-scheduler
```

## App Configuration

The app needs no settings. Add it to `PLUGINS` and leave its `PLUGINS_CONFIG` entry empty.

Configure a provider endpoint through a Nautobot External Integration, not through a setting. See
[External Interactions](../user/external_interactions.md).

### Optional settings

Two optional settings change what an MCP Server Discovery run puts on offer. Both defaults keep the
behavior of an existing deployment, so you do not have to set either one.

| Setting | Default | What it does |
| --- | --- | --- |
| `new_tools_enabled` | `True` | Whether a newly discovered MCP tool arrives switched on. Set it to `False`, and a tool arrives with `enabled` clear. A person then turns the tool on. |
| `disable_on_definition_change` | `False` | Whether discovery clears `enabled` on a tool whose definition changed since the last read. Set it to `True`, and such a tool comes back off. It keeps its schemas and its review history. |

```python
PLUGINS_CONFIG = {
    "nautobot_ai_models": {
        "new_tools_enabled": False,
        "disable_on_definition_change": True,
    },
}
```

Both settings are registry policy, not call policy. That is why they live here. A consuming app can
refuse to call a tool, but it cannot stop a second consuming app from calling the same tool.

WARNING: A server that advertises forty tools puts forty tools on offer to each consuming app,
before a person reads one description. In the prompt of an agent, the description of a tool is its
meaning. Set `new_tools_enabled` to `False` before you register such a server.

Set `disable_on_definition_change` to `True` if you want the app to act on a change of contract
instead of only reporting it. See [MCP Tool](../models/mcptool.md#discovery-policy).
