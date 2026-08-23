"""Test the model-discovery Job."""

from unittest import mock

from nautobot.apps.testing import TransactionTestCase, get_job_class_and_model, run_job_for_testing
from nautobot.extras.models import JobLogEntry

from nautobot_ai_models import models
from nautobot_ai_models.tests import fixtures


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
        fixtures.create_provider()
        self.provider = models.Provider.objects.get(name="Test One")
        _, self.job_model = get_job_class_and_model("nautobot_ai_models.jobs", "DiscoverAIModels")
        self.job_model.enabled = True
        self.job_model.validated_save()

    def run_discovery(self, enable_new_models=True):
        """Run the Job against the single test provider."""
        return run_job_for_testing(
            self.job_model,
            job_kwargs={"provider": str(self.provider.pk), "enable_new_models": enable_new_models},
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
    def test_request_failure_is_reported_without_details(self, mock_get):
        """A failed request logs the exception type only, never the message."""
        mock_get.side_effect = ValueError("https://user:secret@llm.example.com failed")

        job_result = self.run_discovery()

        messages = self.log_messages(job_result)
        self.assertTrue(any("ValueError" in message for message in messages))
        self.assertFalse(any("secret" in message for message in messages))
