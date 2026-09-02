"""Tables for nautobot_ai_models."""

import django_tables2 as tables
from nautobot.apps.tables import BaseTable, BooleanColumn, ButtonsColumn, LinkedCountColumn, ToggleColumn

from nautobot_ai_models import models
from nautobot_ai_models.constants import (
    AI_AGENT_FIELDS,
    AI_AGENT_IDENTITY_FIELDS,
    AI_AGENT_SKILL_FIELDS,
    AI_AGENT_SUBAGENT_FIELDS,
    AI_AGENT_THREAD_FIELDS,
    AI_AGENT_TOOL_FIELDS,
    AI_MODEL_DEFAULT_COLUMNS,
    AI_MODEL_FIELDS,
    AI_SKILL_FIELDS,
    AI_TOOL_DEFINITION_FIELDS,
    AI_TOOL_FIELDS,
    MCP_SERVER_DISCOVERED_COLUMNS,
    MCP_SERVER_OPERATOR_FIELDS,
    MCP_TOOL_DEFINITION_FIELDS,
)


class AIProviderTable(BaseTable):
    # pylint: disable=R0903
    """Table for the AI Provider list view."""

    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    external_integration = tables.Column(linkify=True)
    openai_compatible = BooleanColumn(verbose_name="OpenAI-compatible")
    provider_type = tables.Column(verbose_name="Provider Type")
    enabled = BooleanColumn()
    ai_model_count = LinkedCountColumn(
        viewname="plugins:nautobot_ai_models:aimodel_list",
        url_params={"provider": "name"},
        verbose_name="AI Models",
    )
    actions = ButtonsColumn(
        models.AIProvider,
        pk_field="pk",
    )

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.AIProvider
        fields = (
            "pk",
            "name",
            "description",
            "external_integration",
            "provider_type",
            "openai_compatible",
            "enabled",
            "num_predict",
            "temperature",
            "ai_model_count",
            "actions",
        )
        default_columns = (
            "pk",
            "name",
            "description",
            "external_integration",
            "provider_type",
            "enabled",
            "ai_model_count",
            "actions",
        )


class AIModelTable(BaseTable):
    # pylint: disable=R0903
    """Table for the AI Model list view."""

    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    provider = tables.Column(linkify=True, verbose_name="AI Provider")
    kind = tables.Column(verbose_name="Kind")
    enabled = BooleanColumn()
    actions = ButtonsColumn(
        models.AIModel,
        pk_field="pk",
    )

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.AIModel
        fields = ("pk", *AI_MODEL_FIELDS, "default_parameters", "actions")
        default_columns = ("pk", *AI_MODEL_DEFAULT_COLUMNS, "actions")


MCP_TOOL_COLUMNS = (*MCP_TOOL_DEFINITION_FIELDS, "last_seen_at")


class MCPServerTable(BaseTable):
    # pylint: disable=R0903
    """Table for list view."""

    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    external_integration = tables.Column(linkify=True)
    tenant = tables.Column(linkify=True)
    enabled = BooleanColumn()
    tool_count = LinkedCountColumn(
        viewname="plugins:nautobot_ai_models:mcptool_list",
        url_params={"mcp_server": "name"},
        verbose_name="Tools",
    )
    actions = ButtonsColumn(models.MCPServer, pk_field="pk")

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.MCPServer
        fields = ("pk", *MCP_SERVER_OPERATOR_FIELDS, "tool_count", *MCP_SERVER_DISCOVERED_COLUMNS, "actions")
        default_columns = (
            "pk",
            *(field for field in MCP_SERVER_OPERATOR_FIELDS if field != "tenant"),
            "tool_count",
            "last_discovered_at",
            "actions",
        )


class MCPToolTable(BaseTable):
    # pylint: disable=R0903
    """Table for list view."""

    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    mcp_server = tables.Column(linkify=True, verbose_name="MCP Server")
    enabled = BooleanColumn()
    writable = BooleanColumn()
    advertised_read_only = tables.Column(verbose_name="Advertised Read Only")
    actions = ButtonsColumn(models.MCPTool, pk_field="pk")

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.MCPTool
        fields = ("pk", *MCP_TOOL_COLUMNS, "definition_fingerprint", "actions")
        default_columns = (
            "pk",
            *(field for field in MCP_TOOL_DEFINITION_FIELDS if field != "title"),
            "last_seen_at",
            "actions",
        )


class AIToolTable(BaseTable):
    # pylint: disable=R0903
    """Table for the AI Tool list view."""

    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    kind = tables.Column()
    job = tables.Column(linkify=True)
    git_repository = tables.Column(linkify=True, verbose_name="Git Repository")
    enabled = BooleanColumn()
    writable = BooleanColumn()
    advertised_read_only = BooleanColumn(verbose_name="Advertised Read-only")
    actions = ButtonsColumn(models.AITool, pk_field="pk")

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.AITool
        fields = (
            "pk",
            *AI_TOOL_FIELDS,
            "definition_fingerprint",
            "last_seen_at",
            "actions",
        )
        default_columns = ("pk", *AI_TOOL_DEFINITION_FIELDS, "last_seen_at", "actions")


class AIAgentTable(BaseTable):
    # pylint: disable=R0903
    """Table for the AI Agent list view."""

    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    model = tables.Column(linkify=True, verbose_name="AI Model")
    pattern = tables.Column()
    enabled = BooleanColumn()
    tenant = tables.Column(linkify=True)
    tool_count = LinkedCountColumn(
        viewname="plugins:nautobot_ai_models:aiagenttool_list",
        url_params={"agent": "name"},
        verbose_name="Tools",
    )
    actions = ButtonsColumn(models.AIAgent, pk_field="pk")

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.AIAgent
        fields = ("pk", *AI_AGENT_FIELDS, "tool_count", "tags", "actions")
        default_columns = ("pk", *AI_AGENT_IDENTITY_FIELDS, "tool_count", "actions")


class AIAgentToolTable(BaseTable):
    # pylint: disable=R0903
    """Table for the AI Agent Tool list view, and for the panel on an agent's page."""

    pk = ToggleColumn()
    agent = tables.Column(linkify=True, verbose_name="AI Agent")
    mcp_tool = tables.Column(linkify=True, verbose_name="MCP Tool")
    ai_tool = tables.Column(linkify=True, verbose_name="AI Tool")
    wire_name = tables.Column(verbose_name="Called as", orderable=False)
    writable = BooleanColumn(orderable=False)
    actions = ButtonsColumn(models.AIAgentTool, pk_field="pk")

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.AIAgentTool
        fields = ("pk", *AI_AGENT_TOOL_FIELDS, "wire_name", "writable", "actions")
        default_columns = ("pk", "agent", "wire_name", "writable", "weight", "actions")


class AIAgentSubagentTable(BaseTable):
    # pylint: disable=R0903
    """Table for the AI Agent Subagent list view, and for the panel on a supervisor's page."""

    pk = ToggleColumn()
    parent = tables.Column(linkify=True, verbose_name="Supervisor")
    subagent = tables.Column(linkify=True, verbose_name="Specialist")
    wire_name = tables.Column(verbose_name="Called as", orderable=False)
    input_mode = tables.Column(verbose_name="Input Mode")
    actions = ButtonsColumn(models.AIAgentSubagent, pk_field="pk")

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.AIAgentSubagent
        fields = ("pk", *AI_AGENT_SUBAGENT_FIELDS, "wire_name", "actions")
        default_columns = ("pk", "parent", "subagent", "wire_name", "input_mode", "weight", "actions")


class AISkillTable(BaseTable):
    # pylint: disable=R0903
    """Table for the AI Skill list view."""

    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    enabled = BooleanColumn()
    agent_count = LinkedCountColumn(
        viewname="plugins:nautobot_ai_models:aiagentskill_list",
        url_params={"skill": "name"},
        verbose_name="Agents",
    )
    actions = ButtonsColumn(models.AISkill, pk_field="pk")

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.AISkill
        fields = ("pk", *AI_SKILL_FIELDS, "agent_count", "actions")
        default_columns = ("pk", "name", "description", "enabled", "agent_count", "actions")


class AIAgentSkillTable(BaseTable):
    # pylint: disable=R0903
    """Table for the AI Agent Skill list view, and for the panel on an agent's page."""

    pk = ToggleColumn()
    agent = tables.Column(linkify=True, verbose_name="AI Agent")
    skill = tables.Column(linkify=True, verbose_name="AI Skill")
    actions = ButtonsColumn(models.AIAgentSkill, pk_field="pk")

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.AIAgentSkill
        fields = ("pk", *AI_AGENT_SKILL_FIELDS, "actions")
        default_columns = ("pk", "agent", "skill", "weight", "actions")


class AIAgentThreadTable(BaseTable):
    # pylint: disable=R0903
    """Table for the AI Agent Thread list view.

    No add button and no edit column. Whatever ran the agent writes the thread, and nobody creates
    one by hand.
    """

    pk = ToggleColumn()
    thread_id = tables.Column(linkify=True, verbose_name="Thread ID")
    agent = tables.Column(linkify=True, verbose_name="AI Agent")
    status = tables.Column()

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.AIAgentThread
        fields = ("pk", *AI_AGENT_THREAD_FIELDS)
        default_columns = ("pk", "thread_id", "agent", "status", "started_at", "finished_at")
