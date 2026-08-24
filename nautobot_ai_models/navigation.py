"""Menu items."""

from nautobot.apps.ui import NavMenuAddButton, NavMenuGroup, NavMenuItem, NavMenuTab

from nautobot_ai_models.constants import (
    AI_MODELS_GROUP_WEIGHT,
    AI_TOOLS_TAB_ICON,
    AI_TOOLS_TAB_NAME,
    AI_TOOLS_TAB_WEIGHT,
    MCP_MODELS_GROUP_WEIGHT,
)

ai_model_items = (
    NavMenuItem(
        link="plugins:nautobot_ai_models:aiprovider_list",
        name="AI Providers",
        permissions=["nautobot_ai_models.view_aiprovider"],
        buttons=(
            NavMenuAddButton(
                link="plugins:nautobot_ai_models:aiprovider_add",
                permissions=["nautobot_ai_models.add_aiprovider"],
            ),
        ),
    ),
    NavMenuItem(
        link="plugins:nautobot_ai_models:aimodel_list",
        name="AI Models",
        permissions=["nautobot_ai_models.view_aimodel"],
        buttons=(
            NavMenuAddButton(
                link="plugins:nautobot_ai_models:aimodel_add",
                permissions=["nautobot_ai_models.add_aimodel"],
            ),
        ),
    ),
)

mcp_model_items = (
    NavMenuItem(
        link="plugins:nautobot_ai_models:mcpserver_list",
        name="MCP Servers",
        permissions=["nautobot_ai_models.view_mcpserver"],
        buttons=(
            NavMenuAddButton(
                link="plugins:nautobot_ai_models:mcpserver_add",
                permissions=["nautobot_ai_models.add_mcpserver"],
            ),
        ),
    ),
    NavMenuItem(
        link="plugins:nautobot_ai_models:mcptool_list",
        name="MCP Tools",
        permissions=["nautobot_ai_models.view_mcptool"],
        # Addable by hand as well as by discovery: a stdio server cannot be discovered from a
        # Nautobot worker, so its tools have to be entered.
        buttons=(
            NavMenuAddButton(
                link="plugins:nautobot_ai_models:mcptool_add",
                permissions=["nautobot_ai_models.add_mcptool"],
            ),
        ),
    ),
)

# "AI Tools" is a shared top-level tab. Another AI app, such as an MCP models app, joins it by
# declaring a NavMenuTab with the identical name, weight, and icon, plus its own NavMenuGroup.
# See docs/dev/extending.md.
menu_items = (
    NavMenuTab(
        name=AI_TOOLS_TAB_NAME,
        icon=AI_TOOLS_TAB_ICON,
        weight=AI_TOOLS_TAB_WEIGHT,
        groups=(
            NavMenuGroup(
                name="AI Models",
                weight=AI_MODELS_GROUP_WEIGHT,
                items=ai_model_items,
            ),
            NavMenuGroup(
                name="MCP Models",
                weight=MCP_MODELS_GROUP_WEIGHT,
                items=mcp_model_items,
            ),
        ),
    ),
)
