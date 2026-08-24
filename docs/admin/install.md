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
