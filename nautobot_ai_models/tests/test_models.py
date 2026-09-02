"""Test the registry models."""

import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
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
