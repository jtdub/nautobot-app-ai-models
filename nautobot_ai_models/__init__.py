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
    max_version = "3.9.99"
    required_settings = []
    default_settings = {}
    docs_view_name = "plugins:nautobot_ai_models:docs"
    searchable_models = ["aiprovider", "aimodel", "mcpserver", "mcptool"]

    # Nautobot reads this through getattr() in nautobot.core.utils.config.get_nautobot_edition().
    # NautobotEditionChoices lives in nautobot.core.choices, which is not part of the public
    # nautobot.apps API, so declare the value as a literal. Valid values are "community",
    # "professional", "enterprise", and "cloud".
    nautobot_edition = "community"


config = AIModelsConfig  # pylint:disable=invalid-name
