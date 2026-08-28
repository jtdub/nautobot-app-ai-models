"""Test the MCP service layer.

No test opens a socket: the client is injected through ``discover(client=...)``. Some tests reach
for a private helper, because ``_cause`` and ``_redirect_safe_client_class`` are where two of this
module's security properties live.
"""

# pylint: disable=protected-access

from django.test import override_settings
from nautobot.apps.choices import SecretsGroupAccessTypeChoices, SecretsGroupSecretTypeChoices
from nautobot.apps.testing import TestCase
from nautobot.extras.models import ExternalIntegration, Secret, SecretsGroup, SecretsGroupAssociation

from nautobot_ai_models import models
from nautobot_ai_models.choices import MCPTransportChoices
from nautobot_ai_models.secrets import read_secret
from nautobot_ai_models.services import mcp
from nautobot_ai_models.services.exceptions import MCPCallError, MCPConfigurationError
from nautobot_ai_models.tests import fixtures


class TaskGroupError(Exception):
    """An anyio exception group, on every Python this app supports.

    ``ExceptionGroup`` is a builtin from Python 3.11 and this app supports 3.10. ``_cause()`` reads
    only the ``exceptions`` attribute.
    """

    def __init__(self, message, exceptions):
        """Hold the message and the nested exceptions, as a real group does."""
        super().__init__(message)
        self.exceptions = tuple(exceptions)


class FakeClient:  # pylint: disable=too-few-public-methods
    """Answers `describe()` with whatever a test handed it."""

    def __init__(self, info=None, tools=(), error=None):
        """Hold the canned answer, or the error to raise instead of one."""
        self.info = info if info is not None else mcp.ServerInfo()
        self.tools = tuple(tools)
        self.error = error
        self.calls = []

    def describe(self, connection):
        """Record the connection it was handed, then answer."""
        self.calls.append(connection)
        if self.error is not None:
            raise self.error
        return self.info, self.tools


def tool(name, **kwargs):
    """One `ToolDefinition`, with the boilerplate filled in."""
    kwargs.setdefault("description", f"{name} description")
    kwargs.setdefault("input_schema", {"type": "object"})
    return mcp.ToolDefinition(name=name, **kwargs)


class ConnectionForTest(TestCase):
    """Everything `connection_for()` reads off an ExternalIntegration."""

    def _server(self, **integration_kwargs):
        integration_kwargs.setdefault("name", "Conn Integration")
        integration_kwargs.setdefault("remote_url", "https://mcp.example.com/mcp")
        integration = ExternalIntegration.objects.create(**integration_kwargs)
        return models.MCPServer.objects.create(name="Conn Server", external_integration=integration)

    def test_reads_url_and_headers(self):
        server = self._server(headers={"X-Tenant": "acme"})
        connection = mcp.connection_for(server)
        self.assertEqual(connection.url, "https://mcp.example.com/mcp")
        self.assertEqual(connection.headers["X-Tenant"], "acme")

    def test_renders_jinja_in_the_url(self):
        """All three templated fields support Jinja2, so the raw column must never be read."""
        server = self._server(remote_url="https://mcp.example.com/{{ obj.name | lower }}")
        connection = mcp.connection_for(server)
        self.assertEqual(connection.url, "https://mcp.example.com/conn server")

    def test_renders_jinja_in_the_headers(self):
        server = self._server(headers={"X-Server": "{{ obj.name }}"})
        connection = mcp.connection_for(server)
        self.assertEqual(connection.headers["X-Server"], "Conn Server")

    def test_missing_url_is_a_configuration_error(self):
        """An integration is shared, and can be blanked after a server was saved against it."""
        server = self._server()
        server.external_integration.remote_url = ""
        server.external_integration.save()
        with self.assertRaises(MCPConfigurationError):
            mcp.connection_for(server)

    def test_verify_ssl_off_beats_a_ca_path(self):
        """An operator who did both has said not to verify."""
        server = self._server(verify_ssl=False, ca_file_path="/etc/ssl/ca.pem")
        self.assertIs(mcp.connection_for(server).verify, False)

    def test_ca_path_is_used_when_verifying(self):
        server = self._server(verify_ssl=True, ca_file_path="/etc/ssl/ca.pem")
        self.assertEqual(mcp.connection_for(server).verify, "/etc/ssl/ca.pem")

    def test_verify_defaults_to_true(self):
        self.assertIs(mcp.connection_for(self._server()).verify, True)

    def test_timeout_comes_from_the_integration(self):
        server = self._server(timeout=90)
        self.assertEqual(mcp.connection_for(server).timeout, 90)

    def test_nonsense_timeout_falls_back(self):
        """Zero is not a timeout an operator meant, and it is not a bound either."""
        server = self._server(timeout=0)
        self.assertEqual(mcp.connection_for(server).timeout, mcp.DEFAULT_TIMEOUT_SECONDS)

    def test_token_becomes_a_bearer_header(self):
        """The credential is read from the secrets group at connection time, never stored."""
        group = secrets_group_with_token(name="Bearer Group", value="tok-abc123")
        server = self._server(secrets_group=group)
        server.external_integration.secrets_group = group

        connection = mcp.connection_for(server)

        self.assertEqual(connection.headers["Authorization"], "Bearer tok-abc123")

    def test_a_generic_secret_is_used_when_there_is_no_token(self):
        """Servers are configured both ways; either is a credential."""
        group = secrets_group_with_token(
            name="Secret Group", value="sec-xyz", secret_type=SecretsGroupSecretTypeChoices.TYPE_SECRET
        )
        server = self._server(secrets_group=group)
        server.external_integration.secrets_group = group

        connection = mcp.connection_for(server)

        self.assertEqual(connection.headers["Authorization"], "Bearer sec-xyz")

    def test_an_operator_written_authorization_header_wins(self):
        """An operator who wrote the header has said how this server authenticates.

        The match is case-insensitive, because HTTP field names are.
        """
        group = secrets_group_with_token(name="Ignored Group", value="tok-should-not-appear")
        server = self._server(headers={"authorization": "ApiKey handwritten"}, secrets_group=group)
        server.external_integration.secrets_group = group

        connection = mcp.connection_for(server)

        self.assertEqual(connection.headers["authorization"], "ApiKey handwritten")
        self.assertNotIn("tok-should-not-appear", str(connection.headers))

    def test_no_secrets_group_connects_without_a_credential(self):
        """A server that wants no credential is ordinary, not an error."""
        connection = mcp.connection_for(self._server())
        self.assertNotIn("Authorization", connection.headers)

    def test_repr_hides_the_credential(self):
        """This object is held in tracebacks and rendered onto a DEBUG error page.

        The header names are worth seeing when something is misconfigured; their values never are.
        """
        connection = mcp.MCPConnection(
            url="https://mcp.example.com/mcp",
            headers={"Authorization": "Bearer super-secret-token"},
        )
        rendered = repr(connection)
        self.assertNotIn("super-secret-token", rendered)
        self.assertIn("Authorization", rendered)


class DiscoverTest(TestCase):
    """What one discovery pass writes onto the registry."""

    @classmethod
    def setUpTestData(cls):
        """One reachable server, with nothing discovered on it yet."""
        cls.server = fixtures.create_mcpserver()[0]

    def _discover(self, tools, *, remove_stale=False, info=None, **policy):
        client = FakeClient(info=info, tools=tools)
        return mcp.discover(
            self.server,
            remove_stale=remove_stale,
            client=client,
            policy=mcp.DiscoveryPolicy(**policy) if policy else None,
        )

    def test_disabled_server_is_refused(self):
        """An operator who disabled a server should not find its registry changing underneath them."""
        self.server.enabled = False
        self.server.validated_save()
        with self.assertRaises(MCPConfigurationError):
            self._discover([tool("get_device")])

    def test_stdio_server_is_refused(self):
        """A stdio server is a subprocess of its client. A worker has nothing to connect to."""
        self.server.transport = MCPTransportChoices.TYPE_STDIO
        self.server.validated_save()
        with self.assertRaises(MCPConfigurationError):
            self._discover([tool("get_device")])

    def test_client_failure_becomes_one_family(self):
        """Whatever the client raised, the caller sees an MCPError."""
        client = FakeClient(error=OSError("connection reset"))
        with self.assertRaises(MCPCallError):
            mcp.discover(self.server, client=client)

    def test_new_tools_are_created_with_operator_defaults(self):
        """Discovery believes the server about everything except what the tool may do."""
        report = self._discover([tool("get_device", read_only_hint=True)])

        self.assertEqual(len(report.added), 1)
        created = models.MCPTool.objects.get(mcp_server=self.server, name="get_device")
        self.assertEqual(created.description, "get_device description")
        self.assertTrue(created.advertised_read_only)
        self.assertTrue(created.writable)
        self.assertTrue(created.enabled)
        self.assertIsNotNone(created.last_seen_at)
        self.assertTrue(created.definition_fingerprint)

    def test_server_info_is_recorded_and_stamped(self):
        info = mcp.ServerInfo(
            protocol_version="2026-07-28",
            name="ExampleServer",
            version="1.2.3",
            instructions="Use the read tools first.",
            capabilities={"tools": {"listChanged": True}},
        )
        self._discover([tool("get_device")], info=info)

        self.server.refresh_from_db()
        self.assertEqual(self.server.protocol_version, "2026-07-28")
        self.assertEqual(self.server.server_name, "ExampleServer")
        self.assertEqual(self.server.server_version, "1.2.3")
        self.assertEqual(self.server.instructions, "Use the read tools first.")
        self.assertEqual(self.server.capabilities, {"tools": {"listChanged": True}})
        self.assertIsNotNone(self.server.last_discovered_at)

    def test_rerun_does_not_touch_operator_columns(self):
        """This is the whole contract with an operator: what they decided survives a rerun."""
        self._discover([tool("get_device")])
        reviewed = models.MCPTool.objects.get(name="get_device")
        reviewed.enabled = False
        reviewed.writable = False
        reviewed.validated_save()

        self._discover([tool("get_device", description="a new description")])

        reviewed.refresh_from_db()
        self.assertEqual(reviewed.description, "a new description")
        self.assertFalse(reviewed.enabled)
        self.assertFalse(reviewed.writable)

    def test_unchanged_tool_is_not_rewritten(self):
        """A change-logged model must not collect a row a night saying nothing happened."""
        self._discover([tool("get_device")])
        first = models.MCPTool.objects.get(name="get_device")
        stamp = first.last_seen_at

        report = self._discover([tool("get_device")])

        first.refresh_from_db()
        self.assertEqual(first.last_seen_at, stamp)
        self.assertEqual(len(report.updated), 1)
        self.assertEqual(report.definition_changed, ())

    def test_changed_definition_is_reported(self):
        """Somebody reviewed the old description. They should be told it moved."""
        self._discover([tool("get_device")])
        report = self._discover([tool("get_device", description="something else entirely")])

        self.assertEqual(len(report.definition_changed), 1)
        self.assertEqual(report.definition_changed[0].name, "get_device")

    def test_a_new_tool_can_arrive_switched_off(self):
        """Opt-in. Forty tools nobody has read should not be on offer because a server said so."""
        report = self._discover([tool("get_device", read_only_hint=True)], new_tools_enabled=False)

        self.assertEqual(len(report.added), 1)
        created = models.MCPTool.objects.get(mcp_server=self.server, name="get_device")
        self.assertFalse(created.enabled)
        self.assertTrue(created.writable)

    def test_a_changed_definition_can_switch_a_tool_off(self):
        """Opt-in. A description that moved is the tool's semantics changing under a review."""
        self._discover([tool("get_device")])
        report = self._discover(
            [tool("get_device", description="something else entirely")], disable_on_definition_change=True
        )

        self.assertEqual([each.name for each in report.disabled_by_change], ["get_device"])
        changed = models.MCPTool.objects.get(name="get_device")
        self.assertFalse(changed.enabled)
        self.assertTrue(changed.writable)
        self.assertEqual(changed.description, "something else entirely")
        self.assertIsNotNone(changed.last_seen_at)

    def test_a_changed_definition_leaves_the_tool_on_by_default(self):
        """The default is today's behaviour: report it and hold no policy."""
        self._discover([tool("get_device")])
        report = self._discover([tool("get_device", description="something else entirely")])

        self.assertEqual(report.disabled_by_change, ())
        self.assertTrue(models.MCPTool.objects.get(name="get_device").enabled)

    def test_an_unchanged_definition_is_never_switched_off(self):
        """The policy acts on a moved fingerprint, not on every pass."""
        self._discover([tool("get_device")], disable_on_definition_change=True)
        report = self._discover([tool("get_device")], disable_on_definition_change=True)

        self.assertEqual(report.disabled_by_change, ())
        self.assertTrue(models.MCPTool.objects.get(name="get_device").enabled)

    def test_a_hand_entered_tool_is_not_switched_off_on_first_sight(self):
        """A tool with no fingerprint was never read, so its first reading is not a change.

        A stdio server cannot be discovered, so its tools are entered by hand. One of those on a
        server that later becomes reachable must not lose the review that was just done on it.
        """
        by_hand = models.MCPTool.objects.create(
            mcp_server=self.server,
            name="get_device",
            description="get_device description",
            input_schema={"type": "object"},
            enabled=True,
            writable=False,
        )
        self.assertEqual(by_hand.definition_fingerprint, "")
        self.assertIsNone(by_hand.last_seen_at)

        report = self._discover([tool("get_device")], disable_on_definition_change=True)

        by_hand.refresh_from_db()
        self.assertEqual(report.disabled_by_change, ())
        self.assertTrue(by_hand.enabled)
        self.assertFalse(by_hand.writable)

    def test_an_already_disabled_tool_is_not_reported_as_newly_disabled(self):
        """Re-reporting a tool that was already off trains an operator to ignore the warning."""
        self._discover([tool("get_device")])
        already_off = models.MCPTool.objects.get(name="get_device")
        already_off.enabled = False
        already_off.validated_save()

        report = self._discover(
            [tool("get_device", description="something else entirely")], disable_on_definition_change=True
        )

        self.assertEqual(len(report.definition_changed), 1)
        self.assertEqual(report.disabled_by_change, ())

    def test_stale_tool_is_disabled_and_kept(self):
        """Losing a tool must not lose the review that was done on it."""
        self._discover([tool("get_device"), tool("set_interface")])
        report = self._discover([tool("get_device")])

        self.assertEqual([tool_.name for tool_ in report.missing], ["set_interface"])
        stale = models.MCPTool.objects.get(name="set_interface")
        self.assertFalse(stale.enabled)
        self.assertEqual(stale.description, "set_interface description")
        self.assertIsNotNone(stale.last_seen_at)

    def test_stale_tool_is_deleted_when_asked(self):
        """The operator has to ask for this. A server having a bad minute must not erase a registry."""
        self._discover([tool("get_device"), tool("set_interface")])
        report = self._discover([tool("get_device")], remove_stale=True)

        self.assertEqual(len(report.removed), 1)
        self.assertFalse(models.MCPTool.objects.filter(name="set_interface").exists())

    def test_a_returning_tool_is_left_disabled(self):
        """Discovery never enables. Putting the tool back in service is a person's decision."""
        self._discover([tool("get_device"), tool("set_interface")])
        self._discover([tool("get_device")])
        self._discover([tool("get_device"), tool("set_interface")])

        returned = models.MCPTool.objects.get(name="set_interface")
        self.assertFalse(returned.enabled)

    def test_duplicate_name_does_not_break_the_pass(self):
        """A server advertising one name twice updates its own first row, not a second one."""
        self._discover([tool("get_device"), tool("get_device", description="the second one")])

        self.assertEqual(models.MCPTool.objects.filter(mcp_server=self.server).count(), 1)

    def test_unstorable_tool_leaves_no_half_registry(self):
        """One transaction: a name too long for the column must not commit the tools before it."""
        with self.assertRaises(MCPCallError):
            self._discover([tool("get_device"), tool("x" * 1000)])

        self.assertEqual(models.MCPTool.objects.filter(mcp_server=self.server).count(), 0)


class DiscoveryPolicyTest(TestCase):
    """The one place that reads PLUGINS_CONFIG.

    Everything else asks for behaviour by passing a policy, so this is what pins the settings to
    the behaviour they are supposed to produce.
    """

    def test_the_shipped_defaults_are_todays_behaviour(self):
        """A deployment that has set nothing must see no change."""
        policy = mcp.DiscoveryPolicy.from_settings()
        self.assertTrue(policy.new_tools_enabled)
        self.assertFalse(policy.disable_on_definition_change)
        self.assertEqual(policy, mcp.DiscoveryPolicy())

    @override_settings(
        PLUGINS_CONFIG={"nautobot_ai_models": {"new_tools_enabled": False, "disable_on_definition_change": True}}
    )
    def test_settings_are_read(self):
        """Both keys reach the policy from PLUGINS_CONFIG."""
        policy = mcp.DiscoveryPolicy.from_settings()
        self.assertFalse(policy.new_tools_enabled)
        self.assertTrue(policy.disable_on_definition_change)


class FingerprintTest(TestCase):
    """The digest that answers "did the server change what this tool is"."""

    def test_key_order_does_not_move_it(self):
        """Two servers may serialize one schema differently, and that is not a change."""
        first = tool("t", input_schema={"a": 1, "b": 2})
        second = tool("t", input_schema={"b": 2, "a": 1})
        self.assertEqual(mcp.definition_fingerprint(first), mcp.definition_fingerprint(second))

    def test_description_is_in_it(self):
        """The description is half of what a reviewer read, and all of a tool's prompt semantics."""
        first = tool("t", description="reads a device")
        second = tool("t", description="reads a device and reboots it")
        self.assertNotEqual(mcp.definition_fingerprint(first), mcp.definition_fingerprint(second))

    def test_schema_is_in_it(self):
        first = tool("t", input_schema={"type": "object"})
        second = tool("t", input_schema={"type": "object", "required": ["force"]})
        self.assertNotEqual(mcp.definition_fingerprint(first), mcp.definition_fingerprint(second))


def secrets_group_with_token(name="Token Group", value="super-secret-token", secret_type=None):
    """A SecretsGroup carrying one secret, resolvable without touching the environment."""
    secret_type = secret_type or SecretsGroupSecretTypeChoices.TYPE_TOKEN
    secret = Secret.objects.create(
        name=f"{name} Secret",
        provider="environment-variable",
        parameters={"variable": "IRRELEVANT"},
    )
    group = SecretsGroup.objects.create(name=name)
    SecretsGroupAssociation.objects.create(
        secrets_group=group,
        access_type=SecretsGroupAccessTypeChoices.TYPE_GENERIC,
        secret_type=secret_type,
        secret=secret,
    )
    group.get_secret_value = lambda *args, **kwargs: value
    return group


class ReadSecretTest(TestCase):
    """`read_secret()` - one secret off an integration, or None."""

    def test_no_secrets_group_is_none_not_an_error(self):
        """Every caller treats a missing secret as "connect without it"."""
        integration = ExternalIntegration.objects.create(name="No Group", remote_url="https://x.example.com")
        self.assertIsNone(read_secret(integration, SecretsGroupSecretTypeChoices.TYPE_TOKEN))

    def test_unresolvable_secret_is_none_not_an_error(self):
        """A group that cannot resolve the secret is the same answer as no group at all.

        The server the credential was for refuses the connection itself, and that is the visible
        symptom. Raising here would turn a configuration problem into a traceback.
        """
        group = SecretsGroup.objects.create(name="Empty Group")
        integration = ExternalIntegration.objects.create(
            name="Empty Group Integration", remote_url="https://x.example.com", secrets_group=group
        )
        self.assertIsNone(read_secret(integration, SecretsGroupSecretTypeChoices.TYPE_TOKEN))

    def test_resolvable_secret_comes_back(self):
        group = secrets_group_with_token(name="Readable Group", value="a-token")
        integration = ExternalIntegration.objects.create(
            name="Readable Integration", remote_url="https://x.example.com", secrets_group=group
        )
        integration.secrets_group = group
        self.assertEqual(read_secret(integration, SecretsGroupSecretTypeChoices.TYPE_TOKEN), "a-token")


class ErrorReportingTest(TestCase):
    """What a failed discovery says happened.

    The contract is the exception types and nothing else. A client's message embeds the request
    URL, which an operator may have written a credential into, and it reaches a JobLogEntry that a
    wider audience can read than the Secrets Group it came from.
    """

    @classmethod
    def setUpTestData(cls):
        """One server for the failures to be reported against."""
        cls.server = fixtures.create_mcpserver()[0]

    def _message(self, error):
        with self.assertRaises(MCPCallError) as raised:
            mcp.discover(self.server, client=FakeClient(error=error))
        return str(raised.exception)

    def test_a_plain_exception_is_named_by_type_only(self):
        """The type says what went wrong. The message is the part that can carry a secret."""
        message = self._message(ValueError("401 for https://svc:hunter2@mcp.internal/mcp"))
        self.assertIn("ValueError", message)
        self.assertNotIn("hunter2", message)
        self.assertNotIn("svc:", message)
        self.assertNotIn("mcp.internal", message)

    def test_exception_group_is_unwrapped(self):
        """The MCP client runs on task groups, so the real cause arrives nested.

        Without unwrapping, an operator reads "unhandled errors in a TaskGroup (1 sub-exception)" in
        the Job log, which says nothing about the DNS failure behind it.
        """
        message = self._message(
            TaskGroupError("unhandled errors in a TaskGroup", [OSError("Name or service not known")])
        )
        self.assertIn("OSError", message)
        self.assertNotIn("sub-exception", message)

    def test_every_cause_in_a_group_is_reported(self):
        """A task group can fail more than one way at once, and both are worth seeing."""
        message = self._message(TaskGroupError("group", [OSError("refused"), TimeoutError("timed out")]))
        self.assertIn("OSError", message)
        self.assertIn("TimeoutError", message)

    def test_a_nested_group_cannot_smuggle_a_message_out(self):
        """Redaction has to hold at every depth, not only the top one."""
        error = TaskGroupError("wrapper", [TaskGroupError("inner", [ValueError("token=abc123")])])
        message = self._message(error)
        self.assertIn("ValueError", message)
        self.assertNotIn("abc123", message)

    def test_nesting_is_bounded(self):
        """A deeply nested group must not recurse without end inside a worker."""
        error = OSError("innermost")
        for _ in range(20):
            error = TaskGroupError("wrapper", [error])
        self.assertIn(TaskGroupError.__name__, self._message(error))

    def test_the_server_is_named(self):
        """One failure among twenty servers has to say which one."""
        self.assertIn(self.server.name, self._message(OSError("refused")))


class DiscoverableTransportsTest(TestCase):
    """Test that the transports the job attempts are the ones the client can actually open."""

    def test_only_streamable_http_is_attempted(self):
        """This module speaks streamable HTTP and nothing else.

        Listing another transport here sends its servers through a client that cannot talk to
        them, and the operator gets an opaque failure instead of the skip notice that tells them
        to enter the tools by hand.
        """
        self.assertEqual(mcp.DISCOVERABLE_TRANSPORTS, (MCPTransportChoices.TYPE_STREAMABLE_HTTP,))
        self.assertNotIn(MCPTransportChoices.TYPE_SSE, mcp.DISCOVERABLE_TRANSPORTS)
        self.assertNotIn(MCPTransportChoices.TYPE_STDIO, mcp.DISCOVERABLE_TRANSPORTS)


class RedirectSafeClientTest(TestCase):
    """Test that a redirect off the origin cannot carry the integration's credential with it."""

    class FakeURL:  # pylint: disable=too-few-public-methods
        """The three attributes the origin comparison reads."""

        def __init__(self, scheme, host, port):
            self.scheme = scheme
            self.host = host
            self.port = port

    class FakeRequest:  # pylint: disable=too-few-public-methods
        """A request carrying only its URL."""

        def __init__(self, url):
            self.url = url

    class FakeBase:  # pylint: disable=too-few-public-methods
        """Stands in for the HTTP client, returning the headers a real one would keep."""

        def __init__(self, headers):
            self._headers = headers

        def _redirect_headers(self, request, url, method):  # pylint: disable=unused-argument
            return {**self._headers, "User-Agent": "nautobot"}

    HEADERS = {"Authorization": "Bearer t", "X-Api-Key": "secret", "Accept": "application/json"}

    def build(self):
        """A client class that strips this app's configured headers off-origin."""
        return mcp._redirect_safe_client_class(self.FakeBase, self.HEADERS)

    def test_a_cross_origin_redirect_drops_every_configured_header(self):
        """An operator may authenticate with a header of any name, and it must not travel."""
        client = self.build()(self.HEADERS)
        headers = client._redirect_headers(
            self.FakeRequest(self.FakeURL("https", "mcp.internal", 443)),
            self.FakeURL("https", "attacker.example", 443),
            "GET",
        )
        self.assertNotIn("X-Api-Key", headers)
        self.assertNotIn("Authorization", headers)
        self.assertNotIn("Accept", headers)
        self.assertEqual(headers["User-Agent"], "nautobot")

    def test_a_same_origin_redirect_keeps_them(self):
        """An endpoint sending /mcp to /mcp/ is ordinary and must keep working."""
        client = self.build()(self.HEADERS)
        headers = client._redirect_headers(
            self.FakeRequest(self.FakeURL("https", "mcp.internal", 443)),
            self.FakeURL("https", "mcp.internal", 443),
            "GET",
        )
        self.assertEqual(headers["X-Api-Key"], "secret")

    def test_a_client_without_the_hook_is_refused(self):
        """No hook means no way to strip, so the caller must not follow redirects at all."""

        class NoHook:  # pylint: disable=too-few-public-methods
            """A client library that does not expose its redirect handling."""

        self.assertIsNone(mcp._redirect_safe_client_class(NoHook, self.HEADERS))
