"""Models for AI Models."""

# Django imports
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# Nautobot imports
from nautobot.apps.constants import CHARFIELD_MAX_LENGTH
from nautobot.apps.models import OrganizationalModel, extras_features

from nautobot_ai_models.constants import (
    MAX_TEMPERATURE,
    MIN_NUM_PREDICT,
    MIN_TEMPERATURE,
    TEMPERATURE_DECIMAL_PLACES,
    TEMPERATURE_MAX_DIGITS,
)


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class Provider(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """A remote LLM provider endpoint.

    A Provider records that an endpoint exists and how to reach it. It never stores a URL, a header,
    a TLS setting, or a credential of its own. The related Nautobot ExternalIntegration owns all of
    those. This app performs no inference; it only catalogs what is available.
    """

    # This app catalogs providers. It does not group them, so opt out of Dynamic Groups.
    is_dynamic_group_associable_model = False

    name = models.CharField(max_length=CHARFIELD_MAX_LENGTH, unique=True)
    description = models.CharField(max_length=CHARFIELD_MAX_LENGTH, blank=True)
    external_integration = models.ForeignKey(
        to="extras.ExternalIntegration",
        on_delete=models.PROTECT,
        related_name="ai_model_providers",
        verbose_name="External Integration",
        help_text="Supplies the remote URL, headers, TLS settings, timeout, and credentials.",
    )
    openai_compatible = models.BooleanField(
        default=True,
        verbose_name="OpenAI-compatible",
        help_text="The endpoint serves the OpenAI API shape, including GET /v1/models.",
    )
    num_predict = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(MIN_NUM_PREDICT)],
        verbose_name="Default num_predict",
        help_text="Default maximum number of tokens to generate. -1 means unlimited.",
    )
    temperature = models.DecimalField(
        max_digits=TEMPERATURE_MAX_DIGITS,
        decimal_places=TEMPERATURE_DECIMAL_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(MIN_TEMPERATURE), MaxValueValidator(MAX_TEMPERATURE)],
        verbose_name="Default temperature",
        help_text="Default sampling temperature, between 0 and 2.",
    )

    class Meta:
        """Meta class."""

        ordering = ["name"]

        # Nautobot core already defines circuits.Provider. Keep the UI labels distinct.
        verbose_name = "AI Provider"
        verbose_name_plural = "AI Providers"

    def __str__(self):
        """Stringify instance."""
        return self.name


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class AIModel(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """A single model offered by a Provider.

    The num_predict and temperature fields are optional overrides. An empty value inherits the
    default from the parent Provider. Read the resolved values through resolved_num_predict and
    resolved_temperature.
    """

    # This app catalogs models. It does not group them, so opt out of Dynamic Groups.
    is_dynamic_group_associable_model = False

    provider = models.ForeignKey(
        to="nautobot_ai_models.Provider",
        on_delete=models.CASCADE,
        related_name="ai_models",
        verbose_name="AI Provider",
    )
    name = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        help_text="The model identifier the provider expects, for example gpt-4o-mini.",
    )
    description = models.CharField(max_length=CHARFIELD_MAX_LENGTH, blank=True)
    enabled = models.BooleanField(default=True, help_text="Consumers should ignore a disabled model.")
    num_predict = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(MIN_NUM_PREDICT)],
        verbose_name="num_predict",
        help_text="Overrides the provider default. Leave empty to inherit. -1 means unlimited.",
    )
    temperature = models.DecimalField(
        max_digits=TEMPERATURE_MAX_DIGITS,
        decimal_places=TEMPERATURE_DECIMAL_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(MIN_TEMPERATURE), MaxValueValidator(MAX_TEMPERATURE)],
        help_text="Overrides the provider default. Leave empty to inherit.",
    )

    class Meta:
        """Meta class."""

        ordering = ["provider", "name"]
        # Keep the foreign key last. Nautobot derives the natural key from the first uniqueness
        # constraint, and a trailing related field is the safe order.
        unique_together = [["name", "provider"]]
        verbose_name = "AI Model"
        verbose_name_plural = "AI Models"

    def __str__(self):
        """Stringify instance."""
        return f"{self.provider.name}: {self.name}"

    @property
    def resolved_num_predict(self):
        """Return this model's num_predict, or the provider default when unset."""
        # pylint: disable=no-member  # pylint-django cannot resolve the ForeignKey target here.
        return self.num_predict if self.num_predict is not None else self.provider.num_predict

    @property
    def resolved_temperature(self):
        """Return this model's temperature, or the provider default when unset."""
        # pylint: disable=no-member  # pylint-django cannot resolve the ForeignKey target here.
        return self.temperature if self.temperature is not None else self.provider.temperature
