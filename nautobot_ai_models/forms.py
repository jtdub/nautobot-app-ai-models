"""Forms for nautobot_ai_models.

A ``DynamicModelChoiceField`` on a ``NautobotModelForm`` gets the embedded-create "+" button for
free. To remove that button, add ``external_integration`` to ``Meta.exclude_embedded_create``, or
pass ``embedded_create=False``.
"""

from django import forms
from nautobot.apps.constants import CHARFIELD_MAX_LENGTH
from nautobot.apps.forms import (
    BulkEditNullBooleanSelect,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    NautobotBulkEditForm,
    NautobotFilterForm,
    NautobotModelForm,
    StaticSelect2,
    StaticSelect2Multiple,
    TagsBulkEditFormMixin,
    add_blank_choice,
)
from nautobot.extras.models import ExternalIntegration, GitRepository
from nautobot.tenancy.models import Tenant

from nautobot_ai_models import models
from nautobot_ai_models.choices import (
    AIAgentPatternChoices,
    AIAgentThreadStatusChoices,
    AIModelKindChoices,
    AIProviderTypeChoices,
    AIToolKindChoices,
    MCPTransportChoices,
    SubagentInputModeChoices,
)
from nautobot_ai_models.constants import (
    AI_AGENT_FIELDS,
    AI_AGENT_SKILL_FIELDS,
    AI_AGENT_SUBAGENT_FIELDS,
    AI_AGENT_TOOL_FIELDS,
    AI_SKILL_FIELDS,
    MCP_SERVER_OPERATOR_FIELDS,
    MCP_TOOL_DEFINITION_FIELDS,
    MCP_TOOL_SCHEMA_FIELDS,
)


def _boolean_select():
    """Build a three-state Yes/No/any widget.

    Returns:
        BulkEditNullBooleanSelect: A new instance, because a widget belongs to one field.
    """
    return BulkEditNullBooleanSelect()


class AIProviderForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """AIProvider creation and edit form."""

    external_integration = DynamicModelChoiceField(
        queryset=ExternalIntegration.objects.all(),
        label="External Integration",
        help_text="Supplies the remote URL, headers, TLS settings, timeout, and credentials.",
    )

    class Meta:
        """Meta attributes."""

        model = models.AIProvider
        fields = "__all__"


class AIProviderBulkEditForm(NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """AIProvider bulk edit form."""

    pk = forms.ModelMultipleChoiceField(queryset=models.AIProvider.objects.all(), widget=forms.MultipleHiddenInput)
    description = forms.CharField(required=False, max_length=CHARFIELD_MAX_LENGTH)
    external_integration = DynamicModelChoiceField(
        queryset=ExternalIntegration.objects.all(),
        required=False,
        label="External Integration",
    )
    openai_compatible = forms.NullBooleanField(
        required=False,
        label="OpenAI-compatible",
        widget=_boolean_select(),
    )
    provider_type = forms.ChoiceField(
        choices=add_blank_choice(AIProviderTypeChoices),
        required=False,
        label="Provider type",
        widget=StaticSelect2,
    )
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())
    num_predict = forms.IntegerField(required=False, label="Default num_predict")
    temperature = forms.DecimalField(required=False, label="Default temperature")

    class Meta:
        """Meta attributes."""

        nullable_fields = [
            "description",
            "num_predict",
            "temperature",
        ]


class AIProviderFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filter form to filter searches."""

    model = models.AIProvider
    field_order = ["q", "name", "external_integration", "provider_type", "openai_compatible", "enabled"]

    q = forms.CharField(
        required=False,
        label="Search",
        help_text="Search within Name.",
    )
    name = forms.CharField(required=False, label="Name")
    external_integration = DynamicModelMultipleChoiceField(
        queryset=ExternalIntegration.objects.all(),
        required=False,
        label="External Integration",
    )
    provider_type = forms.MultipleChoiceField(
        choices=AIProviderTypeChoices,
        required=False,
        label="Provider type",
        widget=StaticSelect2Multiple,
    )
    openai_compatible = forms.NullBooleanField(
        required=False,
        label="OpenAI-compatible",
        widget=_boolean_select(),
    )
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())


class AIModelForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """AIModel creation/edit form."""

    provider = DynamicModelChoiceField(
        queryset=models.AIProvider.objects.all(),
        label="AI Provider",
    )

    class Meta:
        """Meta attributes."""

        model = models.AIModel
        fields = "__all__"


class AIModelBulkEditForm(NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """AIModel bulk edit form."""

    pk = forms.ModelMultipleChoiceField(queryset=models.AIModel.objects.all(), widget=forms.MultipleHiddenInput)
    provider = DynamicModelChoiceField(
        queryset=models.AIProvider.objects.all(),
        required=False,
        label="AI Provider",
    )
    description = forms.CharField(required=False, max_length=CHARFIELD_MAX_LENGTH)
    kind = forms.ChoiceField(
        choices=add_blank_choice(AIModelKindChoices),
        required=False,
        widget=StaticSelect2,
    )
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())
    num_predict = forms.IntegerField(required=False)
    temperature = forms.DecimalField(required=False)
    input_cost_per_million = forms.DecimalField(required=False, label="Input cost per million tokens")
    output_cost_per_million = forms.DecimalField(required=False, label="Output cost per million tokens")

    class Meta:
        """Meta attributes."""

        nullable_fields = [
            "description",
            "num_predict",
            "temperature",
            "input_cost_per_million",
            "output_cost_per_million",
        ]


class AIModelFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filter form to filter searches."""

    model = models.AIModel
    field_order = ["q", "name", "provider", "kind", "enabled"]

    q = forms.CharField(
        required=False,
        label="Search",
        help_text="Search within Name.",
    )
    name = forms.CharField(required=False, label="Name")
    provider = DynamicModelMultipleChoiceField(
        queryset=models.AIProvider.objects.all(),
        required=False,
        label="AI Provider",
    )
    kind = forms.MultipleChoiceField(choices=AIModelKindChoices, required=False, widget=StaticSelect2Multiple)
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())


class MCPServerForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """MCPServer creation/edit form."""

    external_integration = DynamicModelChoiceField(
        queryset=ExternalIntegration.objects.all(),
        label="External Integration",
        help_text="Carries the endpoint URL, its headers and TLS settings, and its secrets group.",
    )
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False)

    class Meta:
        """Meta attributes."""

        model = models.MCPServer
        fields = [*MCP_SERVER_OPERATOR_FIELDS, "tags"]  # pylint: disable=nb-use-fields-all


class MCPServerBulkEditForm(TagsBulkEditFormMixin, NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """MCPServer bulk edit form."""

    pk = forms.ModelMultipleChoiceField(queryset=models.MCPServer.objects.all(), widget=forms.MultipleHiddenInput)
    description = forms.CharField(required=False, max_length=CHARFIELD_MAX_LENGTH)
    transport = forms.ChoiceField(
        choices=add_blank_choice(MCPTransportChoices),
        required=False,
        widget=StaticSelect2,
    )
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False)

    class Meta:
        """Meta attributes."""

        nullable_fields = [
            "description",
            "tenant",
        ]


class MCPServerFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filter form to filter searches."""

    model = models.MCPServer
    field_order = ["q", "name", "external_integration", "transport", "enabled", "tenant"]

    q = forms.CharField(
        required=False,
        label="Search",
        help_text="Search within name, description, or the name the server reports for itself.",
    )
    name = forms.CharField(required=False, label="Name")
    external_integration = DynamicModelMultipleChoiceField(
        queryset=ExternalIntegration.objects.all(),
        required=False,
        label="External Integration",
    )
    transport = forms.MultipleChoiceField(choices=MCPTransportChoices, required=False, widget=StaticSelect2Multiple)
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())
    tenant = DynamicModelMultipleChoiceField(queryset=Tenant.objects.all(), required=False)


class MCPToolForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """MCPTool creation and edit form.

    A person edits these rows as well as discovery, because Nautobot cannot discover a stdio
    server.
    """

    mcp_server = DynamicModelChoiceField(queryset=models.MCPServer.objects.all(), label="MCP Server")

    class Meta:
        """Meta attributes."""

        model = models.MCPTool
        fields = [*MCP_TOOL_DEFINITION_FIELDS, *MCP_TOOL_SCHEMA_FIELDS]  # pylint: disable=nb-use-fields-all


class MCPToolBulkEditForm(NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """MCPTool bulk edit form."""

    pk = forms.ModelMultipleChoiceField(queryset=models.MCPTool.objects.all(), widget=forms.MultipleHiddenInput)
    title = forms.CharField(required=False, max_length=CHARFIELD_MAX_LENGTH)
    description = forms.CharField(required=False, widget=forms.Textarea)
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())
    writable = forms.NullBooleanField(required=False, widget=_boolean_select())

    class Meta:
        """Meta attributes."""

        nullable_fields = [
            "title",
            "description",
        ]


class MCPToolFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filter form to filter searches."""

    model = models.MCPTool
    field_order = ["q", "mcp_server", "name", "enabled", "writable", "advertised_read_only"]

    q = forms.CharField(
        required=False,
        label="Search",
        help_text="Search within name, title, or description.",
    )
    mcp_server = DynamicModelMultipleChoiceField(
        queryset=models.MCPServer.objects.all(),
        required=False,
        label="MCP Server",
    )
    name = forms.CharField(required=False, label="Name")
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())
    writable = forms.NullBooleanField(required=False, widget=_boolean_select())
    advertised_read_only = forms.NullBooleanField(
        required=False,
        label="Advertised read only",
        widget=_boolean_select(),
    )


class AIToolForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """Edit one AI Tool.

    Only the two columns a person owns are editable. The Sync AI Tools Job writes the name, the
    description, the schema, and the fingerprint from what the code declared. The next sync would
    overwrite an edit to any of them.
    """

    class Meta:
        """Meta attributes."""

        model = models.AITool
        fields = ["enabled", "writable"]  # pylint: disable=nb-use-fields-all


class AIToolBulkEditForm(NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """Bulk editing AI Tools, which is how a reviewed batch is turned on."""

    pk = forms.ModelMultipleChoiceField(queryset=models.AITool.objects.all(), widget=forms.MultipleHiddenInput)
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())
    writable = forms.NullBooleanField(required=False, widget=_boolean_select())

    class Meta:
        """Meta attributes."""

        nullable_fields = []


class AIToolFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filtering AI Tools."""

    model = models.AITool
    field_order = ["q", "name", "kind", "git_repository", "enabled", "writable", "advertised_read_only"]

    q = forms.CharField(required=False, label="Search", help_text="Search within name, description, or module.")
    name = forms.CharField(required=False, max_length=CHARFIELD_MAX_LENGTH)
    kind = forms.MultipleChoiceField(choices=AIToolKindChoices, required=False, widget=StaticSelect2Multiple)
    git_repository = DynamicModelMultipleChoiceField(
        queryset=GitRepository.objects.all(),
        required=False,
        label="Git Repository",
    )
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())
    writable = forms.NullBooleanField(required=False, widget=_boolean_select())
    advertised_read_only = forms.NullBooleanField(
        required=False, label="Advertised read-only", widget=_boolean_select()
    )


class AIAgentForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """Editing one AI Agent."""

    model = DynamicModelChoiceField(
        queryset=models.AIModel.objects.all(),
        label="AI Model",
        query_params={"kind": AIModelKindChoices.CHAT},
        help_text="The chat model this agent runs on.",
    )
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False)

    class Meta:
        """Meta attributes."""

        model = models.AIAgent
        fields = [*AI_AGENT_FIELDS, "system_prompt", "tags"]  # pylint: disable=nb-use-fields-all


class AIAgentBulkEditForm(TagsBulkEditFormMixin, NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """Bulk editing AI Agents."""

    pk = forms.ModelMultipleChoiceField(queryset=models.AIAgent.objects.all(), widget=forms.MultipleHiddenInput)
    description = forms.CharField(required=False, max_length=CHARFIELD_MAX_LENGTH)
    model = DynamicModelChoiceField(
        queryset=models.AIModel.objects.all(),
        required=False,
        label="AI Model",
        query_params={"kind": AIModelKindChoices.CHAT},
    )
    pattern = forms.ChoiceField(choices=add_blank_choice(AIAgentPatternChoices), required=False, widget=StaticSelect2)
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())
    max_iterations = forms.IntegerField(required=False, min_value=1, label="Max iterations")
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False)

    class Meta:
        """Meta attributes."""

        nullable_fields = ["description", "tenant", "temperature", "num_predict"]


class AIAgentFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filter form for AI Agents.

    `AIAgent.model` collides with the `model` attribute that a filter form uses to name its
    content type, and the Django form metaclass takes a declared field off the class. So
    `__init__` adds the field for that foreign key instead. That leaves the class attribute
    intact and keeps one name, `model`, across the model, the filterset, the API, and the query
    string.
    """

    model = models.AIAgent
    field_order = ["q", "name", "model", "pattern", "enabled", "tenant"]

    q = forms.CharField(required=False, label="Search", help_text="Search within name or description.")
    name = forms.CharField(required=False, max_length=CHARFIELD_MAX_LENGTH)
    pattern = forms.MultipleChoiceField(choices=AIAgentPatternChoices, required=False, widget=StaticSelect2Multiple)
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())
    tenant = DynamicModelMultipleChoiceField(queryset=Tenant.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        """Add the AI Model field, which cannot be declared on the class. See the class docstring."""
        super().__init__(*args, **kwargs)
        self.fields["model"] = DynamicModelMultipleChoiceField(
            queryset=models.AIModel.objects.all(),
            required=False,
            label="AI Model",
        )
        self.order_fields(self.field_order)


class AIAgentToolForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """Bind one tool to one agent.

    The two override fields are the point. A tool's name and its description decide whether the
    model calls it, and a pair that reads badly fails in silence.
    """

    agent = DynamicModelChoiceField(queryset=models.AIAgent.objects.all(), label="AI Agent")
    mcp_tool = DynamicModelChoiceField(queryset=models.MCPTool.objects.all(), required=False, label="MCP Tool")
    ai_tool = DynamicModelChoiceField(queryset=models.AITool.objects.all(), required=False, label="AI Tool")

    class Meta:
        """Meta attributes."""

        model = models.AIAgentTool
        fields = list(AI_AGENT_TOOL_FIELDS)  # pylint: disable=nb-use-fields-all


class AIAgentToolBulkEditForm(NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """Bulk editing tool bindings, which in practice means reordering them."""

    pk = forms.ModelMultipleChoiceField(queryset=models.AIAgentTool.objects.all(), widget=forms.MultipleHiddenInput)
    weight = forms.IntegerField(required=False, min_value=0)

    class Meta:
        """Meta attributes."""

        nullable_fields = ["name_override", "description_override"]


class AIAgentToolFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filtering tool bindings."""

    model = models.AIAgentTool
    field_order = ["q", "agent", "mcp_tool", "ai_tool"]

    q = forms.CharField(required=False, label="Search", help_text="Search within the agent's or the tool's name.")
    agent = DynamicModelMultipleChoiceField(queryset=models.AIAgent.objects.all(), required=False, label="AI Agent")
    mcp_tool = DynamicModelMultipleChoiceField(queryset=models.MCPTool.objects.all(), required=False, label="MCP Tool")
    ai_tool = DynamicModelMultipleChoiceField(queryset=models.AITool.objects.all(), required=False, label="AI Tool")


class AIAgentSubagentForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """Binding one specialist to one supervisor."""

    parent = DynamicModelChoiceField(queryset=models.AIAgent.objects.all(), label="Supervisor")
    subagent = DynamicModelChoiceField(queryset=models.AIAgent.objects.all(), label="Specialist")

    class Meta:
        """Meta attributes."""

        model = models.AIAgentSubagent
        fields = list(AI_AGENT_SUBAGENT_FIELDS)  # pylint: disable=nb-use-fields-all


class AIAgentSubagentBulkEditForm(NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """Bulk editing subagent bindings."""

    pk = forms.ModelMultipleChoiceField(queryset=models.AIAgentSubagent.objects.all(), widget=forms.MultipleHiddenInput)
    input_mode = forms.ChoiceField(
        choices=add_blank_choice(SubagentInputModeChoices),
        required=False,
        widget=StaticSelect2,
        label="Input mode",
    )
    weight = forms.IntegerField(required=False, min_value=0)

    class Meta:
        """Meta attributes."""

        nullable_fields = ["tool_name", "tool_description"]


class AIAgentSubagentFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filtering subagent bindings."""

    model = models.AIAgentSubagent
    field_order = ["q", "parent", "subagent", "input_mode"]

    q = forms.CharField(required=False, label="Search", help_text="Search within either agent's name.")
    parent = DynamicModelMultipleChoiceField(queryset=models.AIAgent.objects.all(), required=False, label="Supervisor")
    subagent = DynamicModelMultipleChoiceField(
        queryset=models.AIAgent.objects.all(), required=False, label="Specialist"
    )
    input_mode = forms.MultipleChoiceField(
        choices=SubagentInputModeChoices, required=False, widget=StaticSelect2Multiple, label="Input mode"
    )


class AISkillForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """Editing one AI Skill."""

    class Meta:
        """Meta attributes."""

        model = models.AISkill
        fields = list(AI_SKILL_FIELDS)  # pylint: disable=nb-use-fields-all


class AISkillBulkEditForm(NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """Bulk editing AI Skills."""

    pk = forms.ModelMultipleChoiceField(queryset=models.AISkill.objects.all(), widget=forms.MultipleHiddenInput)
    description = forms.CharField(required=False, max_length=CHARFIELD_MAX_LENGTH)
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())

    class Meta:
        """Meta attributes."""

        nullable_fields = ["description"]


class AISkillFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filtering AI Skills."""

    model = models.AISkill
    field_order = ["q", "name", "enabled"]

    q = forms.CharField(required=False, label="Search", help_text="Search within name or description.")
    name = forms.CharField(required=False, max_length=CHARFIELD_MAX_LENGTH)
    enabled = forms.NullBooleanField(required=False, widget=_boolean_select())


class AIAgentSkillForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """Binding one skill to one agent."""

    agent = DynamicModelChoiceField(queryset=models.AIAgent.objects.all(), label="AI Agent")
    skill = DynamicModelChoiceField(queryset=models.AISkill.objects.all(), label="AI Skill")

    class Meta:
        """Meta attributes."""

        model = models.AIAgentSkill
        fields = list(AI_AGENT_SKILL_FIELDS)  # pylint: disable=nb-use-fields-all


class AIAgentSkillBulkEditForm(NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """Bulk editing skill bindings."""

    pk = forms.ModelMultipleChoiceField(queryset=models.AIAgentSkill.objects.all(), widget=forms.MultipleHiddenInput)
    weight = forms.IntegerField(required=False, min_value=0)

    class Meta:
        """Meta attributes."""

        nullable_fields = []


class AIAgentSkillFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filtering skill bindings."""

    model = models.AIAgentSkill
    field_order = ["q", "agent", "skill"]

    q = forms.CharField(required=False, label="Search", help_text="Search within the agent's or the skill's name.")
    agent = DynamicModelMultipleChoiceField(queryset=models.AIAgent.objects.all(), required=False, label="AI Agent")
    skill = DynamicModelMultipleChoiceField(queryset=models.AISkill.objects.all(), required=False, label="AI Skill")


class AIAgentThreadFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filter form for AI Agent Threads.

    There is no edit form and no bulk edit form. Whatever ran the agent writes the thread, and a
    delete is the only thing anybody does to one afterwards.
    """

    model = models.AIAgentThread
    field_order = ["q", "agent", "status"]

    q = forms.CharField(required=False, label="Search", help_text="Search within the agent's name or the status.")
    agent = DynamicModelMultipleChoiceField(queryset=models.AIAgent.objects.all(), required=False, label="AI Agent")
    status = forms.MultipleChoiceField(choices=AIAgentThreadStatusChoices, required=False, widget=StaticSelect2Multiple)
