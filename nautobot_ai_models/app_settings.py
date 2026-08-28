"""Reading this app's PLUGINS_CONFIG settings.

One reader, so that no other module has to know how a Nautobot app setting is looked up, and so
that the two policy settings below are named in exactly one place.

Named `app_settings` rather than `config`. Nautobot finds a app's `NautobotAppConfig` by reading
the `config` attribute off the package, and a submodule called `config.py` shadows it the moment
anything imports the submodule.

Both settings are registry policy rather than call policy, which is why they live here rather than
in a consuming app. A consuming app can refuse to call a tool, but it cannot stop a second
consuming app from calling the same one.
"""

from nautobot.apps.config import get_app_settings_or_config

#: This app's key in PLUGINS_CONFIG.
APP_NAME = "nautobot_ai_models"

#: Whether a newly discovered MCP tool arrives switched on. Default True, which is today's
#: behaviour. Set it to False and a tool nobody has read arrives off, and a person turns it on.
NEW_TOOLS_ENABLED = "new_tools_enabled"

#: Whether discovery clears `enabled` on a tool whose definition moved under a review somebody
#: already did. Default False, which is today's behaviour: the change is reported and the tool
#: stays on offer until somebody reads the log.
DISABLE_ON_DEFINITION_CHANGE = "disable_on_definition_change"


def app_setting(name):
    """Return one of this app's settings from PLUGINS_CONFIG.

    Every name here is declared in `AIModelsConfig.default_settings`, which Nautobot merges into
    PLUGINS_CONFIG at start-up, so the key is always present and the lookup never falls through.
    """
    return get_app_settings_or_config(APP_NAME, name)
