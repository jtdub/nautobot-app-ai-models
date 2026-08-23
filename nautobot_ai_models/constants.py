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

# Group weight this app claims under the AI Tools tab. A sibling app must pick a different one.
AI_MODELS_GROUP_WEIGHT = 100
