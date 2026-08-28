"""The MCP service layer: the one module in this app that speaks MCP.

Asks a server what it offers and writes the answer onto the registry. It calls no tool. The client
library is imported here only, lazily, behind the optional ``discovery`` extra. A server's own
annotations are recorded and acted on by nothing.

``writable`` is never written here. ``enabled`` is written only to turn a tool off.
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from nautobot.apps.choices import SecretsGroupSecretTypeChoices

from nautobot_ai_models.app_settings import DISABLE_ON_DEFINITION_CHANGE, NEW_TOOLS_ENABLED, app_setting
from nautobot_ai_models.choices import MCPTransportChoices
from nautobot_ai_models.constants import DEFAULT_TIMEOUT_SECONDS
from nautobot_ai_models.models import MCPTool
from nautobot_ai_models.secrets import read_secret
from nautobot_ai_models.services.exceptions import MCPCallError, MCPConfigurationError

logger = logging.getLogger(__name__)

SSE_READ_TIMEOUT_SECONDS = 300

MAX_TOOL_PAGES = 50

AUTHORIZATION_HEADER = "Authorization"

DISCOVERABLE_TRANSPORTS = (MCPTransportChoices.TYPE_STREAMABLE_HTTP,)


@dataclass(frozen=True)
class MCPConnection:
    """Everything needed to reach one server, resolved from its integration.

    ``verify`` follows httpx's convention: True, False, or a path to a CA bundle.
    """

    url: str
    headers: dict = field(default_factory=dict)
    verify: object = True
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    def __repr__(self):
        """Render everything except the header values, one of which is usually the credential."""
        headers = ", ".join(sorted(self.headers))
        return f"MCPConnection(url={self.url!r}, headers=[{headers}], verify={self.verify!r}, timeout={self.timeout!r})"


@dataclass(frozen=True)
class ServerInfo:
    """What a server said about itself.

    Every field is self-reported and unverified. Stored for display, read by nothing that decides.
    """

    protocol_version: str = ""
    name: str = ""
    version: str = ""
    instructions: str = ""
    capabilities: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ToolDefinition:
    """One tool as a server advertised it, before this app has any opinion about it."""

    name: str
    title: str = ""
    description: str = ""
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    read_only_hint: bool = None


@dataclass(frozen=True)
class DiscoveryPolicy:
    """What a discovery pass may do to an operator's ``enabled`` column.

    Resolved once in :func:`discover` and threaded down. ``remove_stale`` is not here: that is a
    per-run choice, and these two are a standing decision.
    """

    new_tools_enabled: bool = True
    disable_on_definition_change: bool = False

    @classmethod
    def from_settings(cls):
        """Read the policy out of PLUGINS_CONFIG.

        Returns:
            DiscoveryPolicy: The configured policy.
        """
        return cls(
            new_tools_enabled=bool(app_setting(NEW_TOOLS_ENABLED)),
            disable_on_definition_change=bool(app_setting(DISABLE_ON_DEFINITION_CHANGE)),
        )


@dataclass(frozen=True)
class DiscoveryReport:
    """What one discovery pass changed, in the terms an operator needs to act on."""

    added: tuple = ()
    updated: tuple = ()
    definition_changed: tuple = ()
    disabled_by_change: tuple = ()
    missing: tuple = ()
    removed: tuple = ()

    @property
    def needs_attention(self):
        """The tools somebody has to look at: newly offered, or changed since they were reviewed."""
        return tuple(self.added) + tuple(self.definition_changed)

    def summary(self):
        """One line for a log or a Job result."""
        return (
            f"{len(self.added)} new, {len(self.updated)} updated, "
            f"{len(self.definition_changed)} changed definition "
            f"({len(self.disabled_by_change)} disabled), "
            f"{len(self.missing)} no longer offered, {len(self.removed)} deleted"
        )


def require_client():
    """Resolve the MCP client now, so a missing ``discovery`` extra fails early.

    Raises:
        ImproperlyConfigured: The extra is not installed. Deliberately outside ``MCPError``, so a
            handler for an unreachable server does not swallow it.
    """
    _default_client()


def connection_for(server):
    """Read everything the server's integration says about reaching it.

    The credential becomes an ``Authorization: Bearer`` header unless the integration's own headers
    already carry one.

    Args:
        server: The MCPServer to connect to.

    Returns:
        MCPConnection: The resolved connection.

    Raises:
        MCPConfigurationError: The integration carries no remote URL.
    """
    integration = server.external_integration

    url = _rendered(integration, "render_remote_url", server)
    if not url:
        raise MCPConfigurationError(f"MCP server '{server}' has an external integration with no remote URL.")

    headers = dict(_rendered(integration, "render_headers", server) or {})
    if not any(key.lower() == AUTHORIZATION_HEADER.lower() for key in headers):
        for secret_type in (SecretsGroupSecretTypeChoices.TYPE_TOKEN, SecretsGroupSecretTypeChoices.TYPE_SECRET):
            token = read_secret(integration, secret_type)
            if token:
                headers[AUTHORIZATION_HEADER] = f"Bearer {token}"
                break

    if not integration.verify_ssl:
        verify = False
    elif integration.ca_file_path:
        verify = integration.ca_file_path
    else:
        verify = True

    timeout = getattr(integration, "timeout", None)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        timeout = DEFAULT_TIMEOUT_SECONDS

    return MCPConnection(url=url, headers=headers, verify=verify, timeout=timeout)


def discover(server, *, remove_stale=False, client=None, policy=None):
    """Read a server's identity and tool list, and reconcile the registry with it.

    Args:
        server: The MCPServer to read.
        remove_stale: Delete tools the server no longer advertises instead of disabling them.
        client: The test seam. An object with ``describe(connection)``. Nothing outside a test
            supplies one.
        policy: Read from settings when not given.

    Returns:
        DiscoveryReport: What the pass changed.

    Raises:
        MCPConfigurationError: The server cannot be reached because of how it is configured.
        MCPCallError: The server was reached and would not answer usably.
    """
    if not server.enabled:
        raise MCPConfigurationError(f"MCP server '{server}' is disabled.")

    if server.transport not in DISCOVERABLE_TRANSPORTS:
        raise MCPConfigurationError(
            f"MCP server '{server}' uses the '{server.transport}' transport, which a Nautobot "
            "worker cannot open. Register its tools by hand."
        )

    connection = connection_for(server)
    caller = client if client is not None else _default_client()
    policy = policy if policy is not None else DiscoveryPolicy.from_settings()

    try:
        info, advertised = caller.describe(connection)
    except Exception as error:  # pylint: disable=broad-except
        raise MCPCallError(f"Could not read the tools on '{server}': {_cause(error)}") from error

    report = _reconcile(server, tuple(advertised), remove_stale=remove_stale, policy=policy)
    _record_server_info(server, info)
    logger.info("Discovered tools on MCP server %s: %s", server, report.summary())
    return report


def _cause(error, _depth=0):
    """Name the exception types that went wrong, not the wrapper that carried them.

    The MCP client runs on anyio task groups, so a DNS failure reaches this module as
    ``unhandled errors in a TaskGroup``. Only the type name is returned: an HTTP client's message
    embeds the request URL, which an operator may have written a credential into, and it would
    land in a JobLogEntry.

    Args:
        error: The exception to unwrap.
        _depth: Recursion guard.

    Returns:
        str: The type names, joined by ``; ``.
    """
    inner = getattr(error, "exceptions", None)
    if not inner or _depth >= 5:
        return type(error).__name__
    return "; ".join(_cause(sub, _depth + 1) for sub in inner)


def _record_server_info(server, info):
    """Write what the server said about itself, and stamp the run.

    The stamp goes on last, so ``last_discovered_at`` records a refresh rather than an attempt.

    Args:
        server: The MCPServer to write to.
        info: What the handshake returned.

    Raises:
        MCPCallError: The server reported metadata the registry cannot hold.
    """
    server.protocol_version = info.protocol_version or ""
    server.server_name = info.name or ""
    server.server_version = info.version or ""
    server.instructions = info.instructions or ""
    server.capabilities = info.capabilities or {}
    server.last_discovered_at = timezone.now()

    try:
        server.validated_save()
    except (ValidationError, IntegrityError) as error:
        raise MCPCallError(f"'{server}' reported metadata this registry cannot hold: {error}") from error


def _reconcile(server, advertised, *, remove_stale, policy):
    """Write what was advertised onto the registry, in one transaction.

    Args:
        server: The MCPServer being discovered.
        advertised: The tools the server offered.
        remove_stale: Delete tools no longer advertised instead of disabling them.
        policy: What this pass may do to ``enabled``.

    Returns:
        DiscoveryReport: What the pass changed.

    Raises:
        MCPCallError: The server advertised a tool the registry cannot hold.
    """
    now = timezone.now()

    try:
        with transaction.atomic():
            existing = {tool.name: tool for tool in server.tools.all()}
            added, updated, definition_changed, disabled_by_change = _upsert(server, advertised, existing, now, policy)

            advertised_names = {definition.name for definition in advertised}
            stale = tuple(tool for name, tool in sorted(existing.items()) if name not in advertised_names)
            missing, removed = _retire(stale, remove_stale=remove_stale)
    except (ValidationError, IntegrityError) as error:
        raise MCPCallError(f"'{server}' advertised a tool this registry cannot hold: {error}") from error

    return DiscoveryReport(
        added=added,
        updated=updated,
        definition_changed=definition_changed,
        disabled_by_change=disabled_by_change,
        missing=missing,
        removed=removed,
    )


def _upsert(server, advertised, existing, now, policy):
    """Create or refresh a row for each advertised tool.

    ``existing`` is mutated as it goes, so a server advertising one name twice updates its own
    first row instead of colliding on the unique constraint.

    Args:
        server: The MCPServer being discovered.
        advertised: The tools the server offered.
        existing: Tools already in the registry, keyed by name. Mutated.
        now: The timestamp for this pass.
        policy: What this pass may do to ``enabled``.

    Returns:
        tuple: added, updated, definition_changed, disabled_by_change.
    """
    added, updated, definition_changed, disabled_by_change = [], [], [], []

    for definition in advertised:
        fingerprint = definition_fingerprint(definition)
        tool = existing.get(definition.name)

        if tool is None:
            tool = _create(server, definition, fingerprint, now, enabled=policy.new_tools_enabled)
            existing[tool.name] = tool
            added.append(tool)
            continue

        changed, disabled = _update(
            tool, definition, fingerprint, now, disable_on_change=policy.disable_on_definition_change
        )
        (definition_changed if changed else updated).append(tool)
        if disabled:
            disabled_by_change.append(tool)

    return tuple(added), tuple(updated), tuple(definition_changed), tuple(disabled_by_change)


def _create(server, definition, fingerprint, now, *, enabled):
    """Write a newly advertised tool.

    ``writable`` stays at its model default of True: the tool is assumed to change something until
    a person says otherwise. The server's ``readOnlyHint`` is recorded beside it and decides
    nothing. ``enabled`` answers a different question, so the caller decides it.

    Args:
        server: The MCPServer that advertised the tool.
        definition: What the server said about it.
        fingerprint: The digest of that definition.
        now: The timestamp for this pass.
        enabled: Whether the tool arrives on offer.

    Returns:
        MCPTool: The saved row.
    """
    tool = MCPTool(
        mcp_server=server,
        name=definition.name,
        title=definition.title or "",
        description=definition.description or "",
        input_schema=definition.input_schema or {},
        output_schema=definition.output_schema or {},
        enabled=enabled,
        advertised_read_only=definition.read_only_hint,
        definition_fingerprint=fingerprint,
        last_seen_at=now,
    )
    tool.validated_save()
    return tool


def _update(tool, definition, fingerprint, now, *, disable_on_change):
    """Refresh what the server says about an existing tool.

    ``writable`` is never written here. ``enabled`` is written only when ``disable_on_change`` is
    set and the fingerprint moved under a tool that was on and that discovery had seen before. The
    row keeps its schemas, its description, and its review history.

    A tool entered by hand carries no fingerprint and no ``last_seen_at``, so its first sight is a
    first sight and not a change. Switching one off would undo a review that had just been done.

    Args:
        tool: The row to refresh.
        definition: What the server said about it.
        fingerprint: The digest of that definition.
        now: The timestamp for this pass.
        disable_on_change: Clear ``enabled`` when the fingerprint moved.

    Returns:
        tuple[bool, bool]: Whether the definition moved, and whether this call switched the tool
            off.
    """
    changed = tool.definition_fingerprint != fingerprint

    if not changed and tool.last_seen_at is not None:
        return False, False

    disabled = changed and disable_on_change and tool.enabled and tool.last_seen_at is not None

    tool.title = definition.title or ""
    tool.description = definition.description or ""
    tool.input_schema = definition.input_schema or {}
    tool.output_schema = definition.output_schema or {}
    tool.advertised_read_only = definition.read_only_hint
    tool.definition_fingerprint = fingerprint
    tool.last_seen_at = now
    if disabled:
        tool.enabled = False
    tool.validated_save()
    return changed, disabled


def _retire(stale, *, remove_stale):
    """Deal with tools the server no longer advertises.

    Disabling is the default, because it keeps the description, the schema, and the review.
    ``last_seen_at`` is not touched: it is the evidence of when the tool went away.

    Args:
        stale: The tools no longer advertised.
        remove_stale: Delete them instead of disabling them.

    Returns:
        tuple: The tools disabled by this run, and the labels of those deleted.
    """
    disabled, deleted = [], []
    for tool in stale:
        if remove_stale:
            deleted.append(str(tool))
            tool.delete()
            continue
        if tool.enabled:
            tool.enabled = False
            tool.validated_save()
            disabled.append(tool)
    return tuple(disabled), tuple(deleted)


def definition_fingerprint(definition):
    """Digest everything a server said about one tool.

    The description is included as well as the schemas: it is half of what a reviewer read, and it
    is the sentence a compromised server would rewrite while leaving the arguments alone. Keys are
    sorted, so a serialisation order does not move the digest.

    Args:
        definition: What the server advertised.

    Returns:
        str: A hex SHA-256 digest.
    """
    canonical = json.dumps(
        {
            "title": definition.title or "",
            "description": definition.description or "",
            "input_schema": definition.input_schema or {},
            "output_schema": definition.output_schema or {},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _rendered(integration, method_name, server):
    """Render one of the integration's Jinja2 fields.

    All of remote URL, headers, and extra config support Jinja2, so the raw column would hand a
    template string to httpx.

    Args:
        integration: The ExternalIntegration to read.
        method_name: The render method to call.
        server: The object the template renders against.

    Returns:
        The rendered value.

    Raises:
        MCPConfigurationError: The template could not be rendered.
    """
    try:
        return getattr(integration, method_name)({"obj": server})
    except Exception as error:  # pylint: disable=broad-except
        raise MCPConfigurationError(
            f"External integration '{integration}' has a template that does not render: {error}"
        ) from error


def _attr(obj, *names, default=None):
    """Return the first of ``names`` the object has.

    The MCP schema names its fields in camel case and the Python SDK in snake case, and which one
    answers has moved between SDK releases.

    Args:
        obj: The object to read.
        *names: Attribute names to try, in order.
        default: Returned when none of them is set.

    Returns:
        The first value found, or ``default``.
    """
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def _as_dict(value):
    """A plain dict from whatever the SDK handed back - a model, a mapping, or nothing."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    for method in ("model_dump", "dict"):
        dumper = getattr(value, method, None)
        if callable(dumper):
            try:
                return dumper(exclude_none=True)
            except TypeError:
                return dumper()
    return {}


def _redirect_safe_client_class(base_class, protected_headers):
    """Build an HTTP client that drops the integration's headers on a cross-origin redirect.

    The session must follow a redirect, because ``/mcp`` to ``/mcp/`` is ordinary. An HTTP client
    strips only ``Authorization`` when the origin changes, so a server answering
    ``302 Location: https://elsewhere/`` would be handed an ``X-Api-Key`` verbatim.

    Args:
        base_class: The client class to subclass.
        protected_headers: The header names to drop off-origin.

    Returns:
        type | None: The subclass, or None when the library exposes no redirect hook. The caller
            then refuses redirects, which fails loudly rather than leaking quietly.
    """
    if not hasattr(base_class, "_redirect_headers"):
        return None

    lowered = {name.lower() for name in protected_headers}

    class _RedirectSafeClient(base_class):  # pylint: disable=too-few-public-methods
        """Strip the integration's headers whenever a redirect leaves the origin."""

        def _redirect_headers(self, request, url, method):
            headers = super()._redirect_headers(request, url, method)
            same_origin = (url.scheme, url.host, url.port) == (
                request.url.scheme,
                request.url.host,
                request.url.port,
            )
            if not same_origin:
                for name in list(headers.keys()):
                    if name.lower() in lowered:
                        del headers[name]
            return headers

    return _RedirectSafeClient


class _StreamableHTTPClient:  # pylint: disable=too-few-public-methods
    """One MCP session per discovery pass, over HTTP and nothing else.

    A session per pass rather than a pooled one: discovery runs from a Job that does not outlive
    its run. The SDK is asynchronous and every caller here is not, so each pass is one
    ``asyncio.run``, which is correct in a Celery worker and in a WSGI request.
    """

    def __init__(self, session_class, transport, http_client_class, timeout_class):
        """Hold the four pieces of the SDK and its HTTP client that this module uses."""
        self._session_class = session_class
        self._transport = transport
        self._http_client_class = http_client_class
        self._timeout_class = timeout_class

    def describe(self, connection):
        """Read what the server is and every tool it advertises, in one session.

        Args:
        connection: Where and how to connect.

        Returns:
        tuple: A ServerInfo and a tuple of ToolDefinition.
        """
        info, pages = self._run(connection, self._describe)
        definitions = []
        for page in pages:
            definitions.extend(_tool_definition(tool) for tool in page.tools)
        return info, tuple(definitions)

    async def _describe(self, session, initialized):
        """Read the session's own handshake result, then every page of the tool list."""
        return _server_info(initialized), await self._pages(session)

    async def _pages(self, session):
        """Read every page of the tool list, in order.

        Bounded by ``MAX_TOOL_PAGES``, so a cursor pointing at itself is not an infinite loop.

        Args:
            session: The open MCP session.

        Returns:
            list: Every tool the server advertised.
        """
        from mcp import types  # pylint: disable=import-outside-toplevel

        pages = []
        cursor = None
        for _ in range(MAX_TOOL_PAGES):
            params = types.PaginatedRequestParams(cursor=cursor) if cursor else None
            page = await session.list_tools(params=params)
            pages.append(page)
            cursor = _attr(page, "next_cursor", "nextCursor")
            if not cursor:
                return pages
        logger.warning("Stopped reading tool pages after %s; the server kept offering a cursor", MAX_TOOL_PAGES)
        return pages

    def _run(self, connection, operation):
        """Open a session, do one thing, close it."""
        client_class = _redirect_safe_client_class(self._http_client_class, connection.headers)
        follow_redirects = client_class is not None
        if client_class is None:
            client_class = self._http_client_class
            logger.warning(
                "The HTTP client does not expose its redirect hook, so redirects will not be "
                "followed. A server that redirects its endpoint cannot be discovered."
            )

        async def _once():
            async with client_class(
                headers=connection.headers,
                verify=connection.verify,
                timeout=self._timeout_class(
                    connect=connection.timeout,
                    write=connection.timeout,
                    pool=connection.timeout,
                    read=max(connection.timeout, SSE_READ_TIMEOUT_SECONDS),
                ),
                follow_redirects=follow_redirects,
            ) as http_client:
                async with self._transport(connection.url, http_client=http_client) as (read, write):
                    async with self._session_class(read, write, read_timeout_seconds=connection.timeout) as session:
                        initialized = await session.initialize()
                        return await operation(session, initialized)

        try:
            return asyncio.run(_once())
        except RuntimeError as error:
            if "running event loop" not in str(error):
                raise
            raise MCPCallError(
                "MCP discovery is made from synchronous code and cannot run inside an event loop."
            ) from error


def _server_info(initialized):
    """Build a ServerInfo from the SDK's handshake result.

    Every field is optional. A missing one becomes an empty string.

    Args:
        initialized: The SDK's initialize result.

    Returns:
        ServerInfo: What the server reported.
    """
    reported = _attr(initialized, "server_info", "serverInfo")
    return ServerInfo(
        protocol_version=str(_attr(initialized, "protocol_version", "protocolVersion", default="") or ""),
        name=str(_attr(reported, "name", default="") or "") if reported is not None else "",
        version=str(_attr(reported, "version", default="") or "") if reported is not None else "",
        instructions=str(_attr(initialized, "instructions", default="") or ""),
        capabilities=_as_dict(getattr(initialized, "capabilities", None)),
    )


def _tool_definition(tool):
    """A `ToolDefinition` from one of the SDK's tool objects."""
    annotations = getattr(tool, "annotations", None)
    return ToolDefinition(
        name=tool.name,
        title=str(_attr(tool, "title", default="") or ""),
        description=str(_attr(tool, "description", default="") or ""),
        input_schema=_as_dict(_attr(tool, "input_schema", "inputSchema")),
        output_schema=_as_dict(_attr(tool, "output_schema", "outputSchema")),
        read_only_hint=_attr(annotations, "read_only_hint", "readOnlyHint") if annotations is not None else None,
    )


def _default_client():
    """The one place the MCP client library exists. Imported lazily."""
    try:
        import httpx2  # pylint: disable=import-outside-toplevel
        from mcp import ClientSession  # pylint: disable=import-outside-toplevel
        from mcp.client.streamable_http import streamable_http_client  # pylint: disable=import-outside-toplevel
    except ImportError as error:
        raise ImproperlyConfigured(
            "The MCP client could not be imported, so no server can be discovered: "
            f"{type(error).__name__}: {error}. "
            "If it is not installed, install the app with the 'discovery' extra: "
            "nautobot-ai-models[discovery]."
        ) from error
    return _StreamableHTTPClient(ClientSession, streamable_http_client, httpx2.AsyncClient, httpx2.Timeout)
