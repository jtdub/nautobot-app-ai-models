"""Reading credentials out of Nautobot's secrets machinery, in one place.

This app resolves a credential from an ExternalIntegration's secrets group at connection time and
never anywhere else. The retrieval idiom lives here once, so a change to how a secret is read - a
new exception type, a different access type - cannot land in one copy only.
"""

from django.core.exceptions import ObjectDoesNotExist
from nautobot.apps.choices import SecretsGroupAccessTypeChoices
from nautobot.apps.exceptions import SecretError


def read_secret(integration, secret_type, access_type=SecretsGroupAccessTypeChoices.TYPE_GENERIC):
    """One secret off an integration's secrets group, or None when it does not carry one.

    "Not configured" and "configured but unresolvable" both come back as None on purpose: the
    caller treats a missing secret as "connect without it", and the server the credential was for
    will refuse the connection itself, which is the visible symptom.
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
