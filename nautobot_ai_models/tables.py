"""Tables for nautobot_ai_models."""

import django_tables2 as tables
from nautobot.apps.tables import BaseTable, BooleanColumn, ButtonsColumn, LinkedCountColumn, ToggleColumn

from nautobot_ai_models import models
from nautobot_ai_models.constants import (
    AI_MODEL_FIELDS,
    AI_MODEL_NUMERIC_FIELDS,
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
        # `openai_compatible` is off by default now that `provider_type` is here. The two answer
        # different questions, but only one of them is read before every call.
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
        # `default_parameters` is available as a column but off by default: a JSON object does not
        # fit a table row.
        fields = ("pk", *AI_MODEL_FIELDS, "default_parameters", "actions")
        # The numeric columns are off by default: a list is for finding a model, and a price or a
        # token limit is read on the record itself.
        default_columns = (
            "pk",
            *(field for field in AI_MODEL_FIELDS if field not in AI_MODEL_NUMERIC_FIELDS),
            "actions",
        )


#: The tool columns: everything about the tool, plus when discovery last saw it.
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
        # Tenant is off by default: most deployments are not divided that way.
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
    # Not a BooleanColumn: unset is a third state and means "the server claimed nothing", which is
    # a different fact from "the server said it writes".
    advertised_read_only = tables.Column(verbose_name="Advertised Read Only")
    actions = ButtonsColumn(models.MCPTool, pk_field="pk")

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.MCPTool
        fields = ("pk", *MCP_TOOL_COLUMNS, "definition_fingerprint", "actions")
        # Title is off by default: it duplicates the name on most servers.
        default_columns = (
            "pk",
            *(field for field in MCP_TOOL_DEFINITION_FIELDS if field != "title"),
            "last_seen_at",
            "actions",
        )
