"""Unit tests for views."""

from nautobot.apps.testing import ViewTestCases

from nautobot_ai_models import models
from nautobot_ai_models.choices import MCPTransportChoices
from nautobot_ai_models.tests import fixtures


class AIProviderViewTest(ViewTestCases.OrganizationalObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the AIProvider views."""

    model = models.AIProvider
    bulk_edit_data = {"description": "Bulk edit views"}

    @classmethod
    def setUpTestData(cls):
        """Create test data and the form payloads the generic view tests post."""
        fixtures.create_ai_provider()
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
        provider = models.AIProvider.objects.get(name="Test Three")
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


class MCPServerViewTest(ViewTestCases.PrimaryObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the MCPServer views."""

    model = models.MCPServer
    bulk_edit_data = {"description": "Bulk edit views"}

    @classmethod
    def setUpTestData(cls):
        """Create test data for the MCPServer views."""
        fixtures.create_mcpserver()
        integration = fixtures.create_external_integration(name="View Integration")
        cls.form_data = {
            "name": "Test 1",
            "description": "Initial model",
            "external_integration": integration.pk,
            "transport": MCPTransportChoices.TYPE_STREAMABLE_HTTP,
            "enabled": True,
        }
        cls.update_data = {
            "name": "Test 2",
            "description": "Updated model",
            "external_integration": integration.pk,
            "transport": MCPTransportChoices.TYPE_STREAMABLE_HTTP,
            "enabled": True,
        }


class MCPToolViewTest(ViewTestCases.OrganizationalObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the MCPTool views."""

    model = models.MCPTool
    bulk_edit_data = {"enabled": False}

    @classmethod
    def setUpTestData(cls):
        """Create test data for the MCPTool views."""
        server = fixtures.create_mcptool()[0].mcp_server
        cls.form_data = {
            "mcp_server": server.pk,
            "name": "view_tool_one",
            "title": "View Tool One",
            "description": "Initial tool",
            "enabled": True,
            "writable": True,
        }
        cls.update_data = {
            "mcp_server": server.pk,
            "name": "view_tool_two",
            "title": "View Tool Two",
            "description": "Updated tool",
            "enabled": False,
            "writable": False,
        }
