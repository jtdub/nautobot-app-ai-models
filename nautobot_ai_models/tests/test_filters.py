"""Test the AIProvider and AIModel filtersets."""

from nautobot.apps.testing import FilterTestCases

from nautobot_ai_models import filters, models
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
        """Setup test data for MCPServer Model.

        One of the three servers gets a tool, so the generic `has_tools` test has a non-empty
        result on both sides of the boolean.
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
