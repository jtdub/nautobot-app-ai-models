"""Test the model-discovery helper."""

from unittest import mock

from django.test import TestCase

from nautobot_ai_models import discovery, models
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
