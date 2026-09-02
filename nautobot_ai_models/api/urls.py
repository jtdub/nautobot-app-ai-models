"""Django API urlpatterns declaration for nautobot_ai_models app."""

from nautobot.apps.api import OrderedDefaultRouter

from nautobot_ai_models.api import views

router = OrderedDefaultRouter()
router.register("ai-providers", views.AIProviderViewSet)
router.register("ai-models", views.AIModelViewSet)
router.register("mcp-servers", views.MCPServerViewSet)
router.register("mcp-tools", views.MCPToolViewSet)
router.register("ai-tools", views.AIToolViewSet)
router.register("ai-agents", views.AIAgentViewSet)
router.register("ai-agent-tools", views.AIAgentToolViewSet)
router.register("ai-agent-subagents", views.AIAgentSubagentViewSet)
router.register("ai-skills", views.AISkillViewSet)
router.register("ai-agent-skills", views.AIAgentSkillViewSet)
router.register("ai-agent-threads", views.AIAgentThreadViewSet)

app_name = "nautobot_ai_models-api"
urlpatterns = router.urls
