# App Overview

This document provides an overview of the App including critical information and important considerations when applying it to your Nautobot environment.

!!! note
    Throughout this documentation, the terms "app" and "plugin" will be used interchangeably.

## Description

AI Models turns Nautobot into the source of truth for your LLM estate. It records which providers
exist, how to reach each one, and which models each provider offers.

The app is a data catalog. It contains no AI or LLM client code and performs no inference. Another
app, a Job, or an external system reads these records and does the work.

Two models:

- **AI Provider** — one remote LLM endpoint. It points at a Nautobot External Integration, which
  holds the URL, headers, TLS settings, timeout, and Secrets Group. The app stores no credential of
  its own.
- **AI Model** — one model offered by a provider, with an enabled flag and optional inference
  defaults.

## Audience (User Personas) - Who should use this App?

- **Network automation engineers** who want a single, permission-controlled record of which LLM
  endpoints and models an automation platform is allowed to use.
- **Platform administrators** who need to add, rotate, or retire an LLM endpoint without editing
  code or environment variables.
- **App developers** who want to read a provider and a model from the ORM instead of hardcoding an
  endpoint.

## Authors and Maintainers

- [@jtdub](https://github.com/jtdub)

## Nautobot Features Used

- **External Integrations** — every provider references one. It supplies the remote URL, HTTP
  headers, SSL verification, CA file path, timeout, and extra configuration.
- **Secrets and Secrets Groups** — the API key lives in a Nautobot Secret, read at the point of use.
- **Jobs** — the app installs one Job, **Discover AI Models**.
- **Change logging, custom fields, relationships, notes, and saved views** — both models derive from
  `OrganizationalModel`.
- **Navigation** — the app adds a shared top-level **AI Tools** tab. Other AI apps add their own
  groups to the same tab. See [Extending the App](../dev/extending.md).

### Extras

- **Custom Fields** — the app creates none. Both models accept custom fields.
- **Jobs** — the app installs one Job, **Discover AI Models**, in the "AI Models" group.
- **Tags and Dynamic Groups** — neither model supports them. Both are catalog records.
