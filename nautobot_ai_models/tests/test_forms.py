"""Test the Provider and AIModel forms."""

from django.test import TestCase

from nautobot_ai_models import forms, models
from nautobot_ai_models.tests import fixtures


class ProviderFormTest(TestCase):
    """Test the Provider forms."""

    @classmethod
    def setUpTestData(cls):
        """Create the ExternalIntegration every Provider form needs."""
        cls.integration = fixtures.create_external_integration()

    def test_specifying_all_fields_success(self):
        """A form with every field set validates and saves."""
        form = forms.ProviderForm(
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
        form = forms.ProviderForm(
            data={
                "name": "Development",
                "external_integration": self.integration.pk,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save())

    def test_name_is_required(self):
        """The name field is required."""
        form = forms.ProviderForm(data={"external_integration": self.integration.pk})
        self.assertFalse(form.is_valid())
        self.assertIn("This field is required.", form.errors["name"])

    def test_external_integration_is_required(self):
        """The external_integration field is required."""
        form = forms.ProviderForm(data={"name": "Development"})
        self.assertFalse(form.is_valid())
        self.assertIn("This field is required.", form.errors["external_integration"])

    def test_temperature_above_the_maximum_is_rejected(self):
        """A temperature above 2 fails validation."""
        form = forms.ProviderForm(
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
        """Create a Provider for the AIModel form to reference."""
        fixtures.create_provider()
        cls.provider = models.Provider.objects.get(name="Test One")

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
