"""Django API urlpatterns declaration for nautobot_ai_models app."""

from nautobot.apps.api import OrderedDefaultRouter

from nautobot_ai_models.api import views

router = OrderedDefaultRouter()
router.register("providers", views.ProviderViewSet)
router.register("ai-models", views.AIModelViewSet)

app_name = "nautobot_ai_models-api"
urlpatterns = router.urls
