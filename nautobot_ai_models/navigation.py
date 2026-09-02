"""Menu items."""

from nautobot.apps.ui import NavMenuAddButton, NavMenuGroup, NavMenuItem, NavMenuTab

from nautobot_ai_models.constants import (
    AGENTS_GROUP_WEIGHT,
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
        buttons=(
            NavMenuAddButton(
                link="plugins:nautobot_ai_models:mcptool_add",
                permissions=["nautobot_ai_models.add_mcptool"],
            ),
        ),
    ),
)

agent_items = (
    NavMenuItem(
        link="plugins:nautobot_ai_models:aiagent_list",
        name="AI Agents",
        permissions=["nautobot_ai_models.view_aiagent"],
        buttons=(
            NavMenuAddButton(
                link="plugins:nautobot_ai_models:aiagent_add",
                permissions=["nautobot_ai_models.add_aiagent"],
            ),
        ),
    ),
    NavMenuItem(
        link="plugins:nautobot_ai_models:aitool_list",
        name="AI Tools",
        permissions=["nautobot_ai_models.view_aitool"],
    ),
    NavMenuItem(
        link="plugins:nautobot_ai_models:aiskill_list",
        name="AI Skills",
        permissions=["nautobot_ai_models.view_aiskill"],
        buttons=(
            NavMenuAddButton(
                link="plugins:nautobot_ai_models:aiskill_add",
                permissions=["nautobot_ai_models.add_aiskill"],
            ),
        ),
    ),
    NavMenuItem(
        link="plugins:nautobot_ai_models:aiagentthread_list",
        name="Agent Threads",
        permissions=["nautobot_ai_models.view_aiagentthread"],
    ),
)

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
            NavMenuGroup(
                name="Agents",
                weight=AGENTS_GROUP_WEIGHT,
                items=agent_items,
            ),
        ),
    ),
)
