"""Create fixtures for tests."""

from nautobot.extras.models import ExternalIntegration

from nautobot_ai_models.choices import AIModelKindChoices, AIProviderTypeChoices, MCPTransportChoices
from nautobot_ai_models.models import AIModel, AIProvider, MCPServer, MCPTool

# Three distinct integrations. The generic filter tests need at least three unique values per field.
INTEGRATIONS = (
    ("Test Integration One", "https://llm.example.com"),
    ("Test Integration Two", "https://llm2.example.com"),
    ("Test Integration Three", "https://llm3.example.com"),
)

#: Three providers, three distinct dialects. The generic filter tests need at least three distinct
#: values per field, and `provider_type` is exercised by them.
PROVIDERS = (
    ("Test One", "First provider", AIProviderTypeChoices.OPENAI),
    ("Test Two", "Second provider", AIProviderTypeChoices.ANTHROPIC),
    ("Test Three", "Third provider", AIProviderTypeChoices.OLLAMA),
)

#: Two kinds across three models, because `AIModelKindChoices` only has two. `kind` therefore gets
#: a named test rather than a generic filter test.
AI_MODELS = (
    ("Test One", "Test One", "First model", AIModelKindChoices.CHAT),
    ("Test Two", "Test Two", "Second model", AIModelKindChoices.CHAT),
    ("Test Three", "Test Three", "Third model", AIModelKindChoices.EMBEDDING),
)


def create_external_integration(name=INTEGRATIONS[0][0], remote_url=INTEGRATIONS[0][1], **kwargs):
    """One ExternalIntegration for a AIProvider or an MCP Server to point at.

    `get_or_create` rather than `create`: a test that needs a second batch of records should not
    fall over on the integration name before it reaches what it was testing.
    """
    integration, _ = ExternalIntegration.objects.get_or_create(
        name=name,
        defaults={"remote_url": remote_url, "verify_ssl": True, "timeout": 30, **kwargs},
    )
    return integration


def create_ai_provider():
    """Fixture to create the necessary number of AIProvider objects for tests."""
    for (name, description, provider_type), (integration_name, remote_url) in zip(PROVIDERS, INTEGRATIONS):
        AIProvider.objects.create(
            name=name,
            description=description,
            provider_type=provider_type,
            external_integration=create_external_integration(integration_name, remote_url),
        )


def create_aimodel():
    """Fixture to create the necessary number of AIModel objects for tests."""
    create_ai_provider()
    for provider_name, name, description, kind in AI_MODELS:
        AIModel.objects.create(
            provider=AIProvider.objects.get(name=provider_name),
            name=name,
            description=description,
            kind=kind,
        )


#: Three servers, one per transport. The generic filter tests need at least three distinct values
#: for any field they exercise, and the three transports are the field that has exactly three.
SERVER_SPECS = (
    ("Test One", MCPTransportChoices.TYPE_STREAMABLE_HTTP),
    ("Test Two", MCPTransportChoices.TYPE_SSE),
    ("Test Three", MCPTransportChoices.TYPE_STDIO),
)


def create_mcpserver():
    """Fixture to create necessary number of MCPServer for tests.

    Each server gets its own integration. They could share one, but a test that changed an
    integration would then change every server, which is the kind of coupling a fixture should not
    create.
    """
    servers = []
    for index, (label, transport) in enumerate(SERVER_SPECS, start=1):
        integration = create_external_integration(
            name=f"Integration {label}",
            remote_url=f"https://mcp{index}.example.com/mcp",
        )
        server, _ = MCPServer.objects.get_or_create(
            name=label,
            defaults={
                "description": f"{label} description",
                "external_integration": integration,
                "transport": transport,
            },
        )
        servers.append(server)
    return servers


def create_mcptool():
    """Fixture to create necessary number of MCPTool for tests.

    Three tools, deliberately not alike: one that only reads and says so, one that writes, and one
    the server said nothing about. Those are the three states the registry has to hold.

    One tool per server, so the generic filter tests have three distinct server names to work with.
    """
    servers = create_mcpserver()
    return [
        MCPTool.objects.create(
            mcp_server=servers[0],
            name="get_device",
            title="Get Device",
            description="Read one device.",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            writable=False,
            advertised_read_only=True,
        ),
        MCPTool.objects.create(
            mcp_server=servers[1],
            name="set_interface",
            title="Set Interface",
            description="Change one interface.",
            input_schema={"type": "object", "properties": {"id": {"type": "string"}}},
            writable=True,
            advertised_read_only=False,
        ),
        MCPTool.objects.create(
            mcp_server=servers[2],
            name="run_report",
            title="Run Report",
            description="A tool the server annotated with nothing at all.",
            input_schema={"type": "object"},
            enabled=False,
            advertised_read_only=None,
        ),
    ]
