"""Constants for nautobot_ai_models."""

# -1 is the conventional "unlimited" value for num_predict.
MIN_NUM_PREDICT = -1

# Sampling temperature range shared by the OpenAI and Ollama APIs.
MIN_TEMPERATURE = 0
MAX_TEMPERATURE = 2
TEMPERATURE_MAX_DIGITS = 4
TEMPERATURE_DECIMAL_PLACES = 2

# The de facto standard model-discovery endpoint for OpenAI-compatible providers.
MODELS_ENDPOINT = "/v1/models"

# --------------------------------------------------------------------------------------------
# MCP field groupings, shared across the form, table, and detail-view layers.
#
# Defined once so the list view, the detail view and the edit form cannot drift apart. The
# split that matters is by owner. An operator owns one group and the discovery job owns the
# other, and the two are never mixed in the same panel or the same form.
# --------------------------------------------------------------------------------------------
#: What an operator sets on an MCP server. The edit form and the first detail panel.
MCP_SERVER_OPERATOR_FIELDS = (
    "name",
    "description",
    "external_integration",
    "transport",
    "enabled",
    "tenant",
)

#: What the discovery job writes onto an MCP server, in full. Read-only over the REST API.
MCP_SERVER_DISCOVERED_FIELDS = (
    "protocol_version",
    "server_name",
    "server_version",
    "instructions",
    "capabilities",
    "last_discovered_at",
)

#: The subset of the above worth a table column. `instructions` and `capabilities` are too large
#: for a row and get panels of their own.
MCP_SERVER_DISCOVERED_COLUMNS = (
    "protocol_version",
    "server_name",
    "server_version",
    "last_discovered_at",
)

#: Everything about a tool except its two schemas, which are large enough to need their own panels.
MCP_TOOL_DEFINITION_FIELDS = (
    "mcp_server",
    "name",
    "title",
    "description",
    "enabled",
    "writable",
    "advertised_read_only",
)

#: The two JSON Schemas a server advertises for a tool.
MCP_TOOL_SCHEMA_FIELDS = (
    "input_schema",
    "output_schema",
)

# --------------------------------------------------------------------------------------------
# Navigation contract for the shared "AI Tools" top-level tab.
#
# Every AI-related Nautobot app must declare a NavMenuTab with the SAME name, weight, and icon.
# Nautobot merges tabs only when all three match exactly. A sibling app adds its own NavMenuGroup
# under the same tab, with a different group weight.
#
# The weight sits in the data-model band, below the default NavMenuTab weight of 1000.
# The icon is an app static file path. Nautobot treats any icon string containing "/" as a
# static file URL, and any string without one as a name in its own nautobot-icons library.
# --------------------------------------------------------------------------------------------
AI_TOOLS_TAB_NAME = "AI Tools"
AI_TOOLS_TAB_WEIGHT = 950
AI_TOOLS_TAB_ICON = "nautobot_ai_models/icons/stars.svg"

# Group weights this app claims under the AI Tools tab. A sibling app must pick another.
AI_MODELS_GROUP_WEIGHT = 100
MCP_MODELS_GROUP_WEIGHT = 200
