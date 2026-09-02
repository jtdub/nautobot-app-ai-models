"""Test the checkpoint retention service.

The tables this module deletes from are LangGraph's own. Django does not migrate them, so
these tests create them and drop them, in the shape `langgraph-checkpoint-postgres` uses. That
is also why these tests are worth having: nothing else in the app knows those tables exist.
"""

from django.db import connection
from django.utils import timezone
from nautobot.apps.testing import TestCase

from nautobot_ai_models.choices import AIAgentThreadStatusChoices
from nautobot_ai_models.constants import DEFAULT_CHECKPOINT_RETENTION_DAYS
from nautobot_ai_models.models import AIAgentThread
from nautobot_ai_models.services import checkpoints
from nautobot_ai_models.tests import fixtures

SAVER_DDL = (
    """CREATE TABLE IF NOT EXISTS checkpoints (
        thread_id TEXT NOT NULL,
        checkpoint_ns TEXT NOT NULL DEFAULT '',
        checkpoint_id TEXT NOT NULL,
        parent_checkpoint_id TEXT,
        type TEXT,
        checkpoint JSONB NOT NULL,
        metadata JSONB NOT NULL DEFAULT '{}',
        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
    )""",
    """CREATE TABLE IF NOT EXISTS checkpoint_blobs (
        thread_id TEXT NOT NULL,
        checkpoint_ns TEXT NOT NULL DEFAULT '',
        channel TEXT NOT NULL,
        version TEXT NOT NULL,
        type TEXT NOT NULL,
        blob BYTEA,
        PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
    )""",
    """CREATE TABLE IF NOT EXISTS checkpoint_writes (
        thread_id TEXT NOT NULL,
        checkpoint_ns TEXT NOT NULL DEFAULT '',
        checkpoint_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        idx INTEGER NOT NULL,
        channel TEXT NOT NULL,
        type TEXT,
        blob BYTEA NOT NULL,
        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
    )""",
)
"""The three tables `langgraph-checkpoint-postgres` creates, copied verbatim from its own
`MIGRATIONS` in `langgraph/checkpoint/postgres/base.py`. The three shapes differ, and a
fixture that flattened them hid a real defect once."""


class NoCheckpointTablesTest(TestCase):
    """What happens in a deployment that has never run an agent."""

    def test_deleting_a_thread_with_no_tables_is_quiet(self):
        """A DELETE against a missing table is an error, so the tables are checked for first."""
        self.assertEqual(checkpoints.delete_thread("a-thread"), {})


class CheckpointTablesTest(TestCase):
    """Deleting from the tables the saver creates."""

    def setUp(self):
        """Create the checkpoint tables in the shape the Postgres saver uses."""
        super().setUp()
        self.addCleanup(self._drop_tables)
        with connection.cursor() as cursor:
            for statement in SAVER_DDL:
                cursor.execute(statement)

    @staticmethod
    def _drop_tables():
        """Remove them again, so one test does not leave tables for the next."""
        with connection.cursor() as cursor:
            for table in checkpoints.CHECKPOINT_TABLES:
                cursor.execute(f'DROP TABLE IF EXISTS "{table}"')  # noqa: S608

    @staticmethod
    def _write(thread_id, checkpoint_ids):
        """Write one row per table per checkpoint, with each table's own key.

        The three tables have three shapes, which is the point. `checkpoint_blobs` is keyed by channel
        and version, and it carries no `checkpoint_id`.

        Args:
            thread_id: The thread to write under.
            checkpoint_ids: The checkpoints to write.
        """
        with connection.cursor() as cursor:
            for checkpoint_id in checkpoint_ids:
                cursor.execute(
                    "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, checkpoint, metadata) "
                    "VALUES (%s, '', %s, '{}', '{}')",
                    [str(thread_id), checkpoint_id],
                )
                cursor.execute(
                    "INSERT INTO checkpoint_writes "
                    "(thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, blob) "
                    "VALUES (%s, '', %s, 'task', 0, 'messages', 'json', '')",
                    [str(thread_id), checkpoint_id],
                )
                cursor.execute(
                    "INSERT INTO checkpoint_blobs (thread_id, checkpoint_ns, channel, version, type, blob) "
                    "VALUES (%s, '', 'messages', %s, 'json', '')",
                    [str(thread_id), checkpoint_id],
                )

    @staticmethod
    def _count(thread_id):
        """How many rows one thread has across every checkpoint table.

        Args:
            thread_id: The thread to count.

        Returns:
            int: The total.
        """
        total = 0
        with connection.cursor() as cursor:
            for table in checkpoints.CHECKPOINT_TABLES:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}" WHERE thread_id = %s', [str(thread_id)])  # noqa: S608
                total += cursor.fetchone()[0]
        return total

    def test_deleting_a_thread_clears_every_table(self):
        """Nothing cascades between them, so each one has to be named."""
        self._write("alpha", ["1", "2", "3"])
        self._write("bravo", ["1"])

        deleted = checkpoints.delete_thread("alpha")

        self.assertEqual(sorted(deleted), sorted(checkpoints.CHECKPOINT_TABLES))
        self.assertEqual(self._count("alpha"), 0)
        self.assertEqual(self._count("bravo"), len(checkpoints.CHECKPOINT_TABLES))

    def test_checkpoint_blobs_carries_no_checkpoint_id(self):
        """Why there is no trim: every checkpoint that did not change a channel shares one blob.

        This is an assertion rather than a comment. A test fixture with the wrong shape once let a
        `DELETE ... AND checkpoint_id <> %s` against this table pass review.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'checkpoint_blobs'"
            )
            columns = {row[0] for row in cursor.fetchall()}

        self.assertNotIn("checkpoint_id", columns)
        self.assertEqual(columns, {"thread_id", "checkpoint_ns", "channel", "version", "type", "blob"})

    def test_a_thread_id_is_bound_not_interpolated(self):
        """The table names are module constants; no caller input reaches the statement text."""
        self._write("alpha", ["1"])

        checkpoints.delete_thread("alpha'; DROP TABLE checkpoints; --")

        self.assertEqual(self._count("alpha"), len(checkpoints.CHECKPOINT_TABLES))


class RetentionTest(TestCase):
    """Which threads are past the window, and what pruning does to them."""

    @classmethod
    def setUpTestData(cls):
        """Create one thread per status."""
        fixtures.create_aiagentthread()

    def test_the_default_window_is_used_when_nothing_says_otherwise(self):
        """A missing or unusable setting falls back rather than pruning everything."""
        self.assertEqual(checkpoints.retention_days(), DEFAULT_CHECKPOINT_RETENTION_DAYS)

    def test_a_live_thread_is_never_expired(self):
        """However old it is. Something may still be running against it."""
        old = timezone.now() - timezone.timedelta(days=365)
        AIAgentThread.objects.update(started_at=old)

        expired = checkpoints.expired_threads(days=1)

        for thread in AIAgentThread.objects.filter(status=AIAgentThreadStatusChoices.RUNNING):
            self.assertNotIn(thread, expired)

    def test_a_waiting_thread_is_never_expired(self):
        """It has been waiting since somebody stopped looking at it, and the decision is still owed."""
        old = timezone.now() - timezone.timedelta(days=365)
        AIAgentThread.objects.update(started_at=old)

        expired = checkpoints.expired_threads(days=1)

        for thread in AIAgentThread.objects.filter(status=AIAgentThreadStatusChoices.WAITING):
            self.assertNotIn(thread, expired)

    def test_a_finished_thread_inside_the_window_is_kept(self):
        """The window is what it says."""
        self.assertFalse(checkpoints.expired_threads(days=30).exists())

    def test_a_finished_thread_past_the_window_expires(self):
        """The one case that prunes."""
        old = timezone.now() - timezone.timedelta(days=365)
        AIAgentThread.objects.update(started_at=old)

        expired = checkpoints.expired_threads(days=1)

        self.assertTrue(expired.exists())
        for thread in expired:
            self.assertFalse(thread.is_live)

    def test_pruning_can_keep_the_record_and_drop_the_state(self):
        """A deployment that reports on agent activity wants the row and not the checkpoints."""
        old = timezone.now() - timezone.timedelta(days=365)
        AIAgentThread.objects.update(started_at=old)
        before = AIAgentThread.objects.count()

        result = checkpoints.prune(days=1, delete_rows=False)

        self.assertGreater(result["threads"], 0)
        self.assertEqual(AIAgentThread.objects.count(), before)

    def test_pruning_can_delete_the_record_too(self):
        """The default, for a deployment that wants the space back."""
        old = timezone.now() - timezone.timedelta(days=365)
        AIAgentThread.objects.update(started_at=old)
        expected = checkpoints.expired_threads(days=1).count()
        before = AIAgentThread.objects.count()

        result = checkpoints.prune(days=1, delete_rows=True)

        self.assertEqual(result["threads"], expected)
        self.assertEqual(AIAgentThread.objects.count(), before - expected)
