"""Test the Python tool registry.

The registry makes a registered tool safe to name in a database row. A row stores a name. This
module turns that name back into a callable, and refuses when nothing registered it.

The sample functions below have unused parameters on purpose. The signature is the thing under
test, because the argument schema comes from it, and a body that used it would prove nothing.
"""
# pylint: disable=unused-argument

from nautobot.apps.testing import TestCase

from nautobot_ai_models import tools
from nautobot_ai_models.tests.scaffolding import EmptyRegistryMixin


class RegistrationTest(EmptyRegistryMixin, TestCase):
    """Test `register_ai_tool`."""

    def test_a_tool_registers_from_its_own_signature(self):
        """The name, the description and the schema all come from the function."""

        @tools.register_ai_tool(writable=False)
        def lookup_device(hostname: str) -> str:
            """Look up one device by hostname."""

        registered = tools.get_registered_tool("lookup_device")
        self.assertIsNotNone(registered)
        self.assertEqual(registered.name, "lookup_device")
        self.assertEqual(registered.description, "Look up one device by hostname.")
        self.assertEqual(
            registered.argument_schema,
            {"type": "object", "properties": {"hostname": {"type": "string"}}, "required": ["hostname"]},
        )
        self.assertFalse(registered.writable)
        self.assertIs(registered.callable, lookup_device)

    def test_the_decorator_returns_the_function_unchanged(self):
        """Registering a tool must not stop it being an ordinary function."""

        @tools.register_ai_tool(writable=False)
        def add(first: int, second: int = 1) -> int:
            """Add two numbers."""
            return first + second

        self.assertEqual(add(2, 3), 5)

    def test_a_default_makes_a_parameter_optional(self):
        """`required` names the parameters a call has to carry."""

        @tools.register_ai_tool(writable=False)
        def search(term: str, limit: int = 10) -> str:
            """Search for something."""

        schema = tools.get_registered_tool("search").argument_schema
        self.assertEqual(schema["required"], ["term"])
        self.assertEqual(schema["properties"]["limit"], {"type": "integer"})

    def test_an_unknown_annotation_becomes_a_string(self):
        """A model sends text, and refusing a call over a type this cannot read is worse."""

        @tools.register_ai_tool(writable=False)
        def odd(value: complex) -> str:
            """Take something unusual."""

        self.assertEqual(tools.get_registered_tool("odd").argument_schema["properties"]["value"], {"type": "string"})

    def test_writable_has_to_be_stated(self):
        """There is no default, because guessing either way is wrong in a different direction."""
        with self.assertRaises(ValueError) as raised:

            @tools.register_ai_tool
            def anything(value: str) -> str:
                """Do a thing."""

        self.assertIn("writable", str(raised.exception))

    def test_a_tool_needs_a_description(self):
        """The model reads it to decide whether to call the tool. Empty means never called."""
        with self.assertRaises(ValueError) as raised:

            @tools.register_ai_tool(writable=False)
            def undocumented(value: str) -> str:
                pass

        self.assertIn("description", str(raised.exception))

    def test_two_tools_cannot_share_a_name(self):
        """One name, one callable. Otherwise a bound row means two different things."""

        @tools.register_ai_tool(writable=False)
        def first(value: str) -> str:
            """The first one."""

        with self.assertRaises(ValueError) as raised:

            @tools.register_ai_tool(name="first", writable=False)
            def second(value: str) -> str:
                """The second one."""

        self.assertIn("already registered", str(raised.exception))

    def test_registering_the_same_function_twice_is_allowed(self):
        """A module imported twice must not be an error."""

        def once(value: str) -> str:
            """Do it once."""

        tools.register_ai_tool(once, writable=False)
        tools.register_ai_tool(once, writable=False)
        self.assertEqual(len(tools.registered_tools()), 1)

    def test_the_registry_is_returned_as_a_copy(self):
        """A caller editing what it was handed must not edit the registry."""

        @tools.register_ai_tool(writable=False)
        def sample(value: str) -> str:
            """A sample."""

        handed = tools.registered_tools()
        handed.clear()
        self.assertIsNotNone(tools.get_registered_tool("sample"))


class FingerprintTest(EmptyRegistryMixin, TestCase):
    """Test the definition digest."""

    def register(self, description="A tool.", writable=False, name="sample"):
        """Register one tool and hand it back.

        Args:
            description: The tool's description.
            writable: Whether it writes.
            name: The tool's name.

        Returns:
            RegisteredTool: The registered tool.
        """

        def sample(hostname: str) -> str:
            pass

        return tools.register_ai_tool(sample, name=name, description=description, writable=writable) and (
            tools.get_registered_tool(name)
        )

    def test_the_same_definition_gives_the_same_digest(self):
        """A digest that moved on its own would disable every tool on every sync."""
        first = self.register().definition_fingerprint
        tools.clear_registry()
        second = self.register().definition_fingerprint
        self.assertEqual(first, second)

    def test_a_changed_description_changes_the_digest(self):
        """The description is what the model reads, so a change to it is a change to the tool."""
        first = self.register().definition_fingerprint
        tools.clear_registry()
        second = self.register(description="A different tool.").definition_fingerprint
        self.assertNotEqual(first, second)

    def test_writable_is_not_part_of_the_digest(self):
        """A person decides that. Their decision is not a change to what the tool is."""
        first = self.register(writable=False).definition_fingerprint
        tools.clear_registry()
        second = self.register(writable=True).definition_fingerprint
        self.assertEqual(first, second)


class ModuleTest(EmptyRegistryMixin, TestCase):
    """Test the per-module helpers the Git datasource reloads with."""

    def register(self, name, module):
        """Register one tool and claim it came from a module.

        The module is set afterwards, because a test function's real module is this file. What is
        under test is how the registry groups tools by their source.

        Args:
            name: The tool's name.
            module: The module to record.
        """

        def sample(hostname: str) -> str:
            """Do something."""

        tools.register_ai_tool(sample, name=name, writable=False)
        tools.get_registered_tool(name).module = module

    def test_tools_are_grouped_by_the_module_they_came_from(self):
        """A repository owns its tools and no others."""
        self.register("from_repo", "my_repo.ai_tools")
        self.register("from_submodule", "my_repo.ai_tools.devices")
        self.register("from_an_app", "some_app.tools")

        found = tools.tools_from_module("my_repo.ai_tools")

        self.assertEqual(sorted(found), ["from_repo", "from_submodule"])

    def test_a_prefix_does_not_match_a_longer_name(self):
        """`my_repo` must not claim `my_repo_two`."""
        self.register("elsewhere", "my_repo_two.ai_tools")

        self.assertEqual(tools.tools_from_module("my_repo.ai_tools"), {})

    def test_unregistering_a_module_leaves_the_others(self):
        """A sync reloads one repository. It must not empty the registry."""
        self.register("from_repo", "my_repo.ai_tools")
        self.register("from_an_app", "some_app.tools")

        dropped = tools.unregister_module("my_repo.ai_tools")

        self.assertEqual(dropped, ["from_repo"])
        self.assertEqual(sorted(tools.registered_tools()), ["from_an_app"])


class ReimportTest(EmptyRegistryMixin, TestCase):
    """Test what happens when one module registers the same tool twice.

    A private import runs a module body twice, and each sync imports a Git repository again. Both
    hand back a new function object for the same source, so object identity cannot decide whether
    this is the same tool again.
    """

    @staticmethod
    def build(description="Look something up."):
        """Return a fresh function object standing in for a reloaded one.

        Args:
            description: The docstring to give it.

        Returns:
            The function.
        """

        def lookup_device(hostname: str) -> str:
            pass

        lookup_device.__doc__ = description
        return lookup_device

    def test_the_same_function_from_the_same_module_replaces_itself(self):
        """A reload is not a name clash. Refusing one would refuse every sync after the first."""
        tools.register_ai_tool(self.build(), writable=False)
        tools.register_ai_tool(self.build("Look something up. Reworded."), writable=False)

        registered = tools.get_registered_tool("lookup_device")
        self.assertEqual(registered.description, "Look something up. Reworded.")
        self.assertEqual(len(tools.registered_tools()), 1)

    def test_a_different_function_still_cannot_take_the_name(self):
        """One name, one callable. That rule is what a bound record depends on."""
        tools.register_ai_tool(self.build(), writable=False)

        with self.assertRaises(ValueError) as raised:

            @tools.register_ai_tool(name="lookup_device", writable=False)
            def something_else(value: str) -> str:
                """A different tool entirely."""

        self.assertIn("already registered", str(raised.exception))
