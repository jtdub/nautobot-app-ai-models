"""Test the model-discovery Job."""

from unittest import mock

from nautobot.apps.testing import TransactionTestCase, get_job_class_and_model
from nautobot.extras.models import Job, JobLogEntry

from nautobot_ai_models import models
from nautobot_ai_models.choices import MCPTransportChoices
from nautobot_ai_models.services import mcp
from nautobot_ai_models.services.exceptions import MCPCallError
from nautobot_ai_models.tests import fixtures
from nautobot_ai_models.tests.job_runner import run_job


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

    def run_discovery(self, enable_new_models=True):
        """Run the Job against the single test provider."""
        return run_job(
            self.job_model,
            provider=str(self.provider.pk),
            enable_new_models=enable_new_models,
        )

    def run_discovery_for_all(self):
        """Run the Job with no provider selected, so it covers every enabled provider."""
        return run_job(self.job_model, provider=None, enable_new_models=True)

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

        self.run_discovery_for_all()

        self.assertEqual(self.provider.ai_models.count(), 0)
        # The other two fixture providers are still enabled, so they were reached.
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

        The fixture spreads its servers over all three transports, which is what the filter tests
        need. These tests are about which servers the job picks up, so they all start reachable and
        a test that cares about a skip sets that transport itself.
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

        # Reported as a failure, but every other server was still attempted.
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
        """An HTTP client's own message embeds the request URL, and a remote URL may carry a secret.

        The job log is readable by every holder of `extras.view_jobresult`, which is a wider
        audience than the one that may read the Secrets Group the credential came from.
        """
        discover.side_effect = MCPCallError("HTTPStatusError: 401 for https://svc:hunter2@mcp.internal/mcp")

        result = self._run(mcp_server=str(self.servers[0].pk))

        messages = " ".join(self._log_messages(result))
        self.assertNotIn("hunter2", messages)
        self.assertNotIn("svc:", messages)
