"""Test the Git datasource that loads Python tools from a repository.

Nothing here clones anything. `refresh_ai_tools` reads the clone that is already on disk, so a
test writes the files where a clone would be and points `GIT_ROOT` at them. That is the
filesystem state a sync leaves behind, and it keeps the suite off the network.

Most tests hand the callback a recorder in place of a Job Result. Nautobot keeps Job logs in
their own database, which a `TestCase` cannot write to. These tests read what the callback
said, not where Nautobot filed it. `JobResultLoggingTest` covers the real record once.
"""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import override_settings
from nautobot.apps.testing import TestCase, TransactionTestCase
from nautobot.extras.models import GitRepository, JobResult

from nautobot_ai_models import datasources, tools
from nautobot_ai_models.choices import AIToolKindChoices
from nautobot_ai_models.models import AITool
from nautobot_ai_models.tests.scaffolding import EmptyRegistryMixin

REPOSITORY_SLUG = "ai_tools_test_repo"

TWO_TOOLS = '''
"""Tools declared in a repository."""

from nautobot_ai_models.tools import register_ai_tool


@register_ai_tool(writable=False)
def repo_read_tool(hostname: str) -> str:
    """Read something. Send one hostname."""
    return hostname


@register_ai_tool(writable=True)
def repo_write_tool(hostname: str) -> str:
    """Write something. Send one hostname."""
    return hostname
'''

ONE_TOOL_REWORDED = '''
"""Tools declared in a repository."""

from nautobot_ai_models.tools import register_ai_tool


@register_ai_tool(writable=False)
def repo_read_tool(hostname: str) -> str:
    """Read something else entirely. Send one hostname."""
    return hostname
'''


class Recorder:  # pylint: disable=too-few-public-methods
    """A Job Result that keeps what it was told instead of a write.

    Nautobot files Job logs in a second database that a `TestCase` may not write to. These tests
    read the message back, not the record.
    """

    def __init__(self):
        """Start with nothing recorded."""
        self.entries = []

    def log(self, message, obj=None, grouping=None, level_choice=None):
        """Record one message.

        Args:
            message: What the callback said.
            obj: The record it was about, if any.
            grouping: The Job log grouping.
            level_choice: The Job log level.
        """
        self.entries.append((level_choice, message, obj, grouping))


class GitToolsTestCase(EmptyRegistryMixin, TestCase):
    """A repository on disk, and the state to put back afterwards."""

    def setUp(self):
        """Point GIT_ROOT at a temporary directory and start from an empty registry."""
        super().setUp()
        self.git_root = TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self.git_root.cleanup)
        self.addCleanup(self.forget_the_module)

        settings_patch = override_settings(GIT_ROOT=self.git_root.name)
        settings_patch.enable()
        self.addCleanup(settings_patch.disable)

        self.repository = GitRepository(
            name="AI Tools Test Repository",
            slug=REPOSITORY_SLUG,
            remote_url="https://example.com/ai-tools.git",
            provided_contents=[datasources.CONTENT_IDENTIFIER],
        )
        self.repository.save()

    @staticmethod
    def forget_the_module():
        """Drop the repository's modules from `sys.modules`, so the next test imports them again."""
        for name in list(sys.modules):
            if name == REPOSITORY_SLUG or name.startswith(f"{REPOSITORY_SLUG}."):
                del sys.modules[name]

    def write_repository(self, body=TWO_TOOLS, *, module_name="ai_tools.py"):
        """Write a clone to disk.

        Args:
            body: The contents of the tools module.
            module_name: What to call it. Anything but `ai_tools.py` is not found on purpose.
        """
        root = Path(self.git_root.name) / REPOSITORY_SLUG
        root.mkdir(parents=True, exist_ok=True)
        (root / "__init__.py").write_text("", encoding="utf-8")
        (root / module_name).write_text(body, encoding="utf-8")

    def sync(self, *, delete=False):
        """Run the callback and hand back what it logged.

        Args:
            delete: Whether the repository is being deleted.

        Returns:
            Recorder: What the callback said.
        """
        recorder = Recorder()
        datasources.refresh_ai_tools(self.repository, recorder, delete=delete)
        return recorder

    @staticmethod
    def messages(recorder):
        """Every message the callback logged, as one string to search.

        Args:
            recorder: What `sync` handed back.

        Returns:
            str: The messages, joined.
        """
        return " ".join(entry[1] for entry in recorder.entries)


class ImportTest(GitToolsTestCase):  # pylint: disable=too-many-ancestors
    """Test `import_tools`."""

    def test_a_repository_registers_what_it_declares(self):
        """The point of the whole datasource."""
        self.write_repository()

        found = datasources.import_tools(self.repository, ignore_import_errors=False)

        self.assertEqual(sorted(found), ["repo_read_tool", "repo_write_tool"])
        self.assertEqual(found["repo_read_tool"].module, f"{REPOSITORY_SLUG}.ai_tools")

    def test_importing_twice_is_not_an_error(self):
        """A private import runs the module body twice, and every sync runs it again."""
        self.write_repository()

        datasources.import_tools(self.repository, ignore_import_errors=False)
        found = datasources.import_tools(self.repository, ignore_import_errors=False)

        self.assertEqual(sorted(found), ["repo_read_tool", "repo_write_tool"])

    def test_a_tool_the_repository_dropped_is_unregistered(self):
        """Without this, a deleted tool would stay registered for the life of the process."""
        self.write_repository()
        datasources.import_tools(self.repository, ignore_import_errors=False)

        self.write_repository(ONE_TOOL_REWORDED)
        found = datasources.import_tools(self.repository, ignore_import_errors=False)

        self.assertEqual(sorted(found), ["repo_read_tool"])
        self.assertIsNone(tools.get_registered_tool("repo_write_tool"))

    def test_an_unticked_repository_unloads_and_stops(self):
        """What a repository that stopped providing tools gets: the unload, and no import."""
        self.write_repository()
        datasources.import_tools(self.repository, ignore_import_errors=False)
        self.repository.provided_contents = []

        self.assertEqual(datasources.import_tools(self.repository), {})
        self.assertEqual(tools.registered_tools(), {})

    def test_a_missing_module_is_refused_by_name(self):
        """A repository that ticked the box and shipped no module is a mistake worth a message."""
        self.write_repository(module_name="not_ai_tools.py")

        with self.assertRaises(FileNotFoundError) as raised:
            datasources.import_tools(self.repository, ignore_import_errors=False)
        self.assertIn(datasources.TOOLS_MODULE, str(raised.exception))

    def test_an_unsafe_slug_is_refused(self):
        """A slug that shadows an installed package would import the wrong code."""
        self.repository.slug = "django"

        with self.assertRaises(ValueError) as raised:
            datasources.import_tools(self.repository, ignore_import_errors=False)
        self.assertIn("django", str(raised.exception))

    def test_a_repository_that_provides_nothing_registers_nothing(self):
        """The box decides, not the presence of the file."""
        self.write_repository()
        self.repository.provided_contents = []

        self.assertEqual(datasources.import_tools(self.repository), {})


class RefreshTest(GitToolsTestCase):  # pylint: disable=too-many-ancestors
    """Test the callback Nautobot invokes on a sync."""

    def test_a_sync_writes_a_record_per_tool(self):
        """Of kind `git`, pointing back at the repository."""
        self.write_repository()

        self.sync()

        records = AITool.objects.filter(kind=AIToolKindChoices.GIT).order_by("name")
        self.assertEqual([record.name for record in records], ["repo_read_tool", "repo_write_tool"])
        for record in records:
            self.assertEqual(record.git_repository, self.repository)
            self.assertEqual(record.module, f"{REPOSITORY_SLUG}.ai_tools")

    def test_what_the_tool_said_is_recorded_against_what_a_person_decides(self):
        """`writable` seeds from the declaration. `advertised_read_only` keeps the declaration."""
        self.write_repository()

        self.sync()

        read_tool = AITool.objects.get(name="repo_read_tool")
        self.assertFalse(read_tool.writable)
        self.assertTrue(read_tool.advertised_read_only)
        self.assertTrue(AITool.objects.get(name="repo_write_tool").writable)

    def test_a_new_record_honours_new_tools_enabled(self):
        """The same default-deny posture that MCP tools arrive under.

        This test patches the setting reader, not `PLUGINS_CONFIG`, which would replace the
        configuration of every installed app.
        """
        self.write_repository()
        policy = {"new_tools_enabled": False, "disable_on_definition_change": False}

        with mock.patch("nautobot_ai_models.services.tool_records.app_setting", side_effect=policy.get):
            self.sync()

        self.assertEqual(AITool.objects.filter(kind=AIToolKindChoices.GIT, enabled=True).count(), 0)

    def test_a_second_sync_changes_nothing(self):
        """A sync that rewrote records every time would be a sync nobody could read a diff from."""
        self.write_repository()
        self.sync()

        recorder = self.sync()

        self.assertIn("0 added, 2 seen, 0 changed", self.messages(recorder))

    def test_a_reworded_tool_is_reported_as_changed(self):
        """The description is what the model reads, so a change to it is a change to the tool."""
        self.write_repository()
        self.sync()
        before = AITool.objects.get(name="repo_read_tool").definition_fingerprint

        self.write_repository(ONE_TOOL_REWORDED)
        recorder = self.sync()

        self.assertNotEqual(AITool.objects.get(name="repo_read_tool").definition_fingerprint, before)
        self.assertIn("repo_read_tool has changed", self.messages(recorder))

    def test_a_dropped_tool_keeps_its_record(self):
        """Its name may still be on an approved call, and a binding protects it anyway."""
        self.write_repository()
        self.sync()

        self.write_repository(ONE_TOOL_REWORDED)
        recorder = self.sync()

        self.assertTrue(AITool.objects.filter(name="repo_write_tool").exists())
        self.assertIn("repo_write_tool is no longer registered", self.messages(recorder))

    def test_unticking_the_content_disables_the_records(self):
        """The tools stop being offered. The records stay, because an agent may be bound to one."""
        self.write_repository()
        self.sync()
        self.repository.provided_contents = []
        self.repository.save()

        recorder = self.sync()

        self.assertEqual(AITool.objects.filter(kind=AIToolKindChoices.GIT, enabled=True).count(), 0)
        self.assertEqual(AITool.objects.filter(kind=AIToolKindChoices.GIT).count(), 2)
        self.assertIn("no longer provides AI tools", self.messages(recorder))

    def test_a_deletion_says_the_records_go_too(self):
        """`AITool.git_repository` cascades, and a bound tool blocks the deletion instead."""
        self.write_repository()
        self.sync()

        recorder = self.sync(delete=True)

        self.assertIn("being deleted", self.messages(recorder))
        self.assertEqual(tools.registered_tools(), {})

    def test_a_broken_module_is_reported_and_writes_nothing(self):
        """A repository is somebody else's code. A syntax error in it is not a failed sync."""
        self.write_repository("this is not python(")

        recorder = self.sync()

        self.assertIn("Could not load AI tools", self.messages(recorder))
        self.assertEqual(AITool.objects.filter(kind=AIToolKindChoices.GIT).count(), 0)

    def test_a_repository_with_no_tools_says_so(self):
        """Silence would read as success."""
        self.write_repository('"""Nothing here."""\n')

        recorder = self.sync()

        self.assertIn("No tools were registered", self.messages(recorder))


class LoadToolTest(GitToolsTestCase):  # pylint: disable=too-many-ancestors
    """Test the per-process import the agent builder falls back to."""

    def test_a_record_finds_its_callable_in_a_process_that_never_imported_it(self):
        """This is what makes a Git tool usable outside the worker that ran the sync."""
        self.write_repository()
        self.sync()
        record = AITool.objects.get(name="repo_read_tool")
        tools.clear_registry()

        with mock.patch("nautobot_ai_models.datasources.ensure_git_repository"):
            found = datasources.load_tool(record)

        self.assertIsNotNone(found)
        self.assertEqual(found.callable("dfw-core-01"), "dfw-core-01")

    def test_a_record_the_repository_dropped_finds_nothing(self):
        """Not an error here. The builder turns it into one, naming the agent and the binding."""
        self.write_repository()
        self.sync()
        record = AITool.objects.get(name="repo_write_tool")
        self.write_repository(ONE_TOOL_REWORDED)

        with mock.patch("nautobot_ai_models.datasources.ensure_git_repository"):
            self.assertIsNone(datasources.load_tool(record))

    def test_a_record_of_another_kind_is_not_loaded_from_a_repository(self):
        """Only a `git` record names a repository to load from."""
        self.write_repository()
        self.sync()
        record = AITool.objects.get(name="repo_read_tool")
        record.kind = AIToolKindChoices.REGISTERED

        self.assertIsNone(datasources.load_tool(record))

    def test_a_repository_that_cannot_be_reached_returns_nothing(self):
        """A failed clone is a tool the agent is not offered, not a traceback out of the builder."""
        self.write_repository()
        self.sync()
        record = AITool.objects.get(name="repo_read_tool")

        with mock.patch("nautobot_ai_models.datasources.ensure_git_repository", side_effect=OSError("no such remote")):
            self.assertIsNone(datasources.load_tool(record))


class JobResultLoggingTest(EmptyRegistryMixin, TransactionTestCase):
    """Prove the callback logs to a real Job Result, not only to the recorder above.

    This is a `TransactionTestCase` because Nautobot files Job logs in a second database, which a
    `TestCase` may not write to. One test is enough, because the call itself is what is under test.
    """

    databases = ("default", "job_logs")

    def test_a_sync_writes_its_messages_to_the_job_result(self):
        """An operator reads this page to find out what a sync did."""
        git_root = TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(git_root.cleanup)
        self.addCleanup(GitToolsTestCase.forget_the_module)

        root = Path(git_root.name) / REPOSITORY_SLUG
        root.mkdir(parents=True)
        (root / "__init__.py").write_text("", encoding="utf-8")
        (root / "ai_tools.py").write_text(TWO_TOOLS, encoding="utf-8")

        repository = GitRepository(
            name="AI Tools Logging Repository",
            slug=REPOSITORY_SLUG,
            remote_url="https://example.com/ai-tools.git",
            provided_contents=[datasources.CONTENT_IDENTIFIER],
        )
        repository.save()
        job_result = JobResult.objects.create(name="git tools logging")

        with override_settings(GIT_ROOT=git_root.name):
            datasources.refresh_ai_tools(repository, job_result, delete=False)

        entries = list(job_result.job_log_entries.all())
        self.assertTrue(entries)
        self.assertEqual({entry.grouping for entry in entries}, {"ai tools"})
        self.assertIn("2 added", " ".join(entry.message for entry in entries))
