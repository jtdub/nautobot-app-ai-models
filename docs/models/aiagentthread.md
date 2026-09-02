# AI Agent Thread

One LangGraph conversation, and where it got to.

This record is a handle. It is not the state. The checkpointer of LangGraph holds the state, in
tables that it creates and owns.

## Why the record exists

A checkpointer keeps every step of the state of one thread. That is what makes a run resumable,
replayable, and interruptible. Three facts make a Nautobot record necessary beside it:

- The saver creates its own tables. Django does not migrate them. No model describes them, and no
  foreign key points at them.
- Nothing cascades between them. The rows of one thread live in more than one table.
- Every shipped saver raises `NotImplementedError` from `prune`. Only `delete_thread` works.

So this record gives a thread a handle that an operator can find, an agent to attribute it to, and
something for the **Prune Agent Threads** Job to work from.

## The user interface reads and deletes

Whatever ran the agent writes this record. There is no add view, no edit view and no bulk edit,
because there is no form behind them. The list page, the detail page, the change log and the notes
are read. Deleting a thread is the only change a person makes.

CAUTION: Deleting a thread record leaves its checkpoint rows behind. Run the **Prune Agent
Threads** Job, which deletes both.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `agent` | AI Agent | Yes | The agent that ran. |
| `thread_id` | UUID | Yes | The `thread_id` that LangGraph checkpoints under. |
| `status` | Choice | Yes | `running`, `waiting`, `completed`, or `failed`. |
| `interrupt_payload` | JSON | No | What the graph asked when it paused. |
| `started_at` | Datetime | Yes | |
| `finished_at` | Datetime | No | |

The `thread_id` is a UUID because the column of the checkpointer is capped at 255 characters, and
the documentation asks for a deterministic identifier.

## Waiting means a person

A status of `waiting` is an interrupt. The graph paused inside a node, the checkpointer holds
everything, and a person has to answer before the run goes on. Filter on this status to find every
decision that nobody has made.

## The checkpointer needs a driver this app does not install

`langgraph-checkpoint-postgres` uses psycopg 3. Nautobot uses psycopg2, which is a different
package. Without psycopg 3 the saver imports and then fails with `no pq wrapper available`.

The `agents` extra does **not** install it, and that is deliberate.

WARNING: Django prefers psycopg 3 over psycopg2 whenever it can import it. Installing psycopg 3
therefore changes the database driver of the whole Nautobot deployment, not only of the
checkpointer. Under psycopg 3, Nautobot's change logging was measured to deadlock: the JSON adapter
iterates a queryset on a cursor that is already running a statement, and the write never returns.

An optional extra of one app must not do that to a deployment, so the choice is left to you. If you
want a Postgres checkpointer, install psycopg 3 yourself, test the change logging first, and treat
the driver change as the real decision it is.

The retention functions in this app need none of it. They use Django's own connection, so
**Prune Agent Threads** works whichever driver is in place.

## Retention

WARNING: Deleting this record does not delete the checkpoints. Nothing cascades into the tables of
the checkpointer.

Run the **Prune Agent Threads** Job to remove them. It deletes the checkpoints of finished threads
past `checkpoint_retention_days`. It leaves a running thread and a waiting thread alone, whatever
their age: a waiting thread has been waiting since somebody stopped looking at it, and deleting its
state throws away the decision they were asked to make.
