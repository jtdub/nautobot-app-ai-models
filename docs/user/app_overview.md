# App Overview

This document provides an overview of the App including critical information and important considerations when applying it to your Nautobot environment.

!!! note
    Throughout this documentation, the terms "app" and "plugin" will be used interchangeably.

## Description

AI Models turns Nautobot into the source of truth for your AI estate. It holds two registries.

The app is a catalog. It performs no inference and calls no tool. Another app, a Job, or an
external system reads these records and does the work.

Four models, in two pairs:

- **AI Provider** — one remote LLM endpoint. It points at a Nautobot External Integration, which
  holds the URL, headers, TLS settings, timeout, and Secrets Group. The app stores no credential of
  its own.
- **AI Model** — one model offered by a provider, with an enabled flag and optional inference
  defaults.
- **MCP Server** — one MCP server, pointing at its own External Integration, plus everything the
  server reported about itself on the last discovery run.
- **MCP Tool** — one tool a server advertises, with both advertised JSON Schemas, a fingerprint of
  its contract, and the two flags a person owns: `enabled` and `writable`.

## Audience (User Personas) - Who should use this App?

- **Network automation engineers** who want a single, permission-controlled record of which LLM
  endpoints, models, MCP servers, and MCP tools an automation platform is allowed to use.
- **Platform administrators** who need to add, rotate, or retire an LLM endpoint without editing
  code or environment variables.
- **App developers** who want to read a provider, a model, or a tool from the ORM instead of
  hardcoding an endpoint.
- **Reviewers** who need to see what an MCP server claims about a tool beside what a person
  decided about it.

## Authors and Maintainers

- [@jtdub](https://github.com/jtdub)

## Nautobot Features Used

- **External Integrations** — every provider references one. It supplies the remote URL, HTTP
  headers, SSL verification, CA file path, timeout, and extra configuration.
- **Secrets and Secrets Groups** — the API key lives in a Nautobot Secret, read at the point of use.
- **Jobs** — the app installs two Jobs, **Discover AI Models** and **MCP Server Discovery**.
- **Change logging, custom fields, relationships, notes, and saved views** — both models derive from
  `OrganizationalModel`.
- **Navigation** — the app adds a shared top-level **AI Tools** tab. Other AI apps add their own
  groups to the same tab. See [Extending the App](../dev/extending.md).

### Extras

- **Custom Fields** — the app creates none. Every model accepts custom fields.
- **Jobs** — **Discover AI Models** in the "AI Models" group, and **MCP Server Discovery** in the
  "MCP Models" group.
- **Tags** — only **MCP Server** carries them. The other three are catalog records with no tags and
  no dynamic groups.
