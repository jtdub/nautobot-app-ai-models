"""Views for nautobot_ai_models."""

from nautobot.apps.ui import ObjectDetailContent, ObjectFieldsPanel, ObjectsTablePanel, SectionChoices
from nautobot.apps.views import NautobotUIViewSet

from nautobot_ai_models import filters, forms, models, tables
from nautobot_ai_models.api import serializers


class ProviderUIViewSet(NautobotUIViewSet):
    """ViewSet for AI Provider views."""

    bulk_update_form_class = forms.ProviderBulkEditForm
    filterset_class = filters.ProviderFilterSet
    filterset_form_class = forms.ProviderFilterForm
    form_class = forms.ProviderForm
    lookup_field = "pk"
    queryset = models.Provider.objects.select_related("external_integration")
    serializer_class = serializers.ProviderSerializer
    table_class = tables.ProviderTable

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
                fields="__all__",
            ),
        ],
    )
