"""API serializers for nautobot_ai_models.

This is how a consumer outside Nautobot reads the registries, so the MCP tool serializer
carries the whole advertised definition - both schemas included - rather than a summary.
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

        # Written by the discovery job from what the server said about itself. A client that could
        # PATCH these could make the registry claim a server reported something it never did.
        read_only_fields = list(MCP_SERVER_DISCOVERED_FIELDS)

    def get_tool_count(self, obj):
        """How many tools this server offers.

        Read off the viewset's annotation when there is one, and counted otherwise. A serializer
        also renders objects that never came from that queryset - the one just created by a POST,
        for instance - and reading a missing annotation would fail there.
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

        # Discovery's own evidence of what it saw and when. A client that could rewrite either
        # could make the registry claim a review is current when it is not.
        #
        # The rest of what discovery writes - title, description, both schemas, and
        # advertised_read_only - stays writable on purpose. A stdio server cannot be reached
        # from a worker, so its tools are entered and corrected by hand.
        read_only_fields = [
            "definition_fingerprint",
            "last_seen_at",
        ]
