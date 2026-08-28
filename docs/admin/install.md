# Installing the App in Nautobot

Here you will find detailed instructions on how to **install** and **configure** the App within your Nautobot environment.

## Prerequisites

- The app is compatible with Nautobot 3.1.0 and higher.
- Databases supported: PostgreSQL, MySQL

!!! note
    Please check the [dedicated page](compatibility_matrix.md) for a full compatibility matrix and the deprecation policy.

### Access Requirements

The app itself needs no external access. The **Discover AI Models** Job needs outbound HTTPS
access from the Nautobot worker to each provider endpoint you configure. The endpoint must
serve `GET /v1/models`.

## Install Guide

!!! note
    Apps can be installed from the [Python Package Index](https://pypi.org/) or locally. See the [Nautobot documentation](https://docs.nautobot.com/projects/core/en/stable/user-guide/administration/installation/app-install/) for more details. The pip package name for this app is [`nautobot-ai-models`](https://pypi.org/project/nautobot-ai-models/).

The app is available as a Python package via PyPI and can be installed with `pip`:

```shell
pip install nautobot-ai-models
```

To ensure AI Models is automatically re-installed during future upgrades, create a file named `local_requirements.txt` (if not already existing) in the Nautobot root directory (alongside `requirements.txt`) and list the `nautobot-ai-models` package:

```shell
echo nautobot-ai-models >> local_requirements.txt
```

Once installed, the app needs to be enabled in your Nautobot configuration. The following block of code below shows the additional configuration required to be added to your `nautobot_config.py` file:

- Append `"nautobot_ai_models"` to the `PLUGINS` list.
- Append the `"nautobot_ai_models"` dictionary to the `PLUGINS_CONFIG` dictionary and override any defaults.

```python
# In your nautobot_config.py
PLUGINS = ["nautobot_ai_models"]

# PLUGINS_CONFIG = {
#   "nautobot_ai_models": {
#     ADD YOUR SETTINGS HERE
#   }
# }
```

Once the Nautobot configuration is updated, run the Post Upgrade command (`nautobot-server post_upgrade`) to run migrations and clear any cache:

```shell
nautobot-server post_upgrade
```

Then restart (if necessary) the Nautobot services which may include:

- Nautobot
- Nautobot Workers
- Nautobot Scheduler

```shell
sudo systemctl restart nautobot nautobot-worker nautobot-scheduler
```

## App Configuration

This app requires no settings. Add it to `PLUGINS` and leave `PLUGINS_CONFIG` empty:

```python
PLUGINS = ["nautobot_ai_models"]

PLUGINS_CONFIG = {
    "nautobot_ai_models": {},
}
```

You configure a provider endpoint through a Nautobot External Integration, not through a
setting. See [External Interactions](../user/external_interactions.md).

### Optional settings

Two optional settings change what an MCP Server Discovery run puts on offer. Both default to the
behaviour an existing deployment already has, so neither has to be set.

| Setting | Default | What it does |
| --- | --- | --- |
| `new_tools_enabled` | `True` | Whether a newly discovered MCP tool arrives switched on. Set it to `False` and a tool arrives with `enabled` cleared, and a person turns it on. |
| `disable_on_definition_change` | `False` | Whether discovery clears `enabled` on a tool whose definition changed since it was last read. Set it to `True` and such a tool comes back off, keeping its schemas and its review history. |

```python
PLUGINS_CONFIG = {
    "nautobot_ai_models": {
        "new_tools_enabled": False,
        "disable_on_definition_change": True,
    },
}
```

Both are registry policy rather than call policy, which is why they live here. A consuming app can
refuse to call a tool, but it cannot stop a second consuming app from calling the same one.

Set `new_tools_enabled` to `False` when registering a server that advertises many tools. Otherwise
every one of them is on offer to every consuming app before a person has read a single description,
and in an agent's prompt a tool's description **is** its semantics.

Set `disable_on_definition_change` to `True` when a tool's contract moving is something you want
acted on rather than reported. See [MCP Tool](../models/mcptool.md#discovery-policy).
