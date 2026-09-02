"""Test the registry filtersets."""

from nautobot.apps.testing import FilterTestCases
from nautobot.extras.models import GitRepository

from nautobot_ai_models import filters, models
from nautobot_ai_models.choices import (
    AIAgentThreadStatusChoices,
    AIModelKindChoices,
    AIToolKindChoices,
    SubagentInputModeChoices,
)
from nautobot_ai_models.tests import fixtures
from nautobot_ai_models.tests.scaffolding import (
    COMMON_FILTER_TESTS,
    COMMON_FILTER_TESTS_WITH_DESCRIPTION,
)


class AIProviderFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """AIProvider Filter Test Case."""

    queryset = models.AIProvider.objects.all()
    filterset = filters.AIProviderFilterSet
    generic_filter_tests = (
        *COMMON_FILTER_TESTS_WITH_DESCRIPTION,
        ("external_integration", "external_integration__id"),
        ("external_integration", "external_integration__name"),
        ("provider_type",),
    )

    @classmethod
    def setUpTestData(cls):
        """Set up test data for the AIProvider model."""
        fixtures.create_ai_provider()

    def test_q_search_name(self):
        """Test using Q search with the name of a AIProvider."""
        params = {"q": "Test One"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_q_invalid(self):
        """Test using an invalid Q search for a AIProvider."""
        params = {"q": "test-five"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 0)

    def test_openai_compatible(self):
        """Filter on the OpenAI-compatible boolean."""
        provider = models.AIProvider.objects.first()
        provider.openai_compatible = False
        provider.validated_save()
        params = {"openai_compatible": True}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), self.queryset.count() - 1)

    def test_enabled(self):
        """A consuming app filters on this before anything else."""
        provider = models.AIProvider.objects.first()
        provider.enabled = False
        provider.validated_save()

        self.assertEqual(self.filterset({"enabled": True}, self.queryset).qs.count(), 2)
        self.assertEqual(self.filterset({"enabled": False}, self.queryset).qs.count(), 1)


class AIModelFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """AIModel Filter Test Case."""

    queryset = models.AIModel.objects.all()
    filterset = filters.AIModelFilterSet
    generic_filter_tests = (
        *COMMON_FILTER_TESTS_WITH_DESCRIPTION,
        ("provider", "provider__id"),
        ("provider", "provider__name"),
    )

    @classmethod
    def setUpTestData(cls):
        """Set up test data for the AIModel model."""
        fixtures.create_aimodel()

    def test_q_search_name(self):
        """Test using Q search with the name of an AIModel."""
        params = {"q": "Test One"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_enabled(self):
        """Filter on the enabled boolean."""
        ai_model = models.AIModel.objects.first()
        ai_model.enabled = False
        ai_model.validated_save()
        params = {"enabled": False}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_provider_enabled(self):
        """A consuming app asks for the models on offer in one query."""
        provider = models.AIProvider.objects.get(name="Test One")
        provider.enabled = False
        provider.validated_save()

        params = {"enabled": True, "provider_enabled": True}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_default_parameters_are_filterable(self):
        """Nautobot maps a JSONField to a case-insensitive contains filter."""
        ai_model = models.AIModel.objects.get(name="Test One")
        ai_model.default_parameters = {"seed": 7}
        ai_model.validated_save()

        self.assertEqual(self.filterset({"default_parameters": ["seed"]}, self.queryset).qs.count(), 1)

    def test_kind(self):
        """Split the chat models from the embedding models.

        This is a named test rather than a generic filter test. `AIModelKindChoices` has two values,
        and the generic case wants three distinct ones.
        """
        self.assertEqual(self.filterset({"kind": [AIModelKindChoices.EMBEDDING]}, self.queryset).qs.count(), 1)
        self.assertEqual(self.filterset({"kind": [AIModelKindChoices.CHAT]}, self.queryset).qs.count(), 2)


class MCPServerFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """MCPServer Filter Test Case."""

    queryset = models.MCPServer.objects.all()
    filterset = filters.MCPServerFilterSet
    generic_filter_tests = (
        *COMMON_FILTER_TESTS_WITH_DESCRIPTION,
        ("transport",),
        ("external_integration", "external_integration__name"),
    )

    @classmethod
    def setUpTestData(cls):
        """Set up test data for the MCPServer model.

        One of the three servers gets a tool, so the generic `has_tools` test has a non-empty result
        on both sides of the boolean.
        """
        cls.servers = fixtures.create_mcpserver()
        models.MCPTool.objects.create(mcp_server=cls.servers[0], name="only_on_the_first_server")

    def test_q_search_name(self):
        """Test using Q search with name of MCPServer."""
        params = {"q": "Test One"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_q_invalid(self):
        """Test using invalid Q search for MCPServer."""
        params = {"q": "test-five"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 0)

    def test_enabled(self):
        """A consuming app filters on this before anything else."""
        server = self.servers[0]
        server.enabled = False
        server.validated_save()

        self.assertEqual(self.filterset({"enabled": True}, self.queryset).qs.count(), 2)
        self.assertEqual(self.filterset({"enabled": False}, self.queryset).qs.count(), 1)

    def test_has_tools(self):
        """Whether a server has ever been discovered successfully, asked the short way."""
        self.assertEqual(self.filterset({"has_tools": True}, self.queryset).qs.count(), 1)
        self.assertEqual(self.filterset({"has_tools": False}, self.queryset).qs.count(), 2)


class MCPToolFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """MCPTool Filter Test Case."""

    queryset = models.MCPTool.objects.all()
    filterset = filters.MCPToolFilterSet
    generic_filter_tests = (
        *COMMON_FILTER_TESTS,
        ("title",),
        ("mcp_server", "mcp_server__name"),
    )

    @classmethod
    def setUpTestData(cls):
        """Setup test data for MCPTool Model."""
        fixtures.create_mcptool()

    def test_q_search_description(self):
        """Test using Q search against the description."""
        params = {"q": "Change one interface"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_enabled(self):
        """The gate a consuming app reads first."""
        self.assertEqual(self.filterset({"enabled": True}, self.queryset).qs.count(), 2)
        self.assertEqual(self.filterset({"enabled": False}, self.queryset).qs.count(), 1)

    def test_writable(self):
        """ "Which of these only read" has to be one query."""
        self.assertEqual(self.filterset({"writable": False}, self.queryset).qs.count(), 1)
        self.assertEqual(self.filterset({"writable": True}, self.queryset).qs.count(), 2)

    def test_enabled_and_read_only_together(self):
        """The query a consuming app actually writes."""
        params = {"enabled": True, "writable": False}
        results = self.filterset(params, self.queryset).qs
        self.assertEqual([tool.name for tool in results], ["get_device"])

    def test_advertised_read_only_keeps_three_states(self):
        """Unset means the server claimed nothing, which is not the same as claiming it writes."""
        self.assertEqual(self.filterset({"advertised_read_only": True}, self.queryset).qs.count(), 1)
        self.assertEqual(self.filterset({"advertised_read_only": False}, self.queryset).qs.count(), 1)
        self.assertEqual(self.queryset.filter(advertised_read_only__isnull=True).count(), 1)


class AIToolFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """AITool Filter Test Case."""

    queryset = models.AITool.objects.all()
    filterset = filters.AIToolFilterSet
    generic_filter_tests = COMMON_FILTER_TESTS_WITH_DESCRIPTION

    @classmethod
    def setUpTestData(cls):
        """Set up test data for the AITool model."""
        fixtures.create_aitool()

    def test_the_review_queue_is_one_query(self):
        """`enabled=False` is what `new_tools_enabled: False` leaves behind."""
        self.assertEqual(self.filterset({"enabled": False}, self.queryset).qs.count(), 1)

    def test_read_only_and_enabled_together(self):
        """The query a consuming app writes when it wants a safe tool list."""
        params = {"enabled": True, "writable": False}
        results = self.filterset(params, self.queryset).qs
        self.assertEqual([tool.name for tool in results], ["lookup_device"])

    def test_tools_can_be_listed_by_the_repository_they_came_from(self):
        """What one Git repository gave us, which is a question its own page cannot answer."""
        repository = GitRepository(
            name="Filter Test Tools",
            slug="filter_test_tools",
            remote_url="https://example.com/tools.git",
        )
        repository.save()
        models.AITool.objects.create(
            name="from_a_repository",
            description="Declared in a repository.",
            kind=AIToolKindChoices.GIT,
            git_repository=repository,
        )

        results = self.filterset({"git_repository": [repository.name]}, self.queryset).qs

        self.assertEqual([tool.name for tool in results], ["from_a_repository"])


class AIAgentFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """AIAgent Filter Test Case."""

    queryset = models.AIAgent.objects.all()
    filterset = filters.AIAgentFilterSet
    generic_filter_tests = COMMON_FILTER_TESTS_WITH_DESCRIPTION

    @classmethod
    def setUpTestData(cls):
        """Set up test data for the AIAgent model."""
        fixtures.create_aiagentsubagent()

    def test_filtering_by_model_name(self):
        """Which agents run on this model is the question a model page asks."""
        name = models.AIModel.objects.filter(kind=AIModelKindChoices.CHAT).first().name
        results = self.filterset({"model": [name]}, self.queryset).qs
        self.assertTrue(results.exists())
        for agent in results:
            self.assertEqual(agent.model.name, name)

    def test_has_subagents(self):
        """Which agents are supervisors, without reading every binding."""
        supervisors = {binding.parent_id for binding in models.AIAgentSubagent.objects.all()}
        self.assertEqual(self.filterset({"has_subagents": True}, self.queryset).qs.count(), len(supervisors))


class AIAgentToolFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """AIAgentTool Filter Test Case."""

    queryset = models.AIAgentTool.objects.all()
    filterset = filters.AIAgentToolFilterSet
    generic_filter_tests = (("id",), ("created",), ("last_updated",), ("weight",))

    @classmethod
    def setUpTestData(cls):
        """Set up test data for the AIAgentTool model."""
        fixtures.create_aiagenttool()

    def test_filtering_by_agent(self):
        """What may this agent call is the panel on its own page."""
        agent = models.AIAgent.objects.get(name="Test Supervisor")
        self.assertEqual(
            self.filterset({"agent": [agent.name]}, self.queryset).qs.count(),
            self.queryset.filter(agent=agent).count(),
        )

    def test_filtering_by_tool_answers_the_other_direction(self):
        """Which agents may call this tool is the panel on the tool's page."""
        tool = models.AITool.objects.get(name="lookup_device")
        self.assertEqual(self.filterset({"ai_tool": [tool.name]}, self.queryset).qs.count(), 1)


class AIAgentSubagentFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """AIAgentSubagent Filter Test Case."""

    queryset = models.AIAgentSubagent.objects.all()
    filterset = filters.AIAgentSubagentFilterSet
    generic_filter_tests = (("id",), ("created",), ("last_updated",), ("weight",))

    @classmethod
    def setUpTestData(cls):
        """Set up test data for the AIAgentSubagent model."""
        fixtures.create_aiagentsubagent()

    def test_filtering_by_supervisor(self):
        """Which specialists this supervisor has."""
        parent = models.AIAgent.objects.get(name="Test Supervisor")
        self.assertEqual(
            self.filterset({"parent": [parent.name]}, self.queryset).qs.count(),
            self.queryset.filter(parent=parent).count(),
        )

    def test_the_default_input_mode_is_the_task_alone(self):
        """The measured-safe default, checked through the filter that reports it."""
        results = self.filterset({"input_mode": [SubagentInputModeChoices.TASK_ONLY]}, self.queryset).qs
        self.assertEqual(results.count(), self.queryset.filter(input_mode=SubagentInputModeChoices.TASK_ONLY).count())
        self.assertGreater(results.count(), 0)


class AISkillFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """AISkill Filter Test Case."""

    queryset = models.AISkill.objects.all()
    filterset = filters.AISkillFilterSet
    generic_filter_tests = COMMON_FILTER_TESTS_WITH_DESCRIPTION

    @classmethod
    def setUpTestData(cls):
        """Set up test data for the AISkill model."""
        fixtures.create_aiagentskill()

    def test_has_agents(self):
        """A skill nothing loads is a skill nobody is using."""
        bound = {binding.skill_id for binding in models.AIAgentSkill.objects.all()}
        self.assertEqual(self.filterset({"has_agents": True}, self.queryset).qs.count(), len(bound))
        self.assertEqual(
            self.filterset({"has_agents": False}, self.queryset).qs.count(),
            self.queryset.exclude(pk__in=bound).count(),
        )


class AIAgentSkillFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """AIAgentSkill Filter Test Case."""

    queryset = models.AIAgentSkill.objects.all()
    filterset = filters.AIAgentSkillFilterSet
    generic_filter_tests = (("id",), ("created",), ("last_updated",), ("weight",))

    @classmethod
    def setUpTestData(cls):
        """Set up test data for the AIAgentSkill model."""
        fixtures.create_aiagentskill()

    def test_filtering_by_agent(self):
        """Which skills this agent may load."""
        agent = models.AIAgent.objects.get(name="Test Skills Agent")
        self.assertEqual(
            self.filterset({"agent": [agent.name]}, self.queryset).qs.count(),
            self.queryset.filter(agent=agent).count(),
        )


class AIAgentThreadFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """AIAgentThread Filter Test Case."""

    queryset = models.AIAgentThread.objects.all()
    filterset = filters.AIAgentThreadFilterSet
    generic_filter_tests = (("id",), ("status",))

    @classmethod
    def setUpTestData(cls):
        """Set up test data for the AIAgentThread model."""
        fixtures.create_aiagentthread()

    def test_waiting_is_the_queue_that_matters(self):
        """Every thread paused at an interrupt with nobody answering it."""
        results = self.filterset({"status": [AIAgentThreadStatusChoices.WAITING]}, self.queryset).qs
        self.assertEqual(results.count(), 1)
        self.assertTrue(results.first().is_live)
