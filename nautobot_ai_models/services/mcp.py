"""The MCP service layer. This is the one module in this app that speaks MCP.

This module asks a server what it offers and writes the answer onto the registry. It calls no tool.
It imports the client library lazily, behind the optional ``discovery`` extra. Nothing acts on the
annotations a server sends.

This module never writes ``writable``. It writes ``enabled`` only to turn a record off.

A server advertises three things: tools, resources, and prompts. One reconcile drives all three,
because a second copy of the never-delete policy is a second place for it to go wrong. This module
asks for a list only when the handshake said the server offers it: an unsupported method raises,
and one raised method must not fail a whole pass.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from nautobot.apps.choices import SecretsGroupSecretTypeChoices

from nautobot_ai_models.app_settings import DISABLE_ON_DEFINITION_CHANGE, NEW_TOOLS_ENABLED, app_setting
from nautobot_ai_models.choices import MCPTransportChoices
from nautobot_ai_models.constants import DEFAULT_TIMEOUT_SECONDS
from nautobot_ai_models.integrations import canonical_digest, integration_timeout, render_field
from nautobot_ai_models.models import MCPPrompt, MCPResource, MCPTool
from nautobot_ai_models.secrets import read_secret
from nautobot_ai_models.services.exceptions import MCPCallError, MCPConfigurationError

logger = logging.getLogger(__name__)

SSE_READ_TIMEOUT_SECONDS = 300

MAX_LIST_PAGES = 50

TOOLS_CAPABILITY = "tools"

RESOURCES_CAPABILITY = "resources"

PROMPTS_CAPABILITY = "prompts"

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
class ResourceDefinition:  # pylint: disable=too-many-instance-attributes
    """One resource as a server advertised it, before this app has any opinion about it."""

    uri: str
    name: str = ""
    title: str = ""
    description: str = ""
    mime_type: str = ""
    is_template: bool = False
    size: int = None
    annotations: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PromptDefinition:
    """One prompt template as a server advertised it."""

    name: str
    title: str = ""
    description: str = ""
    arguments: tuple = ()


@dataclass(frozen=True)
class AdvertisedCatalog:
    """Everything one server offered, in one answer.

    Each ``*_read`` flag says whether that list was read at all. A list the server does not offer,
    or one that failed on its own, leaves the flag clear, and the reconcile then retires nothing of
    that kind. Without the flag a single failed call would disable every reviewed row.
    """

    tools: tuple = ()
    resources: tuple = ()
    prompts: tuple = ()
    tools_read: bool = False
    resources_read: bool = False
    prompts_read: bool = False


@dataclass(frozen=True)
class DiscoveryPolicy:
    """What a discovery pass may do to an operator's ``enabled`` column.

    :func:`discover` resolves this once and threads it down. ``remove_stale`` is not here,
    because that is a per-run choice and these two are a standing decision.
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


@dataclass(frozen=True)
class ServerDiscoveryReport:
    """What one pass changed, split by the kind of thing the server advertises."""

    tools: DiscoveryReport = field(default_factory=DiscoveryReport)
    resources: DiscoveryReport = field(default_factory=DiscoveryReport)
    prompts: DiscoveryReport = field(default_factory=DiscoveryReport)

    def by_kind(self):
        """Each sub-report beside the label an operator reads.

        Returns:
            tuple: Pairs of a label and a DiscoveryReport, in a stable order.
        """
        return (("Tool", self.tools), ("Resource", self.resources), ("Prompt", self.prompts))

    def summary(self):
        """One line for a log or a Job result."""
        return "; ".join(f"{label.lower()}s: {report.summary()}" for label, report in self.by_kind())


@dataclass(frozen=True)
class RecordKind:
    """How one kind of advertised thing maps onto a registry table.

    One reconcile reads this instead of three near-identical copies of itself.
    """

    label: str
    model: type
    related_name: str
    key_field: str
    columns: tuple
    fingerprint_columns: tuple = ()

    def key(self, definition):
        """The value that identifies one advertised record within its server.

        Args:
            definition: What the server advertised.

        Returns:
            str: The key.
        """
        return getattr(definition, self.key_field)

    def values(self, definition):
        """The server-owned columns of one advertised record.

        Args:
            definition: What the server advertised.

        Returns:
            dict: Column names mapped to what the server said, with an empty value in place of
                None so that a column never holds a null it does not allow.
        """
        return {name: _blank_safe(getattr(definition, name)) for name in self.columns}

    def fingerprint(self, definition):
        """Digest what the server said about one record.

        The digest covers the description as well as the schema. The description is half of what a
        reviewer read, and it is the sentence a compromised server would rewrite while it left the
        rest alone.

        ``fingerprint_columns`` is separate from ``columns`` because a tool's ``readOnlyHint`` is
        stored and is not digested. Folding it in would move the digest of every tool already in
        the registry, which would retire every approval and, under
        ``disable_on_definition_change``, switch every tool off.

        Args:
            definition: What the server advertised.

        Returns:
            str: A hex SHA-256 digest.
        """
        names = self.fingerprint_columns or self.columns
        return canonical_digest({name: _blank_safe(getattr(definition, name)) for name in names})


def _blank_safe(value):
    """Return a value a column can hold, with None turned into an empty one where it must be.

    Args:
        value: What the server said.

    Returns:
        The value, or an empty string, dict, or list in place of a None the column refuses.
    """
    if value is None:
        return value
    if isinstance(value, tuple):
        return list(value)
    return value


TOOL_KIND = RecordKind(
    label="Tool",
    model=MCPTool,
    related_name="tools",
    key_field="name",
    columns=("title", "description", "input_schema", "output_schema", "read_only_hint"),
    fingerprint_columns=("title", "description", "input_schema", "output_schema"),
)

RESOURCE_KIND = RecordKind(
    label="Resource",
    model=MCPResource,
    related_name="resources",
    key_field="uri",
    columns=("name", "title", "description", "mime_type", "is_template", "size", "annotations"),
)

PROMPT_KIND = RecordKind(
    label="Prompt",
    model=MCPPrompt,
    related_name="prompts",
    key_field="name",
    columns=("title", "description", "arguments"),
)

COLUMN_ALIASES = {"read_only_hint": "advertised_read_only"}
"""The one column whose name on the wire is not its name in the registry."""


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

    return MCPConnection(url=url, headers=headers, verify=verify, timeout=integration_timeout(integration))


def discover(server, *, remove_stale=False, client=None, policy=None):
    """Read what a server offers, and reconcile the registry with it.

    Args:
        server: The MCPServer to read.
        remove_stale: Delete records the server no longer advertises instead of disabling them.
        client: The test seam. An object with ``describe(connection)``. Nothing outside a test
            supplies one.
        policy: Read from settings when not given.

    Returns:
        ServerDiscoveryReport: What the pass changed, split by kind.

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
        info, catalog = caller.describe(connection)
    except Exception as error:  # pylint: disable=broad-except
        raise MCPCallError(f"Could not read what '{server}' offers: {_cause(error)}") from error

    report = ServerDiscoveryReport(
        tools=_reconcile(server, TOOL_KIND, catalog.tools, catalog.tools_read, remove_stale, policy),
        resources=_reconcile(server, RESOURCE_KIND, catalog.resources, catalog.resources_read, remove_stale, policy),
        prompts=_reconcile(server, PROMPT_KIND, catalog.prompts, catalog.prompts_read, remove_stale, policy),
    )
    _record_server_info(server, info)
    logger.info("Discovered MCP server %s: %s", server, report.summary())
    return report


def _cause(error, _depth=0):
    """Name the exception types that went wrong, not the wrapper that carried them.

    The MCP client runs on anyio task groups, so a DNS failure reaches this module as ``unhandled
    errors in a TaskGroup``. This function returns the type name only. An HTTP client message
    embeds the request URL, an operator may have written a credential into that URL, and the
    message would land in a JobLogEntry.

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


def _reconcile(server, kind, advertised, was_read, remove_stale, policy):  # pylint: disable=too-many-arguments,too-many-locals
    """Write what was advertised onto one registry table, in one transaction.

    A list that was not read leaves the table alone. A server that offers no prompts, and a
    prompts call that failed on its own, must not disable every prompt somebody reviewed.

    Args:
        server: The MCPServer being discovered.
        kind: Which table this pass writes.
        advertised: What the server offered, of that kind.
        was_read: Whether that list was actually read.
        remove_stale: Delete records no longer advertised instead of disabling them.
        policy: What this pass may do to ``enabled``.

    Returns:
        DiscoveryReport: What the pass changed.

    Raises:
        MCPCallError: The server advertised a record the registry cannot hold.
    """
    if not was_read:
        return DiscoveryReport()

    now = timezone.now()
    advertised = tuple(advertised)

    try:
        with transaction.atomic():
            existing = {kind.key(record): record for record in getattr(server, kind.related_name).all()}
            added, updated, definition_changed, disabled_by_change = _upsert(
                server, kind, advertised, existing, now, policy
            )

            advertised_keys = {kind.key(definition) for definition in advertised}
            stale = tuple(record for key, record in sorted(existing.items()) if key not in advertised_keys)
            missing, removed = _retire(stale, remove_stale=remove_stale)
    except (ValidationError, IntegrityError) as error:
        raise MCPCallError(
            f"'{server}' advertised a {kind.label.lower()} this registry cannot hold: {error}"
        ) from error

    return DiscoveryReport(
        added=added,
        updated=updated,
        definition_changed=definition_changed,
        disabled_by_change=disabled_by_change,
        missing=missing,
        removed=removed,
    )


def _upsert(server, kind, advertised, existing, now, policy):  # pylint: disable=too-many-arguments,too-many-locals
    """Create or refresh a row for each advertised record.

    This function mutates ``existing`` as it goes, so a server that advertises one key twice
    updates its own first row instead of a collision on the unique constraint.

    Args:
        server: The MCPServer under discovery.
        kind: Which table this pass writes.
        advertised: What the server offered.
        existing: Rows already in the registry, keyed by their wire key. Mutated.
        now: The timestamp for this pass.
        policy: What this pass may do to ``enabled``.

    Returns:
        tuple: added, updated, definition_changed, disabled_by_change.
    """
    added, updated, definition_changed, disabled_by_change = [], [], [], []

    for definition in advertised:
        fingerprint = kind.fingerprint(definition)
        key = kind.key(definition)
        record = existing.get(key)

        if record is None:
            record = _create(server, kind, definition, fingerprint, now, enabled=policy.new_tools_enabled)
            existing[key] = record
            added.append(record)
            continue

        changed, disabled = _update(
            record, kind, definition, fingerprint, now, disable_on_change=policy.disable_on_definition_change
        )
        (definition_changed if changed else updated).append(record)
        if disabled:
            disabled_by_change.append(record)

    return tuple(added), tuple(updated), tuple(definition_changed), tuple(disabled_by_change)


def _columns_for(kind, definition):
    """The registry column names and values for one advertised record.

    Args:
        kind: Which table this pass writes.
        definition: What the server advertised.

    Returns:
        dict: Column names as the model spells them, mapped to what the server said.
    """
    return {COLUMN_ALIASES.get(name, name): value for name, value in kind.values(definition).items()}


def _create(server, kind, definition, fingerprint, now, *, enabled):  # pylint: disable=too-many-arguments
    """Write a newly advertised record.

    ``writable`` stays at its model default of True where the model has one. The record changes
    something until a person says otherwise, and the server's own hint sits beside it and decides
    nothing. ``enabled`` answers a different question, so the caller decides it.

    Args:
        server: The MCPServer that advertised it.
        kind: Which table this pass writes.
        definition: What the server said about it.
        fingerprint: The digest of that definition.
        now: The timestamp for this pass.
        enabled: Whether the record arrives on offer.

    Returns:
        The saved row.
    """
    record = kind.model(
        mcp_server=server,
        enabled=enabled,
        definition_fingerprint=fingerprint,
        last_seen_at=now,
        **{kind.key_field: kind.key(definition)},
        **_columns_for(kind, definition),
    )
    record.validated_save()
    return record


def _update(record, kind, definition, fingerprint, now, *, disable_on_change):  # pylint: disable=too-many-arguments
    """Refresh what the server says about an existing record.

    This function never writes ``writable``. It writes ``enabled`` only when ``disable_on_change``
    is set and the fingerprint moved under a record that was on and that discovery had seen before.
    The row keeps its review history either way.

    A record entered by hand carries no fingerprint and no ``last_seen_at``, so its first sight is
    a first sight and not a change. A switch-off there would undo a review somebody had just done.

    Args:
        record: The row to refresh.
        kind: Which table this pass writes.
        definition: What the server said about it.
        fingerprint: The digest of that definition.
        now: The timestamp for this pass.
        disable_on_change: Clear ``enabled`` when the fingerprint moved.

    Returns:
        tuple[bool, bool]: Whether the definition moved, and whether this call switched the record
            off.
    """
    changed = record.definition_fingerprint != fingerprint

    if not changed and record.last_seen_at is not None:
        return False, False

    disabled = changed and disable_on_change and record.enabled and record.last_seen_at is not None

    for name, value in _columns_for(kind, definition).items():
        setattr(record, name, value)
    record.definition_fingerprint = fingerprint
    record.last_seen_at = now
    if disabled:
        record.enabled = False
    record.validated_save()
    return changed, disabled


def _retire(stale, *, remove_stale):
    """Deal with records the server no longer advertises.

    A disable is the default, because it keeps the description, the schema, and the review. This
    function does not touch ``last_seen_at``, which is the evidence of when the record went away.

    Args:
        stale: The records no longer advertised.
        remove_stale: Delete them instead of a disable.

    Returns:
        tuple: The records disabled by this run, and the labels of those deleted.
    """
    disabled, deleted = [], []
    for record in stale:
        if remove_stale:
            deleted.append(str(record))
            record.delete()
            continue
        if record.enabled:
            record.enabled = False
            record.validated_save()
            disabled.append(record)
    return tuple(disabled), tuple(deleted)


def definition_fingerprint(definition):
    """Digest everything a server said about one tool.

    Kept as a named function because another app codes against it. It is
    ``TOOL_KIND.fingerprint`` under a name that says what it digests.

    Args:
        definition: What the server advertised.

    Returns:
        str: A hex SHA-256 digest.
    """
    return canonical_digest(
        {
            "title": definition.title or "",
            "description": definition.description or "",
            "input_schema": definition.input_schema or {},
            "output_schema": definition.output_schema or {},
        }
    )


def _rendered(integration, method_name, server):
    """Render one of the integration's Jinja2 fields.

    The remote URL, the headers, and the extra config all support Jinja2, so the raw column would
    hand a template string to httpx.

    Args:
        integration: The ExternalIntegration to read.
        method_name: The render method to call.
        server: The object the template renders against.

    Returns:
        The rendered value.

    Raises:
        MCPConfigurationError: The template could not be rendered.
    """
    return render_field(integration, method_name, server, MCPConfigurationError)


def _attr(obj, *names, default=None):
    """Return the first of ``names`` the object has.

    The MCP schema names its fields in camel case and the Python SDK in snake case, and the answer
    has moved between SDK releases.

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
    strips ``Authorization`` only when the origin changes, so a server that answers
    ``302 Location: https://elsewhere/`` would receive an ``X-Api-Key`` verbatim.

    Args:
        base_class: The client class to subclass.
        protected_headers: The header names to drop off-origin.

    Returns:
        type | None: The subclass, or None when the library exposes no redirect hook. The caller
            then refuses redirects, which fails loudly instead of a quiet leak.
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

    Discovery runs from a Job that does not outlive its run, so one session per pass is enough.
    The SDK is asynchronous and every caller here is not, so each pass is one ``asyncio.run``.
    That is correct in a Celery worker and in a WSGI request.
    """

    def __init__(self, session_class, transport, http_client_class, timeout_class):
        """Hold the four pieces of the SDK and its HTTP client that this module uses."""
        self._session_class = session_class
        self._transport = transport
        self._http_client_class = http_client_class
        self._timeout_class = timeout_class

    def describe(self, connection):
        """Read what the server is and everything it advertises, in one session.

        Args:
            connection: Where and how to connect.

        Returns:
            tuple: A ServerInfo and an AdvertisedCatalog.
        """
        return self._run(connection, self._describe)

    async def _describe(self, session, initialized):
        """Read the handshake result, then each list the handshake said the server offers."""
        info = _server_info(initialized)
        offered = info.capabilities or {}

        tools, tools_read = await self._listed(
            session, TOOLS_CAPABILITY, offered, "list_tools", "tools", _tool_definition
        )
        resources, resources_read = await self._listed(
            session, RESOURCES_CAPABILITY, offered, "list_resources", "resources", _resource_definition
        )
        templates, templates_read = await self._listed(
            session,
            RESOURCES_CAPABILITY,
            offered,
            "list_resource_templates",
            "resource_templates",
            _resource_template_definition,
        )
        prompts, prompts_read = await self._listed(
            session, PROMPTS_CAPABILITY, offered, "list_prompts", "prompts", _prompt_definition
        )

        return info, AdvertisedCatalog(
            tools=tools,
            resources=resources + templates,
            prompts=prompts,
            tools_read=tools_read,
            resources_read=resources_read and templates_read,
            prompts_read=prompts_read,
        )

    async def _listed(self, session, capability, offered, method, attribute, build):  # pylint: disable=too-many-arguments
        """Read one list, when the server said it has one.

        A list the server does not advertise is not asked for: an unsupported method raises, and
        one raised method would fail the whole pass and leave every other record stale. A list that
        fails on its own is logged and reported as unread, so the reconcile retires nothing.

        Args:
            session: The open MCP session.
            capability: The handshake key that says the server offers this list.
            offered: What the handshake advertised.
            method: The session method to call.
            attribute: The attribute of a page that holds the records.
            build: Turns one SDK object into a definition.

        Returns:
            tuple: The definitions, and whether the list was read.
        """
        if capability not in offered or not hasattr(session, method):
            return (), False

        try:
            pages = await self._pages(getattr(session, method))
        except Exception as error:  # pylint: disable=broad-except
            logger.warning("Could not read %s: %s. Nothing of that kind was retired.", method, _cause(error))
            return (), False

        definitions = []
        for page in pages:
            definitions.extend(build(each) for each in getattr(page, attribute, None) or ())
        return tuple(definitions), True

    async def _pages(self, lister):
        """Read every page of one list, in order.

        Bounded by ``MAX_LIST_PAGES``, so a cursor pointing at itself is not an infinite loop.

        Args:
            lister: The bound session method that reads one page.

        Returns:
            list: Every page the server returned.
        """
        from mcp import types  # pylint: disable=import-outside-toplevel

        pages = []
        cursor = None
        for _ in range(MAX_LIST_PAGES):
            params = types.PaginatedRequestParams(cursor=cursor) if cursor else None
            page = await lister(params=params)
            pages.append(page)
            cursor = _attr(page, "next_cursor", "nextCursor")
            if not cursor:
                return pages
        logger.warning("Stopped reading pages after %s; the server kept offering a cursor", MAX_LIST_PAGES)
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


def _resource_definition(resource):
    """A `ResourceDefinition` from one of the SDK's resource objects."""
    return ResourceDefinition(
        uri=str(_attr(resource, "uri", default="") or ""),
        name=str(_attr(resource, "name", default="") or ""),
        title=str(_attr(resource, "title", default="") or ""),
        description=str(_attr(resource, "description", default="") or ""),
        mime_type=str(_attr(resource, "mime_type", "mimeType", default="") or ""),
        is_template=False,
        size=_attr(resource, "size"),
        annotations=_as_dict(_attr(resource, "annotations")),
    )


def _resource_template_definition(template):
    """A `ResourceDefinition` from one of the SDK's resource-template objects.

    A template carries its URI under another name, and the row records that the URI has parameters
    in it rather than being one a client can read directly.
    """
    return ResourceDefinition(
        uri=str(_attr(template, "uri_template", "uriTemplate", default="") or ""),
        name=str(_attr(template, "name", default="") or ""),
        title=str(_attr(template, "title", default="") or ""),
        description=str(_attr(template, "description", default="") or ""),
        mime_type=str(_attr(template, "mime_type", "mimeType", default="") or ""),
        is_template=True,
        size=None,
        annotations=_as_dict(_attr(template, "annotations")),
    )


def _prompt_definition(prompt):
    """A `PromptDefinition` from one of the SDK's prompt objects.

    The arguments arrive as a list rather than a JSON Schema, so they are stored as a list.
    """
    arguments = _attr(prompt, "arguments") or ()
    return PromptDefinition(
        name=str(_attr(prompt, "name", default="") or ""),
        title=str(_attr(prompt, "title", default="") or ""),
        description=str(_attr(prompt, "description", default="") or ""),
        arguments=tuple(_as_dict(argument) for argument in arguments),
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
