"""Create fixtures for tests."""

from nautobot.extras.models import ExternalIntegration

from nautobot_ai_models.choices import AIModelKindChoices, AIProviderTypeChoices, MCPTransportChoices
from nautobot_ai_models.models import AIModel, AIProvider, MCPServer, MCPTool

INTEGRATIONS = (
    ("Test Integration One", "https://llm.example.com"),
    ("Test Integration Two", "https://llm2.example.com"),
    ("Test Integration Three", "https://llm3.example.com"),
)

PROVIDERS = (
    ("Test One", "First provider", AIProviderTypeChoices.OPENAI),
    ("Test Two", "Second provider", AIProviderTypeChoices.ANTHROPIC),
    ("Test Three", "Third provider", AIProviderTypeChoices.OLLAMA),
)

AI_MODELS = (
    ("Test One", "Test One", "First model", AIModelKindChoices.CHAT),
    ("Test Two", "Test Two", "Second model", AIModelKindChoices.CHAT),
    ("Test Three", "Test Three", "Third model", AIModelKindChoices.EMBEDDING),
)


def create_external_integration(name=INTEGRATIONS[0][0], remote_url=INTEGRATIONS[0][1], **kwargs):
    """Return one ExternalIntegration, creating it if it does not exist.

    Args:
        name: The integration's name.
        remote_url: Its remote URL.
        **kwargs: Further defaults for creation.

    Returns:
        ExternalIntegration: The existing or new record.
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


SERVER_SPECS = (
    ("Test One", MCPTransportChoices.TYPE_STREAMABLE_HTTP),
    ("Test Two", MCPTransportChoices.TYPE_SSE),
    ("Test Three", MCPTransportChoices.TYPE_STDIO),
)


def create_mcpserver():
    """Create one MCPServer per transport, each with its own integration.

    Returns:
        list[MCPServer]: The three servers.
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
    """Create three MCPTool records, one per server and one per annotation state.

    Returns:
        list[MCPTool]: A read-only tool, a writable one, and one the server did not annotate.
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
