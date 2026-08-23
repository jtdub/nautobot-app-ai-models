"""API views for nautobot_ai_models."""

from nautobot.apps.api import NautobotModelViewSet

from nautobot_ai_models import filters, models
from nautobot_ai_models.api import serializers


class ProviderViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """AI Provider viewset."""

    queryset = models.Provider.objects.select_related("external_integration")
    serializer_class = serializers.ProviderSerializer
    filterset_class = filters.ProviderFilterSet


class AIModelViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """AI Model viewset."""

    queryset = models.AIModel.objects.select_related("provider")
    serializer_class = serializers.AIModelSerializer
    filterset_class = filters.AIModelFilterSet
