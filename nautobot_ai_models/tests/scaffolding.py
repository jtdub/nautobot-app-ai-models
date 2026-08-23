"""Test scaffolding shared by the AI and MCP suites.

Three of this app's four registry models are created the same way: a name, a description, and one
required foreign key. The generic Nautobot test cases therefore want the same three payload
attributes and the same leading filter tests from each suite. Building them once here keeps the
test classes from repeating the same blocks.

MCPTool is deliberately absent from the API helper. Its payloads carry no description and its bulk
edit exercises a different field, so sharing would mean parameterising away the difference the test
exists to show.
"""

#: The filters every registry model shares. Each test class appends its own.
COMMON_FILTER_TESTS = (
    ("id",),
    ("created",),
    ("last_updated",),
    ("name",),
)

#: The above plus `description`, for the three models that filter on it.
COMMON_FILTER_TESTS_WITH_DESCRIPTION = (*COMMON_FILTER_TESTS, ("description",))

#: One label per generated create payload.
CREATE_LABELS = ("One", "Two", "Three")


class RegistryAPIPayloadsMixin:  # pylint: disable=too-few-public-methods
    """Build the payload attributes `APIViewTestCases.APIViewTestCase` reads."""

    @classmethod
    def build_api_payloads(cls, common, extras):
        """Set `create_data`, `update_data`, and `bulk_update_data`.

        `common` is merged into every create payload, normally the required foreign key. `extras`
        holds one dictionary per payload, carrying the field that payload exists to exercise.
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
