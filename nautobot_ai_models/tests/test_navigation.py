"""Test the shared AI Tools navigation contract.

Nautobot merges two NavMenuTab declarations only when the name, weight, and icon all match. Other
AI apps copy these three values, so a change here breaks their menus. These tests make that change
visible.
"""

from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from nautobot_ai_models import navigation
from nautobot_ai_models.constants import (
    AI_MODELS_GROUP_WEIGHT,
    AI_TOOLS_TAB_ICON,
    AI_TOOLS_TAB_NAME,
    AI_TOOLS_TAB_WEIGHT,
)


class AIToolsNavigationTest(TestCase):
    """Test the AI Tools tab."""

    def setUp(self):
        """Take the single tab this app declares."""
        self.assertEqual(len(navigation.menu_items), 1)
        self.tab = navigation.menu_items[0]

    def test_tab_contract_values(self):
        """The three merge keys must not change without a documented reason."""
        self.assertEqual(AI_TOOLS_TAB_NAME, "AI Tools")
        self.assertEqual(AI_TOOLS_TAB_WEIGHT, 950)
        self.assertEqual(AI_TOOLS_TAB_ICON, "nautobot_ai_models/icons/stars.svg")

    def test_tab_uses_the_contract(self):
        """The declared tab uses the published constants."""
        self.assertEqual(self.tab.name, AI_TOOLS_TAB_NAME)
        self.assertEqual(self.tab.weight, AI_TOOLS_TAB_WEIGHT)
        self.assertEqual(self.tab.icon, AI_TOOLS_TAB_ICON)

    def test_tab_weight_is_below_the_default(self):
        """Data-model tabs sit below the default NavMenuTab weight of 1000."""
        self.assertLess(AI_TOOLS_TAB_WEIGHT, 1000)

    def test_icon_is_a_static_file_path(self):
        """Nautobot treats an icon containing "/" as a static file URL, not a library name."""
        self.assertIn("/", AI_TOOLS_TAB_ICON)

    def test_icon_file_exists_and_renders_white(self):
        """The bundled SVG must resolve through staticfiles and use the Nautobot color convention."""
        path = finders.find(AI_TOOLS_TAB_ICON)
        self.assertIsNotNone(path, f"{AI_TOOLS_TAB_ICON} was not found by the staticfiles finders")
        content = Path(path).read_text(encoding="utf-8")
        self.assertIn('color="#FFFFFF"', content)
        self.assertIn('fill="currentcolor"', content)

    def test_group_holds_both_models(self):
        """The AI Models group lists the provider and the model."""
        groups = list(self.tab.groups.values()) if hasattr(self.tab.groups, "values") else list(self.tab.groups)
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group.name, "AI Models")
        self.assertEqual(group.weight, AI_MODELS_GROUP_WEIGHT)
        # NavMenuItem stores the resolved URL, not the route name.
        links = [item.link for item in (group.items.values() if hasattr(group.items, "values") else group.items)]
        self.assertIn(reverse("plugins:nautobot_ai_models:provider_list"), links)
        self.assertIn(reverse("plugins:nautobot_ai_models:aimodel_list"), links)
