"""App declaration for nautobot_ai_models."""

from importlib import metadata

from nautobot.apps import NautobotAppConfig

__version__ = metadata.version(__name__)


class AIModelsConfig(NautobotAppConfig):
    """App configuration for the nautobot_ai_models app."""

    name = "nautobot_ai_models"
    verbose_name = "AI Models"
    version = __version__
    author = "James Williams"
    author_email = "james.williams@jtdub.com"
    description = "Nautobot app that catalogs LLM providers, LLM models, MCP servers, and MCP tools."
    base_url = "ai-models"
    min_version = "3.1.0"
    max_version = "3.99.99"
    required_settings = []
    default_settings = {
        "new_tools_enabled": True,
        "disable_on_definition_change": False,
    }
    docs_view_name = "plugins:nautobot_ai_models:docs"
    searchable_models = ["aiprovider", "aimodel", "mcpserver", "mcptool"]

    nautobot_edition = "community"


config = AIModelsConfig  # pylint:disable=invalid-name
