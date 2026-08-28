# Extending the App

You can extend the application. Open an issue first. This makes sure that a maintainer accepts the PR, and that the feature and the design make sense.

## The shared "AI Tools" navigation tab

This app puts its menu under a top-level tab named **AI Tools**, not under **Apps**. The tab is
shared. Each other AI-related Nautobot app must add its own group to the same tab. Do not create a
new top-level tab.

CAUTION: Nautobot merges two `NavMenuTab` declarations only when the **name, the weight, and the
icon all match exactly**. One character of difference makes two separate tabs.

![The AI Tools navigation tab](../images/ai-tools-navigation-light.png#only-light)
![The AI Tools navigation tab](../images/ai-tools-navigation-dark.png#only-dark)

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

The weight of 950 is in the data-model band. It is below the default `NavMenuTab` weight of 1000,
and just after `NavigationWeightChoices.CLOUD` at 900.

The icon is a static file that this app ships. Nautobot reads an icon string that contains a `/` as
a static file URL, and a string without one as a name in its own `nautobot-icons` library. That
library has no three-star icon, so this app includes the `stars` icon from
[Bootstrap Icons](https://icons.getbootstrap.com/icons/stars/), under the MIT license.

### How another app joins the tab

Select one of two methods.

**Copy the literals.** Use this method when your app must not depend on this one.

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

WARNING: The icon becomes a broken image if this app is not installed. Ship your own copy of the
SVG under your own static path, or accept the dependency.

**Import the constants.** Use this method when your app already depends on `nautobot-ai-models`.

```python
from nautobot_ai_models.constants import AI_TOOLS_TAB_ICON, AI_TOOLS_TAB_NAME, AI_TOOLS_TAB_WEIGHT
```

### Group weights

Give each app a different group weight. The groups then keep a stable order.

| Group | Weight | App |
|---|---|---|
| AI Models | 100 | `nautobot-ai-models` |
| (reserved for future apps) | 200 and up | |
