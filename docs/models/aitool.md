# AI Tool

One tool that an agent may call that did not come from an MCP server. A Python function that an app
registered in code, or a Nautobot Job.

This model has the same shape as [MCP Tool](mcptool.md), field for field where it can. The approval
gate of a consuming app asks three questions of every tool: is this offered, does it need a person,
and has its definition moved. A second tool source that could not answer them would walk past the
gate that MCP tools cannot.

## Records are written by a Job

Do not create a row by hand. A consuming app declares a tool in code:

```python
from nautobot_ai_models.tools import register_ai_tool


@register_ai_tool(writable=False)
def lookup_device(hostname: str) -> str:
    """Look up one device by hostname. Returns vendor, site, and platform."""
```

The **Sync AI Tools** Job then reads what the code declared and writes the record. The name comes
from the function. The description comes from the docstring. The argument schema comes from the
type hints.

A tool that a Git repository declares is written by the repository sync instead, and the Job leaves
it alone. Both write the record the same way.

The app refuses to save a row of kind `registered` whose name nothing registered. The row is a
claim that code exists under that name, and a claim with nothing behind it is refused.

NOTE: The registry stores a name. It never stores a Python import path, and it never imports a
module that a database row named.

There is no add view, no import view and no rename view in the user interface, because none of them
could write a usable row. The list and the detail page are read. The edit page offers the two flags
a person owns, `enabled` and `writable`, and nothing else - everything else is written by the Sync
AI Tools Job and would be overwritten on its next run.

A tool of kind `git` comes from a Git repository instead of an installed app. It is declared the
same way, in an `ai_tools` module that the repository carries, and the repository sync writes the
record. See [Tools from a Git Repository](../user/git_tools.md).

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | String | Yes | Unique. The name the tool is called by. |
| `description` | Text | No | What the model reads to decide whether to call this. |
| `argument_schema` | JSON | No | The parameters, as JSON Schema. |
| `kind` | Choice | Yes | `registered`, `git`, or `job`. |
| `module` | String | No | Where the callable was found. |
| `git_repository` | Git Repository | No | The repository the tool was synced from. |
| `job` | Job | No | The Job that a `job` tool starts. |
| `enabled` | Boolean | Yes | A disabled tool is not offered. |
| `writable` | Boolean | Yes | Whether calling this changes something. |
| `advertised_read_only` | Boolean | No | What the tool said about itself. |
| `definition_fingerprint` | String | No | A digest of the name, description, and schema. |
| `last_seen_at` | Datetime | No | When the Sync AI Tools Job last found this tool. |

## Two flags, not one

The same rule that [MCP Tool](mcptool.md) follows.

- **`writable`** is set by a person. It defaults to `True`. A wrong guess this way costs a review. A
  wrong guess the other way tells a consuming app that a tool is safe when it is not.
- **`advertised_read_only`** is what the decorator declared. The Sync AI Tools Job writes it on
  every run. It decides nothing.

## A Job tool starts a Job

WARNING: A Nautobot Job runs through Celery and produces a Job Result. A tool of kind `job` starts
the Job and returns immediately with the Job Result identifier and a link. It does not wait, and it
does not read the result. An agent loop is bounded, and a queue can outlast it.

The Job runs as the user that the consuming app named when it built the agent, and that user has
to be allowed to run it. `JobResult.enqueue_job` is the raw execution primitive and checks nothing,
so the tool checks before it calls: it refuses a Job that is disabled or not installed, a user
without `extras.run_job` on that Job, a Job that takes sensitive variables, and a Job with an
approval workflow. Each refusal is returned to the model as text, so the agent reports it rather
than failing.

WARNING: A model decides when to call a tool, and what a model reads can be written by somebody
else - a syslog line, a ticket, an answer from an MCP server. Binding a Job tool is therefore not
the same as an operator pressing Run. Bind only Jobs you would let that text start, and keep the
`extras.run_job` permission of the user the agent runs as as narrow as the work needs.

The Job cannot be changed on a tool once the record exists. Repointing it would change what an
approved tool does while its name and description, and so its digest, stayed put.
