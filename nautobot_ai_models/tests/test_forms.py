"""Test the AIProvider and AIModel forms."""

from nautobot.apps.testing import FormTestCases

from nautobot_ai_models import forms, models
from nautobot_ai_models.choices import AIModelKindChoices, AIProviderTypeChoices, MCPTransportChoices
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

        Without a blank option the select shows its first choice for such a row, and a save writes
        the dialect that the migration deliberately refused to guess.
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

        `base_url` is the case the allowlist exists for. An operator holding only `change_aimodel`
        could otherwise point a call at a host of their choosing, credential attached.
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

        Guards against ``Meta.exclude_embedded_create`` or ``embedded_create=False`` turning it
        off. Without it a user leaves a half-filled form to create the integration.
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

    Nautobot's bulk-update mixin applies any value that is not None or empty, so a select with no
    blank option rewrites the field on every selected row. That is data loss, not a cosmetic
    problem: `transport` is what discovery gates on.
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
