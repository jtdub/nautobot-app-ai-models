"""Create fixtures for tests."""

from nautobot.extras.models import ExternalIntegration

from nautobot_ai_models.models import AIModel, Provider

# Three distinct integrations. The generic filter tests need at least three unique values per field.
INTEGRATIONS = (
    ("Test Integration One", "https://llm.example.com"),
    ("Test Integration Two", "https://llm2.example.com"),
    ("Test Integration Three", "https://llm3.example.com"),
)

PROVIDERS = (
    ("Test One", "First provider"),
    ("Test Two", "Second provider"),
    ("Test Three", "Third provider"),
)

AI_MODELS = (
    ("Test One", "Test One", "First model"),
    ("Test Two", "Test Two", "Second model"),
    ("Test Three", "Test Three", "Third model"),
)


def create_external_integration(name=INTEGRATIONS[0][0], remote_url=INTEGRATIONS[0][1]):
    """Fixture to create a single ExternalIntegration for a Provider to reference."""
    integration, _ = ExternalIntegration.objects.get_or_create(
        name=name,
        defaults={"remote_url": remote_url, "verify_ssl": True, "timeout": 30},
    )
    return integration


def create_provider():
    """Fixture to create the necessary number of Provider objects for tests."""
    for (name, description), (integration_name, remote_url) in zip(PROVIDERS, INTEGRATIONS):
        Provider.objects.create(
            name=name,
            description=description,
            external_integration=create_external_integration(integration_name, remote_url),
        )


def create_aimodel():
    """Fixture to create the necessary number of AIModel objects for tests."""
    create_provider()
    for provider_name, name, description in AI_MODELS:
        AIModel.objects.create(
            provider=Provider.objects.get(name=provider_name),
            name=name,
            description=description,
        )
