"""Unit tests for the nautobot_ai_models REST API."""

from nautobot.apps.testing import APIViewTestCases

from nautobot_ai_models import models
from nautobot_ai_models.choices import MCPTransportChoices
from nautobot_ai_models.tests import fixtures
from nautobot_ai_models.tests.scaffolding import RegistryAPIPayloadsMixin


class AIProviderAPIViewTest(RegistryAPIPayloadsMixin, APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for AIProvider."""

    model = models.AIProvider
    choices_fields = ()

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIProvider API viewset."""
        super().setUpTestData()
        fixtures.create_ai_provider()
        integration = fixtures.create_external_integration()
        cls.build_api_payloads(
            {"external_integration": integration.pk},
            [{}, {"openai_compatible": False}, {"num_predict": 512}],
        )


class AIModelAPIViewTest(RegistryAPIPayloadsMixin, APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for AIModel."""

    model = models.AIModel
    choices_fields = ()

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIModel API viewset."""
        super().setUpTestData()
        fixtures.create_aimodel()
        provider = models.AIProvider.objects.get(name="Test Three")
        cls.build_api_payloads(
            {"provider": provider.pk},
            [{}, {"enabled": False}, {"num_predict": 1024}],
        )


class MCPServerAPIViewTest(RegistryAPIPayloadsMixin, APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for MCPServer."""

    model = models.MCPServer
    choices_fields = ["transport"]

    @classmethod
    def setUpTestData(cls):
        """Create test data for MCPServer API viewset."""
        super().setUpTestData()
        fixtures.create_mcpserver()
        integration = fixtures.create_external_integration(name="API Integration")
        cls.build_api_payloads(
            {"external_integration": integration.pk},
            [{}, {"transport": MCPTransportChoices.TYPE_STDIO}, {"enabled": False}],
        )

    def test_discovered_fields_are_read_only(self):
        """A client must not be able to make the registry claim a server reported something."""
        self.add_permissions("nautobot_ai_models.change_mcpserver")
        server = models.MCPServer.objects.first()

        response = self.client.patch(
            self._get_detail_url(server),
            {"server_version": "9.9.9", "description": "Changed"},
            format="json",
            **self.header,
        )

        self.assertHttpStatus(response, 200)
        server.refresh_from_db()
        self.assertEqual(server.description, "Changed")
        self.assertEqual(server.server_version, "")


class MCPToolAPIViewTest(APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for MCPTool."""

    model = models.MCPTool
    choices_fields = []

    @classmethod
    def setUpTestData(cls):
        """Create test data for MCPTool API viewset."""
        super().setUpTestData()
        server = fixtures.create_mcptool()[0].mcp_server
        cls.create_data = [
            {"mcp_server": server.pk, "name": "api_tool_one"},
            {"mcp_server": server.pk, "name": "api_tool_two", "writable": False},
            {"mcp_server": server.pk, "name": "api_tool_three", "enabled": False},
        ]
        cls.update_data = {"title": "Updated Title", "description": "Updated"}
        cls.bulk_update_data = {"enabled": False}

    def test_operator_fields_are_writable(self):
        """Enabling a tool and classifying it are the two things the API is for."""
        self.add_permissions("nautobot_ai_models.change_mcptool")
        tool = models.MCPTool.objects.get(name="run_report")

        response = self.client.patch(
            self._get_detail_url(tool),
            {"enabled": True, "writable": False},
            format="json",
            **self.header,
        )

        self.assertHttpStatus(response, 200)
        tool.refresh_from_db()
        self.assertTrue(tool.enabled)
        self.assertFalse(tool.writable)

    def test_discovery_owned_fields_are_read_only(self):
        """The fingerprint is evidence of what discovery saw. A client must not rewrite it."""
        self.add_permissions("nautobot_ai_models.change_mcptool")
        tool = models.MCPTool.objects.get(name="get_device")
        original = tool.definition_fingerprint

        response = self.client.patch(
            self._get_detail_url(tool),
            {"definition_fingerprint": "forged"},
            format="json",
            **self.header,
        )

        self.assertHttpStatus(response, 200)
        tool.refresh_from_db()
        self.assertEqual(tool.definition_fingerprint, original)
