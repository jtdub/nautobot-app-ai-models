"""API serializers for nautobot_ai_models.

The MCP tool serializer carries the whole advertised definition, both schemas included.
"""

from nautobot.apps.api import NautobotModelSerializer, TaggedModelSerializerMixin
from rest_framework import serializers as drf_serializers

from nautobot_ai_models import models
from nautobot_ai_models.constants import MCP_SERVER_DISCOVERED_FIELDS


class AIProviderSerializer(NautobotModelSerializer):  # pylint: disable=too-many-ancestors
    """AI Provider Serializer."""

    class Meta:
        """Meta attributes."""

        model = models.AIProvider
        fields = "__all__"


class AIModelSerializer(NautobotModelSerializer):  # pylint: disable=too-many-ancestors
    """AI Model Serializer."""

    is_available = drf_serializers.BooleanField(read_only=True)
    resolved_parameters = drf_serializers.JSONField(read_only=True)

    class Meta:
        """Meta attributes."""

        model = models.AIModel
        fields = "__all__"


class MCPServerSerializer(NautobotModelSerializer, TaggedModelSerializerMixin):  # pylint: disable=too-many-ancestors
    """MCPServer Serializer."""

    tool_count = drf_serializers.SerializerMethodField()

    class Meta:
        """Meta attributes."""

        model = models.MCPServer
        fields = "__all__"

        read_only_fields = list(MCP_SERVER_DISCOVERED_FIELDS)

    def get_tool_count(self, obj) -> int:
        """Return how many tools this server offers.

        Args:
            obj (MCPServer): The server being rendered.

        Returns:
            The viewset's annotation, or a count when the object did not come from that queryset.
        """
        count = getattr(obj, "tool_count", None)
        return obj.tools.count() if count is None else count


class MCPToolSerializer(NautobotModelSerializer):  # pylint: disable=too-many-ancestors
    """MCPTool Serializer."""

    is_available = drf_serializers.BooleanField(read_only=True)

    class Meta:
        """Meta attributes."""

        model = models.MCPTool
        fields = "__all__"

        read_only_fields = [
            "definition_fingerprint",
            "last_seen_at",
        ]


class AIToolSerializer(NautobotModelSerializer):  # pylint: disable=too-many-ancestors
    """AI Tool Serializer.

    What discovery wrote about the tool is read-only, because the next Sync AI Tools Job run would
    overwrite a change to it. The rest stays writable: a Job tool is an operator's decision, not a
    discovery, and `AITool.clean()` refuses a row that names nothing real.
    """

    is_available = drf_serializers.BooleanField(read_only=True)

    class Meta:
        """Meta attributes."""

        model = models.AITool
        fields = "__all__"
        read_only_fields = ["advertised_read_only", "definition_fingerprint", "last_seen_at"]


class AIAgentSerializer(NautobotModelSerializer, TaggedModelSerializerMixin):  # pylint: disable=too-many-ancestors
    """AI Agent Serializer."""

    is_available = drf_serializers.BooleanField(read_only=True)
    tool_count = drf_serializers.SerializerMethodField()

    class Meta:
        """Meta attributes."""

        model = models.AIAgent
        fields = "__all__"

    def get_tool_count(self, obj) -> int:
        """How many tools this agent may call.

        This method reads the annotation the viewset adds, and falls back to a count, so a queryset
        without the annotation still serialises.

        Args:
            obj (AIAgent): The agent to render.

        Returns:
            The viewset's annotation, or a count when the object did not come from that queryset.
        """
        count = getattr(obj, "tool_count", None)
        return obj.tool_bindings.count() if count is None else count


class AIAgentToolSerializer(NautobotModelSerializer):  # pylint: disable=too-many-ancestors
    """AI Agent Tool Serializer.

    The four resolved fields are what the model is told. They come from the binding and its
    target, so they are read-only, and they are worth a return: a client that checks what an agent
    offers must not have to work them out again.
    """

    wire_name = drf_serializers.CharField(read_only=True)
    wire_description = drf_serializers.CharField(read_only=True)
    writable = drf_serializers.BooleanField(read_only=True)
    fingerprint = drf_serializers.CharField(read_only=True)

    class Meta:
        """Meta attributes."""

        model = models.AIAgentTool
        fields = "__all__"


class AIAgentSubagentSerializer(NautobotModelSerializer):  # pylint: disable=too-many-ancestors
    """AI Agent Subagent Serializer."""

    wire_name = drf_serializers.CharField(read_only=True)
    wire_description = drf_serializers.CharField(read_only=True)

    class Meta:
        """Meta attributes."""

        model = models.AIAgentSubagent
        fields = "__all__"


class AISkillSerializer(NautobotModelSerializer):  # pylint: disable=too-many-ancestors
    """AI Skill Serializer."""

    is_available = drf_serializers.BooleanField(read_only=True)

    class Meta:
        """Meta attributes."""

        model = models.AISkill
        fields = "__all__"


class AIAgentSkillSerializer(NautobotModelSerializer):  # pylint: disable=too-many-ancestors
    """AI Agent Skill Serializer."""

    class Meta:
        """Meta attributes."""

        model = models.AIAgentSkill
        fields = "__all__"


class AIAgentThreadSerializer(NautobotModelSerializer):  # pylint: disable=too-many-ancestors
    """AI Agent Thread Serializer.

    `thread_id` is neither read-only nor writable here. The column is ``editable=False``, so the
    server allocates the value and returns it. A consuming app reads it back from the response and
    checkpoints under it.
    """

    is_live = drf_serializers.BooleanField(read_only=True)

    class Meta:
        """Meta attributes."""

        model = models.AIAgentThread
        fields = "__all__"
