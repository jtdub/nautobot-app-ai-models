"""Tables for nautobot_ai_models."""

import django_tables2 as tables
from nautobot.apps.tables import BaseTable, BooleanColumn, ButtonsColumn, LinkedCountColumn, ToggleColumn

from nautobot_ai_models import models


class ProviderTable(BaseTable):
    # pylint: disable=R0903
    """Table for the AI Provider list view."""

    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    external_integration = tables.Column(linkify=True)
    openai_compatible = BooleanColumn(verbose_name="OpenAI-compatible")
    ai_model_count = LinkedCountColumn(
        viewname="plugins:nautobot_ai_models:aimodel_list",
        url_params={"provider": "name"},
        verbose_name="AI Models",
    )
    actions = ButtonsColumn(
        models.Provider,
        pk_field="pk",
    )

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.Provider
        fields = (
            "pk",
            "name",
            "description",
            "external_integration",
            "openai_compatible",
            "num_predict",
            "temperature",
            "ai_model_count",
            "actions",
        )
        default_columns = (
            "pk",
            "name",
            "description",
            "external_integration",
            "openai_compatible",
            "ai_model_count",
            "actions",
        )


class AIModelTable(BaseTable):
    # pylint: disable=R0903
    """Table for the AI Model list view."""

    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    provider = tables.Column(linkify=True, verbose_name="AI Provider")
    enabled = BooleanColumn()
    actions = ButtonsColumn(
        models.AIModel,
        pk_field="pk",
    )

    class Meta(BaseTable.Meta):
        """Meta attributes."""

        model = models.AIModel
        fields = (
            "pk",
            "name",
            "provider",
            "description",
            "enabled",
            "num_predict",
            "temperature",
            "actions",
        )
        default_columns = (
            "pk",
            "name",
            "provider",
            "description",
            "enabled",
            "actions",
        )
