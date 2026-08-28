# Uninstall the App from Nautobot

This page gives the steps to remove the app from your Nautobot environment.

## Database Cleanup

WARNING: This command deletes each AI Provider, AI Model, MCP Server, and MCP Tool record, together
with the cost data and the review decisions on them. Make a backup before you continue.

Before you remove the app from `nautobot_config.py`, run this command. It reverses each migration
of this app.

```shell
nautobot-server migrate nautobot_ai_models zero
```

## Remove the App configuration

Remove the entries that you added to `PLUGINS` and to `PLUGINS_CONFIG` in `nautobot_config.py`.

## Uninstall the package

```bash
pip3 uninstall nautobot-ai-models
```
