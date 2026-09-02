"""Test the discovery and housekeeping Jobs.

The sample tool below has an unused parameter on purpose: its signature is what the Job reads the
argument schema from, and a body would prove nothing.
"""
# pylint: disable=unused-argument

from unittest import mock

from django.utils import timezone
from nautobot.apps.testing import TransactionTestCase, get_job_class_and_model
from nautobot.extras.models import Job, JobLogEntry

from nautobot_ai_models import models, tools
from nautobot_ai_models.choices import AIAgentThreadStatusChoices, AIToolKindChoices, MCPTransportChoices
from nautobot_ai_models.models import AIAgentThread, AITool
from nautobot_ai_models.services import mcp
from nautobot_ai_models.services.exceptions import MCPCallError
from nautobot_ai_models.tests import fixtures
from nautobot_ai_models.tests.job_runner import run_job

NOT_GIVEN = object()


def catalog_response(names):
    """Return a mock requests response holding an OpenAI-shaped model catalog."""
    return mock.Mock(
        **{
            "raise_for_status.return_value": None,
            "json.return_value": {"data": [{"id": each, "owned_by": "test"} for each in names]},
        }
    )


class DiscoverAIModelsTest(TransactionTestCase):
    """Test the Discover AI Models Job."""

    databases = ("default", "job_logs")

    def setUp(self):
        """Create one provider and load the Job model."""
        super().setUp()
        fixtures.create_ai_provider()
        self.provider = models.AIProvider.objects.get(name="Test One")
        _, self.job_model = get_job_class_and_model("nautobot_ai_models.jobs", "DiscoverAIModels")
        self.job_model.enabled = True
        self.job_model.validated_save()

    def run_discovery(self, enable_new_models=True, provider=NOT_GIVEN):
        """Run the Job against the single test provider, or against all of them.

        Pass `provider=None` for the all-providers path. The sentinel lets None mean every provider
        instead of the default.
        """
        chosen = self.provider if provider is NOT_GIVEN else provider
        return run_job(
            self.job_model,
            provider=str(chosen.pk) if chosen is not None else None,
            enable_new_models=enable_new_models,
        )

    def log_messages(self, job_result):
        """Return every log message the Job wrote."""
        return [entry.message for entry in JobLogEntry.objects.filter(job_result=job_result)]

    @mock.patch("nautobot_ai_models.discovery.requests.get")
    def test_creates_new_models(self, mock_get):
        """A first run creates one AIModel for each catalog entry."""
        mock_get.return_value = catalog_response(["gpt-4o-mini", "llama3"])

        self.run_discovery()

        self.assertEqual(self.provider.ai_models.count(), 2)
        self.assertQuerySetEqual(
            self.provider.ai_models.order_by("name").values_list("name", flat=True),
            ["gpt-4o-mini", "llama3"],
        )
        self.assertTrue(all(each.enabled for each in self.provider.ai_models.all()))

    @mock.patch("nautobot_ai_models.discovery.requests.get")
    def test_new_models_can_start_disabled(self, mock_get):
        """enable_new_models=False creates disabled records."""
        mock_get.return_value = catalog_response(["gpt-4o-mini"])

        self.run_discovery(enable_new_models=False)

        self.assertFalse(self.provider.ai_models.get(name="gpt-4o-mini").enabled)

    @mock.patch("nautobot_ai_models.discovery.requests.get")
    def test_second_run_creates_nothing(self, mock_get):
        """Running twice against the same catalog is idempotent."""
        mock_get.return_value = catalog_response(["gpt-4o-mini", "llama3"])

        self.run_discovery()
        self.run_discovery()

        self.assertEqual(self.provider.ai_models.count(), 2)

    @mock.patch("nautobot_ai_models.discovery.requests.get")
    def test_manual_enabled_state_is_preserved(self, mock_get):
        """A model a user disabled by hand stays disabled."""
        mock_get.return_value = catalog_response(["gpt-4o-mini"])
        self.run_discovery()

        ai_model = self.provider.ai_models.get(name="gpt-4o-mini")
        ai_model.enabled = False
        ai_model.num_predict = 1024
        ai_model.validated_save()

        self.run_discovery()

        ai_model.refresh_from_db()
        self.assertFalse(ai_model.enabled)
        self.assertEqual(ai_model.num_predict, 1024)

    @mock.patch("nautobot_ai_models.discovery.requests.get")
    def test_missing_model_is_kept_and_logged(self, mock_get):
        """A model the provider no longer offers is not deleted."""
        mock_get.return_value = catalog_response(["gpt-4o-mini", "llama3"])
        self.run_discovery()

        mock_get.return_value = catalog_response(["gpt-4o-mini"])
        job_result = self.run_discovery()

        self.assertEqual(self.provider.ai_models.count(), 2)
        self.assertTrue(self.provider.ai_models.filter(name="llama3").exists())
        self.assertTrue(any("no longer offers" in message for message in self.log_messages(job_result)))

    @mock.patch("nautobot_ai_models.discovery.requests.get")
    def test_non_openai_compatible_provider_is_skipped(self, mock_get):
        """A provider that is not OpenAI-compatible is skipped without a request."""
        self.provider.openai_compatible = False
        self.provider.validated_save()

        job_result = self.run_discovery()

        mock_get.assert_not_called()
        self.assertEqual(self.provider.ai_models.count(), 0)
        self.assertTrue(any("OpenAI-compatible" in message for message in self.log_messages(job_result)))

    @mock.patch("nautobot_ai_models.discovery.requests.get")
    def test_a_disabled_provider_named_directly_is_skipped(self, mock_get):
        """An operator who took a provider out of service is told why nothing happened."""
        self.provider.enabled = False
        self.provider.validated_save()

        job_result = self.run_discovery()

        mock_get.assert_not_called()
        self.assertEqual(self.provider.ai_models.count(), 0)
        self.assertTrue(any("disabled" in message for message in self.log_messages(job_result)))

    @mock.patch("nautobot_ai_models.discovery.requests.get")
    def test_a_disabled_provider_is_left_out_of_an_all_providers_run(self, mock_get):
        """A provider taken out of service must not come back the next time discovery runs."""
        mock_get.return_value = catalog_response(["gpt-4o-mini"])
        self.provider.enabled = False
        self.provider.validated_save()

        self.run_discovery(provider=None)

        self.assertEqual(self.provider.ai_models.count(), 0)
        self.assertEqual(models.AIModel.objects.filter(provider__enabled=True).count(), 2)

    @mock.patch("nautobot_ai_models.discovery.requests.get")
    def test_request_failure_is_reported_without_details(self, mock_get):
        """A failed request logs the exception type only, never the message."""
        mock_get.side_effect = ValueError("https://user:secret@llm.example.com failed")

        job_result = self.run_discovery()

        messages = self.log_messages(job_result)
        self.assertTrue(any("ValueError" in message for message in messages))
        self.assertFalse(any("secret" in message for message in messages))


EMPTY_REPORT = mcp.DiscoveryReport()


class MCPServerDiscoveryJobTest(TransactionTestCase):
    """Test MCPServerDiscovery."""

    databases = ("default", "job_logs")

    def setUp(self):
        """Three servers, and the job record that discovers them.

        The fixture spreads its servers over all three transports, which the filter tests need. These
        tests ask which servers the job picks up, so every server starts reachable. A test that cares
        about a skip sets that transport itself.
        """
        super().setUp()
        self.servers = fixtures.create_mcpserver()
        for server in self.servers:
            server.transport = MCPTransportChoices.TYPE_STREAMABLE_HTTP
            server.validated_save()
        self.job = Job.objects.get(
            module_name="nautobot_ai_models.jobs",
            job_class_name="MCPServerDiscovery",
        )
        self.job.enabled = True
        self.job.validated_save()

    def _run(self, **job_kwargs):
        """Run the job, and hand back its result."""
        job_kwargs.setdefault("mcp_server", None)
        job_kwargs.setdefault("remove_stale", False)
        return run_job(self.job, **job_kwargs)

    def _log_messages(self, result):
        """Every log line the run produced."""
        return [entry.message for entry in JobLogEntry.objects.filter(job_result=result)]

    @mock.patch("nautobot_ai_models.jobs.mcp.require_client", mock.Mock())
    @mock.patch("nautobot_ai_models.jobs.mcp.discover")
    def test_no_target_discovers_every_enabled_server(self, discover):
        discover.return_value = EMPTY_REPORT
        disabled = self.servers[2]
        disabled.enabled = False
        disabled.validated_save()

        result = self._run()

        self.assertEqual(result.status, "SUCCESS")
        discovered = {call.args[0].name for call in discover.call_args_list}
        self.assertEqual(discovered, {"Test One", "Test Two"})

    @mock.patch("nautobot_ai_models.jobs.mcp.require_client", mock.Mock())
    @mock.patch("nautobot_ai_models.jobs.mcp.discover")
    def test_named_server_is_the_only_one_discovered(self, discover):
        discover.return_value = EMPTY_REPORT

        result = self._run(mcp_server=self.servers[1].pk)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(discover.call_count, 1)
        self.assertEqual(discover.call_args.args[0].name, "Test Two")

    @mock.patch("nautobot_ai_models.jobs.mcp.require_client", mock.Mock())
    @mock.patch("nautobot_ai_models.jobs.mcp.discover")
    def test_remove_stale_is_passed_through(self, discover):
        discover.return_value = EMPTY_REPORT

        self._run(mcp_server=self.servers[0].pk, remove_stale=True)

        self.assertTrue(discover.call_args.kwargs["remove_stale"])

    @mock.patch("nautobot_ai_models.jobs.mcp.require_client", mock.Mock())
    @mock.patch("nautobot_ai_models.jobs.mcp.discover")
    def test_stdio_server_is_skipped_not_attempted(self, discover):
        discover.return_value = EMPTY_REPORT
        stdio = self.servers[0]
        stdio.transport = MCPTransportChoices.TYPE_STDIO
        stdio.validated_save()

        result = self._run()

        self.assertEqual(result.status, "SUCCESS")
        attempted = {call.args[0].name for call in discover.call_args_list}
        self.assertNotIn("Test One", attempted)
        self.assertTrue(any("cannot open" in message for message in self._log_messages(result)))

    @mock.patch("nautobot_ai_models.jobs.mcp.require_client", mock.Mock())
    @mock.patch("nautobot_ai_models.jobs.mcp.discover")
    def test_one_failure_does_not_stop_the_others(self, discover):
        def _answer(server, **_kwargs):
            if server.name == "Test Two":
                raise MCPCallError("the server would not answer")
            return EMPTY_REPORT

        discover.side_effect = _answer

        result = self._run()

        self.assertEqual(result.status, "FAILURE")
        self.assertEqual(discover.call_count, 3)
        messages = self._log_messages(result)
        self.assertTrue(any("Test Two" in message for message in messages))

    @mock.patch("nautobot_ai_models.jobs.mcp.require_client", mock.Mock())
    @mock.patch("nautobot_ai_models.jobs.mcp.discover")
    def test_nothing_to_do_is_not_a_failure(self, discover):
        discover.return_value = EMPTY_REPORT
        models.MCPServer.objects.update(enabled=False)

        result = self._run()

        self.assertEqual(result.status, "SUCCESS")
        discover.assert_not_called()

    @mock.patch("nautobot_ai_models.jobs.mcp.require_client", mock.Mock())
    @mock.patch("nautobot_ai_models.jobs.mcp.discover")
    def test_new_and_changed_tools_are_called_out(self, discover):
        server = self.servers[0]
        added = models.MCPTool.objects.create(mcp_server=server, name="brand_new")
        changed = models.MCPTool.objects.create(mcp_server=server, name="moved_underneath_us")
        discover.return_value = mcp.DiscoveryReport(added=(added,), definition_changed=(changed,))

        result = self._run(mcp_server=server.pk)

        messages = " ".join(self._log_messages(result))
        self.assertIn("brand_new", messages)
        self.assertIn("moved_underneath_us", messages)

    @mock.patch("nautobot_ai_models.jobs.mcp.require_client", mock.Mock())
    @mock.patch("nautobot_ai_models.jobs.mcp.discover")
    def test_a_failure_never_writes_the_endpoint_into_the_log(self, discover):
        """An HTTP client message embeds the request URL, and a remote URL may carry a secret.

        Every holder of `extras.view_jobresult` reads the job log. That is a wider audience than the
        one that may read the Secrets Group the credential came from.
        """
        discover.side_effect = MCPCallError("HTTPStatusError: 401 for https://svc:hunter2@mcp.internal/mcp")

        result = self._run(mcp_server=str(self.servers[0].pk))

        messages = " ".join(self._log_messages(result))
        self.assertNotIn("hunter2", messages)
        self.assertNotIn("svc:", messages)


class SyncAIToolsTest(TransactionTestCase):
    """Test the Sync AI Tools Job.

    This is discovery, with the in-process registry in place of a remote endpoint. The Job obeys
    the same two policies that govern MCP tools.
    """

    databases = ("default", "job_logs")

    def setUp(self):
        """Start from an empty registry and no tool records."""
        super().setUp()
        self.addCleanup(tools.clear_registry)
        tools.clear_registry()
        AITool.objects.all().delete()
        self.job_class, self.job_model = get_job_class_and_model("nautobot_ai_models.jobs", "SyncAITools")

    @staticmethod
    def register(name="lookup_device", description="Look up one device by hostname.", writable=False):
        """Register one tool.

        Args:
            name: The tool's name.
            description: The tool's description.
            writable: Whether it writes.
        """

        def sample(hostname: str) -> str:
            pass

        tools.register_ai_tool(sample, name=name, description=description, writable=writable)

    @staticmethod
    def policy(**overrides):
        """Override the two registry policy settings for one block.

        `override_settings(PLUGINS_CONFIG=...)` would replace the configuration of every installed
        app, so this patches the reader instead.

        Args:
            **overrides: Settings to change.

        Returns:
            The patcher, for use as a context manager.
        """
        defaults = {"new_tools_enabled": True, "disable_on_definition_change": False, **overrides}
        return mock.patch("nautobot_ai_models.services.tool_records.app_setting", side_effect=defaults.get)

    def test_a_new_tool_is_written(self):
        """The ordinary case: code declared it, so the registry records it."""
        self.register()

        run_job(self.job_model, dry_run=False)

        tool = AITool.objects.get(name="lookup_device")
        self.assertEqual(tool.kind, AIToolKindChoices.REGISTERED)
        self.assertEqual(tool.description, "Look up one device by hostname.")
        self.assertTrue(tool.definition_fingerprint)
        self.assertIsNotNone(tool.last_seen_at)

    def test_a_new_tool_honours_new_tools_enabled(self):
        """The same setting that keeps a newly discovered MCP tool out of an agent's hands."""
        self.register()

        with self.policy(new_tools_enabled=False):
            run_job(self.job_model, dry_run=False)

        self.assertFalse(AITool.objects.get(name="lookup_device").enabled)

    def test_what_the_tool_said_lands_beside_what_a_person_decided(self):
        """Two flags, not one, exactly as MCPTool keeps them."""
        self.register(writable=False)

        run_job(self.job_model, dry_run=False)

        tool = AITool.objects.get(name="lookup_device")
        self.assertFalse(tool.writable)
        self.assertTrue(tool.advertised_read_only)

    def test_a_dry_run_writes_nothing(self):
        """Reporting what would change is not changing it."""
        self.register()

        run_job(self.job_model, dry_run=True)

        self.assertFalse(AITool.objects.filter(name="lookup_device").exists())

    def test_a_changed_definition_is_reported(self):
        """The description is what the model reads, so a change to it is a change to the tool."""
        self.register()
        run_job(self.job_model, dry_run=False)
        before = AITool.objects.get(name="lookup_device").definition_fingerprint

        tools.clear_registry()
        self.register(description="Look up one device. Returns the site code as well.")
        run_job(self.job_model, dry_run=False)

        self.assertNotEqual(AITool.objects.get(name="lookup_device").definition_fingerprint, before)

    def test_a_changed_definition_can_take_a_tool_out_of_service(self):
        """`disable_on_definition_change`, applied to the second tool source."""
        self.register()
        run_job(self.job_model, dry_run=False)
        AITool.objects.filter(name="lookup_device").update(enabled=True)

        tools.clear_registry()
        self.register(description="Something else entirely.")
        with self.policy(disable_on_definition_change=True):
            run_job(self.job_model, dry_run=False)

        self.assertFalse(AITool.objects.get(name="lookup_device").enabled)

    def test_a_persons_decision_survives_a_sync(self):
        """A redeclaration in code is not a review. `writable` is never written by the Job."""
        self.register(writable=True)
        run_job(self.job_model, dry_run=False)
        AITool.objects.filter(name="lookup_device").update(writable=False)

        run_job(self.job_model, dry_run=False)

        self.assertFalse(AITool.objects.get(name="lookup_device").writable)

    def test_a_tool_that_stopped_being_registered_is_kept(self):
        """Its name may be on an approved call, and its app may be halfway through an upgrade."""
        self.register()
        run_job(self.job_model, dry_run=False)

        tools.clear_registry()
        run_job(self.job_model, dry_run=False)

        self.assertTrue(AITool.objects.filter(name="lookup_device").exists())


class PruneAgentThreadsTest(TransactionTestCase):
    """Test the Prune Agent Threads Job."""

    databases = ("default", "job_logs")

    def setUp(self):
        """Create the threads and find the Job."""
        super().setUp()
        fixtures.create_aiagentthread()
        self.job_class, self.job_model = get_job_class_and_model("nautobot_ai_models.jobs", "PruneAgentThreads")

    def test_a_dry_run_deletes_nothing(self):
        """Reporting what would go is not deleting it."""
        AIAgentThread.objects.update(started_at=timezone.now() - timezone.timedelta(days=365))
        before = AIAgentThread.objects.count()

        run_job(self.job_model, days=1, delete_rows=True, dry_run=True)

        self.assertEqual(AIAgentThread.objects.count(), before)

    def test_a_finished_thread_past_the_window_goes(self):
        """The one case that prunes."""
        AIAgentThread.objects.update(started_at=timezone.now() - timezone.timedelta(days=365))
        expected = AIAgentThread.objects.filter(
            status__in=(AIAgentThreadStatusChoices.COMPLETED, AIAgentThreadStatusChoices.FAILED)
        ).count()
        before = AIAgentThread.objects.count()

        run_job(self.job_model, days=1, delete_rows=True, dry_run=False)

        self.assertEqual(AIAgentThread.objects.count(), before - expected)

    def test_a_waiting_thread_is_left_alone(self):
        """Deleting its state throws away a decision somebody was asked to make."""
        AIAgentThread.objects.update(started_at=timezone.now() - timezone.timedelta(days=365))

        run_job(self.job_model, days=1, delete_rows=True, dry_run=False)

        self.assertTrue(AIAgentThread.objects.filter(status=AIAgentThreadStatusChoices.WAITING).exists())
