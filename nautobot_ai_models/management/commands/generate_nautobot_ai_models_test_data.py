"""Generate test data for the AI Models app."""

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS
from django.utils import timezone
from nautobot.extras.models import ExternalIntegration

from nautobot_ai_models.choices import (
    AIAgentPatternChoices,
    AIModelKindChoices,
    AIProviderTypeChoices,
    MCPTransportChoices,
)
from nautobot_ai_models.models import (
    AIAgent,
    AIAgentSkill,
    AIAgentSubagent,
    AIAgentThread,
    AIAgentTool,
    AIModel,
    AIProvider,
    AISkill,
    MCPServer,
    MCPTool,
)
from nautobot_ai_models.services.mcp import ToolDefinition, definition_fingerprint

RETIRED_NAMES = (
    "Demo OpenAI",
    "Demo Ollama",
    "Demo Custom",
    "Demo MCP Gateway",
    "Demo MCP Local",
)

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

AGENTS = (
    {
        "name": "Network Operations Assistant",
        "description": "Answers a network operations question by asking a specialist.",
        "system_prompt": (
            "You answer network operations questions. You have specialists. Use the inventory "
            "specialist for device records and site codes, and the change specialist for "
            "maintenance windows. Never state a fact you did not get from a specialist."
        ),
        "pattern": AIAgentPatternChoices.SUBAGENTS,
        "provider": "OpenAI Production",
    },
    {
        "name": "Inventory Specialist",
        "description": "Look up a network device by hostname. Returns the vendor and the site code.",
        "system_prompt": (
            "You look up network device records. Call the lookup tool for every hostname. Report "
            "the vendor and the site code. Never state a fact you did not get from the tool. Never "
            "quote a maintenance window: that is another team's job."
        ),
        "pattern": AIAgentPatternChoices.SINGLE,
        "provider": "OpenAI Production",
    },
    {
        "name": "Change Window Specialist",
        "description": "Return the approved change window for one site. Give it a site code.",
        "system_prompt": (
            "You answer questions about approved change windows. You start with no rules loaded. "
            "Call load_skill before you answer anything."
        ),
        "pattern": AIAgentPatternChoices.SKILLS,
        "provider": "Ollama Lab",
    },
)

SKILLS = (
    {
        "name": "maintenance_windows",
        "description": "approved change windows",
        "body": (
            "Quote only a window that appears in the change calendar. If the request gives you a "
            "hostname instead of a site code, say you need the site code first. Do not guess it "
            "from the hostname."
        ),
    },
    {
        "name": "escalation",
        "description": "who to tell, and when",
        "body": "Escalate to the on-call engineer when a change window has already closed.",
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

    def _generate_agents(self, db, now):
        """Create the agents, their skills, and the bindings between them.

        Every tool binding points at an MCP tool, because `_generate_static_data` already made those.
        A registered Python tool arrives from the Sync AI Tools Job instead, and only in a deployment
        whose apps declare one.

        Args:
            db: The database alias to write to.
            now: One timestamp for the whole run.
        """
        del now

        skills = {}
        for spec in SKILLS:
            skills[spec["name"]], _ = AISkill.objects.using(db).update_or_create(
                name=spec["name"],
                defaults={"description": spec["description"], "body": spec["body"]},
            )

        agents = {}
        for spec in AGENTS:
            model = AIModel.objects.using(db).filter(provider__name=spec["provider"], kind="chat").first()
            if model is None:
                continue
            agents[spec["name"]], _ = AIAgent.objects.using(db).update_or_create(
                name=spec["name"],
                defaults={
                    "description": spec["description"],
                    "system_prompt": spec["system_prompt"],
                    "model": model,
                    "pattern": spec["pattern"],
                },
            )

        supervisor = agents.get("Network Operations Assistant")
        inventory = agents.get("Inventory Specialist")
        change = agents.get("Change Window Specialist")
        if not (supervisor and inventory and change):
            return

        AIAgentSubagent.objects.using(db).update_or_create(
            parent=supervisor,
            subagent=inventory,
            defaults={
                "tool_name": "inventory_expert",
                "tool_description": (
                    "Look up a network device by hostname. Returns the vendor and the site code. "
                    "Use this first when you need a site code."
                ),
                "weight": 100,
            },
        )
        AIAgentSubagent.objects.using(db).update_or_create(
            parent=supervisor,
            subagent=change,
            defaults={
                "tool_name": "change_expert",
                "tool_description": (
                    "Return the approved change window for one site. You must pass a site code, " "not a hostname."
                ),
                "weight": 200,
            },
        )

        for weight, skill in enumerate(skills.values(), start=1):
            AIAgentSkill.objects.using(db).update_or_create(
                agent=change, skill=skill, defaults={"weight": weight * 100}
            )

        read_only = MCPTool.objects.using(db).filter(writable=False).first()
        if read_only is not None:
            AIAgentTool.objects.using(db).update_or_create(
                agent=inventory,
                mcp_tool=read_only,
                defaults={
                    "description_override": "Look up one device. Send it a hostname and nothing else.",
                    "weight": 100,
                },
            )

    def _flush(self, db):
        """Delete every object _generate_static_data creates.

        This also deletes the names from before this app renamed its demonstration records. The
        integrations are shared and protected, so a surviving old provider would block them.

        Args:
            db: The database alias to delete from.
        """
        server_names = [spec["name"] for spec in MCP_SERVERS] + list(RETIRED_NAMES)
        MCPTool.objects.using(db).filter(mcp_server__name__in=server_names).delete()
        MCPServer.objects.using(db).filter(name__in=server_names).delete()

        agent_names = [spec["name"] for spec in AGENTS]
        AIAgentTool.objects.using(db).filter(agent__name__in=agent_names).delete()
        AIAgentSubagent.objects.using(db).filter(parent__name__in=agent_names).delete()
        AIAgentSkill.objects.using(db).filter(agent__name__in=agent_names).delete()
        AIAgentThread.objects.using(db).filter(agent__name__in=agent_names).delete()
        AIAgent.objects.using(db).filter(name__in=agent_names).delete()
        AISkill.objects.using(db).filter(name__in=[spec["name"] for spec in SKILLS]).delete()

        provider_names = [spec["name"] for spec in PROVIDERS] + list(RETIRED_NAMES)
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
        self._generate_agents(db, timezone.now())
        self.stdout.write(self.style.SUCCESS("Database populated with AI Models test data successfully!"))
