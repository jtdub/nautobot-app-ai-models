"""Test the AIProvider and AIModel forms."""

from django.test import TestCase

from nautobot_ai_models import forms, models
from nautobot_ai_models.choices import MCPTransportChoices
from nautobot_ai_models.tests import fixtures


class AIProviderFormTest(TestCase):
    """Test the AIProvider forms."""

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
                "openai_compatible": True,
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
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

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


class AIModelFormTest(TestCase):
    """Test the AIModel forms."""

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
                "enabled": True,
                "num_predict": 1024,
                "temperature": "1.00",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_specifying_only_required_success(self):
        """A form with only the required fields validates and saves."""
        form = forms.AIModelForm(data={"provider": self.provider.pk, "name": "gpt-4o-mini"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_provider_is_required(self):
        """The provider field is required."""
        form = forms.AIModelForm(data={"name": "gpt-4o-mini"})
        self.assertFalse(form.is_valid())
        self.assertIn("This field is required.", form.errors["provider"])


class MCPServerFormTest(TestCase):
    """Test MCPServer forms."""

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

        Nautobot turns this on for every DynamicModelChoiceField on a NautobotModelForm, so this
        test guards against somebody turning it off - by adding the field to a
        `Meta.exclude_embedded_create` list, or by passing `embedded_create=False` - rather than
        against Nautobot changing. Without it a user has to leave a half-filled form to go and
        create the integration.
        """
        form = forms.MCPServerForm()
        self.assertTrue(form.fields["external_integration"].embedded_create)


class MCPToolFormTest(TestCase):
    """Test MCPTool forms."""

    @classmethod
    def setUpTestData(cls):
        """One server for the tools to hang off."""
        cls.server = fixtures.create_mcpserver()[0]

    def test_specifying_only_required_success(self):
        form = forms.MCPToolForm(data={"mcp_server": self.server.pk, "name": "get_device"})
        self.assertTrue(form.is_valid(), form.errors)
        tool = form.save()
        # Both checkboxes were absent from the POST, which is what an unticked box looks like.
        # The model default does not apply here; the submitted value does.
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
