# Extending the App

Extending the application is welcome, however it is best to open an issue first, to ensure that a PR would be accepted and makes sense in terms of features and design.

## The shared "AI Tools" navigation tab

This app puts its menu under a top-level tab named **AI Tools**, not under **Apps**. The tab is
shared. Every other AI-related Nautobot app, such as an MCP models app, should add its own group to
the same tab instead of creating a new top-level tab.

Nautobot merges two `NavMenuTab` declarations only when the **name, weight, and icon all match
exactly**. A single character of difference produces two separate tabs.

![The AI Tools navigation tab](../images/ai-tools-navigation.png)

### The contract

| Attribute | Value |
|---|---|
| `name` | `"AI Tools"` |
| `weight` | `950` |
| `icon` | `"nautobot_ai_models/icons/stars.svg"` |

This app publishes those three values as constants in `nautobot_ai_models/constants.py`:

```python
AI_TOOLS_TAB_NAME = "AI Tools"
AI_TOOLS_TAB_WEIGHT = 950
AI_TOOLS_TAB_ICON = "nautobot_ai_models/icons/stars.svg"
```

The weight of 950 sits in the data-model band, below Nautobot's default `NavMenuTab` weight of
1000, and just after `NavigationWeightChoices.CLOUD` at 900.

The icon is a static file this app ships. Nautobot treats an icon string that contains a `/` as a
static file URL, and a string without one as a name in its own `nautobot-icons` library. The
Nautobot library has no three-star icon, so this app bundles the `stars` icon from
[Bootstrap Icons](https://icons.getbootstrap.com/icons/stars/), which is MIT licensed.

### How a sibling app joins the tab

Choose one of two approaches.

**Copy the literals.** Use this when your app must not depend on this one.

```python
# nautobot_mcp_models/navigation.py
from nautobot.apps.ui import NavMenuGroup, NavMenuItem, NavMenuTab

menu_items = (
    NavMenuTab(
        name="AI Tools",
        icon="nautobot_ai_models/icons/stars.svg",
        weight=950,
        groups=(
            NavMenuGroup(name="MCP Models", weight=200, items=(...)),
        ),
    ),
)
```

WARNING: the icon renders as a broken image if this app is not installed. Ship your own copy of the
SVG under your own static path, or accept the dependency.

**Import the constants.** Use this when your app already depends on `nautobot-ai-models`.

```python
from nautobot_ai_models.constants import AI_TOOLS_TAB_ICON, AI_TOOLS_TAB_NAME, AI_TOOLS_TAB_WEIGHT
```

### Group weights

Give each app a distinct group weight, so the groups keep a stable order.

| Group | Weight | App |
|---|---|---|
| AI Models | 100 | `nautobot-ai-models` |
| (reserved for future apps) | 200 and up | |
