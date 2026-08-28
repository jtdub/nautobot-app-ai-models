"""Test the AIProvider and AIModel models."""

import json

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from nautobot.apps.testing import ModelTestCases
from nautobot.extras.models import ExternalIntegration

from nautobot_ai_models import models
from nautobot_ai_models.choices import AIModelKindChoices, AIProviderTypeChoices
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
        self.assertTrue(provider.enabled)
        self.assertEqual(provider.provider_type, AIProviderTypeChoices.OPENAI)
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

    def test_a_blank_provider_type_is_refused(self):
        """Only the migration writes a blank, and only for a row it could not answer for."""
        provider = models.AIProvider.objects.get(name="Test One")
        provider.provider_type = ""
        with self.assertRaises(ValidationError):
            provider.validated_save()

    def test_an_addressed_provider_needs_a_remote_url(self):
        """An OpenAI-compatible or Ollama endpoint is an address, not a service."""
        integration = fixtures.create_external_integration(name="No Remote URL", remote_url="")
        provider = models.AIProvider(
            name="Self Hosted",
            external_integration=integration,
            provider_type=AIProviderTypeChoices.OPENAI_COMPATIBLE,
        )
        with self.assertRaises(ValidationError):
            provider.validated_save()

    def test_a_named_service_does_not_need_a_remote_url(self):
        """A client reaching openai.com or Anthropic already knows the address."""
        integration = fixtures.create_external_integration(name="Named Service", remote_url="")
        provider = models.AIProvider(
            name="Hosted Anthropic",
            external_integration=integration,
            provider_type=AIProviderTypeChoices.ANTHROPIC,
        )
        provider.validated_save()
        self.assertEqual(provider.provider_type, AIProviderTypeChoices.ANTHROPIC)

    def test_the_dialect_is_separate_from_the_discovery_flag(self):
        """The two fields answer different questions and must be settable apart.

        Ollama is the case that makes them distinct: its compatibility layer serves /v1/models, so
        the boolean is true, but that layer drops tool calls, so the dialect is its native API.
        """
        provider = models.AIProvider.objects.get(name="Test Three")
        provider.provider_type = AIProviderTypeChoices.OLLAMA
        provider.openai_compatible = True
        provider.validated_save()

        provider.refresh_from_db()
        self.assertEqual(provider.provider_type, AIProviderTypeChoices.OLLAMA)
        self.assertTrue(provider.openai_compatible)


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

    def test_cost_is_recorded_per_model_and_defaults_to_unknown(self):
        """An empty price means nobody recorded one. It does not mean free."""
        ai_model = models.AIModel.objects.get(name="Test One")
        self.assertIsNone(ai_model.input_cost_per_million)
        self.assertIsNone(ai_model.output_cost_per_million)

        ai_model.input_cost_per_million = "2.5000"
        ai_model.output_cost_per_million = "10.0000"
        ai_model.validated_save()

        ai_model.refresh_from_db()
        self.assertEqual(str(ai_model.input_cost_per_million), "2.5000")
        self.assertEqual(str(ai_model.output_cost_per_million), "10.0000")

    def test_a_negative_cost_is_rejected(self):
        """A price below zero is a typo, not a rebate."""
        ai_model = models.AIModel.objects.get(name="Test One")
        ai_model.input_cost_per_million = "-1.0000"
        with self.assertRaises(ValidationError):
            ai_model.validated_save()

    def test_kind_defaults_to_chat(self):
        """Every row that existed before this field means what it always meant."""
        provider = models.AIProvider.objects.get(name="Test One")
        ai_model = models.AIModel.objects.create(provider=provider, name="new-model")
        self.assertEqual(ai_model.kind, AIModelKindChoices.CHAT)

    def test_a_model_on_a_disabled_provider_is_not_available(self):
        """The model's own flag is untouched. One question replaces two."""
        provider = models.AIProvider.objects.get(name="Test One")
        ai_model = models.AIModel.objects.get(provider=provider, name="Test One")
        self.assertTrue(ai_model.is_available)

        provider.enabled = False
        provider.validated_save()

        ai_model.refresh_from_db()
        self.assertTrue(ai_model.enabled)
        self.assertFalse(ai_model.is_available)

    def test_a_parameter_outside_the_allowlist_is_refused(self):
        """`base_url` decides who answers, so it is not a parameter this registry will hold."""
        ai_model = models.AIModel.objects.get(name="Test One")
        ai_model.default_parameters = {"seed": 7, "base_url": "https://attacker.example.com/v1"}
        with self.assertRaises(ValidationError):
            ai_model.validated_save()

    def test_a_parameter_outside_the_allowlist_is_dropped_at_read_time(self):
        """A fixture, a data migration or a direct ORM write never runs clean(). This is the net."""
        ai_model = models.AIModel.objects.get(name="Test One")
        models.AIModel.objects.filter(pk=ai_model.pk).update(
            default_parameters={"seed": 7, "base_url": "https://attacker.example.com/v1"}
        )

        ai_model.refresh_from_db()
        self.assertEqual(ai_model.resolved_parameters, {"seed": 7})

    def test_default_parameters_must_be_an_object(self):
        """A list or a string is not a set of request parameters."""
        ai_model = models.AIModel.objects.get(name="Test One")
        ai_model.default_parameters = ["seed"]
        with self.assertRaises(ValidationError):
            ai_model.validated_save()

    def test_temperature_precedence(self):
        """The column wins, then the parameter, then the provider default.

        Both properties are asserted on every row, because they must never disagree. Compared as
        numbers: ``resolved_temperature`` returns the winning source's type, and
        ``resolved_parameters`` always returns a float.
        """
        cases = (
            ("the column beats both", "1.20", {"temperature": 0.40}, 1.20),
            ("the parameter beats the provider", None, {"temperature": 0.40}, 0.40),
            ("the provider is the last resort", None, {}, 0.10),
        )

        for label, column, parameters, expected in cases:
            with self.subTest(label):
                provider = models.AIProvider.objects.get(name="Test One")
                provider.temperature = "0.10"
                provider.validated_save()

                ai_model = models.AIModel.objects.get(provider=provider, name="Test One")
                ai_model.temperature = column
                ai_model.default_parameters = parameters
                ai_model.validated_save()

                self.assertEqual(float(ai_model.resolved_temperature), expected)
                self.assertEqual(ai_model.resolved_parameters["temperature"], expected)

    def test_resolved_parameters_can_be_serialised_as_json(self):
        """This dictionary exists to be sent, and json.dumps refuses a Decimal."""
        provider = models.AIProvider.objects.get(name="Test One")
        provider.temperature = "0.70"
        provider.validated_save()

        ai_model = models.AIModel.objects.get(provider=provider, name="Test One")
        ai_model.default_parameters = {"seed": 7}
        ai_model.validated_save()

        self.assertEqual(json.loads(json.dumps(ai_model.resolved_parameters)), {"seed": 7, "temperature": 0.7})

    def test_resolved_parameters_omits_temperature_when_nobody_set_one(self):
        """An unset temperature is left out rather than sent as None."""
        ai_model = models.AIModel.objects.get(name="Test One")
        ai_model.default_parameters = {"seed": 7}
        ai_model.validated_save()

        self.assertIsNone(ai_model.resolved_temperature)
        self.assertEqual(ai_model.resolved_parameters, {"seed": 7})

    def test_a_fraction_of_a_cent_survives(self):
        """A cheap model is quoted in fractions of a cent per million tokens."""
        ai_model = models.AIModel.objects.get(name="Test One")
        ai_model.input_cost_per_million = "0.0001"
        ai_model.validated_save()
        ai_model.refresh_from_db()
        self.assertEqual(str(ai_model.input_cost_per_million), "0.0001")

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
