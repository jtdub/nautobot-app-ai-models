"""Forms for nautobot_ai_models.

Note on the External Integration field of `AIProviderForm` and `MCPServerForm`. Each is a
`DynamicModelChoiceField` on a `NautobotModelForm`, which is all that is needed to get the "+"
button that creates an ExternalIntegration in a modal over the page, without losing what has
already been typed. Nautobot turns that on for every such field through
`EmbeddedActionsFormMixin`. Do not add `external_integration` to a `Meta.exclude_embedded_create`
list and do not pass `embedded_create=False` on the field: either one takes the button away.
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
from nautobot.extras.models import ExternalIntegration
from nautobot.tenancy.models import Tenant

from nautobot_ai_models import models
from nautobot_ai_models.choices import AIModelKindChoices, AIProviderTypeChoices, MCPTransportChoices
from nautobot_ai_models.constants import (
    MCP_SERVER_OPERATOR_FIELDS,
    MCP_TOOL_DEFINITION_FIELDS,
    MCP_TOOL_SCHEMA_FIELDS,
)


def _boolean_select():
    """A three-state Yes/No/any widget, built fresh so no two fields share one instance.

    `BulkEditNullBooleanSelect` is what Nautobot uses for exactly this, on a bulk-edit form and
    on a filter form alike. Built per field rather than shared, because a Django widget
    instance belongs to one field.
    """
    return BulkEditNullBooleanSelect()


class AIProviderForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """AIProvider creation/edit form.

    NautobotModelForm inherits EmbeddedActionsFormMixin, so the External Integration field gets the
    built-in "+" button. That button opens a modal, creates the External Integration in place, and
    selects it here. See Nautobot's Embedded Actions feature, added in 3.1.0.
    """

    external_integration = DynamicModelChoiceField(
        queryset=ExternalIntegration.objects.all(),
        label="External Integration",
        help_text="Supplies the remote URL, headers, TLS settings, timeout, and credentials.",
    )
    # The column is blank=True only so the migration can leave a legacy row unanswered. Required
    # here so an operator is stopped at the widget rather than by AIProvider.clean() after posting.
    provider_type = forms.ChoiceField(
        choices=AIProviderTypeChoices,
        label="Provider type",
        widget=StaticSelect2,
        help_text="Which API dialect this endpoint speaks. A consuming app reads this to address it.",
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
    # `add_blank_choice` is load-bearing here, as it is on MCPServerBulkEditForm.transport below.
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
    # Blank choice for the same reason as every other bulk-edit select on this page.
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
    # `add_blank_choice` is not cosmetic. Nautobot's bulk-update mixin applies any value that
    # is not None or empty, so a select with no blank option posts its first choice every time
    # and quietly rewrites `transport` on every selected server.
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
    """MCPTool creation/edit form.

    Editable by hand as well as by discovery: a stdio server cannot be discovered from Nautobot, so
    its tools have to be entered.
    """

    mcp_server = DynamicModelChoiceField(queryset=models.MCPServer.objects.all(), label="MCP Server")

    class Meta:
        """Meta attributes."""

        model = models.MCPTool
        fields = [*MCP_TOOL_DEFINITION_FIELDS, *MCP_TOOL_SCHEMA_FIELDS]  # pylint: disable=nb-use-fields-all


class MCPToolBulkEditForm(NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """MCPTool bulk edit form.

    This is how an operator reviews a newly discovered server: select the tools that only read,
    clear `writable` on all of them at once, and enable them.
    """

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
