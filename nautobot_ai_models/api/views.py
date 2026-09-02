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


class AIToolViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """AI Tool viewset."""

    queryset = models.AITool.objects.select_related("job", "git_repository")
    serializer_class = serializers.AIToolSerializer
    filterset_class = filters.AIToolFilterSet


class AIAgentViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """AI Agent viewset."""

    queryset = models.AIAgent.objects.select_related("model__provider", "tenant").annotate(
        tool_count=count_related(models.AIAgentTool, "agent")
    )
    serializer_class = serializers.AIAgentSerializer
    filterset_class = filters.AIAgentFilterSet


class AIAgentToolViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """AI Agent Tool viewset."""

    queryset = models.AIAgentTool.objects.select_related("agent", "mcp_tool__mcp_server", "ai_tool")
    serializer_class = serializers.AIAgentToolSerializer
    filterset_class = filters.AIAgentToolFilterSet


class AIAgentSubagentViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """AI Agent Subagent viewset."""

    queryset = models.AIAgentSubagent.objects.select_related("parent", "subagent")
    serializer_class = serializers.AIAgentSubagentSerializer
    filterset_class = filters.AIAgentSubagentFilterSet


class AISkillViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """AI Skill viewset."""

    queryset = models.AISkill.objects.all()
    serializer_class = serializers.AISkillSerializer
    filterset_class = filters.AISkillFilterSet


class AIAgentSkillViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """AI Agent Skill viewset."""

    queryset = models.AIAgentSkill.objects.select_related("agent", "skill")
    serializer_class = serializers.AIAgentSkillSerializer
    filterset_class = filters.AIAgentSkillFilterSet


class AIAgentThreadViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """AI Agent Thread viewset."""

    queryset = models.AIAgentThread.objects.select_related("agent")
    serializer_class = serializers.AIAgentThreadSerializer
    filterset_class = filters.AIAgentThreadFilterSet
