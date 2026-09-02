"""Four things that every caller of an `ExternalIntegration` needs, written once.

`discovery.py`, `services/mcp.py`, and `services/agents.py` read the same integration and need the
same four answers: the timeout, the TLS verify setting, the rendered value of a Jinja2 field, and
the digest that stands for a definition. Each module held its own copy. Two modules that compute a
digest differently make an approval gate that two tool sources pass differently.

This is a leaf module. It imports no model and no service, so anything may import it.
"""

import hashlib
import json

from nautobot_ai_models.constants import DEFAULT_TIMEOUT_SECONDS


def integration_timeout(integration):
    """The integration's request timeout, or the shipped default.

    A stored zero or null is a row that says nothing, rather than somebody asking for no limit.

    Args:
        integration: The ExternalIntegration to read.

    Returns:
        int | float: A positive timeout in seconds.
    """
    timeout = getattr(integration, "timeout", None)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        return DEFAULT_TIMEOUT_SECONDS
    return timeout


def integration_verify(integration):
    """What an HTTP client's `verify` argument should be for this integration.

    A cleared *Verify SSL* beats a CA file path. An operator who turned verification off meant it,
    and a CA file given to a client that does not verify is a contradiction.

    Args:
        integration: The ExternalIntegration to read.

    Returns:
        bool | str: False to skip verification, a CA file path, or True.
    """
    if not integration.verify_ssl:
        return False
    return integration.ca_file_path or True


def render_field(integration, method_name, obj, error_class, *, include_error=True):
    """Render one Jinja2-templated field off an integration.

    The remote URL, the headers, and the extra config all support Jinja2, so a raw column would
    hand a template string to an HTTP client.

    Args:
        integration: The ExternalIntegration to read.
        method_name: The render method to call, such as `render_remote_url`.
        obj: The object the template addresses as `obj`.
        error_class: The exception to raise when the template will not render.
        include_error: Whether to report what the template engine said. False reports the
            exception type only, for a caller whose message could otherwise carry the rendered URL.

    Returns:
        The rendered value.

    Raises:
        Exception: `error_class`, when the template will not render.
    """
    try:
        return getattr(integration, method_name)({"obj": obj})
    except Exception as error:  # pylint: disable=broad-except
        detail = error if include_error else f"{type(error).__name__}."
        raise error_class(
            f"External integration '{integration}' has a template that does not render: {detail}"
        ) from error


def canonical_digest(fields):
    """Digest everything a tool advertises about itself.

    The keys are sorted and the separators are fixed, so a serialisation order does not move the
    digest. Every tool source hashes through here, so two approvals checked against two digests are
    checked against one idea.

    Args:
        fields: What the source said, as a JSON-serialisable mapping.

    Returns:
        str: A hex SHA-256 digest.
    """
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
