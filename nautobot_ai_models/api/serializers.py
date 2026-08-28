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
