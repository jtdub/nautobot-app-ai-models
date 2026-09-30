# AI Tool Approval

![The AI Tool Approvals list](../images/ai-tool-approvals-list-light.png#only-light)
![The AI Tool Approvals list](../images/ai-tool-approvals-list-dark.png#only-dark)

One record that a person accepted what an [AI Agent Tool](aiagenttool.md) binding offers, at the
digest it offered then.

The app records the decision. It enforces nothing, because it makes no calls. A consuming app reads
`AIAgentTool.is_approved` before it wires its own caller. Rule **G7** in `services/agents.py` says
the same thing about the gate.

## Why a log and not a flag

A flag on the binding answers "is this approved now" and forgets everything else. This model keeps
one row for each decision, so three questions stay answerable:

- Who accepted the definition that the tool advertises today.
- Who accepted the definition it advertised last month, before the server changed it.
- Who withdrew an approval, and when.

A row is written once and never rewritten. A withdrawal fills in `revoked_at`. Nothing deletes the
evidence that a review happened.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `binding` | AI Agent Tool | Yes | What was approved. Deleting the binding deletes its approvals. |
| `fingerprint` | String | Yes | The digest that was accepted. The app fills this in from the binding. |
| `approved_by` | User | No | Who accepted it. Empty once the account is gone. |
| `approved_by_name` | String | No | The name at the time. It survives a deleted account. |
| `approved_at` | Date and time | Yes | When. |
| `expires_at` | Date and time | No | When the approval has to be renewed. Empty never expires. |
| `revoked_at` | Date and time | No | When it was withdrawn. |
| `revoked_by` | User | No | Who withdrew it. |
| `revoked_by_name` | String | No | The name at the time. |
| `note` | Text | No | Why it was accepted, and why anyone withdrew it. |

You do not enter `fingerprint`, `approved_by`, or either name. The app writes them. A record whose
author chooses both the reviewer and the thing reviewed is not a record.

## Three questions the record answers

```python
approval.is_current
approval.is_expired
approval.is_active
```

`is_current` compares the approved digest against `binding.fingerprint`. `is_active` is the one a
consumer wants: not withdrawn, not expired, and still current.

## Reading it from the binding

```python
binding.approval
binding.is_approved
```

`approval` gives the newest active approval, or `None`. `is_approved` is the boolean. The REST API
returns `is_approved` on the AI Agent Tool as a read-only field.

CAUTION: Reading `is_approved` over a list walks the approvals of each row. Add
`prefetch_related("approvals")` to a queryset of your own. The app's own views and API already do.

## When an approval stops answering

The digest covers the effective definition: the name the model reads, the description it reads, and
the argument schema. Change any of the three and `fingerprint` moves, so every earlier approval
stops being current. This is the point. A description that a reviewer accepted is not the
description a rewritten tool advertises.

An override on the binding moves the digest as well. `name_override` and `description_override` are
what the model is told, so a change to either needs a new review.

See [AI Agent Tool](aiagenttool.md#four-values-the-model-actually-reads).
