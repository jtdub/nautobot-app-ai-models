"""Test the model-discovery helper."""

from unittest import mock

from nautobot.apps.testing import TestCase

from nautobot_ai_models import discovery, models
from nautobot_ai_models.constants import DEFAULT_TIMEOUT_SECONDS
from nautobot_ai_models.tests import fixtures


class BuildModelsURLTest(TestCase):
    """Test URL normalization."""

    def test_plain_base_url(self):
        """A bare host gains the full endpoint path."""
        self.assertEqual(discovery.build_models_url("https://llm.example.com"), "https://llm.example.com/v1/models")

    def test_trailing_slash(self):
        """A trailing slash is removed."""
        self.assertEqual(discovery.build_models_url("https://llm.example.com/"), "https://llm.example.com/v1/models")

    def test_url_already_ending_in_v1(self):
        """An existing /v1 suffix is not duplicated."""
        self.assertEqual(discovery.build_models_url("https://llm.example.com/v1"), "https://llm.example.com/v1/models")

    def test_url_ending_in_v1_and_slash(self):
        """An existing /v1/ suffix is not duplicated."""
        self.assertEqual(discovery.build_models_url("https://llm.example.com/v1/"), "https://llm.example.com/v1/models")


class FetchModelsTest(TestCase):
    """Test the catalog request."""

    @classmethod
    def setUpTestData(cls):
        """Create one AIProvider to query."""
        fixtures.create_ai_provider()
        cls.provider = models.AIProvider.objects.get(name="Test One")

    @mock.patch("nautobot_ai_models.discovery.requests.get")
    def test_fetch_models_parses_the_catalog(self, mock_get):
        """The OpenAI catalog shape maps to name and description."""
        mock_get.return_value = mock.Mock(
            **{
                "raise_for_status.return_value": None,
                "json.return_value": {
                    "data": [
                        {"id": "gpt-4o-mini", "owned_by": "openai"},
                        {"id": "llama3", "owned_by": ""},
                        {"object": "model"},
                    ]
                },
            }
        )

        discovered = discovery.fetch_models(self.provider)

        self.assertEqual(
            discovered,
            [
                {"name": "gpt-4o-mini", "description": "Owned by openai"},
                {"name": "llama3", "description": ""},
            ],
        )
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["timeout"], self.provider.external_integration.timeout)
        self.assertEqual(kwargs["verify"], True)

    @mock.patch("nautobot_ai_models.discovery.requests.get")
    def test_fetch_models_uses_the_normalized_url(self, mock_get):
        """The request targets the /v1/models endpoint."""
        mock_get.return_value = mock.Mock(**{"raise_for_status.return_value": None, "json.return_value": {"data": []}})

        discovery.fetch_models(self.provider)

        args, _ = mock_get.call_args
        self.assertEqual(args[0], "https://llm.example.com/v1/models")


class ConnectionSettingsTest(TestCase):
    """Test how an ExternalIntegration's connection settings reach the HTTP client."""

    @classmethod
    def setUpTestData(cls):
        """One provider to read settings from."""
        fixtures.create_ai_provider()
        cls.provider = models.AIProvider.objects.get(name="Test One")
        cls.integration = cls.provider.external_integration

    def test_unticking_verify_ssl_wins_over_a_ca_path(self):
        """An operator who did both has said not to verify."""
        self.integration.verify_ssl = False
        self.integration.ca_file_path = "/etc/ssl/certs/private-ca.pem"
        self.integration.validated_save()
        self.assertIs(discovery.build_verify(self.integration), False)

    def test_a_ca_path_is_used_when_verification_is_on(self):
        """A CA path is the value the client verifies against."""
        self.integration.verify_ssl = True
        self.integration.ca_file_path = "/etc/ssl/certs/private-ca.pem"
        self.integration.validated_save()
        self.assertEqual(discovery.build_verify(self.integration), "/etc/ssl/certs/private-ca.pem")

    def test_verification_is_on_with_no_ca_path(self):
        """The ordinary case is plain True."""
        self.integration.verify_ssl = True
        self.integration.ca_file_path = ""
        self.integration.validated_save()
        self.assertIs(discovery.build_verify(self.integration), True)

    def test_a_zero_timeout_falls_back(self):
        """ExternalIntegration accepts 0, and a request with a timeout of 0 fails at once."""
        self.integration.timeout = 0
        self.integration.validated_save()
        self.assertEqual(discovery.build_timeout(self.integration), DEFAULT_TIMEOUT_SECONDS)

    def test_a_real_timeout_is_passed_through(self):
        """Anything usable is the operator's number."""
        self.integration.timeout = 12
        self.integration.validated_save()
        self.assertEqual(discovery.build_timeout(self.integration), 12)

    def test_an_operator_written_authorization_header_is_kept(self):
        """An operator who wrote their own authorization header meant it."""
        self.integration.headers = {"authorization": "ApiKey written-by-hand"}
        self.integration.validated_save()
        self.assertEqual(discovery.build_headers(self.provider)["authorization"], "ApiKey written-by-hand")

    @mock.patch("nautobot_ai_models.discovery.requests.get")
    def test_redirects_are_not_followed(self, mock_get):
        """A redirect would replay the integration's headers at whatever host the endpoint names."""
        mock_get.return_value = mock.Mock(**{"raise_for_status.return_value": None, "json.return_value": {"data": []}})
        discovery.fetch_models(self.provider)
        _, kwargs = mock_get.call_args
        self.assertIs(kwargs["allow_redirects"], False)
