"""Views for nautobot_ai_models."""

from django.urls import reverse
from nautobot.apps.models import count_related
from nautobot.apps.ui import (
    Button,
    ButtonColorChoices,
    ObjectDetailContent,
    ObjectFieldsPanel,
    ObjectsTablePanel,
    ObjectTextPanel,
    SectionChoices,
)
from nautobot.apps.views import NautobotUIViewSet
from nautobot.extras.models import Job

from nautobot_ai_models import filters, forms, models, tables
from nautobot_ai_models.api import serializers
from nautobot_ai_models.constants import (
    AI_AGENT_FIELDS,
    AI_AGENT_SKILL_FIELDS,
    AI_AGENT_SUBAGENT_FIELDS,
    AI_AGENT_THREAD_FIELDS,
    AI_AGENT_TOOL_FIELDS,
    AI_MODEL_FIELDS,
    AI_SKILL_FIELDS,
    AI_TOOL_DEFINITION_FIELDS,
    AI_TOOL_DISCOVERY_STAMPS,
    AI_TOOL_SOURCE_FIELDS,
    MCP_SERVER_DISCOVERED_COLUMNS,
    MCP_SERVER_OPERATOR_FIELDS,
    MCP_TOOL_DEFINITION_FIELDS,
)


class AIProviderUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Provider views."""

    bulk_update_form_class = forms.AIProviderBulkEditForm
    filterset_class = filters.AIProviderFilterSet
    filterset_form_class = forms.AIProviderFilterForm
    form_class = forms.AIProviderForm
    lookup_field = "pk"
    queryset = models.AIProvider.objects.select_related("external_integration")
    serializer_class = serializers.AIProviderSerializer
    table_class = tables.AIProviderTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                fields="__all__",
            ),
            ObjectsTablePanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                table_class=tables.AIModelTable,
                table_filter="provider",
                select_related_fields=["provider"],
                related_field_name="provider",
                table_title="AI Models",
            ),
        ],
    )


class AIModelUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Model views."""

    bulk_update_form_class = forms.AIModelBulkEditForm
    filterset_class = filters.AIModelFilterSet
    filterset_form_class = forms.AIModelFilterForm
    form_class = forms.AIModelForm
    lookup_field = "pk"
    queryset = models.AIModel.objects.select_related("provider")
    serializer_class = serializers.AIModelSerializer
    table_class = tables.AIModelTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                fields=list(AI_MODEL_FIELDS),
            ),
            ObjectTextPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="Default Parameters",
                object_field="default_parameters",
                render_as=ObjectTextPanel.RenderOptions.JSON,
            ),
        ],
    )


DISCOVERY_JOB_MODULE = "nautobot_ai_models.jobs"
DISCOVERY_JOB_CLASS = "MCPServerDiscovery"


class RunDiscoveryButton(Button):
    """Open the discovery job with this server already selected.

    This is a subclass rather than a ``link_name``, because the Job's primary key is unknown
    until somebody installs the Job.
    """

    CONTEXT_KEY = "_mcp_discovery_job"

    def _job(self, context):
        """Return the installed, enabled discovery Job, or None.

        The lookup runs once per render. `should_render` and `get_link` both need it, and Nautobot
        calls both on every MCP Server detail page.

        Args:
            context: The render context, which carries the answer between the two calls.

        Returns:
            Job | None: The Job, or None when it is not installed.
        """
        if self.CONTEXT_KEY not in context:
            context[self.CONTEXT_KEY] = Job.objects.filter(
                module_name=DISCOVERY_JOB_MODULE,
                job_class_name=DISCOVERY_JOB_CLASS,
                installed=True,
                enabled=True,
            ).first()
        return context[self.CONTEXT_KEY]

    def should_render(self, context):
        """Hide the button when the Job is not installed."""
        return super().should_render(context) and self._job(context) is not None

    def get_link(self, context):
        """Return the Job's run URL, with this server preselected."""
        job = self._job(context)
        if job is None:
            return None
        obj = context.get("object")
        url = reverse("extras:job_run", kwargs={"pk": job.pk})
        return f"{url}?mcp_server={obj.pk}" if obj is not None else url


class MCPServerUIViewSet(NautobotUIViewSet):
    """ViewSet for MCPServer views."""

    bulk_update_form_class = forms.MCPServerBulkEditForm
    filterset_class = filters.MCPServerFilterSet
    filterset_form_class = forms.MCPServerFilterForm
    form_class = forms.MCPServerForm
    lookup_field = "pk"
    queryset = models.MCPServer.objects.select_related("external_integration", "tenant").annotate(
        tool_count=count_related(models.MCPTool, "mcp_server")
    )
    serializer_class = serializers.MCPServerSerializer
    table_class = tables.MCPServerTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="MCP Server",
                fields=list(MCP_SERVER_OPERATOR_FIELDS),
            ),
            ObjectFieldsPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="Reported by the server",
                fields=list(MCP_SERVER_DISCOVERED_COLUMNS),
            ),
            ObjectTextPanel(
                weight=300,
                section=SectionChoices.RIGHT_HALF,
                label="Advertised Capabilities",
                object_field="capabilities",
                render_as=ObjectTextPanel.RenderOptions.JSON,
            ),
            ObjectTextPanel(
                weight=400,
                section=SectionChoices.FULL_WIDTH,
                label="Server Instructions",
                object_field="instructions",
                render_as=ObjectTextPanel.RenderOptions.MARKDOWN,
            ),
            ObjectsTablePanel(
                weight=500,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.MCPToolTable,
                table_filter="mcp_server",
                select_related_fields=["mcp_server"],
                related_field_name="mcp_server",
                table_title="Tools",
            ),
        ],
        extra_buttons=[
            RunDiscoveryButton(
                weight=100,
                label="Run Discovery",
                icon="mdi-radar",
                color=ButtonColorChoices.BLUE,
                link_includes_pk=False,
                required_permissions=["extras.run_job", "nautobot_ai_models.change_mcptool"],
            ),
        ],
    )


class MCPToolUIViewSet(NautobotUIViewSet):
    """ViewSet for MCPTool views."""

    bulk_update_form_class = forms.MCPToolBulkEditForm
    filterset_class = filters.MCPToolFilterSet
    filterset_form_class = forms.MCPToolFilterForm
    form_class = forms.MCPToolForm
    lookup_field = "pk"
    queryset = models.MCPTool.objects.select_related("mcp_server")
    serializer_class = serializers.MCPToolSerializer
    table_class = tables.MCPToolTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="MCP Tool",
                fields=[*MCP_TOOL_DEFINITION_FIELDS, "last_seen_at", "definition_fingerprint"],
            ),
            ObjectTextPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="Input Schema",
                object_field="input_schema",
                render_as=ObjectTextPanel.RenderOptions.JSON,
            ),
            ObjectTextPanel(
                weight=300,
                section=SectionChoices.RIGHT_HALF,
                label="Output Schema",
                object_field="output_schema",
                render_as=ObjectTextPanel.RenderOptions.JSON,
            ),
        ],
    )


class AIToolUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Tool views.

    No add view and no import. The Sync AI Tools Job writes a tool from what the code declared,
    and a row created by hand would name a callable that nothing registered. `AIToolForm` offers
    the two flags a person owns and nothing else.

    `AIModelsUIViewSetRouter` reads `unsupported_actions` and builds no route for what it names.
    """

    unsupported_actions = ("create", "bulk_create", "bulk_rename")
    action_buttons = ("export",)

    bulk_update_form_class = forms.AIToolBulkEditForm
    filterset_class = filters.AIToolFilterSet
    filterset_form_class = forms.AIToolFilterForm
    form_class = forms.AIToolForm
    lookup_field = "pk"
    queryset = models.AITool.objects.select_related("job", "git_repository")
    serializer_class = serializers.AIToolSerializer
    table_class = tables.AIToolTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="AI Tool",
                fields=list(AI_TOOL_DEFINITION_FIELDS),
            ),
            ObjectFieldsPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="Where it came from",
                fields=[*AI_TOOL_SOURCE_FIELDS, *AI_TOOL_DISCOVERY_STAMPS],
            ),
            ObjectTextPanel(
                weight=300,
                section=SectionChoices.FULL_WIDTH,
                label="Argument Schema",
                object_field="argument_schema",
                render_as=ObjectTextPanel.RenderOptions.JSON,
            ),
            ObjectsTablePanel(
                weight=400,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.AIAgentToolTable,
                table_filter="ai_tool",
                select_related_fields=["agent", "ai_tool", "mcp_tool__mcp_server"],
                related_field_name="ai_tool",
                table_title="Agents that may call this",
            ),
        ],
    )


class AIAgentUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Agent views."""

    bulk_update_form_class = forms.AIAgentBulkEditForm
    filterset_class = filters.AIAgentFilterSet
    filterset_form_class = forms.AIAgentFilterForm
    form_class = forms.AIAgentForm
    lookup_field = "pk"
    queryset = models.AIAgent.objects.select_related("model__provider", "tenant").annotate(
        tool_count=count_related(models.AIAgentTool, "agent")
    )
    serializer_class = serializers.AIAgentSerializer
    table_class = tables.AIAgentTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="AI Agent",
                fields=list(AI_AGENT_FIELDS),
            ),
            ObjectTextPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="System Prompt",
                object_field="system_prompt",
                render_as=ObjectTextPanel.RenderOptions.MARKDOWN,
            ),
            ObjectsTablePanel(
                weight=300,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.AIAgentToolTable,
                table_filter="agent",
                select_related_fields=["agent", "ai_tool", "mcp_tool__mcp_server"],
                related_field_name="agent",
                table_title="Tools",
            ),
            ObjectsTablePanel(
                weight=400,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.AIAgentSubagentTable,
                table_filter="parent",
                select_related_fields=["parent", "subagent"],
                related_field_name="parent",
                table_title="Subagents",
            ),
            ObjectsTablePanel(
                weight=500,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.AIAgentSkillTable,
                table_filter="agent",
                select_related_fields=["agent", "skill"],
                related_field_name="agent",
                table_title="Skills",
            ),
        ],
    )


class AIAgentToolUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Agent Tool views."""

    bulk_update_form_class = forms.AIAgentToolBulkEditForm
    filterset_class = filters.AIAgentToolFilterSet
    filterset_form_class = forms.AIAgentToolFilterForm
    form_class = forms.AIAgentToolForm
    lookup_field = "pk"
    queryset = models.AIAgentTool.objects.select_related("agent", "mcp_tool__mcp_server", "ai_tool")
    serializer_class = serializers.AIAgentToolSerializer
    table_class = tables.AIAgentToolTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="Binding",
                fields=list(AI_AGENT_TOOL_FIELDS),
            ),
            ObjectFieldsPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="What the model is told",
                fields=["wire_name", "wire_description", "writable", "fingerprint"],
            ),
        ],
    )


class AIAgentSubagentUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Agent Subagent views."""

    bulk_update_form_class = forms.AIAgentSubagentBulkEditForm
    filterset_class = filters.AIAgentSubagentFilterSet
    filterset_form_class = forms.AIAgentSubagentFilterForm
    form_class = forms.AIAgentSubagentForm
    lookup_field = "pk"
    queryset = models.AIAgentSubagent.objects.select_related("parent", "subagent")
    serializer_class = serializers.AIAgentSubagentSerializer
    table_class = tables.AIAgentSubagentTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="Binding",
                fields=list(AI_AGENT_SUBAGENT_FIELDS),
            ),
            ObjectFieldsPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="What the supervisor is told",
                fields=["wire_name", "wire_description"],
            ),
        ],
    )


class AISkillUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Skill views."""

    bulk_update_form_class = forms.AISkillBulkEditForm
    filterset_class = filters.AISkillFilterSet
    filterset_form_class = forms.AISkillFilterForm
    form_class = forms.AISkillForm
    lookup_field = "pk"
    queryset = models.AISkill.objects.all()
    serializer_class = serializers.AISkillSerializer
    table_class = tables.AISkillTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="AI Skill",
                fields=[field for field in AI_SKILL_FIELDS if field != "body"],
            ),
            ObjectTextPanel(
                weight=200,
                section=SectionChoices.FULL_WIDTH,
                label="Rules",
                object_field="body",
                render_as=ObjectTextPanel.RenderOptions.MARKDOWN,
            ),
            ObjectsTablePanel(
                weight=300,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.AIAgentSkillTable,
                table_filter="skill",
                select_related_fields=["agent", "skill"],
                related_field_name="skill",
                table_title="Agents that may load this",
            ),
        ],
    )


class AIAgentSkillUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Agent Skill views."""

    bulk_update_form_class = forms.AIAgentSkillBulkEditForm
    filterset_class = filters.AIAgentSkillFilterSet
    filterset_form_class = forms.AIAgentSkillFilterForm
    form_class = forms.AIAgentSkillForm
    lookup_field = "pk"
    queryset = models.AIAgentSkill.objects.select_related("agent", "skill")
    serializer_class = serializers.AIAgentSkillSerializer
    table_class = tables.AIAgentSkillTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.FULL_WIDTH,
                label="Binding",
                fields=list(AI_AGENT_SKILL_FIELDS),
            ),
        ],
    )


class AIAgentThreadUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Agent Thread views.

    Read and delete only. Whatever ran the agent writes the thread. There is no form, so an add
    view, an edit view, or a bulk edit could only fail. A delete leaves the checkpoint rows
    behind until the Prune Agent Threads Job runs.

    `unsupported_actions` does the refusal, the same way `AIToolUIViewSet` refuses its add view.
    Hand-composed read-only mixins would work here and not there, because `ObjectEditViewMixin`
    supplies create and update together.
    """

    unsupported_actions = ("create", "update", "bulk_create", "bulk_update", "bulk_rename")
    action_buttons = ("export",)

    filterset_class = filters.AIAgentThreadFilterSet
    filterset_form_class = forms.AIAgentThreadFilterForm
    lookup_field = "pk"
    queryset = models.AIAgentThread.objects.select_related("agent")
    serializer_class = serializers.AIAgentThreadSerializer
    table_class = tables.AIAgentThreadTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="Thread",
                fields=list(AI_AGENT_THREAD_FIELDS),
            ),
            ObjectTextPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="Waiting on",
                object_field="interrupt_payload",
                render_as=ObjectTextPanel.RenderOptions.JSON,
            ),
        ],
    )
