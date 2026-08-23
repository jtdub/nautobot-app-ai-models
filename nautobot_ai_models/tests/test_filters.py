"""Test the Provider and AIModel filtersets."""

from nautobot.apps.testing import FilterTestCases

from nautobot_ai_models import filters, models
from nautobot_ai_models.tests import fixtures


class ProviderFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """Provider Filter Test Case."""

    queryset = models.Provider.objects.all()
    filterset = filters.ProviderFilterSet
    generic_filter_tests = (
        ("id",),
        ("created",),
        ("last_updated",),
        ("name",),
        ("description",),
        ("external_integration", "external_integration__id"),
        ("external_integration", "external_integration__name"),
    )

    @classmethod
    def setUpTestData(cls):
        """Set up test data for the Provider model."""
        fixtures.create_provider()

    def test_q_search_name(self):
        """Test using Q search with the name of a Provider."""
        params = {"q": "Test One"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_q_invalid(self):
        """Test using an invalid Q search for a Provider."""
        params = {"q": "test-five"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 0)

    def test_openai_compatible(self):
        """Filter on the OpenAI-compatible boolean."""
        provider = models.Provider.objects.first()
        provider.openai_compatible = False
        provider.validated_save()
        params = {"openai_compatible": True}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), self.queryset.count() - 1)


class AIModelFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """AIModel Filter Test Case."""

    queryset = models.AIModel.objects.all()
    filterset = filters.AIModelFilterSet
    generic_filter_tests = (
        ("id",),
        ("created",),
        ("last_updated",),
        ("name",),
        ("description",),
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
