# Upgrading the App

This page gives the steps to upgrade the app in your Nautobot environment.

## Upgrade Guide

A new release can change the data models of this app. Such a change needs a database migration.

1. Update the `nautobot-ai-models` package with `pip`.
2. Run `nautobot-server post-upgrade` in the runtime environment of your Nautobot installation.
3. Restart the Nautobot services.
