"""Unit tests for the nautobot_ai_models REST API."""

from nautobot.apps.testing import APIViewTestCases
from nautobot.extras.models import Job

from nautobot_ai_models import models
from nautobot_ai_models.api.serializers import AIToolSerializer
from nautobot_ai_models.choices import (
    AIAgentPatternChoices,
    AIAgentThreadStatusChoices,
    AIModelKindChoices,
    AIProviderTypeChoices,
    AIToolKindChoices,
    MCPTransportChoices,
    SubagentInputModeChoices,
)
from nautobot_ai_models.tests import fixtures
from nautobot_ai_models.tests.scaffolding import RegistryAPIPayloadsMixin


class AIProviderAPIViewTest(RegistryAPIPayloadsMixin, APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for AIProvider."""

    model = models.AIProvider
    choices_fields = ["provider_type"]

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIProvider API viewset."""
        super().setUpTestData()
        fixtures.create_ai_provider()
        integration = fixtures.create_external_integration()
        cls.build_api_payloads(
            {"external_integration": integration.pk, "provider_type": AIProviderTypeChoices.OPENAI},
            [
                {},
                {"openai_compatible": False, "provider_type": AIProviderTypeChoices.ANTHROPIC},
                {"num_predict": 512, "enabled": False},
            ],
        )


class AIModelAPIViewTest(RegistryAPIPayloadsMixin, APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for AIModel."""

    model = models.AIModel
    choices_fields = ["kind"]

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIModel API viewset."""
        super().setUpTestData()
        fixtures.create_aimodel()
        provider = models.AIProvider.objects.get(name="Test Three")
        cls.build_api_payloads(
            {"provider": provider.pk},
            [
                {},
                {"enabled": False, "kind": AIModelKindChoices.EMBEDDING},
                {"num_predict": 1024, "default_parameters": {"seed": 7, "top_p": 0.9}},
            ],
        )

    def test_a_parameter_outside_the_allowlist_is_refused(self):
        """A key that could change which host answers must not reach the column over the API."""
        self.add_permissions("nautobot_ai_models.change_aimodel")
        ai_model = models.AIModel.objects.first()

        response = self.client.patch(
            self._get_detail_url(ai_model),
            {"default_parameters": {"base_url": "https://attacker.example.com/v1"}},
            format="json",
            **self.header,
        )

        self.assertHttpStatus(response, 400)
        ai_model.refresh_from_db()
        self.assertEqual(ai_model.default_parameters, {})


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


class AIToolAPIViewTest(APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for AITool.

    No create test. The Sync AI Tools Job writes a tool from what the code declared, and every
    field the Job owns is read-only over the API.
    """

    model = models.AITool
    choices_fields = ["kind"]
    update_data = {"enabled": True, "writable": False}
    bulk_update_data = {"enabled": False}

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AITool API viewset.

        The payloads are Job tools, because a Job tool is the one kind an operator creates. The Sync AI
        Tools Job writes a registered tool, and `AITool.clean()` refuses one whose name nothing
        registered.
        """
        super().setUpTestData()
        fixtures.create_aitool()
        jobs = list(Job.objects.all()[:3])
        cls.create_data = [
            {
                "name": f"api_test_job_tool_{index}",
                "description": f"Start the {job.name} Job. It does not wait for the result.",
                "kind": AIToolKindChoices.JOB,
                "job": job.pk,
            }
            for index, job in enumerate(jobs)
        ]

    def test_what_discovery_wrote_is_read_only(self):
        """The Sync AI Tools Job would overwrite a change to any of these on its next run."""
        serializer = AIToolSerializer(context={"request": None})
        for field in ("advertised_read_only", "definition_fingerprint", "last_seen_at"):
            self.assertTrue(serializer.fields[field].read_only, f"{field} should be read-only")


class AIAgentAPIViewTest(RegistryAPIPayloadsMixin, APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for AIAgent."""

    model = models.AIAgent
    choices_fields = ["pattern"]

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIAgent API viewset."""
        super().setUpTestData()
        fixtures.create_aiagent()
        chat = models.AIModel.objects.filter(kind=AIModelKindChoices.CHAT).first()
        cls.build_api_payloads(
            {"model": chat.pk, "system_prompt": "You answer from tools only."},
            [
                {},
                {"pattern": AIAgentPatternChoices.SINGLE, "max_iterations": 4},
                {"enabled": False, "max_iterations": 12},
            ],
        )


class AIAgentToolAPIViewTest(APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for AIAgentTool."""

    model = models.AIAgentTool
    bulk_update_data = {"weight": 250}

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIAgentTool API viewset."""
        super().setUpTestData()
        fixtures.create_aiagenttool()
        agent = models.AIAgent.objects.get(name="Test Skills Agent")
        tools = list(models.AITool.objects.order_by("name"))
        cls.create_data = [
            {"agent": agent.pk, "ai_tool": tools[0].pk},
            {"agent": agent.pk, "ai_tool": tools[1].pk, "name_override": "second"},
            {"agent": agent.pk, "ai_tool": tools[2].pk, "weight": 300},
        ]
        cls.update_data = {"name_override": "renamed", "weight": 175}

    def test_the_resolved_values_are_returned(self):
        """A client checking what an agent offers should not have to work these out again."""
        binding = models.AIAgentTool.objects.filter(ai_tool__isnull=False).first()
        self.add_permissions("nautobot_ai_models.view_aiagenttool")
        response = self.client.get(self._get_detail_url(binding), **self.header)
        self.assertHttpStatus(response, 200)
        for key in ("wire_name", "wire_description", "writable", "fingerprint"):
            self.assertIn(key, response.data)


class AIAgentSubagentAPIViewTest(APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for AIAgentSubagent."""

    model = models.AIAgentSubagent
    choices_fields = ["input_mode"]
    bulk_update_data = {"weight": 250}

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIAgentSubagent API viewset."""
        super().setUpTestData()
        fixtures.create_aiagentsubagent()
        chat = models.AIModel.objects.filter(kind=AIModelKindChoices.CHAT).first()
        specialists = [
            models.AIAgent.objects.create(
                name=f"API Specialist {index}",
                description=f"Answers question {index}. Give it a hostname.",
                system_prompt="You answer from tools only.",
                model=chat,
            )
            for index in range(3)
        ]
        supervisor = models.AIAgent.objects.get(name="Test Supervisor")
        cls.create_data = [
            {"parent": supervisor.pk, "subagent": specialists[0].pk},
            {"parent": supervisor.pk, "subagent": specialists[1].pk, "tool_name": "second_expert"},
            {
                "parent": supervisor.pk,
                "subagent": specialists[2].pk,
                "input_mode": SubagentInputModeChoices.TASK_AND_CONTEXT,
            },
        ]
        cls.update_data = {"tool_name": "renamed_expert", "weight": 175}


class AISkillAPIViewTest(RegistryAPIPayloadsMixin, APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for AISkill."""

    model = models.AISkill

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AISkill API viewset."""
        super().setUpTestData()
        fixtures.create_aiskill()
        cls.build_api_payloads(
            {"body": "Call the tool. Report what it said."},
            [{}, {"enabled": False}, {"body": "A different rule."}],
        )


class AIAgentSkillAPIViewTest(APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for AIAgentSkill."""

    model = models.AIAgentSkill
    bulk_update_data = {"weight": 250}

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIAgentSkill API viewset."""
        super().setUpTestData()
        fixtures.create_aiagentskill()
        agent = models.AIAgent.objects.get(name="Test Inventory Specialist")
        skills = list(models.AISkill.objects.order_by("name"))
        cls.create_data = [{"agent": agent.pk, "skill": skill.pk} for skill in skills]
        cls.update_data = {"weight": 175}


class AIAgentThreadAPIViewTest(APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for AIAgentThread.

    A consuming app creates a thread over this API when it starts a run. It then reads the
    allocated `thread_id` out of the response and checkpoints under it.
    """

    model = models.AIAgentThread
    choices_fields = ["status"]
    update_data = {"status": AIAgentThreadStatusChoices.FAILED}
    bulk_update_data = {"status": AIAgentThreadStatusChoices.COMPLETED}

    @classmethod
    def setUpTestData(cls):
        """Create test data for the AIAgentThread API viewset."""
        super().setUpTestData()
        agents = fixtures.create_aiagent()
        fixtures.create_aiagentthread()
        cls.create_data = [{"agent": agent.pk} for agent in agents]

    def test_the_server_allocates_the_thread_id(self):
        """A client does not choose it, and has to be told what it is."""
        self.add_permissions("nautobot_ai_models.add_aiagentthread", "nautobot_ai_models.view_aiagent")
        agent = models.AIAgent.objects.first()
        response = self.client.post(self._get_list_url(), {"agent": str(agent.pk)}, format="json", **self.header)
        self.assertHttpStatus(response, 201)
        self.assertIsNotNone(response.data["thread_id"])
