"""Filtering for nautobot_ai_models.

The MCP filter surface is written out rather than generated, because another app codes against it.
"""

from nautobot.apps.filters import (
    MultiValueCharFilter,
    MultiValueDateTimeFilter,
    NameSearchFilterSet,
    NaturalKeyOrPKMultipleChoiceFilter,
    NautobotFilterSet,
    RelatedMembershipBooleanFilter,
    SearchFilter,
    TagFilter,
)
from nautobot.extras.models import ExternalIntegration
from nautobot.tenancy.models import Tenant

from nautobot_ai_models import models
from nautobot_ai_models.constants import (
    AI_MODEL_FIELDS,
    MCP_SERVER_DISCOVERED_COLUMNS,
    MCP_SERVER_OPERATOR_FIELDS,
    MCP_TOOL_DEFINITION_FIELDS,
)


class AIProviderFilterSet(NameSearchFilterSet, NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for AIProvider."""

    external_integration = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=ExternalIntegration.objects.all(),
        to_field_name="name",
        label="External Integration (name or ID)",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.AIProvider
        fields = "__all__"


class AIModelFilterSet(NameSearchFilterSet, NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for AIModel."""

    provider = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.AIProvider.objects.all(),
        to_field_name="name",
        label="AI Provider (name or ID)",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.AIModel
        fields = ["id", *AI_MODEL_FIELDS]  # pylint: disable=nb-use-fields-all


class MCPServerFilterSet(NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for MCPServer."""

    q = SearchFilter(
        filter_predicates={
            "name": "icontains",
            "description": "icontains",
            "server_name": "icontains",
        },
    )
    external_integration = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=ExternalIntegration.objects.all(),
        to_field_name="name",
        label="External integration (name or ID)",
    )
    tenant = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=Tenant.objects.all(),
        to_field_name="name",
        label="Tenant (name or ID)",
    )
    transport = MultiValueCharFilter(label="Transport")
    protocol_version = MultiValueCharFilter(label="Protocol version")
    last_discovered_at = MultiValueDateTimeFilter(label="Last discovered")
    has_tools = RelatedMembershipBooleanFilter(
        field_name="tools",
        label="Has tools",
    )
    tags = TagFilter()

    class Meta:
        """Meta attributes for filter."""

        model = models.MCPServer
        fields = [  # pylint: disable=nb-use-fields-all
            "id",
            *MCP_SERVER_OPERATOR_FIELDS,
            *MCP_SERVER_DISCOVERED_COLUMNS,
            "tags",
        ]


class MCPToolFilterSet(NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for MCPTool."""

    q = SearchFilter(
        filter_predicates={
            "name": "icontains",
            "title": "icontains",
            "description": "icontains",
        },
    )
    mcp_server = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.MCPServer.objects.all(),
        to_field_name="name",
        label="MCP server (name or ID)",
    )
    last_seen_at = MultiValueDateTimeFilter(label="Last seen")

    class Meta:
        """Meta attributes for filter."""

        model = models.MCPTool
        fields = [  # pylint: disable=nb-use-fields-all
            "id",
            *MCP_TOOL_DEFINITION_FIELDS,
            "definition_fingerprint",
            "last_seen_at",
        ]
