"""Generate test data for the AI Models app."""

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS
from nautobot.extras.models import ExternalIntegration

from nautobot_ai_models.choices import AIModelKindChoices, AIProviderTypeChoices, MCPTransportChoices
from nautobot_ai_models.models import AIModel, AIProvider, MCPServer, MCPTool

INTEGRATION_NAME = "AI Models Demo Integration"

PROVIDERS = (
    (
        "Demo OpenAI",
        AIProviderTypeChoices.OPENAI,
        True,
        (("gpt-4o", AIModelKindChoices.CHAT), ("text-embedding-3-small", AIModelKindChoices.EMBEDDING)),
    ),
    (
        "Demo Ollama",
        AIProviderTypeChoices.OLLAMA,
        True,
        (("llama3", AIModelKindChoices.CHAT), ("nomic-embed-text", AIModelKindChoices.EMBEDDING)),
    ),
    ("Demo Custom", AIProviderTypeChoices.ANTHROPIC, False, ()),
)

MCP_SERVERS = (
    ("Demo MCP Gateway", MCPTransportChoices.TYPE_STREAMABLE_HTTP, ("get_device", "set_interface")),
    ("Demo MCP Local", MCPTransportChoices.TYPE_STDIO, ()),
)


class Command(BaseCommand):
    """Populate the database with various data as a baseline for testing (automated or manual)."""

    help = __doc__

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help='The database to generate the test data in. Defaults to the "default" database.',
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Flush any existing AI Models test data from the database before generating new data.",
        )

    def _generate_static_data(self, db):
        """Generate static data required for test cases."""
        integration, _ = ExternalIntegration.objects.using(db).get_or_create(
            name=INTEGRATION_NAME,
            defaults={"remote_url": "https://llm.example.com/v1", "verify_ssl": True, "timeout": 30},
        )

        for name, provider_type, openai_compatible, model_specs in PROVIDERS:
            provider, _ = AIProvider.objects.using(db).get_or_create(
                name=name,
                defaults={
                    "external_integration": integration,
                    "provider_type": provider_type,
                    "openai_compatible": openai_compatible,
                },
            )
            for model_name, kind in model_specs:
                AIModel.objects.using(db).get_or_create(provider=provider, name=model_name, defaults={"kind": kind})

        for name, transport, tool_names in MCP_SERVERS:
            server, _ = MCPServer.objects.using(db).get_or_create(
                name=name,
                defaults={"external_integration": integration, "transport": transport},
            )
            for tool_name in tool_names:
                MCPTool.objects.using(db).get_or_create(mcp_server=server, name=tool_name)

    def _flush(self, db):
        """Delete every object _generate_static_data creates."""
        mcp_names = [name for name, _, _ in MCP_SERVERS]
        MCPTool.objects.using(db).filter(mcp_server__name__in=mcp_names).delete()
        MCPServer.objects.using(db).filter(name__in=mcp_names).delete()
        provider_names = [name for name, _, _, _ in PROVIDERS]
        AIModel.objects.using(db).filter(provider__name__in=provider_names).delete()
        AIProvider.objects.using(db).filter(name__in=provider_names).delete()
        ExternalIntegration.objects.using(db).filter(name=INTEGRATION_NAME).delete()

    def handle(self, *args, **options):
        """Entry point to the management command."""
        if options["flush"]:
            self.stdout.write("Flushing existing AI Models test data...")
            self._flush(db=options["database"])

        self._generate_static_data(db=options["database"])

        self.stdout.write(self.style.SUCCESS(f"Database {options['database']} populated with app data successfully!"))
