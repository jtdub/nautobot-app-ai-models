# v1.0 Release Notes

This document describes all new features and changes in the release. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release Overview

- First release of the AI Models app.
- Adds two registries under one shared **AI Tools** navigation tab. Neither performs inference
  and neither calls a tool; both record what exists so that other apps read one place.
- Adds the AI Provider and AI Model data models, which catalog LLM endpoints, the models each
  one offers, and what a million tokens cost.
- Adds the MCP Server and MCP Tool data models, which catalog MCP servers and what each one
  advertises.
- Adds two read-only discovery Jobs: **Discover AI Models** and **MCP Server Discovery**.
  Neither deletes a record, and neither grants anything.
- No model stores a URL, a header, or a credential. Each points at a Nautobot External
  Integration, and the credential comes from that integration's Secrets Group at the point of
  use.
- Requires Nautobot 3.1.0 or newer, and Python 3.10 or newer.

<!-- towncrier release notes start -->

## [v1.0.0 (2026-08-23)](https://github.com/jtdub/nautobot-app-ai-models/releases/tag/v1.0.0)

### Added

- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added the AIProvider model, which records a remote LLM endpoint and references a Nautobot External Integration for its URL, headers, TLS settings, timeout, and credentials. It is named AIProvider rather than Provider so that it does not overlap with circuits.Provider in Nautobot core.
- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added the AIModel model, which records a single model offered by an AIProvider, with an enabled flag, optional num_predict and temperature overrides that fall back to the provider default, and the input and output token prices per million.
- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added the MCP Server model, which records an MCP server, its transport, and everything the server reported about itself on the last discovery run.
- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added the MCP Tool model, which records one tool a server advertises, both advertised JSON Schemas, a fingerprint of its contract, and the enabled and writable flags a person owns.
- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added UI list, detail, edit, and bulk views, filtersets, forms, and tables for all four models.
- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added a shared top-level "AI Tools" navigation tab holding an "AI Models" group and an "MCP Models" group, so that other AI-related apps can add their own groups beside them.
- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added REST API endpoints at /api/plugins/ai-models/ for ai-providers, ai-models, mcp-servers, and mcp-tools.
- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added the Discover AI Models Job, which reads GET /v1/models from each OpenAI-compatible provider and creates or updates AI Model records without ever deleting one.
- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added the MCP Server Discovery Job, which reads each MCP server's advertised capabilities and tool list. It never enables a tool and never sets writable.
- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added an optional "discovery" extra that brings the MCP client library. Every part of the app except the MCP Server Discovery job works without it.
- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added credential-safe outbound behaviour to both discovery jobs: a failure is reported by exception type only, so a remote URL carrying a credential cannot reach a job log, and neither job follows a redirect to another origin while holding an External Integration's headers.

### Documentation

- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added documentation screenshots for both registries, captured in the light and dark themes: the AI Providers and AI Models lists, the AI Provider detail view, the add form, the embedded External Integration modal, the discovery job result, the MCP Servers and MCP Tools lists, the MCP Server and MCP Tool detail views, and the AI Tools navigation tab.
- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added development/bin/take_screenshots.py, a Playwright script that recaptures every documentation screenshot from a running development instance.
- [#1](https://github.com/jtdub/nautobot-app-ai-models/pull/1) - Added a guide for other AI apps on joining the shared "AI Tools" navigation tab.
