"""Model discovery against OpenAI-compatible provider endpoints.

This module performs no inference. It reads the provider's model catalog only.
"""

import requests
from nautobot.apps.choices import SecretsGroupAccessTypeChoices, SecretsGroupSecretTypeChoices

from nautobot_ai_models.constants import MODELS_ENDPOINT


def build_models_url(remote_url):
    """Return the /v1/models URL for a provider base URL.

    The External Integration remote URL may or may not already end in /v1. Handle both.
    """
    base = remote_url.strip().rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return f"{base}{MODELS_ENDPOINT}"


def build_headers(provider):
    """Return the request headers for a provider, including the bearer token when one is defined.

    Raises whatever the secrets backend raises. The caller decides how to report a failure.
    """
    integration = provider.external_integration
    context = {"obj": provider}
    headers = dict(integration.render_headers(context) or {})

    if integration.secrets_group is not None:
        token = integration.secrets_group.get_secret_value(
            SecretsGroupAccessTypeChoices.TYPE_HTTP,
            SecretsGroupSecretTypeChoices.TYPE_TOKEN,
            obj=provider,
        )
        headers["Authorization"] = f"Bearer {token}"

    return headers


def fetch_models(provider):
    """Return a list of dicts with "name" and "description" keys, read from the provider.

    Honors the External Integration timeout, SSL verification, and CA file path. Returns the parsed
    catalog only. It never returns a header or a token.
    """
    integration = provider.external_integration
    url = build_models_url(integration.render_remote_url({"obj": provider}))

    response = requests.get(
        url,
        headers=build_headers(provider),
        timeout=integration.timeout,
        verify=integration.ca_file_path or integration.verify_ssl,
    )
    response.raise_for_status()

    discovered = []
    for entry in response.json().get("data", []):
        name = entry.get("id")
        if not name:
            continue
        owner = entry.get("owned_by") or ""
        discovered.append({"name": name, "description": f"Owned by {owner}" if owner else ""})
    return discovered
