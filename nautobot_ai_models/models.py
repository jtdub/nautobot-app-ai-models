"""Registry models for LLM providers, LLM models, MCP servers, and MCP tools.

Every model keeps its endpoint, headers, TLS settings, and credentials in a Nautobot
ExternalIntegration. None of them calls anything.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from nautobot.apps.constants import CHARFIELD_MAX_LENGTH
from nautobot.apps.models import OrganizationalModel, PrimaryModel, extras_features

from nautobot_ai_models.choices import (
    ADDRESSED_PROVIDER_TYPES,
    AIModelKindChoices,
    AIProviderTypeChoices,
    MCPTransportChoices,
)
from nautobot_ai_models.constants import (
    ALLOWED_MODEL_PARAMETERS,
    COST_DECIMAL_PLACES,
    COST_MAX_DIGITS,
    MAX_TEMPERATURE,
    MIN_COST,
    MIN_NUM_PREDICT,
    MIN_TEMPERATURE,
    TEMPERATURE_DECIMAL_PLACES,
    TEMPERATURE_MAX_DIGITS,
)


def validate_remote_url(instance, message):
    """Check that the instance's External Integration carries a remote URL.

    Args:
        instance: A model with an ``external_integration`` foreign key.
        message: The error to raise against that field.

    Raises:
        ValidationError: The integration is set and carries no remote URL.
    """
    if instance.external_integration_id is not None and not instance.external_integration.remote_url:
        raise ValidationError({"external_integration": message})


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class AIProvider(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """A remote LLM provider endpoint.

    Records that an endpoint exists and how to reach it. The related ExternalIntegration owns the
    URL, the headers, the TLS settings, and the credentials.
    """

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
    provider_type = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        choices=AIProviderTypeChoices,
        default=AIProviderTypeChoices.OPENAI,
        blank=True,
        db_index=True,
        verbose_name="Provider type",
        help_text=(
            "Which API dialect this endpoint speaks. A consuming app reads this to decide how to "
            "address it. Separate from OpenAI-compatible, which only says whether models can be "
            "discovered here."
        ),
    )
    enabled = models.BooleanField(
        default=True,
        help_text=(
            "Whether this provider is in service. A disabled provider is skipped by discovery and "
            "is meant to be skipped by any app reading this registry."
        ),
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

        verbose_name = "AI Provider"
        verbose_name_plural = "AI Providers"

    def __str__(self):
        """Stringify instance."""
        return self.name

    def clean(self):
        """Check that this provider can be addressed.

        ``blank=True`` exists so the migration can leave a legacy row unanswered, and so the form
        renders an empty option for one. Without it the select would show the first choice for such
        a row, and a save would write the dialect the migration refused to guess.

        Raises:
            ValidationError: The dialect is unanswered, or the provider type is in
                ``ADDRESSED_PROVIDER_TYPES`` and its integration carries no remote URL, so a client
                would fall back to another company's endpoint.
        """
        super().clean()

        if not self.provider_type:
            raise ValidationError(
                {"provider_type": "Say which API dialect this endpoint speaks. Nothing can address it otherwise."}
            )

        if self.provider_type in ADDRESSED_PROVIDER_TYPES:
            validate_remote_url(
                self,
                f"A {self.get_provider_type_display()} provider is an address, not a service. It needs an "
                "external integration with a remote URL.",
            )


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class AIModel(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """A single model offered by an AIProvider.

    ``num_predict`` and ``temperature`` are optional overrides. An empty value inherits the
    provider default. Read the effective values through the ``resolved_*`` properties.
    """

    is_dynamic_group_associable_model = False

    provider = models.ForeignKey(
        to="nautobot_ai_models.AIProvider",
        on_delete=models.CASCADE,
        related_name="ai_models",
        verbose_name="AI Provider",
    )
    name = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        help_text="The model identifier the provider expects, for example gpt-4o-mini.",
    )
    description = models.CharField(max_length=CHARFIELD_MAX_LENGTH, blank=True)
    kind = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        choices=AIModelKindChoices,
        default=AIModelKindChoices.CHAT,
        db_index=True,
        help_text=(
            "What this model is for. A chat model and an embedding model are not interchangeable, "
            "and they are not even the same endpoint. Set by a person: discovery cannot tell them apart."
        ),
    )
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
    input_cost_per_million = models.DecimalField(
        max_digits=COST_MAX_DIGITS,
        decimal_places=COST_DECIMAL_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(MIN_COST)],
        verbose_name="Input cost per million tokens",
        help_text=(
            "What a million input tokens cost, in the provider's billing currency. Empty means "
            "nobody has recorded a price, which is not the same as free."
        ),
    )
    output_cost_per_million = models.DecimalField(
        max_digits=COST_MAX_DIGITS,
        decimal_places=COST_DECIMAL_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(MIN_COST)],
        verbose_name="Output cost per million tokens",
        help_text=(
            "What a million output tokens cost, in the provider's billing currency. Usually "
            "several times the input price, which is why the two are recorded apart."
        ),
    )
    default_parameters = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Default parameters",
        help_text=(
            "Extra request parameters to send with every call to this model, as a JSON object. "
            "Only the keys on this app's allowlist are accepted, so that nothing here can change "
            "which host answers. The contents of extra_body are passed through unchecked."
        ),
    )

    class Meta:
        """Meta class."""

        ordering = ["provider", "name"]
        unique_together = [["name", "provider"]]
        verbose_name = "AI Model"
        verbose_name_plural = "AI Models"

    def __str__(self):
        """Stringify instance."""
        return f"{self.provider.name}: {self.name}"

    def clean(self):
        """Check ``default_parameters`` against the allowlist.

        Checked again in :attr:`resolved_parameters`, because a fixture, a data migration, or a
        direct ORM write never runs this method.

        ``temperature`` is checked against the same range as the column of the same name, so that
        the JSON field cannot be used to get past the validators on that column.

        Raises:
            ValidationError: The value is not a mapping, a key is not in
                ``ALLOWED_MODEL_PARAMETERS``, or the temperature is not a number in range.
        """
        super().clean()

        if not isinstance(self.default_parameters, dict):
            raise ValidationError({"default_parameters": "Default parameters must be a JSON object."})

        rejected = sorted(key for key in self.default_parameters if key not in ALLOWED_MODEL_PARAMETERS)
        if rejected:
            raise ValidationError(
                {
                    "default_parameters": (
                        f"These parameters are not on the allowlist: {', '.join(rejected)}. "
                        f"Accepted keys are: {', '.join(ALLOWED_MODEL_PARAMETERS)}."
                    )
                }
            )

        if "temperature" in self.default_parameters:
            temperature = self.default_parameters["temperature"]
            if isinstance(temperature, bool) or not isinstance(temperature, (int, float, Decimal)):
                raise ValidationError({"default_parameters": "The temperature parameter must be a number."})
            if not MIN_TEMPERATURE <= temperature <= MAX_TEMPERATURE:
                raise ValidationError(
                    {
                        "default_parameters": (
                            f"The temperature parameter must be between {MIN_TEMPERATURE} and {MAX_TEMPERATURE}."
                        )
                    }
                )

    @property
    def is_available(self):
        """Whether the registry offers this model at all.

        Returns:
            bool: True when the model and its provider are both enabled.
        """
        # pylint: disable=no-member  # pylint-django cannot resolve the ForeignKey target here.
        return self.enabled and self.provider.enabled

    @property
    def resolved_num_predict(self):
        """The model's ``num_predict``, or the provider default when unset.

        Returns:
            int | None: The effective token limit.
        """
        # pylint: disable=no-member  # pylint-django cannot resolve the ForeignKey target here.
        return self.num_predict if self.num_predict is not None else self.provider.num_predict

    @property
    def _stored_parameters(self):
        """The raw parameter mapping, or an empty one when the column holds something else.

        Returns:
            dict: What is in the column, if it is a mapping.
        """
        return self.default_parameters if isinstance(self.default_parameters, dict) else {}

    @property
    def resolved_temperature(self):
        """The effective temperature.

        Precedence: this model's column, then ``default_parameters["temperature"]``, then the
        provider default.

        Returns:
            Decimal | float | None: The effective temperature, in the type its source held.
        """
        # pylint: disable=no-member  # pylint-django cannot resolve the ForeignKey target here.
        if self.temperature is not None:
            return self.temperature
        from_parameters = self._stored_parameters.get("temperature")
        if from_parameters is not None:
            return from_parameters
        return self.provider.temperature

    @property
    def resolved_parameters(self):
        """The request parameters to send with a call to this model.

        Applies the allowlist a second time, dropping any key that got past :meth:`clean`, and
        folds :attr:`resolved_temperature` in as a float so the result is JSON serialisable.

        Never raises. A consuming app and the REST API both read this on a list, so one row that a
        direct ORM write left unusable must not take the whole response with it.

        Returns:
            dict: Allowlisted parameters, ready to send.
        """
        parameters = {key: value for key, value in self._stored_parameters.items() if key in ALLOWED_MODEL_PARAMETERS}

        parameters.pop("temperature", None)
        try:
            temperature = self.resolved_temperature
            if temperature is not None:
                parameters["temperature"] = float(temperature)
        except (TypeError, ValueError):
            pass

        return parameters


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class MCPServer(PrimaryModel):  # pylint: disable=too-many-ancestors
    """An MCP server registered by an operator.

    The ExternalIntegration holds the endpoint, its headers, its TLS settings, and its secrets
    group. An operator owns the fields above ``protocol_version``; discovery owns the rest and
    rewrites them on every successful run.
    """

    is_dynamic_group_associable_model = False

    name = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        unique=True,
        help_text="What this server is called in Nautobot. Not the name the server reports for itself.",
    )
    description = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        blank=True,
        help_text="What this server is for, in an operator's words.",
    )
    external_integration = models.ForeignKey(
        to="extras.ExternalIntegration",
        on_delete=models.PROTECT,
        related_name="mcp_servers",
        help_text="Carries the endpoint URL, its headers and TLS settings, and its secrets group.",
    )
    transport = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        choices=MCPTransportChoices,
        default=MCPTransportChoices.TYPE_STREAMABLE_HTTP,
        help_text="How a client reaches this server. A stdio server cannot be discovered from Nautobot.",
    )
    enabled = models.BooleanField(
        default=True,
        help_text=(
            "Whether this server is in service. A disabled server is skipped by discovery and is "
            "meant to be skipped by any app reading this registry."
        ),
    )
    tenant = models.ForeignKey(
        to="tenancy.Tenant",
        on_delete=models.PROTECT,
        related_name="mcp_servers",
        null=True,
        blank=True,
        help_text="The tenant this server belongs to, if the deployment is divided that way.",
    )
    protocol_version = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        blank=True,
        help_text="The MCP protocol revision the last discovery negotiated. Set by discovery.",
    )
    server_name = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        blank=True,
        help_text=(
            "The name the server reports for itself. Self-reported and unverified: the "
            "specification says in as many words that a client must not make decisions from it."
        ),
    )
    server_version = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        blank=True,
        help_text="The version the server reports for itself. Self-reported, like the name. Set by discovery.",
    )
    instructions = models.TextField(
        blank=True,
        help_text="The server's own guidance on how to use it, as it advertised. Set by discovery.",
    )
    capabilities = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "The capabilities object the server advertised, stored whole. Says which of tools, "
            "resources and prompts it offers. Set by discovery."
        ),
    )
    last_discovered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "When this server's tool list was last read successfully. Left alone when a run fails, "
            "so an operator can see which servers have gone stale."
        ),
    )

    class Meta:
        """Meta class."""

        ordering = ["name"]
        verbose_name = "MCP Server"
        verbose_name_plural = "MCP Servers"

    def __str__(self):
        """Stringify instance."""
        return self.name

    def clean(self):
        """Check that the server has a remote URL.

        Raises:
            ValidationError: The integration carries no remote URL, so nothing can reach the
                server.
        """
        super().clean()
        validate_remote_url(self, "An MCP server needs an external integration with a remote URL.")


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class MCPTool(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """One tool an MCP server advertises.

    ``advertised_read_only`` is what the server claimed. ``writable`` is what a person decided.
    The MCP specification requires that a client treat a server's annotations as untrusted, so
    discovery records the claim and never acts on it.
    """

    is_dynamic_group_associable_model = False

    mcp_server = models.ForeignKey(
        to=MCPServer,
        on_delete=models.CASCADE,
        related_name="tools",
        help_text="A tool cannot outlive the server that offers it.",
    )
    name = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        help_text="The tool name sent on the wire. Unique within its server, and case sensitive.",
    )
    title = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        blank=True,
        help_text="The human-readable name the server offered for display, if it offered one.",
    )
    description = models.TextField(
        blank=True,
        help_text="What the tool does, as the server advertised it.",
    )
    input_schema = models.JSONField(
        default=dict,
        blank=True,
        help_text="The JSON Schema the server advertised for this tool's arguments.",
    )
    output_schema = models.JSONField(
        default=dict,
        blank=True,
        help_text="The JSON Schema the server advertised for this tool's structured result, if any.",
    )
    enabled = models.BooleanField(
        default=True,
        help_text=(
            "Whether this tool is offered to apps reading this registry. Set by a person. "
            "Discovery only ever clears it, and only for a tool the server stopped advertising."
        ),
    )
    writable = models.BooleanField(
        default=True,
        help_text=(
            "Whether calling this tool changes something. Set by a person, never by discovery. "
            "True until somebody says otherwise: guessing wrong this way costs a review, and "
            "guessing wrong the other way tells every consuming app a tool is safe when it is not."
        ),
    )
    advertised_read_only = models.BooleanField(
        null=True,
        blank=True,
        help_text=(
            "What the server's own readOnlyHint annotation claims, or unset when it claims "
            "nothing. Shown so a reviewer can see it. It decides nothing: the MCP specification "
            "requires that a client treat annotations from a server as untrusted."
        ),
    )
    definition_fingerprint = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        blank=True,
        help_text=(
            "Digest of everything the server advertised about this tool - its description as well "
            "as its argument schema - as of the last discovery. A consuming app compares it to "
            "detect that a tool's contract changed under a review somebody already did."
        ),
    )
    last_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When discovery last saw this tool advertised. An older time means the server stopped offering it.",
    )

    natural_key_field_names = ["mcp_server", "name"]

    class Meta:
        """Meta class."""

        ordering = ["mcp_server__name", "name"]
        verbose_name = "MCP Tool"
        verbose_name_plural = "MCP Tools"
        constraints = [
            models.UniqueConstraint(
                fields=["mcp_server", "name"],
                name="nautobot_ai_models_mcptool_unique_server_name",
            ),
        ]

    def __str__(self):
        """Stringify instance."""
        return f"{self.mcp_server.name}: {self.name}"

    @property
    def is_available(self):
        """Whether the registry offers this tool at all.

        Returns:
            bool: True when the tool and its server are both enabled.
        """
        return self.enabled and self.mcp_server.enabled
