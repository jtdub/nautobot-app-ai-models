"""Menu items."""

from nautobot.apps.ui import NavMenuAddButton, NavMenuGroup, NavMenuItem, NavMenuTab

from nautobot_ai_models.constants import (
    AI_MODELS_GROUP_WEIGHT,
    AI_TOOLS_TAB_ICON,
    AI_TOOLS_TAB_NAME,
    AI_TOOLS_TAB_WEIGHT,
)

items = (
    NavMenuItem(
        link="plugins:nautobot_ai_models:provider_list",
        name="AI Providers",
        permissions=["nautobot_ai_models.view_provider"],
        buttons=(
            NavMenuAddButton(
                link="plugins:nautobot_ai_models:provider_add",
                permissions=["nautobot_ai_models.add_provider"],
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
                items=tuple(items),
            ),
        ),
    ),
)
