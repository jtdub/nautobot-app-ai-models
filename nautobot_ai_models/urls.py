"""Django urlpatterns declaration for nautobot_ai_models app."""

from django.templatetags.static import static
from django.urls import path
from django.views.generic import RedirectView
from nautobot.apps.urls import NautobotUIViewSetRouter

from nautobot_ai_models import views

app_name = "nautobot_ai_models"
router = NautobotUIViewSetRouter()

# The standard is for the route to be the hyphenated version of the model class name plural.
router.register("providers", views.ProviderUIViewSet)
router.register("ai-models", views.AIModelUIViewSet)


urlpatterns = [
    path("docs/", RedirectView.as_view(url=static("nautobot_ai_models/docs/index.html")), name="docs"),
]

urlpatterns += router.urls
