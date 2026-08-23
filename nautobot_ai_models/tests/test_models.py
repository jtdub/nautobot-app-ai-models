"""Test the AIProvider and AIModel models."""

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from nautobot.apps.testing import ModelTestCases
from nautobot.extras.models import ExternalIntegration

from nautobot_ai_models import models
from nautobot_ai_models.tests import fixtures


class TestAIProvider(ModelTestCases.BaseModelTestCase):
    """Test AIProvider."""

    model = models.AIProvider

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIProvider model."""
        super().setUpTestData()
        fixtures.create_ai_provider()

    def test_create_provider_only_required(self):
        """Create with only required fields, and validate the defaults and __str__."""
        integration = fixtures.create_external_integration()
        provider = models.AIProvider.objects.create(name="Development", external_integration=integration)
        self.assertEqual(provider.name, "Development")
        self.assertEqual(provider.description, "")
        self.assertTrue(provider.openai_compatible)
        self.assertIsNone(provider.num_predict)
        self.assertIsNone(provider.temperature)
        self.assertEqual(str(provider), "Development")

    def test_create_provider_all_fields_success(self):
        """Create a AIProvider with every field set."""
        integration = fixtures.create_external_integration()
        provider = models.AIProvider.objects.create(
            name="Development",
            description="Development Test",
            external_integration=integration,
            openai_compatible=False,
            num_predict=512,
            temperature="0.70",
        )
        self.assertEqual(provider.description, "Development Test")
        self.assertFalse(provider.openai_compatible)
        self.assertEqual(provider.num_predict, 512)

    def test_external_integration_is_protected(self):
        """Deleting an ExternalIntegration a AIProvider uses must fail."""
        integration = fixtures.create_external_integration(name="Protected", remote_url="https://x.example.com")
        models.AIProvider.objects.create(name="Protected AIProvider", external_integration=integration)
        with self.assertRaises(ProtectedError):
            integration.delete()


class TestAIModel(ModelTestCases.BaseModelTestCase):
    """Test AIModel."""

    model = models.AIModel

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIModel model."""
        super().setUpTestData()
        fixtures.create_aimodel()

    def test_str(self):
        """__str__ includes the provider name."""
        ai_model = models.AIModel.objects.get(name="Test One")
        self.assertEqual(str(ai_model), "Test One: Test One")

    def test_resolved_values_inherit_from_provider(self):
        """An empty override reads the provider default."""
        provider = models.AIProvider.objects.get(name="Test One")
        provider.num_predict = 256
        provider.temperature = "0.50"
        provider.validated_save()

        ai_model = models.AIModel.objects.get(provider=provider, name="Test One")
        self.assertEqual(ai_model.resolved_num_predict, 256)
        self.assertEqual(str(ai_model.resolved_temperature), "0.50")

    def test_resolved_values_prefer_the_override(self):
        """A set override wins over the provider default."""
        provider = models.AIProvider.objects.get(name="Test One")
        provider.num_predict = 256
        provider.temperature = "0.50"
        provider.validated_save()

        ai_model = models.AIModel.objects.get(provider=provider, name="Test One")
        ai_model.num_predict = 1024
        ai_model.temperature = "1.20"
        ai_model.validated_save()

        self.assertEqual(ai_model.resolved_num_predict, 1024)
        self.assertEqual(str(ai_model.resolved_temperature), "1.20")

    def test_name_is_unique_per_provider(self):
        """The same model name may exist under two different providers."""
        other = models.AIProvider.objects.get(name="Test Three")
        duplicate = models.AIModel(provider=other, name="Test One")
        duplicate.validated_save()
        self.assertEqual(models.AIModel.objects.filter(name="Test One").count(), 2)

    def test_deleting_a_provider_deletes_its_models(self):
        """The provider foreign key cascades."""
        provider = models.AIProvider.objects.get(name="Test One")
        provider.delete()
        self.assertEqual(models.AIModel.objects.filter(name="Test One").count(), 0)


class TestMCPServer(ModelTestCases.BaseModelTestCase):
    """Test MCPServer."""

    model = models.MCPServer

    @classmethod
    def setUpTestData(cls):
        """Create test data for MCPServer Model."""
        super().setUpTestData()
        fixtures.create_mcpserver()

    def test_create_mcpserver_only_required(self):
        """Create with only required fields, and validate the defaults and __str__."""
        integration = fixtures.create_external_integration(name="Only Required")
        server = models.MCPServer.objects.create(name="Development", external_integration=integration)
        self.assertEqual(server.name, "Development")
        self.assertEqual(server.description, "")
        self.assertEqual(str(server), "Development")
        # A server is in service the moment it is registered, and nothing has been discovered yet.
        self.assertTrue(server.enabled)
        self.assertEqual(server.protocol_version, "")
        self.assertEqual(server.capabilities, {})
        self.assertIsNone(server.last_discovered_at)

    def test_integration_without_remote_url_is_rejected(self):
        """An integration carrying no URL is not something an MCP server can point at."""
        integration = ExternalIntegration.objects.create(name="No URL", remote_url="")
        server = models.MCPServer(name="Unreachable", external_integration=integration)
        with self.assertRaises(ValidationError) as raised:
            server.validated_save()
        self.assertIn("external_integration", raised.exception.message_dict)


class TestMCPTool(ModelTestCases.BaseModelTestCase):
    """Test MCPTool."""

    model = models.MCPTool

    @classmethod
    def setUpTestData(cls):
        """Create test data for MCPTool Model."""
        super().setUpTestData()
        cls.tools = fixtures.create_mcptool()
        cls.server = cls.tools[0].mcp_server

    def test_str_names_the_server(self):
        """A tool name only means anything next to its server."""
        self.assertEqual(str(self.tools[0]), f"{self.server.name}: get_device")

    def test_defaults_assume_the_tool_writes(self):
        """A tool nobody has classified is treated as though it changes something."""
        tool = models.MCPTool.objects.create(mcp_server=self.server, name="unclassified")
        self.assertTrue(tool.writable)
        self.assertTrue(tool.enabled)
        self.assertIsNone(tool.advertised_read_only)

    def test_name_is_unique_per_server_not_globally(self):
        """Two servers may both offer `get_device`; one server may not offer it twice."""
        other = models.MCPServer.objects.create(
            name="Another Server",
            external_integration=fixtures.create_external_integration(name="Another Integration"),
        )
        models.MCPTool.objects.create(mcp_server=other, name="get_device")

        with self.assertRaises(IntegrityError):
            models.MCPTool.objects.create(mcp_server=self.server, name="get_device")

    def test_natural_key_is_the_server_and_the_name(self):
        """The natural key has to name both halves, for the same reason the constraint does."""
        self.assertEqual(self.tools[0].natural_key(), [self.server.name, "get_device"])

    def test_is_available_follows_the_server(self):
        """An enabled tool on a disabled server is not on offer."""
        tool = self.tools[0]
        self.assertTrue(tool.is_available)

        self.server.enabled = False
        self.server.validated_save()
        tool.refresh_from_db()
        self.assertFalse(tool.is_available)
