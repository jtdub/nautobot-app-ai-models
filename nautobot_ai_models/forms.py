"""Forms for nautobot_ai_models."""

from django import forms
from nautobot.apps.constants import CHARFIELD_MAX_LENGTH
from nautobot.apps.forms import (
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    NautobotBulkEditForm,
    NautobotFilterForm,
    NautobotModelForm,
)
from nautobot.extras.models import ExternalIntegration

from nautobot_ai_models import models


class ProviderForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """Provider creation/edit form.

    NautobotModelForm inherits EmbeddedActionsFormMixin, so the External Integration field gets the
    built-in "+" button. That button opens a modal, creates the External Integration in place, and
    selects it here. See Nautobot's Embedded Actions feature, added in 3.1.0.
    """

    external_integration = DynamicModelChoiceField(
        queryset=ExternalIntegration.objects.all(),
        label="External Integration",
        help_text="Supplies the remote URL, headers, TLS settings, timeout, and credentials.",
    )

    class Meta:
        """Meta attributes."""

        model = models.Provider
        fields = "__all__"


class ProviderBulkEditForm(NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """Provider bulk edit form."""

    pk = forms.ModelMultipleChoiceField(queryset=models.Provider.objects.all(), widget=forms.MultipleHiddenInput)
    description = forms.CharField(required=False, max_length=CHARFIELD_MAX_LENGTH)
    external_integration = DynamicModelChoiceField(
        queryset=ExternalIntegration.objects.all(),
        required=False,
        label="External Integration",
    )
    openai_compatible = forms.NullBooleanField(required=False, label="OpenAI-compatible")
    num_predict = forms.IntegerField(required=False, label="Default num_predict")
    temperature = forms.DecimalField(required=False, label="Default temperature")

    class Meta:
        """Meta attributes."""

        nullable_fields = [
            "description",
            "num_predict",
            "temperature",
        ]


class ProviderFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filter form to filter searches."""

    model = models.Provider
    field_order = ["q", "name", "external_integration", "openai_compatible"]

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
    openai_compatible = forms.NullBooleanField(required=False, label="OpenAI-compatible")


class AIModelForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """AIModel creation/edit form."""

    provider = DynamicModelChoiceField(
        queryset=models.Provider.objects.all(),
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
        queryset=models.Provider.objects.all(),
        required=False,
        label="AI Provider",
    )
    description = forms.CharField(required=False, max_length=CHARFIELD_MAX_LENGTH)
    enabled = forms.NullBooleanField(required=False)
    num_predict = forms.IntegerField(required=False)
    temperature = forms.DecimalField(required=False)

    class Meta:
        """Meta attributes."""

        nullable_fields = [
            "description",
            "num_predict",
            "temperature",
        ]


class AIModelFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filter form to filter searches."""

    model = models.AIModel
    field_order = ["q", "name", "provider", "enabled"]

    q = forms.CharField(
        required=False,
        label="Search",
        help_text="Search within Name.",
    )
    name = forms.CharField(required=False, label="Name")
    provider = DynamicModelMultipleChoiceField(
        queryset=models.Provider.objects.all(),
        required=False,
        label="AI Provider",
    )
    enabled = forms.NullBooleanField(required=False)
