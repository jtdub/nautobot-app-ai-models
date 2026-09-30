"""Test the registry models."""

import json
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from django.utils import timezone
from nautobot.apps.testing import ModelTestCases, TestCase
from nautobot.extras.models import ExternalIntegration, GitRepository

from nautobot_ai_models import models
from nautobot_ai_models.choices import (
    AIAgentPatternChoices,
    AIAgentThreadStatusChoices,
    AIModelKindChoices,
    AIProviderTypeChoices,
    AIToolKindChoices,
    SubagentInputModeChoices,
)
from nautobot_ai_models.services import usage
from nautobot_ai_models.tests import fixtures


def _spare_agent(name):
    """Create an agent with no tool bindings, so every target pair is free.

    Args:
        name: The agent's name.

    Returns:
        AIAgent: The saved agent.
    """
    return models.AIAgent.objects.create(
        name=name,
        description=f"{name}. Give it a hostname.",
        system_prompt="You answer from tools only.",
        model=models.AIModel.objects.filter(kind=AIModelKindChoices.CHAT).first(),
    )


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

        Ollama makes them distinct. Its compatibility layer serves /v1/models, so the boolean is true,
        but that layer drops tool calls, so the dialect is its native API.
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

    def test_a_capability_starts_unrecorded(self):
        """An empty column is not a no. Nobody has answered the question yet."""
        provider = models.AIProvider.objects.get(name="Test One")
        ai_model = models.AIModel.objects.create(provider=provider, name="fresh-model")
        self.assertIsNone(ai_model.context_window)
        self.assertIsNone(ai_model.max_output_tokens)
        self.assertIsNone(ai_model.supports_tools)
        self.assertIsNone(ai_model.supports_vision)
        self.assertIsNone(ai_model.supports_structured_output)

    def test_an_answer_larger_than_the_context_window_is_refused(self):
        """The context window holds the prompt as well, so the answer cannot fill it twice."""
        ai_model = models.AIModel.objects.get(name="Test One")
        ai_model.context_window = 8192
        ai_model.max_output_tokens = 16384
        with self.assertRaises(ValidationError) as raised:
            ai_model.validated_save()
        self.assertIn("max_output_tokens", raised.exception.message_dict)

    def test_a_token_limit_above_the_model_ceiling_is_refused(self):
        """A limit the model cannot meet is a typo, and it fails at run time instead."""
        ai_model = models.AIModel.objects.get(name="Test One")
        ai_model.max_output_tokens = 4096
        ai_model.num_predict = 8192
        with self.assertRaises(ValidationError) as raised:
            ai_model.validated_save()
        self.assertIn("num_predict", raised.exception.message_dict)

    def test_an_unlimited_token_limit_passes_the_ceiling(self):
        """-1 means unlimited, and the provider applies its own ceiling."""
        ai_model = models.AIModel.objects.get(name="Test One")
        ai_model.max_output_tokens = 4096
        ai_model.num_predict = -1
        ai_model.validated_save()
        ai_model.refresh_from_db()
        self.assertEqual(ai_model.num_predict, -1)


class TestAIModelParameters(TestCase):
    """The default-parameter allowlist, and the values read back through it.

    This is a plain TestCase, not a second BaseModelTestCase. The generic model tests already run
    against AIModel above, and a second one would run every one of them again.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIModel model."""
        fixtures.create_aimodel()

    def test_a_parameter_outside_the_allowlist_is_refused(self):
        """`base_url` decides who answers, so it is not a parameter this registry will hold."""
        ai_model = models.AIModel.objects.get(name="Test One")
        ai_model.default_parameters = {"seed": 7, "base_url": "https://attacker.example.com/v1"}
        with self.assertRaises(ValidationError):
            ai_model.validated_save()

    def test_clearing_the_default_parameters_box_is_allowed(self):
        """The edit form renders an empty textarea as None, and the field is optional."""
        ai_model = models.AIModel.objects.get(name="Test One")
        for value in (None, "", {}):
            with self.subTest(value=value):
                ai_model.default_parameters = value
                ai_model.validated_save()
                ai_model.refresh_from_db()
                self.assertEqual(ai_model.default_parameters, {})

    def test_a_temperature_parameter_outside_the_range_is_refused(self):
        """The JSON field must not be a way past the validators on the column of the same name."""
        ai_model = models.AIModel.objects.get(name="Test One")
        for value in (-1, 900, "warm", True, None):
            with self.subTest(value=value):
                ai_model.default_parameters = {"temperature": value}
                with self.assertRaises(ValidationError):
                    ai_model.validated_save()

    def test_resolved_parameters_survives_a_value_no_validation_saw(self):
        """A list endpoint renders this for every row. One unusable row must not take the rest."""
        ai_model = models.AIModel.objects.get(name="Test One")
        models.AIModel.objects.filter(pk=ai_model.pk).update(default_parameters={"temperature": "warm", "seed": 7})

        ai_model.refresh_from_db()
        self.assertEqual(ai_model.resolved_parameters, {"seed": 7})

    def test_resolved_parameters_survives_a_column_that_is_not_a_mapping(self):
        """A direct ORM write can put a list here. Reading it must not raise."""
        ai_model = models.AIModel.objects.get(name="Test One")
        models.AIModel.objects.filter(pk=ai_model.pk).update(default_parameters=["seed"])

        ai_model.refresh_from_db()
        self.assertEqual(ai_model.resolved_parameters, {})
        self.assertIsNone(ai_model.resolved_temperature)

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

        This test asserts both properties on every row, because they must never disagree. It compares
        them as numbers: ``resolved_temperature`` returns the winning source's type, and
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


class TestMCPResource(ModelTestCases.BaseModelTestCase):
    """Test MCPResource."""

    model = models.MCPResource

    @classmethod
    def setUpTestData(cls):
        """Create test data for the MCPResource model."""
        super().setUpTestData()
        fixtures.create_mcpresource()

    def test_str_names_the_server(self):
        """One URI can exist under two servers, so the server has to be in the label."""
        resource = models.MCPResource.objects.filter(name="inventory").first()
        self.assertTrue(str(resource).startswith(resource.mcp_server.name))

    def test_the_uri_is_unique_per_server_not_globally(self):
        """Two servers can offer the same URI, and they are two records."""
        self.assertEqual(models.MCPResource.objects.filter(uri="nautobot://devices/inventory").count(), 2)

    def test_the_natural_key_is_the_server_and_the_uri(self):
        """The name is not the key: the specification does not promise it is unique."""
        self.assertEqual(models.MCPResource.natural_key_field_names, ["mcp_server", "uri"])

    def test_a_template_records_that_its_uri_has_parameters(self):
        """A template URI is not one a client can read directly."""
        template = models.MCPResource.objects.get(is_template=True)
        self.assertIn("{", template.uri)

    def test_is_available_follows_the_server(self):
        """One question replaces two, the same as for a tool."""
        resource = models.MCPResource.objects.first()
        self.assertTrue(resource.is_available)
        server = resource.mcp_server
        server.enabled = False
        server.validated_save()
        resource.refresh_from_db()
        self.assertTrue(resource.enabled)
        self.assertFalse(resource.is_available)

    def test_deleting_a_server_deletes_its_resources(self):
        """A resource cannot outlive the server that offers it."""
        server = models.MCPResource.objects.first().mcp_server
        server.delete()
        self.assertEqual(models.MCPResource.objects.filter(mcp_server_id=server.pk).count(), 0)

    def test_argument_schema_lists_the_template_variables(self):
        """Each RFC 6570 variable in a template URI is one string property."""
        resource = models.MCPResource.objects.get(uri="nautobot://sites/{site_code}")
        self.assertEqual(
            resource.argument_schema,
            {"type": "object", "properties": {"site_code": {"type": "string"}}},
        )

    def test_argument_schema_is_empty_for_a_plain_resource(self):
        """A plain URI has no parameters for a caller to fill."""
        resource = models.MCPResource.objects.filter(uri="nautobot://devices/inventory").first()
        self.assertEqual(resource.argument_schema, {})

    def test_writable_is_false(self):
        """A resource is read by protocol, so nothing a call writes."""
        self.assertFalse(models.MCPResource.objects.first().writable)


class TestMCPPrompt(ModelTestCases.BaseModelTestCase):
    """Test MCPPrompt."""

    model = models.MCPPrompt

    @classmethod
    def setUpTestData(cls):
        """Create test data for the MCPPrompt model."""
        super().setUpTestData()
        fixtures.create_mcpprompt()

    def test_name_is_unique_per_server_not_globally(self):
        """Two servers can offer a prompt of one name."""
        self.assertEqual(models.MCPPrompt.objects.filter(name="triage_device").count(), 2)

    def test_the_arguments_are_a_list_not_a_schema(self):
        """The protocol sends a list here, so a caller cannot treat it as a JSON Schema."""
        prompt = models.MCPPrompt.objects.get(name="summarise_site")
        self.assertIsInstance(prompt.arguments, list)

    def test_required_arguments_names_only_the_required_ones(self):
        """A reviewer wants the ones a caller has to supply."""
        prompt = next(each for each in models.MCPPrompt.objects.filter(name="triage_device") if each.arguments)
        self.assertEqual(prompt.required_arguments, ("hostname",))
        optional = models.MCPPrompt.objects.get(name="summarise_site")
        self.assertEqual(optional.required_arguments, ())

    def test_required_arguments_survives_a_column_that_is_not_a_list(self):
        """A fixture or a direct write can put anything here, and a list view must not break."""
        prompt = models.MCPPrompt.objects.first()
        prompt.arguments = {"not": "a list"}
        self.assertEqual(prompt.required_arguments, ())

    def test_is_available_follows_the_server(self):
        """One question replaces two."""
        prompt = models.MCPPrompt.objects.first()
        server = prompt.mcp_server
        server.enabled = False
        server.validated_save()
        prompt.refresh_from_db()
        self.assertFalse(prompt.is_available)

    def test_argument_schema_builds_from_the_arguments(self):
        """The schema is what a caller needs, not the list the protocol sent."""
        prompt = models.MCPPrompt.objects.filter(name="triage_device").first()
        self.assertEqual(
            prompt.argument_schema,
            {
                "type": "object",
                "properties": {"hostname": {"type": "string", "description": "The device name."}},
                "required": ["hostname"],
            },
        )

    def test_argument_schema_leaves_an_optional_argument_out_of_required(self):
        """Only the marked-required arguments go into `required`."""
        prompt = models.MCPPrompt.objects.get(name="summarise_site")
        self.assertEqual(
            prompt.argument_schema,
            {"type": "object", "properties": {"site_code": {"type": "string"}}},
        )

    def test_writable_is_false(self):
        """A prompt is content chosen by a person, not a write."""
        self.assertFalse(models.MCPPrompt.objects.first().writable)


class TestAITool(ModelTestCases.BaseModelTestCase):
    """Test AITool."""

    model = models.AITool

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AITool model."""
        super().setUpTestData()
        fixtures.create_aitool()

    def test_the_name_is_the_natural_key(self):
        """A tool is found by the name it is called by, not by a surrogate."""
        tool = models.AITool.objects.get(name="lookup_device")
        self.assertEqual(tool.natural_key(), ["lookup_device"])
        self.assertEqual(models.AITool.objects.get_by_natural_key("lookup_device"), tool)

    def test_a_registered_tool_nothing_registered_is_refused(self):
        """The row is a claim that code exists under that name. An unbacked claim is refused."""
        tool = models.AITool(name="no_such_tool", description="Nothing declares this.")
        with self.assertRaises(ValidationError) as raised:
            tool.full_clean()
        self.assertIn("name", raised.exception.message_dict)

    def test_a_job_tool_has_to_name_a_job(self):
        """A Job tool with no Job would start nothing."""
        fixtures.register_test_tools()
        tool = models.AITool(name="lookup_device", description="x", kind=AIToolKindChoices.JOB)
        with self.assertRaises(ValidationError) as raised:
            tool.full_clean()
        self.assertIn("job", raised.exception.message_dict)

    def test_a_git_tool_has_to_name_a_repository(self):
        """The repository is what a later process imports the code from."""
        tool = models.AITool(name="orphan_tool", description="x", kind=AIToolKindChoices.GIT)
        with self.assertRaises(ValidationError) as raised:
            tool.full_clean()
        self.assertIn("git_repository", raised.exception.message_dict)

    def test_a_git_tool_is_not_checked_against_the_registry(self):
        """A process that never imported the repository still has to be able to save the record."""
        repository = GitRepository(
            name="Model Test Tools",
            slug="model_test_tools",
            remote_url="https://example.com/tools.git",
        )
        repository.save()
        tool = models.AITool(
            name="never_imported_here",
            description="Declared in a repository this process has not read.",
            kind=AIToolKindChoices.GIT,
            git_repository=repository,
        )

        tool.full_clean()

    def test_is_available_follows_enabled(self):
        """A disabled tool is not offered."""
        tool = models.AITool.objects.get(name="unreviewed_tool")
        self.assertFalse(tool.enabled)
        self.assertFalse(tool.is_available)

    def test_a_tool_arrives_writable(self):
        """Guessing wrong this way costs a review; guessing wrong the other way is worse."""
        tool = models.AITool.objects.create(name="fresh_tool", description="x")
        self.assertTrue(tool.writable)


class TestAIAgent(ModelTestCases.BaseModelTestCase):
    """Test AIAgent."""

    model = models.AIAgent

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIAgent model."""
        super().setUpTestData()
        fixtures.create_aiagent()

    def test_an_embedding_model_is_refused(self):
        """An agent talks. An embedding model does not."""
        embedding = models.AIModel.objects.filter(kind=AIModelKindChoices.EMBEDDING).first()
        agent = models.AIAgent(name="Wrong Kind", system_prompt="x", model=embedding)
        with self.assertRaises(ValidationError) as raised:
            agent.full_clean()
        self.assertIn("model", raised.exception.message_dict)

    def test_a_subagents_agent_needs_a_subagent(self):
        """The pattern names a shape. An agent with no specialists is not that shape."""
        agent = models.AIAgent.objects.get(name="Test Supervisor")
        agent.pattern = AIAgentPatternChoices.SUBAGENTS
        with self.assertRaises(ValidationError) as raised:
            agent.full_clean()
        self.assertIn("pattern", raised.exception.message_dict)

    def test_a_skills_agent_needs_a_skill(self):
        """The same rule, for the other pattern."""
        agent = models.AIAgent.objects.get(name="Test Supervisor")
        agent.pattern = AIAgentPatternChoices.SKILLS
        with self.assertRaises(ValidationError) as raised:
            agent.full_clean()
        self.assertIn("pattern", raised.exception.message_dict)

    def test_the_pattern_check_does_not_block_creation(self):
        """A binding cannot exist before its agent, so a create cannot be asked to have one."""
        chat = models.AIModel.objects.filter(kind=AIModelKindChoices.CHAT).first()
        agent = models.AIAgent(
            name="Fresh Supervisor",
            system_prompt="x",
            model=chat,
            pattern=AIAgentPatternChoices.SUBAGENTS,
        )
        agent.full_clean()

    def test_a_model_that_cannot_call_a_tool_is_refused_for_an_agent_with_tools(self):
        """The build fails at run time otherwise, and nothing says why beforehand."""
        agent = fixtures.create_aiagenttool()[0].agent
        agent.model.supports_tools = False
        agent.model.validated_save()
        with self.assertRaises(ValidationError) as raised:
            agent.full_clean()
        self.assertIn("model", raised.exception.message_dict)

    def test_a_model_that_cannot_call_a_tool_is_refused_for_a_supervisor(self):
        """A supervisor reaches a specialist as a tool, so the same rule applies."""
        agent = fixtures.create_aiagentsubagent()[0].parent
        agent.model.supports_tools = False
        agent.model.validated_save()
        with self.assertRaises(ValidationError) as raised:
            agent.full_clean()
        self.assertIn("model", raised.exception.message_dict)

    def test_an_unrecorded_tool_capability_does_not_refuse(self):
        """Nobody has answered the question. An empty column is not a no."""
        agent = fixtures.create_aiagenttool()[0].agent
        self.assertIsNone(agent.model.supports_tools)
        agent.full_clean()

    def test_a_model_that_cannot_call_a_tool_suits_an_agent_with_none(self):
        """An agent that only answers needs no tool, so the capability does not matter."""
        agent = models.AIAgent.objects.get(name="Test Supervisor")
        self.assertFalse(agent.tool_bindings.exists())
        self.assertFalse(agent.subagent_bindings.exists())
        agent.model.supports_tools = False
        agent.model.validated_save()
        agent.full_clean()

    def test_temperature_resolves_agent_then_model_then_provider(self):
        """One more level on the chain AIModel already has."""
        agent = models.AIAgent.objects.get(name="Test Supervisor")
        agent.model.provider.temperature = Decimal("0.90")
        agent.model.provider.save()
        agent.model.temperature = None
        agent.model.save()

        self.assertEqual(agent.resolved_temperature, Decimal("0.90"))

        agent.model.temperature = Decimal("0.50")
        agent.model.save()
        self.assertEqual(agent.resolved_temperature, Decimal("0.50"))

        agent.temperature = Decimal("0.10")
        self.assertEqual(agent.resolved_temperature, Decimal("0.10"))

    def test_num_predict_resolves_the_same_way(self):
        """The completion cap follows the same three levels."""
        agent = models.AIAgent.objects.get(name="Test Supervisor")
        agent.model.provider.num_predict = 100
        agent.model.provider.save()
        agent.model.num_predict = None
        agent.model.save()

        self.assertEqual(agent.resolved_num_predict, 100)

        agent.num_predict = 7
        self.assertEqual(agent.resolved_num_predict, 7)

    def test_is_available_follows_the_whole_chain(self):
        """A disabled provider takes every agent on it out of service."""
        agent = models.AIAgent.objects.get(name="Test Supervisor")
        self.assertTrue(agent.is_available)

        agent.model.provider.enabled = False
        agent.model.provider.save()
        agent.model.refresh_from_db()
        self.assertFalse(agent.is_available)

    def test_the_model_is_protected_while_an_agent_uses_it(self):
        """Deleting a catalog row must not silently delete authored work."""
        agent = models.AIAgent.objects.get(name="Test Supervisor")
        with self.assertRaises(ProtectedError):
            agent.model.delete()  # pylint: disable=no-member


class TestAIAgentTool(ModelTestCases.BaseModelTestCase):
    """Test AIAgentTool."""

    model = models.AIAgentTool

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIAgentTool model."""
        super().setUpTestData()
        fixtures.create_aiagenttool()

    def test_a_binding_names_exactly_one_tool(self):
        """Neither is nothing to call; both is two things under one name."""
        agent = models.AIAgent.objects.get(name="Test Supervisor")
        with self.assertRaises(ValidationError):
            models.AIAgentTool(agent=agent).full_clean()

        with self.assertRaises(ValidationError):
            models.AIAgentTool(
                agent=agent,
                mcp_tool=models.MCPTool.objects.first(),
                ai_tool=models.AITool.objects.first(),
            ).full_clean()

    def test_the_override_is_what_the_model_reads(self):
        """A name and a description that read badly are why a tool is never called."""
        binding = models.AIAgentTool.objects.get(name_override="find_device")
        self.assertEqual(binding.wire_name, "find_device")
        self.assertEqual(binding.wire_description, "Look up a device. Send it one hostname.")

    def test_no_override_falls_back_to_the_tool(self):
        """An operator who has nothing to add adds nothing."""
        binding = models.AIAgentTool.objects.filter(mcp_tool__isnull=False).first()
        self.assertEqual(binding.wire_name, binding.mcp_tool.name)
        self.assertEqual(binding.wire_description, binding.mcp_tool.description)

    def test_writable_reads_through_to_the_tool(self):
        """Stored twice is stored wrong. One answer, read from the target."""
        binding = models.AIAgentTool.objects.filter(mcp_tool__isnull=False).first()
        self.assertEqual(binding.writable, binding.mcp_tool.writable)

        binding.mcp_tool.writable = not binding.mcp_tool.writable
        binding.mcp_tool.save()
        binding.refresh_from_db()
        self.assertEqual(binding.writable, binding.mcp_tool.writable)

    def test_the_fingerprint_comes_from_the_target(self):
        """Whichever source, an approval is checked against the same idea."""
        binding = models.AIAgentTool.objects.filter(ai_tool__isnull=False).first()
        self.assertEqual(binding.fingerprint, binding.ai_tool.definition_fingerprint)

    def test_a_tool_is_bound_to_an_agent_once(self):
        """Twice would offer the model the same tool under two names."""
        binding = models.AIAgentTool.objects.filter(ai_tool__isnull=False).first()
        with self.assertRaises(IntegrityError):
            models.AIAgentTool.objects.create(agent=binding.agent, ai_tool=binding.ai_tool)

    def test_the_tool_is_protected_while_a_binding_uses_it(self):
        """A tool an agent is bound to is not tidied away by accident."""
        binding = models.AIAgentTool.objects.filter(ai_tool__isnull=False).first()
        with self.assertRaises(ProtectedError):
            binding.ai_tool.delete()  # pylint: disable=no-member

    def test_a_binding_names_exactly_one_of_four_targets(self):
        """A prompt or a resource is a target, and two targets are still one too many."""
        agent = _spare_agent("Four Targets Agent")
        prompt = fixtures.create_mcpprompt()[0]
        resource = fixtures.create_mcpresource()[0]

        models.AIAgentTool(agent=agent, mcp_prompt=prompt).full_clean()
        models.AIAgentTool(agent=agent, mcp_resource=resource).full_clean()

        with self.assertRaises(ValidationError):
            models.AIAgentTool(agent=agent, mcp_prompt=prompt, mcp_resource=resource).full_clean()
        with self.assertRaises(ValidationError):
            models.AIAgentTool(
                agent=agent,
                mcp_tool=models.MCPTool.objects.first(),
                mcp_prompt=prompt,
            ).full_clean()

    def test_target_returns_the_prompt_or_the_resource(self):
        """Whatever kind the binding names, `target` answers every question."""
        agent = _spare_agent("Target Agent")
        prompt = fixtures.create_mcpprompt()[0]
        resource = fixtures.create_mcpresource()[0]
        prompt_binding = models.AIAgentTool(agent=agent, mcp_prompt=prompt)
        resource_binding = models.AIAgentTool(agent=agent, mcp_resource=resource)

        self.assertIs(prompt_binding.target, prompt)
        self.assertIs(resource_binding.target, resource)

    def test_mcp_kind_reports_which_mcp_call_to_make(self):
        """A consuming app reads this to pick tool, prompt, resource, or none."""
        agent = _spare_agent("MCP Kind Agent")
        mcp_tool = models.MCPTool.objects.first()
        ai_tool = models.AITool.objects.first()
        prompt = fixtures.create_mcpprompt()[0]
        resource = fixtures.create_mcpresource()[0]

        self.assertEqual(
            models.AIAgentTool.objects.create(agent=agent, mcp_tool=mcp_tool).mcp_kind,
            "tool",
        )
        self.assertIsNone(
            models.AIAgentTool.objects.create(agent=agent, ai_tool=ai_tool).mcp_kind
        )
        self.assertEqual(
            models.AIAgentTool.objects.create(agent=agent, mcp_prompt=prompt).mcp_kind,
            "prompt",
        )
        self.assertEqual(
            models.AIAgentTool.objects.create(agent=agent, mcp_resource=resource).mcp_kind,
            "resource",
        )

    def test_a_resource_binding_with_a_blank_name_and_override_is_refused(self):
        """Without a name the model could not say which resource it meant."""
        agent = _spare_agent("Blank Resource Agent")
        resource = fixtures.create_mcpresource()[0]
        resource.name = ""
        binding = models.AIAgentTool(agent=agent, mcp_resource=resource)

        with self.assertRaises(ValidationError):
            binding.full_clean()

        binding.name_override = "inventory"
        binding.full_clean()

    def test_a_prompt_or_resource_binding_is_read_only(self):
        """Neither changes anything, so an approval can never approve a write."""
        agent = _spare_agent("Read Only Agent")
        prompt_binding = models.AIAgentTool(agent=agent, mcp_prompt=fixtures.create_mcpprompt()[0])
        resource_binding = models.AIAgentTool(agent=agent, mcp_resource=fixtures.create_mcpresource()[0])

        self.assertFalse(prompt_binding.writable)
        self.assertFalse(resource_binding.writable)

    def test_a_bound_prompt_is_protected_from_delete(self):
        """A prompt an agent is bound to is not tidied away by accident."""
        agent = _spare_agent("Protected Prompt Agent")
        prompt = fixtures.create_mcpprompt()[0]
        models.AIAgentTool.objects.create(agent=agent, mcp_prompt=prompt)

        with self.assertRaises(ProtectedError):
            prompt.delete()

    def test_the_fingerprint_moves_when_prompt_arguments_change(self):
        """An approval must not survive a definition that changed under it."""
        agent = _spare_agent("Fingerprint Agent")
        prompt = fixtures.create_mcpprompt()[0]
        binding = models.AIAgentTool.objects.create(agent=agent, mcp_prompt=prompt)
        before = binding.fingerprint

        prompt.arguments = [
            {"name": "hostname", "description": "The device name.", "required": True},
            {"name": "timeout", "required": False},
        ]
        prompt.save()

        binding = models.AIAgentTool.objects.get(pk=binding.pk)
        self.assertNotEqual(binding.fingerprint, before)


class TestAIToolApproval(ModelTestCases.BaseModelTestCase):
    """Test AIToolApproval."""

    model = models.AIToolApproval

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIToolApproval model."""
        super().setUpTestData()
        fixtures.create_aitoolapproval()

    def _binding_without_an_approval(self):
        """Return one binding that nobody has approved yet."""
        bindings = fixtures.create_aiagenttool()
        return next(binding for binding in bindings if not binding.approvals.exists())

    def test_a_create_takes_the_digest_from_the_binding(self):
        """A reviewer accepts what is on offer, and does not type a digest."""
        binding = self._binding_without_an_approval()
        approval = models.AIToolApproval(binding=binding)
        approval.validated_save()
        self.assertEqual(approval.fingerprint, binding.fingerprint)

    def test_a_digest_the_binding_does_not_offer_is_refused(self):
        """An approval of something else answers a question nobody asked."""
        binding = self._binding_without_an_approval()
        approval = models.AIToolApproval(binding=binding, fingerprint="0" * 64)
        with self.assertRaises(ValidationError) as raised:
            approval.validated_save()
        self.assertIn("fingerprint", raised.exception.message_dict)

    def test_the_binding_cannot_be_moved_afterwards(self):
        """Moving it would carry a review across to a definition nobody looked at."""
        approval = models.AIToolApproval.objects.filter(revoked_at__isnull=True).first()
        approval.binding = self._binding_without_an_approval()
        with self.assertRaises(ValidationError):
            approval.validated_save()

    def test_an_expiry_before_the_approval_is_refused(self):
        """An approval cannot lapse before it is given."""
        binding = self._binding_without_an_approval()
        approval = models.AIToolApproval(binding=binding, expires_at=timezone.now() - timedelta(days=1))
        with self.assertRaises(ValidationError) as raised:
            approval.validated_save()
        self.assertIn("expires_at", raised.exception.message_dict)

    def test_a_standing_approval_answers_for_the_binding(self):
        """The digest still matches, and nobody withdrew it."""
        approval = models.AIToolApproval.objects.filter(revoked_at__isnull=True, expires_at__isnull=True).first()
        self.assertTrue(approval.is_current)
        self.assertFalse(approval.is_expired)
        self.assertTrue(approval.is_active)
        self.assertTrue(approval.binding.is_approved)

    def test_a_withdrawn_approval_answers_nothing(self):
        """The row stays, because the review still happened."""
        approval = models.AIToolApproval.objects.filter(revoked_at__isnull=False).first()
        self.assertTrue(approval.is_current)
        self.assertFalse(approval.is_active)
        self.assertFalse(approval.binding.is_approved)

    def test_an_expired_approval_answers_nothing(self):
        """A quarterly review that nobody renewed stops standing."""
        approval = models.AIToolApproval.objects.filter(expires_at__isnull=False).first()
        self.assertTrue(approval.is_expired)
        self.assertFalse(approval.is_active)
        self.assertFalse(approval.binding.is_approved)

    def test_a_moved_definition_ends_the_approval(self):
        """This is the point of the digest. A rewritten description needs a new review."""
        approval = models.AIToolApproval.objects.filter(revoked_at__isnull=True, expires_at__isnull=True).first()
        binding = approval.binding
        self.assertTrue(binding.is_approved)

        binding.description_override = "Something the reviewer never read."
        binding.validated_save()

        binding.refresh_from_db()
        self.assertFalse(binding.is_approved)
        self.assertFalse(binding.approvals.first().is_current)

    def test_a_binding_can_be_approved_again_after_a_withdrawal(self):
        """A withdrawal is not a ban. There is no uniqueness constraint in the way."""
        approval = models.AIToolApproval.objects.filter(revoked_at__isnull=False).first()
        binding = approval.binding
        again = models.AIToolApproval(binding=binding)
        again.validated_save()
        self.assertTrue(binding.is_approved)
        self.assertEqual(binding.approvals.count(), 2)

    def test_deleting_a_binding_deletes_its_approvals(self):
        """An orphan approval has no digest to be checked against."""
        approval = models.AIToolApproval.objects.first()
        approval.binding.delete()
        self.assertFalse(models.AIToolApproval.objects.filter(pk=approval.pk).exists())


class TestAIAgentSubagent(ModelTestCases.BaseModelTestCase):
    """Test AIAgentSubagent."""

    model = models.AIAgentSubagent

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIAgentSubagent model."""
        super().setUpTestData()
        fixtures.create_aiagentsubagent()

    def test_an_agent_cannot_delegate_to_itself(self):
        """A specialist that is its own supervisor never returns."""
        agent = models.AIAgent.objects.get(name="Test Supervisor")
        with self.assertRaises(ValidationError) as raised:
            models.AIAgentSubagent(parent=agent, subagent=agent).full_clean()
        self.assertIn("subagent", raised.exception.message_dict)

    def test_a_cycle_is_refused(self):
        """Building follows these rows, and a cycle in them is a build that never returns."""
        binding = models.AIAgentSubagent.objects.first()
        with self.assertRaises(ValidationError) as raised:
            models.AIAgentSubagent(parent=binding.subagent, subagent=binding.parent).full_clean()
        self.assertIn("subagent", raised.exception.message_dict)

    def test_a_longer_cycle_is_refused(self):
        """The walk follows the whole chain, not just one step."""
        first = models.AIAgentSubagent.objects.first()
        third = models.AIAgent.objects.get(name="Test Skills Agent")
        models.AIAgentSubagent.objects.create(parent=first.subagent, subagent=third)

        with self.assertRaises(ValidationError):
            models.AIAgentSubagent(parent=third, subagent=first.parent).full_clean()

    def test_the_routing_strings_come_from_the_binding(self):
        """These two decide whether the specialist is called at all."""
        binding = models.AIAgentSubagent.objects.get(tool_name="inventory_expert")
        self.assertEqual(binding.wire_name, "inventory_expert")
        self.assertIn("hostname", binding.wire_description)

    def test_the_input_mode_defaults_to_the_task_alone(self):
        """Widening the input can activate a rule in the specialist's own prompt."""
        agent = models.AIAgent.objects.get(name="Test Skills Agent")
        other = models.AIAgent.objects.get(name="Test Supervisor")
        binding = models.AIAgentSubagent.objects.create(parent=agent, subagent=other)
        self.assertEqual(binding.input_mode, SubagentInputModeChoices.TASK_ONLY)


class TestAISkill(ModelTestCases.BaseModelTestCase):
    """Test AISkill."""

    model = models.AISkill

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AISkill model."""
        super().setUpTestData()
        fixtures.create_aiskill()

    def test_a_skill_is_available_when_enabled(self):
        """A disabled skill is not offered."""
        skill = models.AISkill.objects.first()
        self.assertTrue(skill.is_available)
        skill.enabled = False
        self.assertFalse(skill.is_available)

    def test_the_skill_is_protected_while_an_agent_loads_it(self):
        """A skill an agent may load is not deleted from under it."""
        binding = fixtures.create_aiagentskill()[0]
        with self.assertRaises(ProtectedError):
            binding.skill.delete()  # pylint: disable=no-member


class TestAIAgentSkill(ModelTestCases.BaseModelTestCase):
    """Test AIAgentSkill."""

    model = models.AIAgentSkill

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIAgentSkill model."""
        super().setUpTestData()
        fixtures.create_aiagentskill()

    def test_a_skill_is_bound_to_an_agent_once(self):
        """Twice would list the same skill twice in the load tool's description."""
        binding = models.AIAgentSkill.objects.first()
        with self.assertRaises(IntegrityError):
            models.AIAgentSkill.objects.create(agent=binding.agent, skill=binding.skill)


class TestAIUsageRecord(TestCase):
    """Test AIUsageRecord.

    A plain `TestCase`: the model is a `BaseModel`, so the generic model suite's change-log and
    custom-field checks have nothing to check.
    """

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIUsageRecord model."""
        fixtures.create_aiusagerecord()

    def test_the_cost_is_frozen_at_the_price_of_the_day(self):
        """A vendor changing its price must not reprice last quarter."""
        record = models.AIUsageRecord.objects.filter(input_cost__isnull=False).first()
        was = record.input_cost

        ai_model = record.model
        ai_model.input_cost_per_million = "99.0000"
        ai_model.validated_save()

        record.refresh_from_db()
        self.assertEqual(record.input_cost, was)

    def test_the_cost_follows_the_price_and_the_token_count(self):
        """A million tokens costs the recorded price, so 1200 costs a thousandth of it."""
        threads = fixtures.create_aiagentthread()
        ai_model = models.AIModel.objects.filter(kind=AIModelKindChoices.CHAT).first()
        ai_model.input_cost_per_million = "10.0000"
        ai_model.output_cost_per_million = "30.0000"
        ai_model.validated_save()

        record = usage.record(threads[0], threads[0].agent, ai_model, input_tokens=500_000, output_tokens=100_000)
        self.assertEqual(record.input_cost, Decimal("5.0000"))
        self.assertEqual(record.output_cost, Decimal("3.0000"))
        self.assertEqual(record.total_cost, Decimal("8.0000"))

    def test_an_unpriced_model_records_no_cost(self):
        """Empty means nobody recorded a price. It does not mean free."""
        record = models.AIUsageRecord.objects.filter(input_cost__isnull=True).first()
        self.assertIsNone(record.input_cost)
        self.assertIsNone(record.total_cost)
        self.assertGreater(record.total_tokens, 0)

    def test_total_tokens_is_not_stored(self):
        """The provider's own figure is in the payload, and it does not always equal the sum."""
        record = models.AIUsageRecord.objects.first()
        self.assertEqual(record.total_tokens, record.input_tokens + record.output_tokens)

    def test_a_subagent_call_is_attributed_to_the_subagent(self):
        """The model actually called is not always the thread agent's model."""
        threads = fixtures.create_aiagentthread()
        specialist = models.AIAgent.objects.exclude(pk=threads[0].agent_id).first()
        record = usage.record(threads[0], specialist, specialist.model, input_tokens=10)
        self.assertEqual(record.agent, specialist)
        self.assertNotEqual(record.agent, threads[0].agent)

    def test_deleting_a_thread_deletes_its_usage(self):
        """Retention deletes threads, and PROTECT here would make that Job fail."""
        thread = models.AIUsageRecord.objects.first().thread
        thread.delete()
        self.assertEqual(models.AIUsageRecord.objects.filter(thread_id=thread.pk).count(), 0)

    def test_the_model_is_protected_while_a_record_names_it(self):
        """A model cannot be deleted out from under its own cost history."""
        record = models.AIUsageRecord.objects.first()
        with self.assertRaises(ProtectedError):
            record.model.delete()


class TestAIAgentThread(ModelTestCases.BaseModelTestCase):
    """Test AIAgentThread."""

    model = models.AIAgentThread

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIAgentThread model."""
        super().setUpTestData()
        fixtures.create_aiagentthread()

    def test_a_thread_gets_an_identifier_of_its_own(self):
        """The thread_id is what LangGraph checkpoints under, and it is a UUID for a stated reason."""
        thread = models.AIAgentThread.objects.first()
        self.assertIsNotNone(thread.thread_id)
        self.assertLess(len(str(thread.thread_id)), 255)

    def test_two_threads_do_not_share_an_identifier(self):
        """Two threads sharing one id would share one checkpoint lineage."""
        identifiers = set(models.AIAgentThread.objects.values_list("thread_id", flat=True))
        self.assertEqual(len(identifiers), models.AIAgentThread.objects.count())

    def test_is_live_covers_waiting(self):
        """A thread paused at an interrupt has not finished; somebody has to answer it."""
        waiting = models.AIAgentThread.objects.get(status=AIAgentThreadStatusChoices.WAITING)
        self.assertTrue(waiting.is_live)

        done = models.AIAgentThread.objects.get(status=AIAgentThreadStatusChoices.COMPLETED)
        self.assertFalse(done.is_live)

    def test_a_thread_is_change_logged(self):
        """A thread changes state two or three times a run, which the change log can carry.

        The per-call records a consuming app keeps are the ones that cannot be logged. A thread is not
        one of them, and an OrganizationalModel makes every generic Nautobot surface work on it.
        """
        self.assertTrue(hasattr(models.AIAgentThread.objects.first(), "to_objectchange"))

    def test_the_agent_is_protected_while_a_thread_records_it(self):
        """History outlives a tidy-up of the registry."""
        thread = models.AIAgentThread.objects.first()
        with self.assertRaises(ProtectedError):
            thread.agent.delete()  # pylint: disable=no-member
