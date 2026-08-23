"""The MCP service layer: the one module in this app that speaks MCP.

This app calls no tool. All this module does is ask a server what it offers and write the answer
onto the registry. The rules it holds to:

* The MCP client library is imported only here, lazily, behind the optional ``discovery`` extra. A
  deployment without it gets a plain ``ImproperlyConfigured`` naming the extra.
* The endpoint, its headers, its TLS settings and its timeout come from the server's
  ExternalIntegration at connection time, and the credential from that integration's secrets group.
  Nothing key-shaped lives in settings, on a model, or in a log line.
* Discovery owns the fields a server told us about. It never writes ``enabled`` or ``writable`` on
  a tool that still exists: those two belong to a person. The one exception is a tool the server
  stopped advertising, which is disabled so it stops being handed out.
* A server's own annotations are recorded and acted on by nothing. The MCP specification requires
  that a client treat annotations as untrusted, and deciding "this tool is safe" from the claim of
  the server the claim describes is exactly the decision it forbids.

Moved here from nautobot-app-mcp-models when the two registries merged into one app. The
tool-calling half is deliberately absent.
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

from nautobot_ai_models.choices import MCPTransportChoices
from nautobot_ai_models.constants import DEFAULT_TIMEOUT_SECONDS
from nautobot_ai_models.models import MCPTool
from nautobot_ai_models.secrets import read_secret
from nautobot_ai_models.services.exceptions import MCPCallError, MCPConfigurationError

logger = logging.getLogger(__name__)

#: How long the read side of a session may wait. The transport keeps a server-sent-event stream
#: open, so the read deadline is not the request deadline and must not be set from it. Matches what
#: the SDK's own HTTP client factory uses.
SSE_READ_TIMEOUT_SECONDS = 300

#: A ceiling on tool-list pages, so a server offering a cursor that never ends cannot hold a worker
#: open forever. Far above any real tool list.
MAX_TOOL_PAGES = 50

#: How the credential is presented when the integration's own headers do not present it. Bearer is
#: what MCP servers over HTTP overwhelmingly expect; an operator who needs something else writes
#: that header on the integration, and this defers to them.
AUTHORIZATION_HEADER = "Authorization"

#: Transports this app can open from a Nautobot worker.
#:
#: A stdio server is a subprocess of its client, so there is nothing for a worker to connect
#: to. HTTP+SSE is absent for a different reason: this module speaks streamable HTTP and only
#: streamable HTTP, so listing SSE here would send every such server through a client that
#: cannot talk to it, and the operator would get an opaque failure instead of the skip notice
#: that tells them to enter the tools by hand.
DISCOVERABLE_TRANSPORTS = (MCPTransportChoices.TYPE_STREAMABLE_HTTP,)


@dataclass(frozen=True)
class MCPConnection:
    """Everything needed to reach one server, resolved from its integration.

    ``verify`` carries httpx's own convention rather than a pair of fields: True, False, or the
    path to a CA bundle.
    """

    url: str
    headers: dict = field(default_factory=dict)
    verify: object = True
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    def __repr__(self):
        """Say everything except the header values, one of which is usually the credential.

        A dataclass renders its whole contents by default, and this one is passed around, held in
        tracebacks and - with ``DEBUG`` on - rendered onto an error page. The header *names* are
        worth seeing when something is misconfigured; their values never are.
        """
        headers = ", ".join(sorted(self.headers))
        return f"MCPConnection(url={self.url!r}, headers=[{headers}], verify={self.verify!r}, timeout={self.timeout!r})"


@dataclass(frozen=True)
class ServerInfo:
    """What a server said about itself, before this app has any opinion about it.

    Every field is self-reported and unverified. Stored for display and for an operator's
    debugging, and read by nothing that makes a decision.
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
    #: The server's own claim that this tool only reads. Recorded and shown; never acted on.
    read_only_hint: bool = None


@dataclass(frozen=True)
class DiscoveryReport:
    """What one discovery pass changed, in the terms an operator needs to act on."""

    added: tuple = ()
    updated: tuple = ()
    definition_changed: tuple = ()
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
            f"{len(self.definition_changed)} changed definition, "
            f"{len(self.missing)} no longer offered, {len(self.removed)} deleted"
        )


def require_client():
    """Resolve the client now, so a missing ``discovery`` extra is a refusal rather than a later crash.

    The failure is an ``ImproperlyConfigured``, deliberately outside the ``MCPError`` family, so
    nothing that handles a server being unreachable swallows a deployment that cannot discover at
    all.
    """
    _default_client()


def connection_for(server):
    """Everything the server's ExternalIntegration says about reaching it, read now.

    The credential becomes an ``Authorization: Bearer`` header unless the integration's own headers
    already carry an Authorization, in which case the operator has said how this server is
    authenticated and this defers to them.
    """
    integration = server.external_integration

    url = _rendered(integration, "render_remote_url", server)
    if not url:
        # `clean()` demands a URL at save time, but an integration is a shared object and can be
        # blanked afterwards without revalidating what points at it.
        raise MCPConfigurationError(f"MCP server '{server}' has an external integration with no remote URL.")

    headers = dict(_rendered(integration, "render_headers", server) or {})
    if not any(key.lower() == AUTHORIZATION_HEADER.lower() for key in headers):
        for secret_type in (SecretsGroupSecretTypeChoices.TYPE_TOKEN, SecretsGroupSecretTypeChoices.TYPE_SECRET):
            token = read_secret(integration, secret_type)
            if token:
                headers[AUTHORIZATION_HEADER] = f"Bearer {token}"
                break

    # Unticking *Verify SSL* wins over a CA path: an operator who has done both has said not to
    # verify, and quietly verifying anyway is the surprise this rule exists to prevent.
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


def discover(server, *, remove_stale=False, client=None):
    """Read a server's identity and tool list, and reconcile the registry with it.

    ``client`` is the test seam - an object with ``describe(connection)`` - and nothing outside a
    test supplies one. No test opens a socket.

    Returns a `DiscoveryReport`. Raises `MCPConfigurationError` when the server cannot be reached
    because of how it is configured, and `MCPCallError` when the server was reached and would not
    answer usably.
    """
    if not server.enabled:
        # Reading a disabled server is harmless, and refusing it is still right: an operator who
        # disabled a server should not find its registry changing underneath them.
        raise MCPConfigurationError(f"MCP server '{server}' is disabled.")

    if server.transport not in DISCOVERABLE_TRANSPORTS:
        raise MCPConfigurationError(
            f"MCP server '{server}' uses the '{server.transport}' transport, which a Nautobot "
            "worker cannot open. Register its tools by hand."
        )

    connection = connection_for(server)
    caller = client if client is not None else _default_client()

    try:
        info, advertised = caller.describe(connection)
    except Exception as error:  # pylint: disable=broad-except
        # Whatever the client raised, the caller sees one family.
        raise MCPCallError(f"Could not read the tools on '{server}': {_cause(error)}") from error

    report = _reconcile(server, tuple(advertised), remove_stale=remove_stale)
    _record_server_info(server, info)
    logger.info("Discovered tools on MCP server %s: %s", server, report.summary())
    return report


def _cause(error, _depth=0):
    """The exception types naming what actually went wrong, not the wrapper that carried them.

    The MCP client runs on anyio task groups, so a DNS failure or a refused connection reaches this
    module as `unhandled errors in a TaskGroup (1 sub-exception)`. That sentence tells an operator
    nothing, and it is the sentence they get in the Job log. This digs out the real exceptions.

    Only the type name is returned. An HTTP client's own message embeds the request URL, and a
    remote URL is free text that an operator may well have written a credential into, as
    `https://user:password@host/mcp` or as a token query parameter. That message ends up in a
    JobLogEntry, which every holder of `extras.view_jobresult` can read - a wider audience than
    the one that may read the Secrets Group the credential came from. The status code and the type
    are what an operator needs; the URL they already know.
    """
    inner = getattr(error, "exceptions", None)
    if not inner or _depth >= 5:
        return type(error).__name__
    return "; ".join(_cause(sub, _depth + 1) for sub in inner)


def _record_server_info(server, info):
    """Write what the server said about itself, and stamp the run.

    The stamp goes on last and only on a run that got this far, so an operator reading
    ``last_discovered_at`` sees when the registry was actually refreshed rather than when somebody
    last tried.
    """
    server.protocol_version = info.protocol_version or ""
    server.server_name = info.name or ""
    server.server_version = info.version or ""
    server.instructions = info.instructions or ""
    server.capabilities = info.capabilities or {}
    server.last_discovered_at = timezone.now()

    # Every value above is self-reported by an unverified party and lands in a bounded column. A
    # server reporting a 300-character name must fail this one server, not raise out of the job
    # and skip every server after it.
    try:
        server.validated_save()
    except (ValidationError, IntegrityError) as error:
        raise MCPCallError(f"'{server}' reported metadata this registry cannot hold: {error}") from error


def _reconcile(server, advertised, *, remove_stale=False):
    """Write what was advertised onto the registry, and say what changed.

    One transaction: a server that advertises the same tool twice, or a name longer than the
    column, must not leave half a registry behind and half a discovery reported. Model validation
    catches both, and it raises `ValidationError`, which is outside the family every caller of this
    module handles - so it is translated here rather than escaping as a 500.
    """
    now = timezone.now()

    try:
        with transaction.atomic():
            existing = {tool.name: tool for tool in server.tools.all()}
            added, updated, definition_changed = _upsert(server, advertised, existing, now)

            advertised_names = {definition.name for definition in advertised}
            stale = tuple(tool for name, tool in sorted(existing.items()) if name not in advertised_names)
            missing, removed = _retire(stale, remove_stale=remove_stale)
    except (ValidationError, IntegrityError) as error:
        raise MCPCallError(f"'{server}' advertised a tool this registry cannot hold: {error}") from error

    return DiscoveryReport(
        added=added,
        updated=updated,
        definition_changed=definition_changed,
        missing=missing,
        removed=removed,
    )


def _upsert(server, advertised, existing, now):
    """Create or refresh a row for each advertised tool. Returns (added, updated, changed).

    `existing` is mutated as it goes, so a server advertising one name twice updates its own first
    row rather than colliding with it on the unique constraint. The caller reads it afterwards to
    work out what went missing.
    """
    added, updated, definition_changed = [], [], []

    for definition in advertised:
        fingerprint = definition_fingerprint(definition)
        tool = existing.get(definition.name)

        if tool is None:
            tool = _create(server, definition, fingerprint, now)
            existing[tool.name] = tool
            added.append(tool)
            continue

        changed = _update(tool, definition, fingerprint, now)
        (definition_changed if changed else updated).append(tool)

    return tuple(added), tuple(updated), tuple(definition_changed)


def _create(server, definition, fingerprint, now):
    """Write a newly advertised tool, believing the server about everything except what it may do.

    ``writable`` and ``enabled`` are left at their model defaults - the tool is offered, and it is
    assumed to change something until a person says otherwise. The server's ``readOnlyHint`` is
    recorded beside them and decides neither: it is written by the party a reviewer is checking,
    and a registry that let it through would let a hostile server file ``push_config`` under "safe".
    """
    tool = MCPTool(
        mcp_server=server,
        name=definition.name,
        title=definition.title or "",
        description=definition.description or "",
        input_schema=definition.input_schema or {},
        output_schema=definition.output_schema or {},
        advertised_read_only=definition.read_only_hint,
        definition_fingerprint=fingerprint,
        last_seen_at=now,
    )
    tool.validated_save()
    return tool


def _update(tool, definition, fingerprint, now):
    """Refresh what the server says about an existing tool. True when the definition moved.

    ``enabled`` and ``writable`` are the operator's two columns and are never written here. A
    changed definition is reported so somebody can look at it; acting on it is a policy decision,
    and this app holds no policy.
    """
    changed = tool.definition_fingerprint != fingerprint

    if not changed and tool.last_seen_at is not None:
        # Nothing to write but the timestamp, and this is a change-logged model: a nightly run
        # against a forty-tool server would otherwise file forty ObjectChange rows a night
        # recording that nothing happened. The stamp is worth less than the change log is.
        return False

    tool.title = definition.title or ""
    tool.description = definition.description or ""
    tool.input_schema = definition.input_schema or {}
    tool.output_schema = definition.output_schema or {}
    tool.advertised_read_only = definition.read_only_hint
    tool.definition_fingerprint = fingerprint
    tool.last_seen_at = now
    tool.validated_save()
    return changed


def _retire(stale, *, remove_stale):
    """Deal with tools the server no longer advertises. Returns (disabled, deleted).

    Disabling is the default because it loses nothing: the row keeps its description, its schema
    and whatever a reviewer decided, ``last_seen_at`` still says when the server last offered it,
    and a tool that comes back is one click from being in service again. Deleting is available for
    an operator who wants the table to mirror the server exactly, and has to be asked for.

    ``last_seen_at`` is deliberately not touched. It is the evidence of when the tool went away.
    """
    disabled, deleted = [], []
    for tool in stale:
        if remove_stale:
            deleted.append(str(tool))
            tool.delete()
            continue
        # Only a tool this run turned off. A tool disabled by an earlier run is already known,
        # and re-reporting it nightly forever trains an operator to ignore the one warning that
        # is meant to say something changed.
        if tool.enabled:
            tool.enabled = False
            tool.validated_save()
            disabled.append(tool)
    return tuple(disabled), tuple(deleted)


def definition_fingerprint(definition):
    """A stable digest of everything a server said about one tool, so "did this change" is one test.

    The description is in it as well as the schemas. It is half of what a reviewer read when they
    decided whether the tool writes - a schema rarely says that on its own - and in an agent's
    prompt it *is* the tool's semantics, which makes it the sentence a compromised server would
    rewrite while leaving the arguments alone.

    Sorted keys, because two servers - or two versions of one - may serialize the same schema in
    different orders, and a fingerprint that moves on a key ordering is an alarm an operator stops
    reading.
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
    """One of the integration's Jinja2-templated fields, rendered rather than read raw.

    All three of remote URL, headers and extra config support Jinja2, so reading the raw column
    would hand a template string to httpx.
    """
    try:
        return getattr(integration, method_name)({"obj": server})
    except Exception as error:  # pylint: disable=broad-except
        raise MCPConfigurationError(
            f"External integration '{integration}' has a template that does not render: {error}"
        ) from error


def _attr(obj, *names, default=None):
    """The first of ``names`` this object actually has.

    The MCP schema names its fields in camel case and the Python SDK exposes them in snake case,
    and which of the two an attribute answers to has moved between SDK releases. Asking for both is
    cheaper than pinning the SDK to a patch version.
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
    """An HTTP client that drops the integration's headers on a cross-origin redirect.

    The session has to follow a redirect, because an endpoint sending `/mcp` to `/mcp/` is
    ordinary and the SDK's own client factory allows it. But the headers on this client are the
    integration's, and `connection_for` puts whatever header an operator chose to authenticate
    with among them. An HTTP client strips only `Authorization` when the origin changes, so a
    server answering `302 Location: https://elsewhere/` would be handed an `X-Api-Key` verbatim.

    Returns None when the client library does not expose the hook this relies on. The caller then
    refuses to follow redirects at all, which fails loudly rather than quietly leaking.
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
    """The real client: one MCP session per discovery pass, over HTTP and nothing else.

    A session per pass rather than a pooled one. Discovery runs from a Job that does not outlive
    its own run, and a cached session would have to be invalidated on every registry edit.

    The SDK is asynchronous and every caller here is not, so each pass is one ``asyncio.run``. That
    is correct in a Celery worker and in a WSGI request, and it is wrong inside a running event
    loop - which this app has none of, and which the error below explains if that changes.
    """

    def __init__(self, session_class, transport, http_client_class, timeout_class):
        """Hold the four pieces of the SDK and its HTTP client that this module uses."""
        self._session_class = session_class
        self._transport = transport
        self._http_client_class = http_client_class
        self._timeout_class = timeout_class

    def describe(self, connection):
        """What the server says it is, and every tool it advertises. One session for both.

        ``tools/list`` is paginated: a server may answer with a page and a cursor. Reading one page
        would leave the rest unregistered, and would also report every tool from page two onwards
        as "no longer offered" on each run - which is the one signal an operator is meant to act
        on.
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
        """Every page of the tool list, in order.

        Bounded: a server that answered with a cursor pointing at itself would otherwise be an
        infinite loop inside a worker. The cap is far above any real tool list.
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
        # Redirects are allowed only while the integration's headers can be stripped when the
        # origin changes. See `_redirect_safe_client_class`.
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
                # Not a flat timeout. The SDK's own client factory documents why: the read side of
                # a streamable HTTP session is a long-lived server-sent-event stream, and a
                # 30-second read deadline cuts it mid-answer. The other three phases keep the
                # integration's number, which is what an operator set it for.
                timeout=self._timeout_class(
                    connect=connection.timeout,
                    write=connection.timeout,
                    pool=connection.timeout,
                    read=max(connection.timeout, SSE_READ_TIMEOUT_SECONDS),
                ),
                # An endpoint that redirects `/mcp` to `/mcp/` is ordinary, and without this the
                # session simply fails. The SDK's factory sets it for the same reason.
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
    """A `ServerInfo` from whatever the SDK's handshake returned.

    Everything is optional. A server that reports nothing about itself is still a server whose
    tools are worth reading, so a missing field is an empty string rather than a failure.
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
        # The cause is in the message on purpose: a dependency that is installed and unimportable
        # is not a missing extra, and telling somebody to install it again sends them the wrong way.
        raise ImproperlyConfigured(
            "The MCP client could not be imported, so no server can be discovered: "
            f"{type(error).__name__}: {error}. "
            "If it is not installed, install the app with the 'discovery' extra: "
            "nautobot-ai-models[discovery]."
        ) from error
    return _StreamableHTTPClient(ClientSession, streamable_http_client, httpx2.AsyncClient, httpx2.Timeout)
