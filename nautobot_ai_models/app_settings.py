"""Read this app's PLUGINS_CONFIG settings.

This module is not named ``config``. Nautobot finds an app's ``NautobotAppConfig`` through the
``config`` attribute of the package, and a ``config`` submodule shadows it.
"""

from nautobot.apps.config import get_app_settings_or_config

APP_NAME = "nautobot_ai_models"

NEW_TOOLS_ENABLED = "new_tools_enabled"

DISABLE_ON_DEFINITION_CHANGE = "disable_on_definition_change"

CHECKPOINT_RETENTION_DAYS = "checkpoint_retention_days"


def app_setting(name):
    """Return one of this app's settings.

    Args:
        name: A key declared in ``AIModelsConfig.default_settings``.

    Returns:
        The configured value, or the shipped default.
    """
    return get_app_settings_or_config(APP_NAME, name)
