"""Test scaffolding shared by the AI and MCP suites.

MCPTool is absent from the API helper: its payloads carry no description and its bulk edit
exercises a different field.
"""

from nautobot_ai_models import models
from nautobot_ai_models.choices import AIModelKindChoices

COMMON_FILTER_TESTS = (
    ("id",),
    ("created",),
    ("last_updated",),
    ("name",),
)

COMMON_FILTER_TESTS_WITH_DESCRIPTION = (*COMMON_FILTER_TESTS, ("description",))

CREATE_LABELS = ("One", "Two", "Three")


def spare_agent(name):
    """Create an agent with no bindings, so every target pair is free.

    Every pair the fixtures make is already taken, and each binding model allows one row per pair.
    A fresh agent leaves every pair free.

    Args:
        name: The agent's name.

    Returns:
        AIAgent: The saved agent.
    """
    return models.AIAgent.objects.create(
        name=name,
        description=f"{name}. Give it a hostname.",
        system_prompt="You answer from tools only.",
        model=models.AIModel.objects.filter(kind=AIModelKindChoices.CHAT).first(),
    )


class RegistryAPIPayloadsMixin:  # pylint: disable=too-few-public-methods
    """Build the payload attributes `APIViewTestCases.APIViewTestCase` reads."""

    @classmethod
    def build_api_payloads(cls, common, extras):
        """Set ``create_data``, ``update_data``, and ``bulk_update_data``.

        Args:
            common: Merged into every create payload, normally the required foreign key.
            extras: One mapping per payload, carrying the field that payload exercises.
        """
        cls.create_data = [
            {
                "name": f"API Test {label}",
                "description": f"Test {label} Description",
                **common,
                **extra,
            }
            for label, extra in zip(CREATE_LABELS, extras)
        ]
        cls.update_data = {
            "name": "Update Test Two",
            "description": "Test Two Description",
        }
        cls.bulk_update_data = {
            "description": "Test Bulk Update Description",
        }


class EmptyRegistryMixin:  # pylint: disable=too-few-public-methods
    """Start each test with an empty Python tool registry, and leave one behind.

    The registry is a module-level dict that lives for the life of the process, so a test that
    registers a tool changes what every later test sees. Six suites needed the same two lines.
    """

    def setUp(self):  # pylint: disable=invalid-name
        """Empty the registry now, and again when the test finishes."""
        super().setUp()
        from nautobot_ai_models import tools  # pylint: disable=import-outside-toplevel

        self.addCleanup(tools.clear_registry)
        tools.clear_registry()
