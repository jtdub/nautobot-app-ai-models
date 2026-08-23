"""Filtering for nautobot_ai_models."""

from nautobot.apps.filters import (
    NameSearchFilterSet,
    NaturalKeyOrPKMultipleChoiceFilter,
    NautobotFilterSet,
)
from nautobot.extras.models import ExternalIntegration

from nautobot_ai_models import models


class ProviderFilterSet(NameSearchFilterSet, NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for Provider."""

    external_integration = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=ExternalIntegration.objects.all(),
        to_field_name="name",
        label="External Integration (name or ID)",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.Provider
        fields = "__all__"


class AIModelFilterSet(NameSearchFilterSet, NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for AIModel."""

    provider = NaturalKeyOrPKMultipleChoiceFilter(
        queryset=models.Provider.objects.all(),
        to_field_name="name",
        label="AI Provider (name or ID)",
    )

    class Meta:
        """Meta attributes for filter."""

        model = models.AIModel
        fields = "__all__"
