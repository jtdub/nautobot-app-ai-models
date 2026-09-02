"""Model discovery against OpenAI-compatible provider endpoints.

This module reads the provider's model catalog only. The connection rules match ``services/mcp.py``.
"""

import requests
from nautobot.apps.choices import SecretsGroupAccessTypeChoices, SecretsGroupSecretTypeChoices

from nautobot_ai_models.constants import MODELS_ENDPOINT
from nautobot_ai_models.integrations import integration_timeout, integration_verify
from nautobot_ai_models.secrets import read_secret

AUTHORIZATION_HEADER = "Authorization"


def build_models_url(remote_url):
    """Return the ``/v1/models`` URL for a provider base URL.

    Args:
        remote_url: The integration's remote URL, with or without a trailing ``/v1``.

    Returns:
        str: The catalog URL.
    """
    base = remote_url.strip().rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return f"{base}{MODELS_ENDPOINT}"


def build_headers(provider):
    """Return the request headers for a provider.

    An authorization header written on the integration by hand is left alone.

    Args:
        provider: The AIProvider to read headers and credentials for.

    Returns:
        dict: Headers, with a bearer token added when a secret supplies one.
    """
    integration = provider.external_integration
    headers = dict(integration.render_headers({"obj": provider}) or {})

    if any(key.lower() == AUTHORIZATION_HEADER.lower() for key in headers):
        return headers

    for access_type in (SecretsGroupAccessTypeChoices.TYPE_HTTP, SecretsGroupAccessTypeChoices.TYPE_GENERIC):
        for secret_type in (SecretsGroupSecretTypeChoices.TYPE_TOKEN, SecretsGroupSecretTypeChoices.TYPE_SECRET):
            token = read_secret(integration, secret_type, access_type=access_type)
            if token:
                headers[AUTHORIZATION_HEADER] = f"Bearer {token}"
                return headers

    return headers


def build_verify(integration):
    """Return the value for an HTTP client's ``verify`` argument.

    A cleared *Verify SSL* wins over a CA file path.

    Args:
        integration: The ExternalIntegration to read.

    Returns:
        bool | str: False, a CA file path, or True.
    """
    return integration_verify(integration)


def build_timeout(integration):
    """Return the request timeout.

    Args:
        integration: The ExternalIntegration to read.

    Returns:
        int | float: The integration's timeout, or ``DEFAULT_TIMEOUT_SECONDS`` when it carries one
            a request cannot use.
    """
    return integration_timeout(integration)


def fetch_models(provider):
    """Read the model catalog from a provider.

    This function honors the integration's timeout, SSL verification, and CA file path. It never
    returns a header or a token.

    Args:
        provider: The AIProvider to query.

    Returns:
        list[dict]: One mapping per model, with ``name`` and ``description`` keys.

    Raises:
        requests.HTTPError: The endpoint answered with an error status.
    """
    integration = provider.external_integration
    url = build_models_url(integration.render_remote_url({"obj": provider}))

    response = requests.get(
        url,
        headers=build_headers(provider),
        timeout=build_timeout(integration),
        verify=build_verify(integration),
        allow_redirects=False,
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
