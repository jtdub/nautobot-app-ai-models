# v1.1 Release Notes

This document describes all new features and changes in the release. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release Overview

This release closes the gaps that a consuming app hit when it read this registry and made the calls
itself. Before it, such an app had to keep facts in its own settings that belong in the catalog.

After it, an app reads one AI Provider record and one AI Model record, and learns four things: how
to address the endpoint, what the model is for, whether the model is in service, and which
parameters to send.

### What is new

- **AI Provider** records the API dialect of an endpoint, in `provider_type`. `openai_compatible`
  keeps its meaning and answers a different question: whether this app can discover models there.
  Ollama needs both fields, because its compatibility layer gives `GET /v1/models` and still does
  not return tool calls.
- **AI Provider** has an `enabled` flag. An operator takes a whole provider out of service in one
  click. Before, the operator disabled each model, and the discovery job undid that on its next run.
- **AI Model** records a `kind` of `chat` or `embedding`. The two are not interchangeable, so this
  app now refuses a wrong configuration before any network traffic.
- **AI Model** carries the rest of a request in `default_parameters`, behind an allowlist that the
  app checks on save and again on read.
- **MCP tool discovery** takes two optional settings. `new_tools_enabled` makes a new tool arrive
  switched off. `disable_on_definition_change` switches a tool off when its contract moves after a
  review.

### Compatibility

Nothing changes. This release supports Nautobot 3.1.0 and later, as 1.0 does. It adds no dependency.

### What an upgrade does

The migration adds four columns and fills them in.

Each AI Model becomes a `chat` model with no default parameters, which is what each record already
meant. Each AI Provider becomes enabled.

`provider_type` is the one field that needs an operator. The migration answers for one case only. A
provider that was OpenAI-compatible and has a remote URL becomes `openai_compatible`. The migration
leaves each other provider empty, because the old boolean says nothing about what such an endpoint
speaks instead.

The app refuses an empty value on save, and the form offers an empty option for such a record. Thus
no save can write a dialect that nobody chose.

After the upgrade, do two things. Set the dialect on each provider that the migration left empty.
Set the `kind` of each embedding model.

<!-- towncrier release notes start -->

## [v1.1.0 (2026-09-02)](https://github.com/jtdub/nautobot-app-ai-models/releases/tag/v1.1.0)

### Security

- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - A Job tool now checks the `extras.run_job` permission, the enabled flag, and the approval workflow on every call. It checked none of them before.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - `new_tools_enabled` now governs AI Tools too. A newly found Python tool arrives switched off where you set it.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - An AI Tool record stores a name, never a Python import path. Nothing imports a module that a database row named.

### Added

- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Added an Agents section under AI Tools, where you build an agent from a model, a system prompt, and the tools it may call.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Added AI Tools from Git repositories. A repository supplies tools the same way it supplies Jobs.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Added a Nautobot Job as a tool. An agent starts the Job and reports the Job Result at once. It never waits.

### Changed

- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - The app builds an agent and stops. It opens no socket, writes no row, and calls no model. Your own app runs it.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - The Sync AI Tools Job now leaves a tool that a Git repository supplied to the repository sync.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - A repository sync no longer fails when a tool registers again under the same name.

### Fixed

- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Removed the AI Tool and AI Agent Thread add pages. Neither model is created by hand, and the thread page raised an error.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Kept the AI Tool edit page, which is where you turn a discovered tool on.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Removed `trim_thread`. It raised a database error against a real checkpointer schema, so no deployment could trim a thread.

### Dependencies

- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Added the `agents` extra: langchain, langgraph, and the three provider packages. A deployment that only catalogs models installs none of it.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Added a separate `checkpointer` extra. It is absent from `agents` and from `all` on purpose.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - WARNING: `checkpointer` installs psycopg 3. That changes the database driver of the deployment and deadlocks change logging. Read the AI Agent Thread page first.

### Documentation

- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Added seven model pages under Data Models.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Added a user guide for Git-sourced tools: the repository layout, the required root `__init__.py`, and what each sync does to a record.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Corrected the group-weight table in the app extension guide. A sibling app now takes weight 400 or higher.

### Housekeeping

- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Added a `checkpoint_retention_days` setting, which defaults to 30 days.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Added a Prune Agent Threads Job. Nothing else deletes the conversation state an agent leaves behind.
- [#9](https://github.com/jtdub/nautobot-app-ai-models/issues/9) - Added a Sync AI Tools Job. It reports a tool that is no longer registered, and never deletes the record.

## [v1.1.0 (2026-08-27)](https://github.com/jtdub/nautobot-app-ai-models/releases/tag/v1.1.0)

### Added

- [#2](https://github.com/jtdub/nautobot-app-ai-models/issues/2) - Added `AIProvider.provider_type`, which records the API dialect of an endpoint: OpenAI, Anthropic, OpenAI-compatible, or Ollama. A consuming app reads this field to find out how to address the provider. `openai_compatible` keeps its meaning and answers a different question: whether this app can discover models at the endpoint. Ollama shows why both are necessary. Its OpenAI-compatibility layer gives `GET /v1/models`, but it does not return tool calls in the `tool_calls` field.
- [#2](https://github.com/jtdub/nautobot-app-ai-models/issues/2) - Added validation that refuses an OpenAI-compatible or Ollama provider whose External Integration has no remote URL. Those two types are an address, not a service. A client with no URL for one of them goes to a default endpoint that belongs to another company.
- [#2](https://github.com/jtdub/nautobot-app-ai-models/issues/2) - Added a data migration that fills `provider_type` in from `openai_compatible`. A provider that gave the OpenAI shape becomes `openai_compatible`, but only when its External Integration carries a remote URL, because that dialect needs one. Each other provider is left empty, because the boolean says nothing about what such an endpoint speaks instead. An operator must then answer the next time the record is saved. The form shows an empty option for such a record, so no save can write a dialect that nobody chose.
- [#3](https://github.com/jtdub/nautobot-app-ai-models/issues/3) - Added `AIModel.kind`, which records whether a model is for chat or for embedding. A chat model and an embedding model are not interchangeable and are not the same endpoint. This app now refuses a retrieval feature that is configured with a chat model, before any network traffic, in place of a confusing provider-side error later. The default is `chat`, so each record that existed before keeps its meaning. The Discover AI Models job leaves the field at its default, because `GET /v1/models` has no field that says which kind a model is.
- [#4](https://github.com/jtdub/nautobot-app-ai-models/issues/4) - Added `AIProvider.enabled`, which matches `AIModel.enabled` and `MCPServer.enabled`. An operator can now take a whole provider out of service. Before, the operator had to disable each model one at a time, or delete the provider, which also deleted each model record and its cost data.
- [#4](https://github.com/jtdub/nautobot-app-ai-models/issues/4) - Added the `AIModel.is_available` property, and gave it on the REST API. It is true only when the model and its provider are both enabled, so a consuming app asks one question in place of two. Added an `AIModel` filter named `provider_enabled`, which asks the same question over the API, because a read-only field cannot be a filter.
- [#4](https://github.com/jtdub/nautobot-app-ai-models/issues/4) - Changed the Discover AI Models job to skip a disabled provider. This applies both when an operator names that provider directly and when the job runs against every provider. A provider that an operator takes out of service no longer comes back on the next discovery run.
- [#5](https://github.com/jtdub/nautobot-app-ai-models/issues/5) - Added `AIModel.default_parameters`, a JSON object of extra request parameters to send with each call to a model. It holds what the two existing columns do not: `seed` for a run that must repeat, `reasoning_effort` for a reasoning model, `top_k` and `top_p` for a local model, `extra_body` for a parameter that a unified client has no name for, and the two repetition penalties.
- [#5](https://github.com/jtdub/nautobot-app-ai-models/issues/5) - Added an allowlist for those keys. The app checks it when it saves a record and again when it reads the parameters. It is an allowlist and not a denylist, because the keyword surface of a unified LLM client is wide and it moves between releases. A denylist would fail open on a key that nobody examined, and one such key would let an operator who holds only `change_aimodel` send a call, and the credential of the provider, to a host of their choice.
- [#5](https://github.com/jtdub/nautobot-app-ai-models/issues/5) - Added the `AIModel.resolved_parameters` property, and gave it on the REST API. It applies the allowlist a second time and adds the resolved temperature as a float, so a consuming app has one dictionary to build a request from. You can set `temperature` in the column or in the parameters. The column wins, then the parameters, then the provider default. `resolved_temperature` gives the same answer.
- [#6](https://github.com/jtdub/nautobot-app-ai-models/issues/6) - Added two optional `PLUGINS_CONFIG` settings for MCP tool discovery. Both defaults keep the behavior that an existing deployment already has.
- [#6](https://github.com/jtdub/nautobot-app-ai-models/issues/6) - Added `new_tools_enabled`, with the default `True`. Set it to `False`, and a newly discovered tool arrives with `enabled` clear. A server that advertises forty tools then does not put forty tools on offer before a person reads one description. `writable` and `enabled` answer different questions: `writable` says that a tool needs a review before each call, and `enabled` says that the tool is on offer at all.
- [#6](https://github.com/jtdub/nautobot-app-ai-models/issues/6) - Added `disable_on_definition_change`, with the default `False`. Set it to `True`, and discovery clears `enabled` on a tool whose definition fingerprint moved after a review. The tool keeps its row, its schemas, and its review history, and one click puts it back. The job log names such a tool separately from a tool that only changed.
