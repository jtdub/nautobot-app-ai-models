"""Test scaffolding shared by the AI and MCP suites.

MCPTool is absent from the API helper: its payloads carry no description and its bulk edit
exercises a different field.
"""

COMMON_FILTER_TESTS = (
    ("id",),
    ("created",),
    ("last_updated",),
    ("name",),
)

COMMON_FILTER_TESTS_WITH_DESCRIPTION = (*COMMON_FILTER_TESTS, ("description",))

CREATE_LABELS = ("One", "Two", "Three")


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
