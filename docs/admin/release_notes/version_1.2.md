# v1.2 Release Notes

This document describes all new features and changes in the release. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release Overview

This release adds the agent half of the registry. Before it, the catalog held a provider, a model,
an MCP server, and an MCP tool. An app that wanted an agent wrote that agent in Python, and kept
the prompt and the tool list in its own code.

After it, an operator builds an agent in the user interface, from a model, a system prompt, and the
tools the agent may call. Your own app reads the record and gets a built agent back.

### This app builds an agent. It does not run one.

The app assembles an agent from rows and stops there. It opens no socket, writes no row, and calls
no model. Your own app runs what it gets. Read the AI Agent page before you build the first one.

### What is new

- **AI Agent** is a new section under AI Tools. One agent is a model, a system prompt, and the
  tools it may reach. The prompt is a column and the tool list is a table, so nothing about an
  agent is a constant in Python code.
- **AI Tool** records one callable tool by name. The record never stores a Python import path, so
  nothing imports a module that a database row named.
- **Git repositories** now supply AI Tools. A repository serves tools the same way it serves Jobs.
  Read the Tools from a Git Repository guide for the layout that a repository needs.
- **A Nautobot Job is a tool.** An agent starts the Job and reports the Job Result at once. It
  never waits for the Job to finish.
- **AI Agent Thread** gives one LangGraph conversation a handle that an operator can find. The
  **Prune Agent Threads** Job deletes a thread and its checkpoint rows together.

### Security

A Job tool now checks the `extras.run_job` permission, the enabled flag, and the approval workflow
on every call. It checked none of them before. Upgrade before you let an agent reach a Job.

The `new_tools_enabled` setting now governs AI Tools too. A newly found Python tool arrives
switched off where you set that flag.

### Compatibility

This release supports Nautobot 3.1.0 and later, as 1.1 does.

The agent features need the new `agents` extra: langchain, langgraph, and the three provider
packages. A deployment that only catalogs models installs none of it.

WARNING: The separate `checkpointer` extra installs psycopg 3. That changes the database driver of
the deployment and deadlocks change logging. It is absent from `agents` and from `all` on purpose.
Read the AI Agent Thread page before you install it.

### What an upgrade does

The migration adds the seven agent models. It changes no existing record, and it asks nothing of an
operator.

Set `checkpoint_retention_days` if 30 days is the wrong window for your deployment. Then schedule
the **Prune Agent Threads** Job, because nothing else deletes the conversation state that an agent
leaves behind.

<!-- towncrier release notes start -->

## [v1.2.0 (2026-09-02)](https://github.com/jtdub/nautobot-app-ai-models/releases/tag/v1.2.0)

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

