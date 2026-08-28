"""Django urlpatterns declaration for nautobot_ai_models app."""

from django.templatetags.static import static
from django.urls import path
from django.views.generic import RedirectView
from nautobot.apps.urls import NautobotUIViewSetRouter

from nautobot_ai_models import views

app_name = "nautobot_ai_models"
router = NautobotUIViewSetRouter()

router.register("ai-providers", views.AIProviderUIViewSet)
router.register("ai-models", views.AIModelUIViewSet)
router.register("mcp-servers", views.MCPServerUIViewSet)
router.register("mcp-tools", views.MCPToolUIViewSet)


urlpatterns = [
    path("docs/", RedirectView.as_view(url=static("nautobot_ai_models/docs/index.html")), name="docs"),
]

urlpatterns += router.urls
