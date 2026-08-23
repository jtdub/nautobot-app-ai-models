"""Model discovery against OpenAI-compatible provider endpoints.

This module performs no inference. It reads the provider's model catalog only.

The connection rules here match `services/mcp.py`, deliberately. Both halves of this app reach a
remote endpoint through an ExternalIntegration, and two answers to "does unticking Verify SSL win"
in one app is a trap for whoever reads the second one.
"""

import requests
from nautobot.apps.choices import SecretsGroupAccessTypeChoices, SecretsGroupSecretTypeChoices

from nautobot_ai_models.constants import DEFAULT_TIMEOUT_SECONDS, MODELS_ENDPOINT
from nautobot_ai_models.secrets import read_secret

#: How the credential is presented when the integration's own headers do not present it.
AUTHORIZATION_HEADER = "Authorization"


def build_models_url(remote_url):
    """Return the /v1/models URL for a provider base URL.

    The External Integration remote URL may or may not already end in /v1. Handle both.
    """
    base = remote_url.strip().rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return f"{base}{MODELS_ENDPOINT}"


def build_headers(provider):
    """Return the request headers for a provider, with a bearer token when one is defined.

    An operator who wrote their own authorization header on the integration meant it, so this
    defers to them rather than overwriting it.
    """
    integration = provider.external_integration
    headers = dict(integration.render_headers({"obj": provider}) or {})

    if any(key.lower() == AUTHORIZATION_HEADER.lower() for key in headers):
        return headers

    # Both access types, because one Secrets Group may serve an AI provider and an MCP server, and
    # an operator should not have to know which access type each half of this app reads.
    for access_type in (SecretsGroupAccessTypeChoices.TYPE_HTTP, SecretsGroupAccessTypeChoices.TYPE_GENERIC):
        for secret_type in (SecretsGroupSecretTypeChoices.TYPE_TOKEN, SecretsGroupSecretTypeChoices.TYPE_SECRET):
            token = read_secret(integration, secret_type, access_type=access_type)
            if token:
                headers[AUTHORIZATION_HEADER] = f"Bearer {token}"
                return headers

    return headers


def build_verify(integration):
    """Return the value an HTTP client's `verify` argument should take.

    Unticking *Verify SSL* wins over a CA path: an operator who has done both has said not to
    verify, and quietly verifying anyway is the surprise this rule exists to prevent.
    """
    if not integration.verify_ssl:
        return False
    return integration.ca_file_path or True


def build_timeout(integration):
    """Return the request timeout, falling back when the integration carries an unusable one.

    `ExternalIntegration.timeout` accepts 0, and a request with a timeout of 0 fails at once with
    an error that says nothing about why.
    """
    timeout = getattr(integration, "timeout", None)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        return DEFAULT_TIMEOUT_SECONDS
    return timeout


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
        timeout=build_timeout(integration),
        verify=build_verify(integration),
        # A redirect would replay the integration's headers, credential included, at whatever host
        # the endpoint names. This client has no way to strip them, so it does not follow one.
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
