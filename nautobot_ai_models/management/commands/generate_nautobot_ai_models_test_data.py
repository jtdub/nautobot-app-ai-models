"""Generate test data for the AI Models app."""

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS
from django.utils import timezone
from nautobot.extras.models import ExternalIntegration

from nautobot_ai_models.choices import AIModelKindChoices, AIProviderTypeChoices, MCPTransportChoices
from nautobot_ai_models.models import AIModel, AIProvider, MCPServer, MCPTool
from nautobot_ai_models.services.mcp import ToolDefinition, definition_fingerprint

INTEGRATIONS = (
    ("AI Models Demo Integration", "https://llm.example.com/v1"),
    ("Ollama Lab Integration", "https://ollama.lab.example.com"),
    ("Anthropic Demo Integration", ""),
    ("Nautobot MCP Integration", "https://mcp.example.com/mcp"),
)

PROVIDERS = (
    {
        "name": "OpenAI Production",
        "description": "The hosted OpenAI API.",
        "integration": "AI Models Demo Integration",
        "provider_type": AIProviderTypeChoices.OPENAI,
        "openai_compatible": True,
        "enabled": True,
        "temperature": "0.20",
        "models": (
            {
                "name": "gpt-4o-mini",
                "description": "Owned by openai",
                "kind": AIModelKindChoices.CHAT,
                "input_cost_per_million": "0.1500",
                "output_cost_per_million": "0.6000",
                "default_parameters": {"seed": 7, "top_p": 0.9},
            },
            {
                "name": "gpt-4o",
                "description": "Owned by openai",
                "kind": AIModelKindChoices.CHAT,
                "input_cost_per_million": "2.5000",
                "output_cost_per_million": "10.0000",
                "default_parameters": {},
            },
            {
                "name": "text-embedding-3-small",
                "description": "Owned by openai",
                "kind": AIModelKindChoices.EMBEDDING,
                "input_cost_per_million": "0.0200",
                "output_cost_per_million": None,
                "default_parameters": {},
            },
        ),
    },
    {
        "name": "Ollama Lab",
        "description": "Self-hosted Ollama. OpenAI-compatible, but addressed natively for tool calls.",
        "integration": "Ollama Lab Integration",
        "provider_type": AIProviderTypeChoices.OLLAMA,
        "openai_compatible": True,
        "enabled": True,
        "temperature": "0.70",
        "models": (
            {
                "name": "llama3",
                "description": "Owned by library",
                "kind": AIModelKindChoices.CHAT,
                "input_cost_per_million": None,
                "output_cost_per_million": None,
                "default_parameters": {"top_k": 40, "top_p": 0.9, "seed": 42},
            },
            {
                "name": "nomic-embed-text",
                "description": "Owned by library",
                "kind": AIModelKindChoices.EMBEDDING,
                "input_cost_per_million": None,
                "output_cost_per_million": None,
                "default_parameters": {},
            },
        ),
    },
    {
        "name": "Anthropic Retired",
        "description": "Out of service. The contract lapsed.",
        "integration": "Anthropic Demo Integration",
        "provider_type": AIProviderTypeChoices.ANTHROPIC,
        "openai_compatible": False,
        "enabled": False,
        "temperature": None,
        "models": (
            {
                "name": "claude-sonnet-4",
                "description": "",
                "kind": AIModelKindChoices.CHAT,
                "input_cost_per_million": "3.0000",
                "output_cost_per_million": "15.0000",
                "default_parameters": {},
            },
        ),
    },
)

TOOLS = (
    {
        "name": "get_device",
        "title": "Get Device",
        "description": "Return one device by name, with its location, its role, and its interfaces.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "The device name."}},
            "required": ["name"],
        },
        "output_schema": {"type": "object", "properties": {"device": {"type": "object"}}},
        "writable": False,
        "advertised_read_only": True,
    },
    {
        "name": "set_interface_description",
        "title": "Set Interface Description",
        "description": "Change the description of one interface.",
        "input_schema": {
            "type": "object",
            "properties": {"interface_id": {"type": "string"}, "description": {"type": "string"}},
            "required": ["interface_id", "description"],
        },
        "output_schema": {},
        "writable": True,
        "advertised_read_only": False,
    },
    {
        "name": "run_report",
        "title": "Run Report",
        "description": "Run a saved report. The server made no claim about whether this writes.",
        "input_schema": {"type": "object", "properties": {"report": {"type": "string"}}},
        "output_schema": {},
        "writable": True,
        "advertised_read_only": None,
    },
)

MCP_SERVERS = (
    {
        "name": "Nautobot MCP",
        "description": "The MCP server that fronts this Nautobot.",
        "integration": "Nautobot MCP Integration",
        "transport": MCPTransportChoices.TYPE_STREAMABLE_HTTP,
        "enabled": True,
        "discovered": {
            "protocol_version": "2025-06-18",
            "server_name": "nautobot-mcp",
            "server_version": "0.4.1",
            "instructions": "Read a device before you change one. Every write needs an approval.",
            "capabilities": {"tools": {"listChanged": True}, "resources": {"subscribe": False}},
        },
        "tools": TOOLS,
    },
    {
        "name": "Local Toolbox",
        "description": "A stdio server. A Nautobot worker cannot reach one, so its tools are entered by hand.",
        "integration": "Nautobot MCP Integration",
        "transport": MCPTransportChoices.TYPE_STDIO,
        "enabled": True,
        "discovered": None,
        "tools": (),
    },
)


class Command(BaseCommand):
    """Populate the database with demonstration data for manual testing and for the screenshots."""

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

    def _integrations(self, db):
        """Create the demonstration External Integrations.

        Args:
            db: The database alias to write to.

        Returns:
            dict: Each integration, keyed by name.
        """
        integrations = {}
        for name, remote_url in INTEGRATIONS:
            integration, _ = ExternalIntegration.objects.using(db).get_or_create(
                name=name,
                defaults={"remote_url": remote_url, "verify_ssl": True, "timeout": 30},
            )
            integrations[name] = integration
        return integrations

    def _generate_static_data(self, db):
        """Generate the demonstration records.

        Args:
            db: The database alias to write to.
        """
        integrations = self._integrations(db)

        for spec in PROVIDERS:
            provider, _ = AIProvider.objects.using(db).get_or_create(
                name=spec["name"],
                defaults={
                    "description": spec["description"],
                    "external_integration": integrations[spec["integration"]],
                    "provider_type": spec["provider_type"],
                    "openai_compatible": spec["openai_compatible"],
                    "enabled": spec["enabled"],
                    "temperature": spec["temperature"],
                },
            )
            for model_spec in spec["models"]:
                AIModel.objects.using(db).get_or_create(
                    provider=provider,
                    name=model_spec["name"],
                    defaults={
                        "description": model_spec["description"],
                        "kind": model_spec["kind"],
                        "input_cost_per_million": model_spec["input_cost_per_million"],
                        "output_cost_per_million": model_spec["output_cost_per_million"],
                        "default_parameters": model_spec["default_parameters"],
                    },
                )

        now = timezone.now()
        for spec in MCP_SERVERS:
            defaults = {
                "description": spec["description"],
                "external_integration": integrations[spec["integration"]],
                "transport": spec["transport"],
                "enabled": spec["enabled"],
            }
            if spec["discovered"]:
                defaults.update(spec["discovered"])
                defaults["last_discovered_at"] = now
            server, _ = MCPServer.objects.using(db).get_or_create(name=spec["name"], defaults=defaults)

            for tool_spec in spec["tools"]:
                MCPTool.objects.using(db).get_or_create(
                    mcp_server=server,
                    name=tool_spec["name"],
                    defaults={
                        "title": tool_spec["title"],
                        "description": tool_spec["description"],
                        "input_schema": tool_spec["input_schema"],
                        "output_schema": tool_spec["output_schema"],
                        "writable": tool_spec["writable"],
                        "advertised_read_only": tool_spec["advertised_read_only"],
                        "definition_fingerprint": definition_fingerprint(
                            ToolDefinition(
                                name=tool_spec["name"],
                                title=tool_spec["title"],
                                description=tool_spec["description"],
                                input_schema=tool_spec["input_schema"],
                                output_schema=tool_spec["output_schema"],
                                read_only_hint=tool_spec["advertised_read_only"],
                            )
                        ),
                        "last_seen_at": now,
                    },
                )

    def _flush(self, db):
        """Delete every object _generate_static_data creates.

        Args:
            db: The database alias to delete from.
        """
        server_names = [spec["name"] for spec in MCP_SERVERS]
        MCPTool.objects.using(db).filter(mcp_server__name__in=server_names).delete()
        MCPServer.objects.using(db).filter(name__in=server_names).delete()

        provider_names = [spec["name"] for spec in PROVIDERS]
        AIModel.objects.using(db).filter(provider__name__in=provider_names).delete()
        AIProvider.objects.using(db).filter(name__in=provider_names).delete()

        ExternalIntegration.objects.using(db).filter(name__in=[name for name, _ in INTEGRATIONS]).delete()

    def handle(self, *args, **options):
        """Entry point to the management command."""
        db = options["database"]
        if options["flush"]:
            self.stdout.write(self.style.WARNING("Flushing all existing AI Models test data..."))
            self._flush(db)
        self._generate_static_data(db)
        self.stdout.write(self.style.SUCCESS("Database populated with AI Models test data successfully!"))
