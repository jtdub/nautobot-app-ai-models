"""Constants for nautobot_ai_models."""

MIN_NUM_PREDICT = -1

MIN_TEMPERATURE = 0
MAX_TEMPERATURE = 2
TEMPERATURE_MAX_DIGITS = 4
TEMPERATURE_DECIMAL_PLACES = 2

COST_MAX_DIGITS = 12
COST_DECIMAL_PLACES = 4
MIN_COST = 0

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

MODELS_ENDPOINT = "/v1/models"

DEFAULT_TIMEOUT_SECONDS = 30

AI_MODEL_DEFAULT_COLUMNS = (
    "name",
    "provider",
    "description",
    "kind",
    "enabled",
)

AI_MODEL_NUMERIC_FIELDS = (
    "num_predict",
    "temperature",
    "input_cost_per_million",
    "output_cost_per_million",
)

AI_MODEL_FIELDS = (*AI_MODEL_DEFAULT_COLUMNS, *AI_MODEL_NUMERIC_FIELDS)

MCP_SERVER_OPERATOR_FIELDS = (
    "name",
    "description",
    "external_integration",
    "transport",
    "enabled",
    "tenant",
)

MCP_SERVER_DISCOVERED_FIELDS = (
    "protocol_version",
    "server_name",
    "server_version",
    "instructions",
    "capabilities",
    "last_discovered_at",
)

MCP_SERVER_DISCOVERED_COLUMNS = (
    "protocol_version",
    "server_name",
    "server_version",
    "last_discovered_at",
)

MCP_TOOL_DEFINITION_FIELDS = (
    "mcp_server",
    "name",
    "title",
    "description",
    "enabled",
    "writable",
    "advertised_read_only",
)

MCP_TOOL_SCHEMA_FIELDS = (
    "input_schema",
    "output_schema",
)

AI_TOOLS_TAB_NAME = "AI Tools"
AI_TOOLS_TAB_WEIGHT = 950
AI_TOOLS_TAB_ICON = "nautobot_ai_models/icons/stars.svg"

AI_MODELS_GROUP_WEIGHT = 100
MCP_MODELS_GROUP_WEIGHT = 200
