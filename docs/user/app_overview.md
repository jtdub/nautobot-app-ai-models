# App Overview

This document gives an overview of the app. It includes the important facts and the points to
consider before you apply the app to your Nautobot environment.

!!! note
    This documentation uses the terms "app" and "plugin" with the same meaning.

## Description

AI Models makes Nautobot the source of truth for your AI estate. It holds two registries.

The app is a catalog. It does no inference and it calls no tool. Another app, a Job, or an external
system reads these records and does the work.

There are four models, in two pairs:

- **AI Provider** — one remote LLM endpoint. It points at a Nautobot External Integration, which
  holds the URL, the headers, the TLS settings, the timeout, and the Secrets Group. The app keeps
  no credential of its own.
- **AI Model** — one model that a provider offers, with an enabled flag, a kind, and optional
  inference defaults.
- **MCP Server** — one MCP server. It points at its own External Integration and holds what the
  server reported about itself on the last discovery run.
- **MCP Tool** — one tool that a server advertises, with both advertised JSON Schemas, a
  fingerprint of its contract, and the two flags that a person owns: `enabled` and `writable`.

## Audience (User Personas) - Who must use this App?

- **Network automation engineers** who want one record, controlled by permissions, of the LLM
  endpoints, the models, the MCP servers, and the MCP tools that an automation platform can use.
- **Platform administrators** who must add, change, or retire an LLM endpoint without an edit to
  code or to an environment variable.
- **App developers** who want to read a provider, a model, or a tool from the ORM in place of a
  hardcoded endpoint.
- **Reviewers** who must see the claim of an MCP server about a tool beside the decision that a
  person made about it.

## Authors and Maintainers

- [@jtdub](https://github.com/jtdub)

## Nautobot Features Used

- **External Integrations** — each provider refers to one. It gives the remote URL, the HTTP
  headers, the SSL verification, the CA file path, the timeout, and the extra configuration.
- **Secrets and Secrets Groups** — the API key stays in a Nautobot Secret. The app reads it at the
  point of use.
- **Jobs** — the app installs two Jobs: **Discover AI Models** and **MCP Server Discovery**.
- **Change logging, custom fields, relationships, notes, and saved views** — the models come from
  `OrganizationalModel` and `PrimaryModel`.
- **Navigation** — the app adds a shared top-level **AI Tools** tab. Another AI app adds its own
  groups to the same tab. See [Extending the App](../dev/extending.md).

### Extras

- **Custom Fields** — the app creates none. Each model accepts custom fields.
- **Jobs** — **Discover AI Models** in the "AI Models" group, and **MCP Server Discovery** in the
  "MCP Models" group.
- **Tags** — only **MCP Server** has them. The other three are catalog records with no tags and no
  dynamic groups.
