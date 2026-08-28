"""App declaration for nautobot_ai_models."""

# Metadata is inherited from Nautobot. If not including Nautobot in the environment, this should be added
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
    # Both default to today's behaviour, so an existing deployment sees no change. See
    # nautobot_ai_models/app_settings.py for what each one does.
    default_settings = {
        "new_tools_enabled": True,
        "disable_on_definition_change": False,
    }
    docs_view_name = "plugins:nautobot_ai_models:docs"
    searchable_models = ["aiprovider", "aimodel", "mcpserver", "mcptool"]

    # Read through getattr() by nautobot.core.utils.config.get_nautobot_edition(), which
    # arrived in Nautobot 3.2. On the 3.1 floor this attribute is simply unread, which is
    # harmless. NautobotEditionChoices lives in nautobot.core.choices and is not part of the
    # public nautobot.apps API, so the value is a literal. The set is "community",
    # "professional", "enterprise", and "cloud".
    nautobot_edition = "community"


config = AIModelsConfig  # pylint:disable=invalid-name
