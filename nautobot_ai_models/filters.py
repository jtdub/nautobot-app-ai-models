"""Filters for nautobot_ai_models.

This module writes out the MCP filter surface instead of generating it, because another app codes
against it.
"""

from django_filters import BooleanFilter
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
from nautobot.extras.models import ExternalIntegration, GitRepository
from nautobot.tenancy.models import Tenant

from nautobot_ai_models import models
from nautobot_ai_models.constants import (
    AI_AGENT_SKILL_FIELDS,
    AI_AGENT_SUBAGENT_FIELDS,
    AI_AGENT_TOOL_FIELDS,
    AI_SKILL_FIELDS,
    AI_TOOL_DEFINITION_FIELDS,
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
    provider_enabled = BooleanFilter(
        field_name="provider__enabled",
        label="Provider enabled",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.AIModel
        fields = "__all__"


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


class AIToolFilterSet(NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for AITool.

    This page answers two questions: what may an agent be given, and what waits for a review.
    `enabled=False` is the queue that `new_tools_enabled` creates.
    """

    q = SearchFilter(filter_predicates={"name": "icontains", "description": "icontains", "module": "icontains"})
    kind = MultiValueCharFilter(label="Kind")
    module = MultiValueCharFilter(label="Module")
    last_seen_at = MultiValueDateTimeFilter(label="Last seen at")
    git_repository = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=GitRepository.objects.all(),
        to_field_name="name",
        label="Git Repository (name or ID)",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.AITool
        fields = [*AI_TOOL_DEFINITION_FIELDS, "module", "git_repository"]  # pylint: disable=nb-use-fields-all


class AIAgentFilterSet(NameSearchFilterSet, NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for AIAgent."""

    model = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.AIModel.objects.all(),
        to_field_name="name",
        label="AI Model (name or ID)",
    )
    pattern = MultiValueCharFilter(label="Pattern")
    tenant = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=Tenant.objects.all(),
        to_field_name="name",
        label="Tenant (name or ID)",
    )
    has_subagents = RelatedMembershipBooleanFilter(
        field_name="subagent_bindings",
        label="Has subagents",
    )
    tags = TagFilter()

    class Meta:
        """Meta attributes for filter."""

        model = models.AIAgent
        fields = "__all__"


class AIAgentToolFilterSet(NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for AIAgentTool.

    A filter on one agent is what the panel on its page does. A filter on one tool answers the
    other direction: which agents may call this tool.
    """

    q = SearchFilter(
        filter_predicates={
            "agent__name": "icontains",
            "name_override": "icontains",
            "mcp_tool__name": "icontains",
            "ai_tool__name": "icontains",
        }
    )
    agent = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.AIAgent.objects.all(),
        to_field_name="name",
        label="AI Agent (name or ID)",
    )
    mcp_tool = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.MCPTool.objects.all(),
        label="MCP Tool",
    )
    ai_tool = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.AITool.objects.all(),
        to_field_name="name",
        label="AI Tool (name or ID)",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.AIAgentTool
        fields = list(AI_AGENT_TOOL_FIELDS)  # pylint: disable=nb-use-fields-all


class AIAgentSubagentFilterSet(NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for AIAgentSubagent."""

    q = SearchFilter(filter_predicates={"tool_name": "icontains", "tool_description": "icontains"})
    parent = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.AIAgent.objects.all(),
        to_field_name="name",
        label="Supervisor (name or ID)",
    )
    subagent = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.AIAgent.objects.all(),
        to_field_name="name",
        label="Specialist (name or ID)",
    )
    input_mode = MultiValueCharFilter(label="Input mode")

    class Meta:
        """Meta attributes for filter."""

        model = models.AIAgentSubagent
        fields = list(AI_AGENT_SUBAGENT_FIELDS)  # pylint: disable=nb-use-fields-all


class AISkillFilterSet(NameSearchFilterSet, NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for AISkill."""

    has_agents = RelatedMembershipBooleanFilter(
        field_name="agent_bindings",
        label="Bound to an agent",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.AISkill
        fields = list(AI_SKILL_FIELDS)  # pylint: disable=nb-use-fields-all


class AIAgentSkillFilterSet(NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for AIAgentSkill."""

    q = SearchFilter(filter_predicates={"agent__name": "icontains", "skill__name": "icontains"})
    agent = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.AIAgent.objects.all(),
        to_field_name="name",
        label="AI Agent (name or ID)",
    )
    skill = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.AISkill.objects.all(),
        to_field_name="name",
        label="AI Skill (name or ID)",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.AIAgentSkill
        fields = list(AI_AGENT_SKILL_FIELDS)  # pylint: disable=nb-use-fields-all


class AIAgentThreadFilterSet(NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for AIAgentThread.

    `status=waiting` is the queue that matters: every thread paused at an interrupt with nobody to
    answer it.
    """

    q = SearchFilter(filter_predicates={"agent__name": "icontains", "status": "icontains"})
    agent = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.AIAgent.objects.all(),
        to_field_name="name",
        label="AI Agent (name or ID)",
    )
    status = MultiValueCharFilter(label="Status")
    started_at = MultiValueDateTimeFilter(label="Started at")
    finished_at = MultiValueDateTimeFilter(label="Finished at")

    class Meta:
        """Meta attributes for filter."""

        model = models.AIAgentThread
        fields = "__all__"
