"""Django API urlpatterns declaration for nautobot_ai_models app."""

from nautobot.apps.api import OrderedDefaultRouter

from nautobot_ai_models.api import views

router = OrderedDefaultRouter()
router.register("ai-providers", views.AIProviderViewSet)
router.register("ai-models", views.AIModelViewSet)
router.register("mcp-servers", views.MCPServerViewSet)
router.register("mcp-tools", views.MCPToolViewSet)

app_name = "nautobot_ai_models-api"
urlpatterns = router.urls
