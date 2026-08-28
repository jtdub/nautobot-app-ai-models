"""Constants for nautobot_ai_models."""

# -1 is the conventional "unlimited" value for num_predict.
MIN_NUM_PREDICT = -1

# Sampling temperature range shared by the OpenAI and Ollama APIs.
MIN_TEMPERATURE = 0
MAX_TEMPERATURE = 2
TEMPERATURE_MAX_DIGITS = 4
TEMPERATURE_DECIMAL_PLACES = 2

# Token pricing. Four decimal places because a cheap model is quoted in fractions of a cent per
# million tokens, and twelve digits because nothing real approaches that and rounding a price
# is worse than storing a wide column.
COST_MAX_DIGITS = 12
COST_DECIMAL_PLACES = 4
MIN_COST = 0

#: Request parameters an operator may put in AIModel.default_parameters.
#:
#: An allowlist, not a denylist. The keyword surface of a unified LLM client is wide, aliased, and
#: moves between releases. `base_url` alone overrides `api_base` in litellm, so a denylist naming
#: `api_base` never sees it. An operator holding only `change_aimodel` could then redirect a call
#: to a host of their choosing, and the provider's credential would go with it. An allowlist fails
#: closed on a key nobody has considered; a denylist fails open.
#:
#: Every key here shapes an answer. None of them decides who answers.
#:
#: `temperature` is in the list even though it has a column of its own. An operator who sets it in
#: both places gets the same answer either way: AIModel.resolved_parameters and
#: AIModel.resolved_temperature read the column first, then this dictionary, then the provider.
ALLOWED_MODEL_PARAMETERS = (
    "extra_body",
    "frequency_penalty",
    "logit_bias",
    "n",
    "presence_penalty",
    "reasoning_effort",
    "seed",
    "stop",
    "temperature",
    "timeout",
    "top_k",
    "top_p",
)

# The de facto standard model-discovery endpoint for OpenAI-compatible providers.
MODELS_ENDPOINT = "/v1/models"

# Applied when an ExternalIntegration carries no usable timeout. It accepts 0, and a request
# with a timeout of 0 fails at once with an error that says nothing about why.
DEFAULT_TIMEOUT_SECONDS = 30

# --------------------------------------------------------------------------------------------
# AI field grouping.
#
# One tuple, because three layers list these fields by hand: the AI Model filterset, its table,
# and its detail panel. `default_parameters` is deliberately absent - it is a JSON object, so it
# gets a panel of its own on the detail view, a column that is off by default in the table, and no
# filter at all. That is how `capabilities` and the two MCP tool schemas are already treated.
# --------------------------------------------------------------------------------------------
#: Everything about an AI model except its default parameters.
AI_MODEL_FIELDS = (
    "name",
    "provider",
    "description",
    "kind",
    "enabled",
    "num_predict",
    "temperature",
    "input_cost_per_million",
    "output_cost_per_million",
)

#: The subset of the above that carries a number. Off by default in the table: a list view is for
#: finding a model, and a price or a token limit is read on the record itself.
AI_MODEL_NUMERIC_FIELDS = (
    "num_predict",
    "temperature",
    "input_cost_per_million",
    "output_cost_per_million",
)

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
