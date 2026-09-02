"""Test the agent builder.

The builder claims that it assembles and does not run. These tests make that claim checkable:
they build agents and assert that nothing was called.

No test here needs LangChain installed. Each test either reads a function that does not touch
it, or asserts the refusal a deployment without the extra gets.
"""

import ast
import uuid
from pathlib import Path
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from nautobot.apps.testing import TestCase
from nautobot.extras.models import Job

from nautobot_ai_models.choices import AIProviderTypeChoices, MCPTransportChoices
from nautobot_ai_models.models import AIAgent, AIAgentTool, AITool
from nautobot_ai_models.services import agents
from nautobot_ai_models.tests import fixtures

SERVICE_PATH = Path(agents.__file__)


class BuildingRunsNothingTest(TestCase):
    """Rule G1: `build_agent()` opens no socket, writes no row and calls no model."""

    def test_only_the_subagent_wrapper_calls_anything(self):
        """One `invoke` in the module, and it sits inside a function the supervisor calls later.

        This test reads the source instead of an assertion at run time. The point is that no code path
        reaches a model, and a run-time assertion covers only the paths a test takes.
        """
        tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))
        callers = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("invoke", "ainvoke", "stream", "astream")
        ]
        self.assertEqual(len(callers), 1, "Only the subagent wrapper may call a model.")

        wrappers = [
            node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "call_specialist"
        ]
        self.assertEqual(len(wrappers), 1)
        self.assertIn(callers[0], list(ast.walk(wrappers[0])), "The one call must be inside the wrapper.")

    def test_building_writes_nothing(self):
        """A build of an agent is a read. A build that wrote a row would be a build with a history.

        One function may write, and this test names it. `_start_or_submit` runs when a model calls a
        Job tool, which is a run and not a build. It creates a ScheduledJob to ask whether an approval
        workflow applies, which is the only way to ask, and deletes it again when none does. This test
        reads the source, so the claim covers every path.
        """
        tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))
        writes = {"create", "get_or_create", "update_or_create", "bulk_create", "update", "save", "delete"}
        allowed = "_start_or_submit"

        at_run_time = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == allowed:
                at_run_time = {inner for inner in ast.walk(node)}

        offenders = [
            f"line {node.lineno} calls .{node.func.attr}()"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in writes
            and node not in at_run_time
        ]
        self.assertEqual(offenders, [], "The builder writes nothing. Offending lines: " + ", ".join(offenders))
        self.assertTrue(at_run_time, f"{allowed} is gone; this test now permits nothing and proves less.")

    def test_the_one_writing_function_is_only_reached_when_a_tool_is_called(self):
        """`_start_or_submit` is what the guard above excuses, so where it is called from matters."""
        tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))
        callers = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
                    if inner.func.id == "_start_or_submit":
                        callers.append(node.name)

        self.assertEqual(callers, ["start_job"], "Only the Job tool's own body may reach it.")

    def test_langchain_is_imported_lazily(self):
        """Rule G2. A module-level import would make the extra mandatory for every deployment."""
        tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                name = getattr(node, "module", "") or ""
                names = [alias.name for alias in node.names]
                self.assertFalse(
                    name.startswith("lang") or any(alias.startswith("lang") for alias in names),
                    f"line {node.lineno} imports LangChain at module level",
                )


class WireNameTest(TestCase):
    """Rule G5: one name, one tool, within one agent."""

    @classmethod
    def setUpTestData(cls):
        """Create an agent with tools bound from both sources."""
        fixtures.create_aiagenttool()

    def test_the_binding_decides_the_name(self):
        """Rule G4. An override is what an operator has to fix a badly-read name with."""
        agent = AIAgent.objects.get(name="Test Supervisor")
        names = agents.named_bindings(agent)
        self.assertIn("find_device", names)

    def test_two_sources_sharing_a_name_are_separated(self):
        """A model offered two tools of one name has no way to say which it meant."""
        agent = AIAgent.objects.get(name="Test Supervisor")
        binding = AIAgentTool.objects.filter(agent=agent, mcp_tool__isnull=False).first()
        clash = AITool.objects.exclude(agent_bindings__agent=agent).first()
        AIAgentTool.objects.create(agent=agent, ai_tool=clash, name_override=binding.mcp_tool.name)

        names = agents.named_bindings(agent)

        self.assertIn(f"{binding.mcp_tool.name}_2", names)

    def test_an_unusable_character_is_replaced(self):
        """A wire name is what goes into a tool schema, and not every string is one."""
        agent = AIAgent.objects.get(name="Test Supervisor")
        binding = AIAgentTool.objects.filter(agent=agent).first()
        binding.name_override = "get device/status"
        binding.save()

        self.assertIn("get_device_status", agents.named_bindings(agent))

    def test_a_disabled_tool_is_not_offered(self):
        """A model that is never told about a tool cannot ask for it."""
        agent = AIAgent.objects.get(name="Test Supervisor")
        before = len(agents.tool_bindings(agent))
        AITool.objects.filter(name="lookup_device").update(enabled=False)

        self.assertEqual(len(agents.tool_bindings(agent)), before - 1)


class MCPBindingsTest(TestCase):
    """Rule G7: this module builds no MCP tool, and says which ones a caller has to build."""

    @classmethod
    def setUpTestData(cls):
        """Create an agent with tools bound from both sources."""
        fixtures.create_aiagenttool()

    def test_mcp_bindings_are_handed_back_rather_than_built(self):
        """Calling one needs a gate this app does not own."""
        agent = AIAgent.objects.get(name="Test Supervisor")
        bindings = agents.mcp_bindings(agent)

        self.assertTrue(bindings)
        for binding in bindings.values():
            self.assertIsNotNone(binding.mcp_tool_id)

    def test_the_names_match_the_ones_the_builder_allocated(self):
        """Otherwise a caller's tool and the builder's could collide under one agent."""
        agent = AIAgent.objects.get(name="Test Supervisor")
        allocated = agents.named_bindings(agent)

        for name, binding in agents.mcp_bindings(agent).items():
            self.assertEqual(allocated[name], binding)

    def test_a_transport_that_cannot_be_reached_is_refused(self):
        """The registry catalogs `sse` and `stdio`. Nautobot reaches neither."""
        agent = AIAgent.objects.get(name="Test Supervisor")
        binding = AIAgentTool.objects.filter(agent=agent, mcp_tool__isnull=False).first()
        server = binding.mcp_tool.mcp_server
        server.transport = MCPTransportChoices.TYPE_STDIO
        server.save()

        with self.assertRaises(agents.AgentBuildError) as raised:
            agents.mcp_bindings(agent)
        self.assertIn("stdio", str(raised.exception))


class RefusalTest(TestCase):
    """Rule G3, and the refusals that come before anything is assembled."""

    @classmethod
    def setUpTestData(cls):
        """Create an agent to disable pieces of."""
        fixtures.create_aiagent()

    def test_a_disabled_agent_is_refused(self):
        """Nothing is built, so nothing could have run."""
        agent = AIAgent.objects.get(name="Test Supervisor")
        agent.enabled = False
        agent.save()

        with self.assertRaises(agents.AgentBuildError):
            agents.build_agent(agent)

    def test_a_disabled_model_is_refused(self):
        """The same check `AIModel.is_available` describes, made before the build."""
        agent = AIAgent.objects.get(name="Test Supervisor")
        agent.model.enabled = False
        agent.model.save()

        with self.assertRaises(agents.AgentBuildError):
            agents.build_agent(agent)

    def test_a_disabled_provider_is_refused(self):
        """A disabled provider takes every agent on it out of service."""
        agent = AIAgent.objects.get(name="Test Supervisor")
        agent.model.provider.enabled = False
        agent.model.provider.save()

        with self.assertRaises(agents.AgentBuildError):
            agents.build_agent(agent)

    def test_a_missing_extra_is_a_plain_configuration_error(self):
        """A deployment without LangChain gets a sentence naming the extra, not an ImportError."""
        with mock.patch.dict("sys.modules", {"langchain": None, "langchain.agents": None}):
            with self.assertRaises(ImproperlyConfigured) as raised:
                agents.require_langchain()
        self.assertIn("agents", str(raised.exception))


class ChatModelTest(TestCase):
    """What `chat_model_for` reads before it builds a client."""

    @classmethod
    def setUpTestData(cls):
        """Create the providers and models."""
        fixtures.create_aimodel()

    def test_an_addressed_provider_needs_a_url(self):
        """Ollama is an address, not a service. Without one a client falls back elsewhere."""
        from nautobot_ai_models.models import AIModel  # pylint: disable=import-outside-toplevel

        model = AIModel.objects.filter(provider__provider_type=AIProviderTypeChoices.OLLAMA).first()
        integration = model.provider.external_integration
        integration.remote_url = ""
        integration.save()

        with self.assertRaises(agents.AgentBuildError) as raised:
            agents.chat_model_for(model)
        self.assertIn("remote URL", str(raised.exception))

    def test_every_recorded_dialect_has_a_client(self):
        """A provider type with no builder is an agent that cannot be addressed at all."""
        for value, _ in AIProviderTypeChoices.CHOICES:
            self.assertIn(value, agents._CHAT_MODEL_BUILDERS)  # pylint: disable=protected-access


class JobRefusalTest(TestCase):
    """Test the gate on a Job tool.

    `JobResult.enqueue_job` checks nothing: no `extras.run_job` permission, no `Job.enabled` flag,
    and no approval workflow. All three live in Nautobot's own run view, and this path does not go
    through that view, so the tool checks them itself.
    """

    @classmethod
    def setUpTestData(cls):
        """Find a Job to bind, and two users to try it as."""
        cls.job = Job.objects.filter(installed=True).first()
        cls.permitted = mock.Mock(spec=["has_perm"])
        cls.permitted.has_perm.return_value = True
        cls.refused = mock.Mock(spec=["has_perm"])
        cls.refused.has_perm.return_value = False

    def test_a_permitted_user_and_a_runnable_job_are_not_refused(self):
        """The ordinary case has to survive every check."""
        self.job.enabled = True

        self.assertIsNone(agents._job_refusal(self.job, self.permitted))  # pylint: disable=protected-access

    def test_a_disabled_job_is_refused(self):
        """Disabled is how an administrator takes a Job out of service, and how every Job arrives."""
        self.job.enabled = False

        refusal = agents._job_refusal(self.job, self.permitted)  # pylint: disable=protected-access

        self.assertIsNotNone(refusal)
        self.assertIn("disabled", refusal)

    def test_a_user_without_the_run_permission_is_refused(self):
        """Otherwise binding a tool would be a way around `extras.run_job`."""
        self.job.enabled = True

        refusal = agents._job_refusal(self.job, self.refused)  # pylint: disable=protected-access

        self.assertIsNotNone(refusal)
        self.assertIn("permission", refusal)
        self.refused.has_perm.assert_called_once_with("extras.run_job", self.job)

    def test_a_job_taking_sensitive_variables_is_refused(self):
        """A model would have to be handed the secret to fill them in."""
        self.job.enabled = True
        self.job.has_sensitive_variables = True

        refusal = agents._job_refusal(self.job, self.permitted)  # pylint: disable=protected-access

        self.assertIsNotNone(refusal)
        self.assertIn("sensitive", refusal)

    def test_a_job_needing_approval_is_submitted_rather_than_started(self):
        """An approval workflow that an agent could walk past is not an approval workflow."""
        scheduled = mock.Mock()
        scheduled.has_approval_workflow_definition.return_value = True
        scheduled.pk = uuid.uuid4()

        with mock.patch("nautobot.extras.models.ScheduledJob.create_schedule", return_value=scheduled):
            answer = agents._start_or_submit(self.job, self.permitted)  # pylint: disable=protected-access

        self.assertIn("approve", answer)
        scheduled.delete.assert_not_called()

    def test_a_job_needing_no_approval_is_started(self):
        """The schedule exists only to ask the question, so it goes again once it is answered."""
        scheduled = mock.Mock()
        scheduled.has_approval_workflow_definition.return_value = False
        job_result = mock.Mock(pk=uuid.uuid4())

        with mock.patch("nautobot.extras.models.ScheduledJob.create_schedule", return_value=scheduled):
            with mock.patch("nautobot.extras.models.JobResult.enqueue_job", return_value=job_result) as enqueued:
                answer = agents._start_or_submit(self.job, self.permitted)  # pylint: disable=protected-access

        self.assertIn("Started", answer)
        scheduled.delete.assert_called_once()
        enqueued.assert_called_once_with(self.job, self.permitted)


class UniqueToolNameTest(TestCase):
    """Rule G5, across every source of a tool rather than within the tool bindings."""

    @classmethod
    def setUpTestData(cls):
        """Create an agent with tools bound."""
        fixtures.create_aiagenttool()

    def test_two_tools_of_one_name_are_refused(self):
        """A model offered both has no way to say which it meant."""
        agent = AIAgent.objects.get(name="Test Supervisor")
        clash = [mock.Mock(name="first"), mock.Mock(name="second")]
        for each in clash:
            each.name = "lookup_device"

        with self.assertRaises(agents.AgentBuildError) as raised:
            agents._check_names_are_unique(agent, clash)  # pylint: disable=protected-access

        self.assertIn("lookup_device", str(raised.exception))

    def test_a_list_with_no_repeat_passes(self):
        """The check must not refuse an ordinary build."""
        agent = AIAgent.objects.get(name="Test Supervisor")
        fine = [mock.Mock(), mock.Mock()]
        fine[0].name, fine[1].name = "one", "two"

        agents._check_names_are_unique(agent, fine)  # pylint: disable=protected-access

    def test_a_second_specialist_of_one_name_is_separated(self):
        """`(parent, subagent)` is unique and `tool_name` is not, so two can carry one name."""
        taken = {"expert"}

        self.assertEqual(agents.wire_unique("expert", "specialist", taken), "expert_2")
