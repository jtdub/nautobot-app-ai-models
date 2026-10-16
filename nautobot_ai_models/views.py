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
    AI_AGENT_FALLBACK_FIELDS,
    AI_AGENT_FIELDS,
    AI_AGENT_SKILL_FIELDS,
    AI_AGENT_SUBAGENT_FIELDS,
    AI_AGENT_THREAD_FIELDS,
    AI_AGENT_TOOL_FIELDS,
    AI_MODEL_CAPABILITY_FIELDS,
    AI_MODEL_FIELDS,
    AI_SKILL_FIELDS,
    AI_TOOL_APPROVAL_FIELDS,
    AI_TOOL_DEFINITION_FIELDS,
    AI_TOOL_DISCOVERY_STAMPS,
    AI_TOOL_SOURCE_FIELDS,
    AI_USAGE_BUDGET_FIELDS,
    AI_USAGE_RECORD_FIELDS,
    MCP_PROMPT_DEFINITION_FIELDS,
    MCP_RESOURCE_DEFINITION_FIELDS,
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
            ObjectFieldsPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="Capabilities",
                fields=list(AI_MODEL_CAPABILITY_FIELDS),
            ),
            ObjectTextPanel(
                weight=300,
                section=SectionChoices.RIGHT_HALF,
                label="Default Parameters",
                object_field="default_parameters",
                render_as=ObjectTextPanel.RenderOptions.JSON,
            ),
            ObjectsTablePanel(
                weight=400,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.AIAgentFallbackTable,
                table_filter="model",
                select_related_fields=["agent", "model"],
                related_field_name="model",
                table_title="Agents that fall back to this",
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
            ObjectsTablePanel(
                weight=600,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.MCPResourceTable,
                table_filter="mcp_server",
                select_related_fields=["mcp_server"],
                related_field_name="mcp_server",
                table_title="Resources",
            ),
            ObjectsTablePanel(
                weight=700,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.MCPPromptTable,
                table_filter="mcp_server",
                select_related_fields=["mcp_server"],
                related_field_name="mcp_server",
                table_title="Prompts",
            ),
        ],
        extra_buttons=[
            RunDiscoveryButton(
                weight=100,
                label="Run Discovery",
                icon="mdi-radar",
                color=ButtonColorChoices.BLUE,
                link_includes_pk=False,
                required_permissions=[
                    "extras.run_job",
                    "nautobot_ai_models.change_mcptool",
                    "nautobot_ai_models.change_mcpresource",
                    "nautobot_ai_models.change_mcpprompt",
                ],
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


class MCPResourceUIViewSet(NautobotUIViewSet):
    """ViewSet for MCP Resource views."""

    bulk_update_form_class = forms.MCPResourceBulkEditForm
    filterset_class = filters.MCPResourceFilterSet
    filterset_form_class = forms.MCPResourceFilterForm
    form_class = forms.MCPResourceForm
    lookup_field = "pk"
    queryset = models.MCPResource.objects.select_related("mcp_server")
    serializer_class = serializers.MCPResourceSerializer
    table_class = tables.MCPResourceTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="MCP Resource",
                fields=[*MCP_RESOURCE_DEFINITION_FIELDS, "last_seen_at", "definition_fingerprint"],
            ),
            ObjectTextPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="Advertised Annotations",
                object_field="annotations",
                render_as=ObjectTextPanel.RenderOptions.JSON,
            ),
            ObjectsTablePanel(
                weight=300,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.AIAgentToolTable,
                table_filter="mcp_resource",
                select_related_fields=[
                    "agent",
                    "ai_tool",
                    "mcp_tool__mcp_server",
                    "mcp_prompt__mcp_server",
                    "mcp_resource__mcp_server",
                ],
                related_field_name="mcp_resource",
                table_title="Agents that may use this",
            ),
        ],
    )


class MCPPromptUIViewSet(NautobotUIViewSet):
    """ViewSet for MCP Prompt views."""

    bulk_update_form_class = forms.MCPPromptBulkEditForm
    filterset_class = filters.MCPPromptFilterSet
    filterset_form_class = forms.MCPPromptFilterForm
    form_class = forms.MCPPromptForm
    lookup_field = "pk"
    queryset = models.MCPPrompt.objects.select_related("mcp_server")
    serializer_class = serializers.MCPPromptSerializer
    table_class = tables.MCPPromptTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="MCP Prompt",
                fields=[*MCP_PROMPT_DEFINITION_FIELDS, "last_seen_at", "definition_fingerprint"],
            ),
            ObjectTextPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="Advertised Arguments",
                object_field="arguments",
                render_as=ObjectTextPanel.RenderOptions.JSON,
            ),
            ObjectsTablePanel(
                weight=300,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.AIAgentToolTable,
                table_filter="mcp_prompt",
                select_related_fields=[
                    "agent",
                    "ai_tool",
                    "mcp_tool__mcp_server",
                    "mcp_prompt__mcp_server",
                    "mcp_resource__mcp_server",
                ],
                related_field_name="mcp_prompt",
                table_title="Agents that may use this",
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
            ObjectsTablePanel(
                weight=600,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.AIAgentFallbackTable,
                table_filter="agent",
                select_related_fields=["agent", "model"],
                related_field_name="agent",
                table_title="Fallback models",
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
    queryset = models.AIAgentTool.objects.for_list()
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
                fields=["wire_name", "wire_description", "writable", "fingerprint", "is_approved"],
            ),
            ObjectsTablePanel(
                weight=300,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.AIToolApprovalTable,
                table_filter="binding",
                related_field_name="binding",
                table_title="Approvals",
            ),
        ],
    )


class AIToolApprovalUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Tool Approval views.

    The reviewer and the digest are stamped here, not asked for on the form. A record of who
    approved what is worth nothing when the person filling it in chooses both.
    """

    filterset_class = filters.AIToolApprovalFilterSet
    filterset_form_class = forms.AIToolApprovalFilterForm
    form_class = forms.AIToolApprovalForm
    lookup_field = "pk"
    queryset = models.AIToolApproval.objects.for_list()
    serializer_class = serializers.AIToolApprovalSerializer
    table_class = tables.AIToolApprovalTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="Approval",
                fields=list(AI_TOOL_APPROVAL_FIELDS),
            ),
            ObjectFieldsPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="Does it still answer",
                fields=["is_current", "is_expired", "is_active"],
            ),
        ],
    )

    def form_save(self, form, **kwargs):
        """Stamp the reviewer on a create, and stamp whoever withdraws it.

        Both names are copied beside the foreign key, so a deleted account does not erase the
        record of who decided.

        Args:
            form: The bound form.
            **kwargs: Passed through to the base implementation.

        Returns:
            AIToolApproval: The saved record.
        """
        user = self.request.user
        approval = form.instance
        if not approval.present_in_database:
            approval.approved_by = user
            approval.approved_by_name = user.get_username()
        elif approval.revoked_at is not None and approval.revoked_by_id is None:
            approval.revoked_by = user
            approval.revoked_by_name = user.get_username()
        return super().form_save(form, **kwargs)


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


class AIUsageBudgetUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Usage Budget views."""

    bulk_update_form_class = forms.AIUsageBudgetBulkEditForm
    filterset_class = filters.AIUsageBudgetFilterSet
    filterset_form_class = forms.AIUsageBudgetFilterForm
    form_class = forms.AIUsageBudgetForm
    lookup_field = "pk"
    queryset = models.AIUsageBudget.objects.select_related("agent", "model", "tenant")
    serializer_class = serializers.AIUsageBudgetSerializer
    table_class = tables.AIUsageBudgetTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="Budget",
                fields=list(AI_USAGE_BUDGET_FIELDS),
            ),
            ObjectFieldsPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="This period",
                fields=["spent_cost", "spent_tokens", "is_exceeded"],
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


class AIAgentFallbackUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Agent Fallback views."""

    bulk_update_form_class = forms.AIAgentFallbackBulkEditForm
    filterset_class = filters.AIAgentFallbackFilterSet
    filterset_form_class = forms.AIAgentFallbackFilterForm
    form_class = forms.AIAgentFallbackForm
    lookup_field = "pk"
    queryset = models.AIAgentFallback.objects.select_related("agent", "model")
    serializer_class = serializers.AIAgentFallbackSerializer
    table_class = tables.AIAgentFallbackTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.FULL_WIDTH,
                label="Binding",
                fields=list(AI_AGENT_FALLBACK_FIELDS),
            ),
        ],
    )


class AIUsageRecordUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Usage Record views.

    Read and delete only, the same as the thread views and for the same reason: this app makes no
    model call, so it has nothing to record. A consuming app writes these over the REST API.
    """

    unsupported_actions = ("create", "update", "bulk_create", "bulk_update", "bulk_rename")
    action_buttons = ("export",)

    filterset_class = filters.AIUsageRecordFilterSet
    filterset_form_class = forms.AIUsageRecordFilterForm
    lookup_field = "pk"
    queryset = models.AIUsageRecord.objects.select_related("thread", "agent", "model__provider")
    serializer_class = serializers.AIUsageRecordSerializer
    table_class = tables.AIUsageRecordTable

    object_detail_content = ObjectDetailContent(
        panels=[
            ObjectFieldsPanel(
                weight=100,
                section=SectionChoices.LEFT_HALF,
                label="Usage",
                fields=[*AI_USAGE_RECORD_FIELDS, "total_tokens", "total_cost"],
            ),
            ObjectTextPanel(
                weight=200,
                section=SectionChoices.RIGHT_HALF,
                label="What the provider reported",
                object_field="usage_payload",
                render_as=ObjectTextPanel.RenderOptions.JSON,
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
            ObjectsTablePanel(
                weight=300,
                section=SectionChoices.FULL_WIDTH,
                table_class=tables.AIUsageRecordTable,
                table_filter="thread",
                select_related_fields=["agent", "model"],
                related_field_name="thread",
                table_title="Usage",
            ),
        ],
    )
