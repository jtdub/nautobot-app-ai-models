"""Delete what the LangGraph checkpointer wrote, because nothing else will.

A checkpointer keeps every step of one thread's graph state. That makes a run resumable, and it
also makes the tables grow without bound.

Three facts force this module to exist:

* The saver creates its own tables. Django's migrations do not describe them, and no foreign key
  points at them. A delete of an `AIAgentThread` row deletes none of them.
* Nothing cascades between those tables. One thread has rows in `checkpoints` and in `writes`.
* `BaseCheckpointSaver` declares `prune`, `copy_thread`, and `delete_for_runs`, and every shipped
  saver raises `NotImplementedError` from all three.

NOTE: This module cannot trim a thread to its newest checkpoint. `checkpoint_blobs` carries no
`checkpoint_id`, because every checkpoint that did not change a channel shares one blob. This
module keeps a thread whole or deletes it whole.
"""

import logging

from django.db import connection
from django.db.models.functions import Coalesce
from django.utils import timezone

from nautobot_ai_models.app_settings import CHECKPOINT_RETENTION_DAYS, app_setting
from nautobot_ai_models.choices import AIAgentThreadStatusChoices
from nautobot_ai_models.constants import DEFAULT_CHECKPOINT_RETENTION_DAYS

logger = logging.getLogger(__name__)

CHECKPOINT_TABLES = ("checkpoint_writes", "checkpoint_blobs", "checkpoints")

THREAD_COLUMN = "thread_id"


def _existing_tables():
    """Which checkpoint tables this database has.

    A deployment that never ran an agent has none of them, and a `DELETE` against a missing table
    is an error rather than a no-op. Django's introspection answers this on every backend, where a
    hand-written `information_schema` query answers it on PostgreSQL alone.

    A MySQL deployment never has them, because the saver that creates them is PostgreSQL-only. It
    gets an empty tuple, and every caller then does nothing.

    Returns:
        tuple: The names from `CHECKPOINT_TABLES` that exist.
    """
    found = set(connection.introspection.table_names())
    return tuple(name for name in CHECKPOINT_TABLES if name in found)


def delete_thread(thread_id, *, tables=None):
    """Delete every checkpoint row for one thread.

    The saver's own `delete_thread` does this too. This function needs no saver instance, no
    connection string, and not the `agents` extra. A retention Job must not have to build a client
    to delete a row.

    The statement interpolates a table name from `CHECKPOINT_TABLES` only, quoted by the backend's
    own `quote_name`. No caller value ever reaches the statement text.

    Args:
        thread_id: The LangGraph thread_id, as a string or UUID.
        tables: The checkpoint tables this database has, when the caller already looked them up.
            `prune` passes its own, so a backlog of threads costs one schema query, not one query
            for each thread.

    Returns:
        dict: Rows deleted, keyed by table name.
    """
    deleted = {}
    with connection.cursor() as cursor:
        for table in _existing_tables() if tables is None else tables:
            name = connection.ops.quote_name(table)
            cursor.execute(f"DELETE FROM {name} WHERE {THREAD_COLUMN} = %s", [str(thread_id)])  # noqa: S608
            deleted[table] = cursor.rowcount
    logger.debug("Deleted checkpoints for thread %s: %s", thread_id, deleted)
    return deleted


def retention_days():
    """How long a finished thread is kept.

    Returns:
        int: The configured window, or the shipped default when the setting is missing or unusable.
    """
    configured = app_setting(CHECKPOINT_RETENTION_DAYS)
    if isinstance(configured, bool) or not isinstance(configured, int) or configured < 1:
        return DEFAULT_CHECKPOINT_RETENTION_DAYS
    return configured


def expired_threads(*, days=None):
    """The finished threads past the retention window.

    A live thread never expires, however old it is. A thread that waits for a person has waited
    since somebody stopped looking at it, and a delete would throw away the decision they were
    asked to make.

    Args:
        days: Override the configured window.

    Returns:
        QuerySet: The AIAgentThread rows that may be deleted.
    """
    from nautobot_ai_models.models import AIAgentThread  # pylint: disable=import-outside-toplevel

    cutoff = timezone.now() - timezone.timedelta(days=days if days is not None else retention_days())
    return (
        AIAgentThread.objects.filter(
            status__in=(AIAgentThreadStatusChoices.COMPLETED, AIAgentThreadStatusChoices.FAILED),
        )
        .annotate(ended_at=Coalesce("finished_at", "started_at"))
        .filter(ended_at__lt=cutoff)
        .select_related("agent")
    )


def prune(*, days=None, delete_rows=True):
    """Delete the checkpoints of every expired thread, and optionally the thread rows.

    Args:
        days: Override the configured window.
        delete_rows: Also delete the `AIAgentThread` rows. False keeps the record of what ran and
            drops only the state, which is what a deployment that reports on agent activity wants.

    Returns:
        dict: `threads` pruned, and `rows` deleted across the checkpoint tables.
    """
    threads, rows = 0, 0
    tables = _existing_tables()
    for thread in expired_threads(days=days).iterator():
        rows += sum(delete_thread(thread.thread_id, tables=tables).values())
        threads += 1
        if delete_rows:
            thread.delete()
    logger.info("Pruned %s thread(s) and %s checkpoint row(s).", threads, rows)
    return {"threads": threads, "rows": rows}
