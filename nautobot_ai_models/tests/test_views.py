"""Unit tests for views."""

from nautobot.apps.testing import ViewTestCases

from nautobot_ai_models import models
from nautobot_ai_models.tests import fixtures


class ProviderViewTest(ViewTestCases.OrganizationalObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the Provider views."""

    model = models.Provider
    bulk_edit_data = {"description": "Bulk edit views"}

    @classmethod
    def setUpTestData(cls):
        """Create test data and the form payloads the generic view tests post."""
        fixtures.create_provider()
        integration = fixtures.create_external_integration()
        cls.form_data = {
            "name": "Test 1",
            "description": "Initial model",
            "external_integration": integration.pk,
            "openai_compatible": True,
        }
        cls.update_data = {
            "name": "Test 2",
            "description": "Updated model",
            "external_integration": integration.pk,
            "openai_compatible": True,
        }


class AIModelViewTest(ViewTestCases.OrganizationalObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the AIModel views."""

    model = models.AIModel
    bulk_edit_data = {"description": "Bulk edit views"}

    @classmethod
    def setUpTestData(cls):
        """Create test data and the form payloads the generic view tests post."""
        fixtures.create_aimodel()
        provider = models.Provider.objects.get(name="Test Three")
        cls.form_data = {
            "provider": provider.pk,
            "name": "Test 1",
            "description": "Initial model",
            "enabled": True,
        }
        cls.update_data = {
            "provider": provider.pk,
            "name": "Test 2",
            "description": "Updated model",
            "enabled": True,
        }
