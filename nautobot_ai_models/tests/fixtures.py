"""Create fixtures for tests."""

from django.utils import timezone
from nautobot.extras.models import ExternalIntegration

from nautobot_ai_models.choices import (
    AIAgentPatternChoices,
    AIAgentThreadStatusChoices,
    AIModelKindChoices,
    AIProviderTypeChoices,
    AIToolKindChoices,
    MCPTransportChoices,
    SubagentInputModeChoices,
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
    AITool,
    MCPServer,
    MCPTool,
)

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


REGISTERED_TOOLS = (
    ("lookup_device", "Look up one device by hostname. Returns vendor, site, and platform.", False),
    ("reboot_device", "Reboot one device by hostname. Returns nothing.", True),
    ("unreviewed_tool", "A tool discovery found and nobody has looked at yet.", True),
)


def register_test_tools():
    """Register the suite's tools, so `AITool` rows of kind `registered` validate.

    This is idempotent. The same callable may register twice under one name, and the suite calls
    this from more than one `setUpTestData`.
    """
    from nautobot_ai_models import tools  # pylint: disable=import-outside-toplevel

    for name, description, writable in REGISTERED_TOOLS:
        if tools.get_registered_tool(name) is not None:
            continue

        def placeholder(hostname: str) -> str:
            return hostname

        placeholder.__name__ = name
        tools.register_ai_tool(placeholder, name=name, description=description, writable=writable)


def create_aitool(**kwargs):
    """Return the suite's AI Tools, creating them if they do not exist.

    Returns:
        list: Three AITool records: a read-only registered tool, a writable one, and one that is
            disabled the way `new_tools_enabled: False` leaves a newly discovered tool.
    """
    register_test_tools()
    if AITool.objects.exists():
        return list(AITool.objects.all())

    from nautobot_ai_models import tools  # pylint: disable=import-outside-toplevel

    records = []
    for name, description, writable in REGISTERED_TOOLS:
        registered = tools.get_registered_tool(name)
        records.append(
            AITool.objects.create(
                name=name,
                description=description,
                argument_schema=registered.argument_schema,
                kind=AIToolKindChoices.REGISTERED,
                module=registered.module,
                writable=writable,
                advertised_read_only=not writable,
                definition_fingerprint=registered.definition_fingerprint,
                **kwargs,
            )
        )
    records[-1].enabled = False
    records[-1].module = "nautobot_ai_models.tests.other_module"
    records[-1].save()
    return records


def create_aiagent(**kwargs):
    """Return the suite's AI Agents, creating them if they do not exist.

    Returns:
        list: Three AIAgent records: a supervisor, a specialist, and a skills agent.
    """
    if AIAgent.objects.exists():
        return list(AIAgent.objects.all())

    if not AIModel.objects.exists():
        create_aimodel()
    chat = list(AIModel.objects.filter(kind=AIModelKindChoices.CHAT))

    return [
        AIAgent.objects.create(
            name="Test Supervisor",
            description="Answers network operations questions by asking specialists.",
            system_prompt="You answer network operations questions. Never state a fact you did not get from a tool.",
            model=chat[0],
            pattern=AIAgentPatternChoices.SINGLE,
            **kwargs,
        ),
        AIAgent.objects.create(
            name="Test Inventory Specialist",
            description="Looks up a network device by hostname. Give it a hostname.",
            system_prompt="You look up device records. Never state a fact you did not get from the tool.",
            model=chat[0],
            **kwargs,
        ),
        AIAgent.objects.create(
            name="Test Skills Agent",
            description="One agent that loads its rules as it needs them.",
            system_prompt="You start with no domain rules loaded. Call load_skill before any other tool.",
            model=chat[1],
            **kwargs,
        ),
    ]


def create_aiagenttool(**kwargs):
    """Return the suite's tool bindings, and create them if they do not exist.

    One binding per source, so a test that reads `wire_name` or `writable` off a binding gets both
    kinds without a build of its own.

    Returns:
        list: Two AIAgentTool records, one MCP and one registered.
    """
    if AIAgentTool.objects.exists():
        return list(AIAgentTool.objects.all())

    agents = create_aiagent()
    mcp_tools = create_mcptool()
    ai_tools = create_aitool()
    return [
        AIAgentTool.objects.create(agent=agents[0], mcp_tool=mcp_tools[0], **kwargs),
        AIAgentTool.objects.create(
            agent=agents[0],
            ai_tool=ai_tools[0],
            name_override="find_device",
            description_override="Look up a device. Send it one hostname.",
            **kwargs,
        ),
        AIAgentTool.objects.create(agent=agents[1], mcp_tool=mcp_tools[1], weight=200, **kwargs),
        AIAgentTool.objects.create(agent=agents[1], ai_tool=ai_tools[1], weight=300, **kwargs),
    ]


def create_aiagentsubagent(**kwargs):
    """Return the suite's subagent bindings, creating them if they do not exist.

    Returns:
        list: One AIAgentSubagent record.
    """
    if AIAgentSubagent.objects.exists():
        return list(AIAgentSubagent.objects.all())

    agents = create_aiagent()
    return [
        AIAgentSubagent.objects.create(
            parent=agents[0],
            subagent=agents[1],
            tool_name="inventory_expert",
            tool_description="Look up a network device by hostname. Returns the vendor and the site code.",
            input_mode=SubagentInputModeChoices.TASK_ONLY,
            **kwargs,
        ),
        AIAgentSubagent.objects.create(
            parent=agents[0],
            subagent=agents[2],
            tool_name="policy_expert",
            tool_description="Answer a policy question. Give it the area of work.",
            input_mode=SubagentInputModeChoices.TASK_AND_CONTEXT,
            weight=200,
            **kwargs,
        ),
        AIAgentSubagent.objects.create(parent=agents[2], subagent=agents[1], weight=300, **kwargs),
    ]


def create_aiskill(**kwargs):
    """Return the suite's AI Skills, creating them if they do not exist.

    Returns:
        list: Two AISkill records.
    """
    if AISkill.objects.exists():
        return list(AISkill.objects.all())

    return [
        AISkill.objects.create(
            name="device_records",
            description="looking up devices",
            body="Call lookup_device for every hostname. Report the vendor and the site code.",
            **kwargs,
        ),
        AISkill.objects.create(
            name="maintenance_windows",
            description="approved change windows",
            body="If the request gives you a hostname instead of a site code, ask for the site code.",
            **kwargs,
        ),
        AISkill.objects.create(
            name="escalation",
            description="who to tell, and when",
            body="Escalate to the on-call engineer when a change window has already closed.",
            enabled=False,
            **kwargs,
        ),
    ]


def create_aiagentskill(**kwargs):
    """Return the suite's skill bindings, creating them if they do not exist.

    Returns:
        list: Two AIAgentSkill records.
    """
    if AIAgentSkill.objects.exists():
        return list(AIAgentSkill.objects.all())

    agents = create_aiagent()
    skills = create_aiskill()
    return [
        AIAgentSkill.objects.create(agent=agents[2], skill=skills[0], **kwargs),
        AIAgentSkill.objects.create(agent=agents[2], skill=skills[1], weight=200, **kwargs),
        AIAgentSkill.objects.create(agent=agents[0], skill=skills[0], weight=300, **kwargs),
    ]


def create_aiagentthread(**kwargs):
    """Return the suite's threads, creating them if they do not exist.

    Returns:
        list: Three AIAgentThread records, one per interesting status.
    """
    if AIAgentThread.objects.exists():
        return list(AIAgentThread.objects.all())

    agents = create_aiagent()
    return [
        AIAgentThread.objects.create(agent=agents[0], **kwargs),
        AIAgentThread.objects.create(
            agent=agents[0],
            status=AIAgentThreadStatusChoices.WAITING,
            interrupt_payload={"question": "Approve the reboot?"},
            **kwargs,
        ),
        AIAgentThread.objects.create(
            agent=agents[1],
            status=AIAgentThreadStatusChoices.COMPLETED,
            finished_at=timezone.now(),
            **kwargs,
        ),
    ]
