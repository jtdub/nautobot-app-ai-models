"""Django urlpatterns declaration for nautobot_ai_models app."""

from django.templatetags.static import static
from django.urls import path
from django.views.generic import RedirectView
from nautobot.apps.urls import NautobotUIViewSetRouter

from nautobot_ai_models import views

app_name = "nautobot_ai_models"


class AIModelsUIViewSetRouter(NautobotUIViewSetRouter):
    """A router that lets a ViewSet refuse one of the actions it inherits.

    `NautobotUIViewSet` composes create and update from one mixin, so a ViewSet cannot drop the
    add view and keep the edit view. `AITool` needs exactly that: the Sync AI Tools Job writes
    the row, and a person edits the two flags on it afterwards.

    This router builds a route only for an action the ViewSet has. The list template reverses the
    add route before it draws the button, so a dropped route removes the URL and the button
    together.
    """

    def get_method_map(self, viewset, method_map):
        """Drop every action the ViewSet named in `unsupported_actions`.

        Args:
            viewset: The ViewSet class being routed.
            method_map: The HTTP-method-to-action mapping of one route.

        Returns:
            dict: The mapping, without the refused actions. A route left empty is not built.
        """
        mapping = super().get_method_map(viewset, method_map)
        refused = set(getattr(viewset, "unsupported_actions", ()))
        return {method: action for method, action in mapping.items() if action not in refused}


router = AIModelsUIViewSetRouter()

router.register("ai-providers", views.AIProviderUIViewSet)
router.register("ai-models", views.AIModelUIViewSet)
router.register("mcp-servers", views.MCPServerUIViewSet)
router.register("mcp-tools", views.MCPToolUIViewSet)
router.register("ai-tools", views.AIToolUIViewSet)
router.register("ai-agents", views.AIAgentUIViewSet)
router.register("ai-agent-tools", views.AIAgentToolUIViewSet)
router.register("ai-agent-subagents", views.AIAgentSubagentUIViewSet)
router.register("ai-skills", views.AISkillUIViewSet)
router.register("ai-agent-skills", views.AIAgentSkillUIViewSet)
router.register("ai-agent-threads", views.AIAgentThreadUIViewSet)


urlpatterns = [
    path("docs/", RedirectView.as_view(url=static("nautobot_ai_models/docs/index.html")), name="docs"),
]

urlpatterns += router.urls
