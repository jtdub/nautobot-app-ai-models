"""API serializers for nautobot_ai_models."""

from nautobot.apps.api import NautobotModelSerializer

from nautobot_ai_models import models


class ProviderSerializer(NautobotModelSerializer):  # pylint: disable=too-many-ancestors
    """AI Provider Serializer."""

    class Meta:
        """Meta attributes."""

        model = models.Provider
        fields = "__all__"


class AIModelSerializer(NautobotModelSerializer):  # pylint: disable=too-many-ancestors
    """AI Model Serializer."""

    class Meta:
        """Meta attributes."""

        model = models.AIModel
        fields = "__all__"
