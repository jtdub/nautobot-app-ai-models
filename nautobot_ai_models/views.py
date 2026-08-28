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
    AI_MODEL_FIELDS,
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

    A subclass rather than a ``link_name``, because the Job's primary key is unknown until the Job
    is installed.
    """

    def _job(self):
        """Return the installed, enabled discovery Job, or None."""
        return Job.objects.filter(
            module_name=DISCOVERY_JOB_MODULE,
            job_class_name=DISCOVERY_JOB_CLASS,
            installed=True,
            enabled=True,
        ).first()

    def should_render(self, context):
        """Hide the button when the Job is not installed."""
        return super().should_render(context) and self._job() is not None

    def get_link(self, context):
        """Return the Job's run URL, with this server preselected."""
        job = self._job()
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
