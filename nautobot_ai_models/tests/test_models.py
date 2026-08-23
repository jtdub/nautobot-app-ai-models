"""Test the Provider and AIModel models."""

from django.db.models import ProtectedError
from nautobot.apps.testing import ModelTestCases

from nautobot_ai_models import models
from nautobot_ai_models.tests import fixtures


class TestProvider(ModelTestCases.BaseModelTestCase):
    """Test Provider."""

    model = models.Provider

    @classmethod
    def setUpTestData(cls):
        """Create test data for the Provider model."""
        super().setUpTestData()
        fixtures.create_provider()

    def test_create_provider_only_required(self):
        """Create with only required fields, and validate the defaults and __str__."""
        integration = fixtures.create_external_integration()
        provider = models.Provider.objects.create(name="Development", external_integration=integration)
        self.assertEqual(provider.name, "Development")
        self.assertEqual(provider.description, "")
        self.assertTrue(provider.openai_compatible)
        self.assertIsNone(provider.num_predict)
        self.assertIsNone(provider.temperature)
        self.assertEqual(str(provider), "Development")

    def test_create_provider_all_fields_success(self):
        """Create a Provider with every field set."""
        integration = fixtures.create_external_integration()
        provider = models.Provider.objects.create(
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
        """Deleting an ExternalIntegration a Provider uses must fail."""
        integration = fixtures.create_external_integration(name="Protected", remote_url="https://x.example.com")
        models.Provider.objects.create(name="Protected Provider", external_integration=integration)
        with self.assertRaises(ProtectedError):
            integration.delete()


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
        provider = models.Provider.objects.get(name="Test One")
        provider.num_predict = 256
        provider.temperature = "0.50"
        provider.validated_save()

        ai_model = models.AIModel.objects.get(provider=provider, name="Test One")
        self.assertEqual(ai_model.resolved_num_predict, 256)
        self.assertEqual(str(ai_model.resolved_temperature), "0.50")

    def test_resolved_values_prefer_the_override(self):
        """A set override wins over the provider default."""
        provider = models.Provider.objects.get(name="Test One")
        provider.num_predict = 256
        provider.temperature = "0.50"
        provider.validated_save()

        ai_model = models.AIModel.objects.get(provider=provider, name="Test One")
        ai_model.num_predict = 1024
        ai_model.temperature = "1.20"
        ai_model.validated_save()

        self.assertEqual(ai_model.resolved_num_predict, 1024)
        self.assertEqual(str(ai_model.resolved_temperature), "1.20")

    def test_name_is_unique_per_provider(self):
        """The same model name may exist under two different providers."""
        other = models.Provider.objects.get(name="Test Three")
        duplicate = models.AIModel(provider=other, name="Test One")
        duplicate.validated_save()
        self.assertEqual(models.AIModel.objects.filter(name="Test One").count(), 2)

    def test_deleting_a_provider_deletes_its_models(self):
        """The provider foreign key cascades."""
        provider = models.Provider.objects.get(name="Test One")
        provider.delete()
        self.assertEqual(models.AIModel.objects.filter(name="Test One").count(), 0)
