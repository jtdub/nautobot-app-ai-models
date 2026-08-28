"""Reading credentials out of Nautobot's secrets machinery, in one place."""

from django.core.exceptions import ObjectDoesNotExist
from nautobot.apps.choices import SecretsGroupAccessTypeChoices
from nautobot.apps.exceptions import SecretError


def read_secret(integration, secret_type, access_type=SecretsGroupAccessTypeChoices.TYPE_GENERIC):
    """Read one secret off an integration's secrets group.

    Args:
        integration: The ExternalIntegration to read.
        secret_type: The secret type to look for.
        access_type: The access type to look under.

    Returns:
        str | None: The secret value, or None when the group is missing or the secret cannot be
            resolved. The caller connects without it and lets the far end refuse.
    """
    if integration.secrets_group is None:
        return None
    try:
        return integration.secrets_group.get_secret_value(
            access_type=access_type,
            secret_type=secret_type,
            obj=integration,
        )
    except (SecretError, ObjectDoesNotExist):
        return None
