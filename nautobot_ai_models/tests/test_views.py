"""Unit tests for views."""

import uuid

from django.urls import NoReverseMatch, reverse
from nautobot.apps.testing import TestCase, ViewTestCases

from nautobot_ai_models import models
from nautobot_ai_models.choices import (
    AIAgentPatternChoices,
    AIModelKindChoices,
    AIProviderTypeChoices,
    MCPTransportChoices,
    SubagentInputModeChoices,
)
from nautobot_ai_models.tests import fixtures


class AIProviderViewTest(ViewTestCases.OrganizationalObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the AIProvider views."""

    model = models.AIProvider
    bulk_edit_data = {"description": "Bulk edit views", "enabled": False}

    @classmethod
    def setUpTestData(cls):
        """Create test data and the form payloads the generic view tests post."""
        fixtures.create_ai_provider()
        integration = fixtures.create_external_integration()
        cls.form_data = {
            "name": "Test 1",
            "description": "Initial model",
            "external_integration": integration.pk,
            "provider_type": AIProviderTypeChoices.OPENAI,
            "openai_compatible": True,
            "enabled": True,
        }
        cls.update_data = {
            "name": "Test 2",
            "description": "Updated model",
            "external_integration": integration.pk,
            "provider_type": AIProviderTypeChoices.ANTHROPIC,
            "openai_compatible": True,
            "enabled": True,
        }


class AIModelViewTest(ViewTestCases.OrganizationalObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the AIModel views."""

    model = models.AIModel
    bulk_edit_data = {"description": "Bulk edit views", "kind": AIModelKindChoices.EMBEDDING}

    @classmethod
    def setUpTestData(cls):
        """Create test data and the form payloads the generic view tests post."""
        fixtures.create_aimodel()
        provider = models.AIProvider.objects.get(name="Test Three")
        cls.form_data = {
            "provider": provider.pk,
            "name": "Test 1",
            "description": "Initial model",
            "kind": AIModelKindChoices.CHAT,
            "enabled": True,
            "default_parameters": '{"seed": 7}',
        }
        cls.update_data = {
            "provider": provider.pk,
            "name": "Test 2",
            "description": "Updated model",
            "kind": AIModelKindChoices.EMBEDDING,
            "enabled": True,
            "default_parameters": "{}",
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


class AIToolViewTest(ViewTestCases.OrganizationalObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the AITool views.

    The Sync AI Tools Job writes a tool, so there is no add view and the create tests are off. A
    person edits the two flags.
    """

    model = models.AITool
    bulk_edit_data = {"enabled": True}

    test_create_object_with_permission = None
    test_create_object_without_permission = None
    test_create_object_with_constrained_permission = None

    test_bulk_rename_objects_with_permission = None
    test_bulk_rename_objects_with_constrained_permission = None

    @classmethod
    def setUpTestData(cls):
        """Create test data and the form payloads the generic view tests post."""
        fixtures.create_aitool()
        cls.form_data = {"enabled": True, "writable": False}
        cls.update_data = {"enabled": False, "writable": True}


class AIAgentViewTest(ViewTestCases.PrimaryObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the AIAgent views."""

    model = models.AIAgent
    bulk_edit_data = {"description": "Bulk edit views", "enabled": False}

    @classmethod
    def setUpTestData(cls):
        """Create test data and the form payloads the generic view tests post."""
        fixtures.create_aiagent()
        chat = models.AIModel.objects.filter(kind=AIModelKindChoices.CHAT).first()
        cls.form_data = {
            "name": "View Test One",
            "description": "Looks things up. Give it a hostname.",
            "system_prompt": "You answer questions from tools only.",
            "model": chat.pk,
            "pattern": AIAgentPatternChoices.SINGLE,
            "enabled": True,
            "max_iterations": 8,
        }
        cls.update_data = {
            "name": "View Test Two",
            "description": "Updated description.",
            "system_prompt": "You answer questions from tools only, and you say so.",
            "model": chat.pk,
            "pattern": AIAgentPatternChoices.SINGLE,
            "enabled": False,
            "max_iterations": 4,
        }


class AIAgentToolViewTest(ViewTestCases.OrganizationalObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the AIAgentTool views."""

    model = models.AIAgentTool
    bulk_edit_data = {"weight": 200}

    @classmethod
    def setUpTestData(cls):
        """Create test data and the form payloads the generic view tests post."""
        fixtures.create_aiagenttool()
        agent = models.AIAgent.objects.get(name="Test Inventory Specialist")
        tools = list(models.AITool.objects.order_by("name"))
        cls.form_data = {
            "agent": agent.pk,
            "ai_tool": tools[0].pk,
            "name_override": "find_it",
            "description_override": "Look it up. Send one hostname.",
            "weight": 100,
        }
        cls.update_data = {
            "agent": agent.pk,
            "ai_tool": tools[1].pk,
            "name_override": "find_it_again",
            "description_override": "Look it up again.",
            "weight": 150,
        }


class AIAgentSubagentViewTest(ViewTestCases.OrganizationalObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the AIAgentSubagent views."""

    model = models.AIAgentSubagent
    bulk_edit_data = {"weight": 200}

    @classmethod
    def setUpTestData(cls):
        """Create test data and the form payloads the generic view tests post."""
        fixtures.create_aiagentsubagent()
        supervisor = models.AIAgent.objects.get(name="Test Skills Agent")
        specialist = models.AIAgent.objects.get(name="Test Inventory Specialist")
        other = models.AIAgent.objects.get(name="Test Supervisor")
        cls.form_data = {
            "parent": supervisor.pk,
            "subagent": specialist.pk,
            "tool_name": "inventory",
            "tool_description": "Look up a device. Give it a hostname.",
            "input_mode": SubagentInputModeChoices.TASK_ONLY,
            "weight": 100,
        }
        cls.update_data = {
            "parent": supervisor.pk,
            "subagent": other.pk,
            "tool_name": "inventory_two",
            "tool_description": "Look up a device. Give it a hostname, not a site code.",
            "input_mode": SubagentInputModeChoices.TASK_ONLY,
            "weight": 150,
        }


class AISkillViewTest(ViewTestCases.OrganizationalObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the AISkill views."""

    model = models.AISkill
    bulk_edit_data = {"description": "Bulk edit views", "enabled": False}

    @classmethod
    def setUpTestData(cls):
        """Create test data and the form payloads the generic view tests post."""
        fixtures.create_aiskill()
        cls.form_data = {
            "name": "view_test_skill",
            "description": "one area of work",
            "body": "Call the tool. Report what it said.",
            "enabled": True,
        }
        cls.update_data = {
            "name": "view_test_skill_two",
            "description": "another area of work",
            "body": "Call the other tool. Report what it said.",
            "enabled": False,
        }


class AIAgentSkillViewTest(ViewTestCases.OrganizationalObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the AIAgentSkill views."""

    model = models.AIAgentSkill
    bulk_edit_data = {"weight": 200}

    @classmethod
    def setUpTestData(cls):
        """Create test data and the form payloads the generic view tests post."""
        fixtures.create_aiagentskill()
        agent = models.AIAgent.objects.get(name="Test Supervisor")
        skills = list(models.AISkill.objects.order_by("name"))
        cls.form_data = {"agent": agent.pk, "skill": skills[0].pk, "weight": 100}
        cls.update_data = {"agent": agent.pk, "skill": skills[1].pk, "weight": 150}


class AIAgentThreadViewTest(
    ViewTestCases.GetObjectViewTestCase,
    ViewTestCases.GetObjectChangelogViewTestCase,
    ViewTestCases.GetObjectNotesViewTestCase,
    ViewTestCases.ListObjectsViewTestCase,
    ViewTestCases.DeleteObjectViewTestCase,
    ViewTestCases.BulkDeleteObjectsViewTestCase,
):
    # pylint: disable=too-many-ancestors
    """Test the AIAgentThread views.

    This names one test case at a time instead of `OrganizationalObjectViewTestCase`, because the
    ViewSet is read and delete only. The create and edit cases would test views that do not exist.
    `RefusedViewTest` proves they do not.
    """

    model = models.AIAgentThread

    @classmethod
    def setUpTestData(cls):
        """Create the threads the read and delete tests work on."""
        fixtures.create_aiagentthread()


class RefusedViewTest(TestCase):
    """Test that a view a model has no form for is not routed.

    A route with no form behind it renders a page that cannot work. The AI Tool add form offered
    two flags and no name, and the thread add view raised a TypeError before it rendered anything.
    A reverse of the name is the check, because the list template reverses it too, and it draws
    the button only when the name resolves.
    """

    def assert_not_routed(self, *names):
        """Fail if any of these URL names resolves, with or without a primary key.

        This tries both forms. A name that takes no argument raises `NoReverseMatch` when it gets one,
        which would pass this test whether the route existed or not.

        Args:
            *names: URL names within the app's namespace, without the namespace.
        """
        for name in names:
            with self.subTest(name=name):
                for args in ([], [uuid.uuid4()]):
                    try:
                        url = reverse(f"plugins:nautobot_ai_models:{name}", args=args)
                    except NoReverseMatch:
                        continue
                    self.fail(f"{name} is still routed, at {url}")

    def test_an_ai_tool_is_not_created_by_hand(self):
        """It is written by the Sync AI Tools Job, and `AITool.clean()` refuses one that is not."""
        self.assert_not_routed("aitool_add", "aitool_import", "aitool_bulk_rename")

    def test_an_ai_tool_is_still_editable(self):
        """The two flags a person owns are the reason the edit view stays."""
        self.assertTrue(reverse("plugins:nautobot_ai_models:aitool_edit", args=[uuid.uuid4()]))
        self.assertTrue(reverse("plugins:nautobot_ai_models:aitool_bulk_edit"))

    def test_a_thread_is_not_written_through_the_ui(self):
        """Whatever ran the agent writes it. There is no form, so there is no view."""
        self.assert_not_routed(
            "aiagentthread_add",
            "aiagentthread_edit",
            "aiagentthread_import",
            "aiagentthread_bulk_edit",
        )

    def test_a_thread_is_still_read_and_deleted(self):
        """Deleting one is the only thing anybody does to it."""
        self.assertTrue(reverse("plugins:nautobot_ai_models:aiagentthread", args=[uuid.uuid4()]))
        self.assertTrue(reverse("plugins:nautobot_ai_models:aiagentthread_delete", args=[uuid.uuid4()]))
        self.assertTrue(reverse("plugins:nautobot_ai_models:aiagentthread_list"))
