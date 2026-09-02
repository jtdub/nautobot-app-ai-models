"""Test the registry forms."""

from nautobot.apps.testing import FormTestCases

from nautobot_ai_models import forms, models
from nautobot_ai_models.choices import (
    AIAgentPatternChoices,
    AIModelKindChoices,
    AIProviderTypeChoices,
    MCPTransportChoices,
    SubagentInputModeChoices,
)
from nautobot_ai_models.tests import fixtures


class AIProviderFormTest(FormTestCases.BaseFormTestCase):
    """Test the AIProvider forms."""

    form_class = forms.AIProviderForm

    @classmethod
    def setUpTestData(cls):
        """Create the ExternalIntegration every AIProvider form needs."""
        cls.integration = fixtures.create_external_integration()

    def test_specifying_all_fields_success(self):
        """A form with every field set validates and saves."""
        form = forms.AIProviderForm(
            data={
                "name": "Development",
                "description": "Development Testing",
                "external_integration": self.integration.pk,
                "provider_type": AIProviderTypeChoices.OPENAI,
                "openai_compatible": True,
                "enabled": True,
                "num_predict": 512,
                "temperature": "0.70",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_specifying_only_required_success(self):
        """A form with only the required fields validates and saves."""
        form = forms.AIProviderForm(
            data={
                "name": "Development",
                "external_integration": self.integration.pk,
                "provider_type": AIProviderTypeChoices.OPENAI,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_the_form_offers_an_empty_provider_type(self):
        """A migrated row carries an empty dialect, and the form must show it as empty.

        Without a blank option the select shows its first choice for that row, and a save writes the
        dialect that the migration refused to guess.
        """
        form = forms.AIProviderForm()
        self.assertIn("", [value for value, _ in form.fields["provider_type"].choices])

    def test_an_empty_provider_type_is_refused_by_the_form(self):
        """The empty option must not be a way to save a row with no dialect."""
        form = forms.AIProviderForm(
            data={
                "name": "Development",
                "external_integration": self.integration.pk,
                "provider_type": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("provider_type", form.errors)

    def test_an_openai_compatible_provider_needs_a_remote_url(self):
        """That type is an address, not a service. Without a URL a client reaches somebody else."""
        integration = fixtures.create_external_integration(name="No URL", remote_url="")
        form = forms.AIProviderForm(
            data={
                "name": "Self Hosted",
                "external_integration": integration.pk,
                "provider_type": AIProviderTypeChoices.OPENAI_COMPATIBLE,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("external_integration", form.errors)

    def test_name_is_required(self):
        """The name field is required."""
        form = forms.AIProviderForm(data={"external_integration": self.integration.pk})
        self.assertFalse(form.is_valid())
        self.assertIn("This field is required.", form.errors["name"])

    def test_external_integration_is_required(self):
        """The external_integration field is required."""
        form = forms.AIProviderForm(data={"name": "Development"})
        self.assertFalse(form.is_valid())
        self.assertIn("This field is required.", form.errors["external_integration"])

    def test_temperature_above_the_maximum_is_rejected(self):
        """A temperature above 2 fails validation."""
        form = forms.AIProviderForm(
            data={
                "name": "Development",
                "external_integration": self.integration.pk,
                "temperature": "3.00",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("temperature", form.errors)


class AIModelFormTest(FormTestCases.BaseFormTestCase):
    """Test the AIModel forms."""

    form_class = forms.AIModelForm

    @classmethod
    def setUpTestData(cls):
        """Create a AIProvider for the AIModel form to reference."""
        fixtures.create_ai_provider()
        cls.provider = models.AIProvider.objects.get(name="Test One")

    def test_specifying_all_fields_success(self):
        """A form with every field set validates and saves."""
        form = forms.AIModelForm(
            data={
                "provider": self.provider.pk,
                "name": "gpt-4o-mini",
                "description": "Small model",
                "kind": AIModelKindChoices.CHAT,
                "enabled": True,
                "num_predict": 1024,
                "temperature": "1.00",
                "default_parameters": '{"seed": 7, "top_p": 0.9}',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_specifying_only_required_success(self):
        """A form with only the required fields validates and saves."""
        form = forms.AIModelForm(
            data={"provider": self.provider.pk, "name": "gpt-4o-mini", "kind": AIModelKindChoices.CHAT}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_provider_is_required(self):
        """The provider field is required."""
        form = forms.AIModelForm(data={"name": "gpt-4o-mini"})
        self.assertFalse(form.is_valid())
        self.assertIn("This field is required.", form.errors["provider"])

    def test_a_parameter_outside_the_allowlist_is_rejected(self):
        """A key that decides who answers must not get past the form.

        `base_url` is the case the allowlist exists for. An operator who holds only `change_aimodel`
        could otherwise point a call at a host of their choice, with the credential attached.
        """
        form = forms.AIModelForm(
            data={
                "provider": self.provider.pk,
                "name": "gpt-4o-mini",
                "kind": AIModelKindChoices.CHAT,
                "default_parameters": '{"base_url": "https://attacker.example.com/v1"}',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("default_parameters", form.errors)


class MCPServerFormTest(FormTestCases.BaseFormTestCase):
    """Test MCPServer forms."""

    form_class = forms.MCPServerForm

    @classmethod
    def setUpTestData(cls):
        """One integration for the forms to point at."""
        cls.integration = fixtures.create_external_integration()

    def test_specifying_all_fields_success(self):
        form = forms.MCPServerForm(
            data={
                "name": "Development",
                "description": "Development Testing",
                "external_integration": self.integration.pk,
                "transport": MCPTransportChoices.TYPE_STREAMABLE_HTTP,
                "enabled": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_specifying_only_required_success(self):
        form = forms.MCPServerForm(
            data={
                "name": "Development",
                "external_integration": self.integration.pk,
                "transport": MCPTransportChoices.TYPE_STREAMABLE_HTTP,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_validate_name_is_required(self):
        form = forms.MCPServerForm(
            data={"description": "Development Testing", "external_integration": self.integration.pk}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("This field is required.", form.errors["name"])

    def test_validate_external_integration_is_required(self):
        """A server with no integration has no URL, so it is not a server."""
        form = forms.MCPServerForm(data={"name": "Development"})
        self.assertFalse(form.is_valid())
        self.assertIn("This field is required.", form.errors["external_integration"])

    def test_external_integration_offers_embedded_create(self):
        """The "+" button that creates an ExternalIntegration in a modal must stay on.

        This test guards against ``Meta.exclude_embedded_create`` or ``embedded_create=False``.
        Without the button, a user leaves a half-filled form to create the integration.
        """
        form = forms.MCPServerForm()
        self.assertTrue(form.fields["external_integration"].embedded_create)


class MCPToolFormTest(FormTestCases.BaseFormTestCase):
    """Test MCPTool forms."""

    form_class = forms.MCPToolForm

    @classmethod
    def setUpTestData(cls):
        """One server for the tools to hang off."""
        cls.server = fixtures.create_mcpserver()[0]

    def test_specifying_only_required_success(self):
        form = forms.MCPToolForm(data={"mcp_server": self.server.pk, "name": "get_device"})
        self.assertTrue(form.is_valid(), form.errors)
        tool = form.save()
        self.assertFalse(tool.enabled)
        self.assertFalse(tool.writable)

    def test_add_form_starts_with_both_flags_ticked(self):
        """What an operator opening the add form sees, which is where the model defaults land."""
        form = forms.MCPToolForm()
        self.assertTrue(form.fields["enabled"].initial)
        self.assertTrue(form.fields["writable"].initial)

    def test_validate_server_is_required(self):
        """A tool with no server is not a tool anything can find."""
        form = forms.MCPToolForm(data={"name": "get_device"})
        self.assertFalse(form.is_valid())
        self.assertIn("This field is required.", form.errors["mcp_server"])

    def test_server_offers_embedded_create(self):
        """A tool added by hand should be able to create its server without leaving the page."""
        form = forms.MCPToolForm()
        self.assertTrue(form.fields["mcp_server"].embedded_create)


class MCPServerBulkEditFormTest(FormTestCases.BaseFormTestCase):
    """Test MCPServerBulkEditForm.

    Nautobot's bulk-update mixin applies any value that is not None and not empty, so a select
    with no blank option rewrites the field on every selected row. That is data loss, not a
    cosmetic problem, because discovery gates on `transport`.
    """

    form_class = forms.MCPServerBulkEditForm

    @classmethod
    def setUpTestData(cls):
        """Three servers, one per transport."""
        cls.servers = fixtures.create_mcpserver()

    def test_transport_offers_a_blank_choice(self):
        """Leaving transport alone has to be expressible."""
        choices = forms.MCPServerBulkEditForm(models.MCPServer).fields["transport"].choices
        blanks = [value for value, _ in choices if value in (None, "")]
        self.assertTrue(blanks, f"transport offers no blank choice: {list(choices)}")

    def test_leaving_transport_blank_is_valid_and_changes_nothing(self):
        """A bulk edit that only sets a description must not touch transport."""
        form = forms.MCPServerBulkEditForm(
            models.MCPServer,
            data={
                "pk": [server.pk for server in self.servers],
                "description": "Bulk edited",
                "transport": "",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["transport"], "")


class AIAgentFormTest(FormTestCases.BaseFormTestCase):
    """Test the AIAgent forms."""

    form_class = forms.AIAgentForm

    @classmethod
    def setUpTestData(cls):
        """Create the models an agent form needs."""
        fixtures.create_aimodel()
        cls.chat = models.AIModel.objects.filter(kind=AIModelKindChoices.CHAT).first()
        cls.embedding = models.AIModel.objects.filter(kind=AIModelKindChoices.EMBEDDING).first()

    def payload(self, **overrides):
        """One valid agent payload.

        Args:
            **overrides: Fields to change.

        Returns:
            dict: Form data.
        """
        return {
            "name": "Form Test Agent",
            "description": "Looks things up. Give it a hostname.",
            "system_prompt": "You answer from tools only.",
            "model": self.chat.pk,
            "pattern": AIAgentPatternChoices.SINGLE,
            "enabled": True,
            "max_iterations": 8,
            **overrides,
        }

    def test_a_complete_agent_saves(self):
        """The ordinary case."""
        form = forms.AIAgentForm(data=self.payload())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_an_embedding_model_is_refused(self):
        """An agent talks; an embedding model does not."""
        form = forms.AIAgentForm(data=self.payload(model=self.embedding.pk))
        self.assertFalse(form.is_valid())
        self.assertIn("model", form.errors)

    def test_the_prompt_is_required(self):
        """An agent with no standing instructions is an agent with no rules."""
        payload = self.payload()
        del payload["system_prompt"]
        form = forms.AIAgentForm(data=payload)
        self.assertFalse(form.is_valid())
        self.assertIn("system_prompt", form.errors)

    def test_the_filter_form_keeps_both_meanings_of_model(self):
        """`AIAgent.model` is a field name and the filter form's content type. Both have to work."""
        form = forms.AIAgentFilterForm()
        self.assertIs(forms.AIAgentFilterForm.model, models.AIAgent)
        self.assertIn("model", form.fields)


class AIAgentToolFormTest(FormTestCases.BaseFormTestCase):
    """Test the AIAgentTool forms."""

    form_class = forms.AIAgentToolForm

    @classmethod
    def setUpTestData(cls):
        """Create an agent and the two kinds of tool."""
        cls.agent = fixtures.create_aiagent()[0]
        cls.ai_tool = fixtures.create_aitool()[0]
        cls.mcp_tool = fixtures.create_mcptool()[0]

    def test_binding_one_tool_saves(self):
        """The ordinary case."""
        form = forms.AIAgentToolForm(data={"agent": self.agent.pk, "ai_tool": self.ai_tool.pk, "weight": 100})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_binding_no_tool_is_refused(self):
        """A binding with nothing to call is nothing."""
        form = forms.AIAgentToolForm(data={"agent": self.agent.pk, "weight": 100})
        self.assertFalse(form.is_valid())

    def test_binding_two_tools_is_refused(self):
        """Two things under one name."""
        form = forms.AIAgentToolForm(
            data={
                "agent": self.agent.pk,
                "ai_tool": self.ai_tool.pk,
                "mcp_tool": self.mcp_tool.pk,
                "weight": 100,
            }
        )
        self.assertFalse(form.is_valid())


class AIAgentSubagentFormTest(FormTestCases.BaseFormTestCase):
    """Test the AIAgentSubagent forms."""

    form_class = forms.AIAgentSubagentForm

    @classmethod
    def setUpTestData(cls):
        """Create two agents to bind together."""
        agents = fixtures.create_aiagent()
        cls.supervisor, cls.specialist = agents[0], agents[1]

    def test_binding_a_specialist_saves(self):
        """The ordinary case."""
        form = forms.AIAgentSubagentForm(
            data={
                "parent": self.supervisor.pk,
                "subagent": self.specialist.pk,
                "tool_name": "inventory_expert",
                "tool_description": "Look up a device by hostname.",
                "input_mode": SubagentInputModeChoices.TASK_ONLY,
                "weight": 100,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_an_agent_delegating_to_itself_is_refused(self):
        """A specialist that is its own supervisor never returns."""
        form = forms.AIAgentSubagentForm(
            data={
                "parent": self.supervisor.pk,
                "subagent": self.supervisor.pk,
                "input_mode": SubagentInputModeChoices.TASK_ONLY,
                "weight": 100,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("subagent", form.errors)


class AISkillFormTest(FormTestCases.BaseFormTestCase):
    """Test the AISkill forms."""

    form_class = forms.AISkillForm

    def test_a_complete_skill_saves(self):
        """The ordinary case."""
        form = forms.AISkillForm(
            data={
                "name": "form_test_skill",
                "description": "one area of work",
                "body": "Call the tool. Report what it said.",
                "enabled": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_the_body_is_required(self):
        """A skill with no rules loads nothing."""
        form = forms.AISkillForm(data={"name": "empty_skill", "enabled": True})
        self.assertFalse(form.is_valid())
        self.assertIn("body", form.errors)


class AIToolFormTest(FormTestCases.BaseFormTestCase):
    """Test the AITool forms."""

    form_class = forms.AIToolForm

    @classmethod
    def setUpTestData(cls):
        """Create the tools the Sync AI Tools Job would have written."""
        cls.tool = fixtures.create_aitool()[0]

    def test_what_discovery_wrote_is_not_editable(self):
        """The Sync AI Tools Job would overwrite a change to any of these on its next run."""
        fields = forms.AIToolForm().fields
        self.assertIn("enabled", fields)
        self.assertIn("writable", fields)
        for owned in ("name", "description", "argument_schema", "kind", "definition_fingerprint"):
            self.assertNotIn(owned, fields)

    def test_turning_a_reviewed_tool_on_saves(self):
        """The one thing this form exists for."""
        form = forms.AIToolForm(data={"enabled": True, "writable": False}, instance=self.tool)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertTrue(saved.enabled)
        self.assertFalse(saved.writable)
