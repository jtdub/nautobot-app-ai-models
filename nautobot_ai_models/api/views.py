"""API views for nautobot_ai_models."""

from nautobot.apps.api import NautobotModelViewSet
from nautobot.apps.models import count_related

from nautobot_ai_models import filters, models
from nautobot_ai_models.api import serializers


class AIProviderViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """AI Provider viewset."""

    queryset = models.AIProvider.objects.select_related("external_integration")
    serializer_class = serializers.AIProviderSerializer
    filterset_class = filters.AIProviderFilterSet


class AIModelViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """AI Model viewset."""

    queryset = models.AIModel.objects.select_related("provider")
    serializer_class = serializers.AIModelSerializer
    filterset_class = filters.AIModelFilterSet


class MCPServerViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """MCPServer viewset."""

    queryset = models.MCPServer.objects.select_related("external_integration", "tenant").annotate(
        tool_count=count_related(models.MCPTool, "mcp_server")
    )
    serializer_class = serializers.MCPServerSerializer
    filterset_class = filters.MCPServerFilterSet


class MCPToolViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """MCPTool viewset."""

    queryset = models.MCPTool.objects.select_related("mcp_server")
    serializer_class = serializers.MCPToolSerializer
    filterset_class = filters.MCPToolFilterSet
