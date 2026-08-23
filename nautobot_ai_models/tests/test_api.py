"""Unit tests for the nautobot_ai_models REST API."""

from nautobot.apps.testing import APIViewTestCases

from nautobot_ai_models import models
from nautobot_ai_models.tests import fixtures


class ProviderAPIViewTest(APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for Provider."""

    model = models.Provider
    choices_fields = ()

    @classmethod
    def setUpTestData(cls):
        """Create test data for the Provider API viewset."""
        super().setUpTestData()
        fixtures.create_provider()
        integration = fixtures.create_external_integration()
        cls.create_data = [
            {
                "name": "API Test One",
                "description": "Test One Description",
                "external_integration": integration.pk,
            },
            {
                "name": "API Test Two",
                "description": "Test Two Description",
                "external_integration": integration.pk,
                "openai_compatible": False,
            },
            {
                "name": "API Test Three",
                "description": "Test Three Description",
                "external_integration": integration.pk,
                "num_predict": 512,
            },
        ]
        cls.update_data = {
            "name": "Update Test Two",
            "description": "Test Two Description",
        }
        cls.bulk_update_data = {
            "description": "Test Bulk Update Description",
        }


class AIModelAPIViewTest(APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for AIModel."""

    model = models.AIModel
    choices_fields = ()

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIModel API viewset."""
        super().setUpTestData()
        fixtures.create_aimodel()
        provider = models.Provider.objects.get(name="Test Three")
        cls.create_data = [
            {
                "provider": provider.pk,
                "name": "API Test One",
                "description": "Test One Description",
            },
            {
                "provider": provider.pk,
                "name": "API Test Two",
                "description": "Test Two Description",
                "enabled": False,
            },
            {
                "provider": provider.pk,
                "name": "API Test Three",
                "description": "Test Three Description",
                "num_predict": 1024,
            },
        ]
        cls.update_data = {
            "name": "Update Test Two",
            "description": "Test Two Description",
        }
        cls.bulk_update_data = {
            "description": "Test Bulk Update Description",
        }
