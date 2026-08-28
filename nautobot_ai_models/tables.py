"""Tables for nautobot_ai_models."""

import django_tables2 as tables
from nautobot.apps.tables import BaseTable, BooleanColumn, ButtonsColumn, LinkedCountColumn, ToggleColumn

from nautobot_ai_models import models
from nautobot_ai_models.constants import (
    AI_MODEL_DEFAULT_COLUMNS,
    AI_MODEL_FIELDS,
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
