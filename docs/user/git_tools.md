# Tools from a Git Repository

An agent can call a Python function that lives in a Git repository instead of in an installed app.
Nautobot clones the repository, this app imports the tools in it, and each one becomes an
[AI Tool](../models/aitool.md) record of kind `git`.

This is the same mechanism Nautobot uses for Git-sourced Jobs. The same directory convention, the
same private import, and the same trust boundary.

WARNING: Code in the repository runs inside Nautobot, with the permissions of the process that runs
it. Only give this content type to a repository you control. A user who may add a Git repository
can already add a Job the same way; this adds no new trust, but it adds no less either.

## The repository layout

```text
my-tools-repo/
├── __init__.py          # required, and empty is fine
└── ai_tools.py          # or an ai_tools/ package with its own __init__.py
```

The root `__init__.py` is required. Without it Python does not treat the clone as a package, and
nothing in it is found.

## Declare a tool

```python
# ai_tools.py
from nautobot_ai_models.tools import register_ai_tool


@register_ai_tool(writable=False)
def site_device_count(site: str) -> str:
    """Count the devices at one site. Send the site name."""
    from nautobot.dcim.models import Device

    return f"{Device.objects.filter(location__name=site).count()} devices at {site}"
```

The name comes from the function. The description comes from the docstring, and the model reads it
to decide whether to call the tool. The argument schema comes from the type hints.

Pass `writable=True` when calling the function changes something. There is no default.

## Add the repository

1. Go to **Extensibility > Git Repositories** and add a repository.
2. Tick **AI tools** under *Provides*.
3. Save. Nautobot clones the repository and runs the sync.

Each sync reports what it did in the Job Result, under the grouping `ai tools`.

## What a sync does

| The repository | The record |
| --- | --- |
| Declares a new tool | A record arrives, enabled or disabled as `new_tools_enabled` says |
| Reworded a description | The digest changes, and the record is disabled if `disable_on_definition_change` is on |
| Dropped a tool | The record is reported and kept |
| Stopped providing AI tools | Every record from it is disabled and kept |
| Is deleted | Its records go with it |

A record is never deleted by a sync. Its name may still be on an approved call, and an agent bound
to it protects it: a repository whose tools are in use refuses to be deleted at all.

## Two things worth knowing

**Every process imports the code it needs, when it needs it.** The registry lives in one process.
The worker that ran the sync holds the repository's tools; a different worker holds nothing. So the
agent builder imports the repository on the first miss, from the repository the record names. A
record names a repository and the fixed `ai_tools` module inside it. It never names an import path.

**Turning a tool on is a separate decision.** Set `new_tools_enabled` to `False` and a synced tool
arrives disabled. Somebody then reads what the repository declared, sets `writable` from what the
code actually does, and enables it. That review is the point of the setting.

```python
PLUGINS_CONFIG = {
    "nautobot_ai_models": {
        "new_tools_enabled": False,
        "disable_on_definition_change": True,
    },
}
```
