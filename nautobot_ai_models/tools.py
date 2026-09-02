"""Register Python callables that an agent may be given as tools.

A consuming app declares its tools in code, the way it declares Jobs. `SyncAITools` then writes one
`AITool` row for each tool, under the same policy that governs MCP tools.

The registry holds a name and a callable. It never holds an import path, and nothing here imports a
module that a database row named.

Two rules hold here:

* Registration happens at import time only. A consuming app registers in a module that Nautobot
  imports on start. A later registration makes a worker and a web process disagree.
* A registered tool declares whether it writes. The decorator takes `writable` and records the
  answer as `advertised_read_only`, against the `writable` column that a person decides.
"""

import inspect
import logging
import typing

from nautobot_ai_models.integrations import canonical_digest

logger = logging.getLogger(__name__)

_REGISTRY = {}

_JSON_TYPES = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


class RegisteredTool:  # pylint: disable=too-few-public-methods
    """One callable a consuming app offered, and everything the registry knows about it."""

    __slots__ = ["argument_schema", "callable", "description", "module", "name", "qualname", "writable"]

    def __init__(  # pylint: disable=too-many-arguments
        self, *, name, description, callable_, argument_schema, module, qualname, writable
    ):
        """Hold what registration worked out.

        Args:
            name: The name a model calls this tool by.
            description: What the model reads when it decides to call it.
            callable_: The function itself. Named with a trailing underscore because `callable` is
                a builtin.
            argument_schema: The parameters, as JSON Schema.
            module: Where the function was found, for an operator tracing it back.
            qualname: The function's qualified name, which with the module identifies it across a
                reload.
            writable: Whether calling it changes something.
        """
        self.name = name
        self.description = description
        self.callable = callable_
        self.argument_schema = argument_schema
        self.module = module
        self.qualname = qualname
        self.writable = writable

    def __repr__(self):
        """Represent the tool by its name and whether it writes."""
        return f"<RegisteredTool: {self.name} writable={self.writable}>"

    @property
    def identity(self):
        """What makes this the same function after a reload.

        A reloaded module hands back new function objects, so the object cannot say whether a second
        registration is the same tool again or a second tool that takes the name. The module and the
        qualified name can.

        Returns:
            tuple: The module and the qualified name.
        """
        return (self.module, self.qualname)

    @property
    def definition_fingerprint(self):
        """A digest of everything a model is told about this tool.

        `integrations.canonical_digest` hashes it, with the same recipe that
        `services.mcp.definition_fingerprint` uses for an MCP tool, so an approval checked against
        either digest is checked against one idea.

        Returns:
            str: A hex SHA-256 digest.
        """
        return canonical_digest(
            {
                "name": self.name,
                "description": self.description,
                "argument_schema": self.argument_schema,
            }
        )


def register_ai_tool(function=None, *, name=None, description=None, writable=None):
    """Register one callable as a tool an agent may be given.

    Use it bare or with arguments::

        @register_ai_tool(writable=False)
        def lookup_device(hostname: str) -> str:
            \"\"\"Look up one device by hostname. Returns vendor, site, and platform.\"\"\"

    The name comes from the function, the description from its docstring, and the argument schema
    from its type hints. An explicit value overrides each of those.

    Args:
        function: The callable, when the decorator is used bare.
        name: Overrides the function's name.
        description: Overrides the function's docstring.
        writable: Whether a call to this changes something. Required.

    Returns:
        The callable, unchanged, or the decorator when called with arguments.

    Raises:
        ValueError: `writable` was not given, the callable has no description, or the name
            already belongs to a different function.
    """

    def decorate(target):
        tool_name = name or target.__name__
        tool_description = (description or inspect.getdoc(target) or "").strip()

        if writable is None:
            raise ValueError(
                f"Tool '{tool_name}' has to say whether it writes. Pass writable=True or writable=False. "
                "There is no default, because guessing either way is wrong in a different direction."
            )
        if not tool_description:
            raise ValueError(
                f"Tool '{tool_name}' needs a description. Give the function a docstring, or pass "
                "description=. The model reads it to decide whether to call the tool, and an empty "
                "one means the tool is never called."
            )

        target_module = getattr(target, "__module__", "")
        target_qualname = getattr(target, "__qualname__", target.__name__)

        existing = _REGISTRY.get(tool_name)
        if existing is not None and existing.identity != (target_module, target_qualname):
            raise ValueError(
                f"Tool '{tool_name}' is already registered by {existing.module}. Two tools cannot "
                "share a name; pass name= to one of them."
            )

        _REGISTRY[tool_name] = RegisteredTool(
            name=tool_name,
            description=tool_description,
            callable_=target,
            argument_schema=argument_schema_for(target),
            module=target_module,
            qualname=target_qualname,
            writable=writable,
        )
        logger.debug("Registered AI tool %s from %s", tool_name, getattr(target, "__module__", "?"))
        return target

    return decorate if function is None else decorate(function)


def argument_schema_for(target):
    """Build a JSON Schema object from a callable's signature.

    The schema holds only the shape a tool call needs: the parameter names, a type for each, and
    which of them have no default. An annotation this cannot read becomes a string, because a
    model sends text and a wrong guess at a richer type refuses a call that would have worked.

    Args:
        target: The callable to inspect.

    Returns:
        dict: A JSON Schema object.
    """
    try:
        signature = inspect.signature(target)
        hints = typing.get_type_hints(target)
    except (TypeError, ValueError, NameError):
        logger.warning("Could not read the signature of %r; offering it with no parameters.", target)
        return {"type": "object", "properties": {}}

    properties, required = {}, []
    for parameter in signature.parameters.values():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        properties[parameter.name] = {"type": _JSON_TYPES.get(hints.get(parameter.name), "string")}
        if parameter.default is parameter.empty:
            required.append(parameter.name)

    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def registered_tools():
    """Every tool registered in this process.

    Returns:
        dict: Registered tools, keyed by name. A copy, so a caller cannot edit the registry.
    """
    return dict(_REGISTRY)


def get_registered_tool(name):
    """One registered tool, or None.

    Args:
        name: The name to look up.

    Returns:
        RegisteredTool | None: The tool, or None when nothing registered that name.
    """
    return _REGISTRY.get(name)


def tools_from_module(module_prefix):
    """Every registered tool that came from one module or its submodules.

    Args:
        module_prefix: A module name, such as `my_repo.ai_tools`.

    Returns:
        dict: The matching tools, keyed by name.
    """
    return {
        name: tool
        for name, tool in _REGISTRY.items()
        if tool.module == module_prefix or tool.module.startswith(f"{module_prefix}.")
    }


def unregister_module(module_prefix):
    """Drop every tool that came from one module or its submodules.

    Each sync imports a Git repository again. Without this drop, a tool that the repository
    deleted stays registered for the life of the process, and nothing ever reports its record as
    missing.

    Args:
        module_prefix: A module name, such as `my_repo.ai_tools`.

    Returns:
        list: The names dropped.
    """
    dropped = sorted(tools_from_module(module_prefix))
    for name in dropped:
        _REGISTRY.pop(name, None)
    if dropped:
        logger.debug("Unregistered %s tool(s) from %s: %s", len(dropped), module_prefix, ", ".join(dropped))
    return dropped


def clear_registry():
    """Empty the registry.

    For tests. Nothing in the app calls this. Registration happens once at import time, and a
    process with an empty registry offers an agent no tools.
    """
    _REGISTRY.clear()
