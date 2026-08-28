"""Models for AI Models.

Two registries live here, and neither one calls anything.

* AIProvider and AIModel record which LLM endpoints exist and which models each one offers.
* MCPServer and MCPTool record which MCP servers exist and what each one advertises.

Every one of them keeps its endpoint, headers, TLS settings, and credentials in a Nautobot
ExternalIntegration rather than in a field of its own.
"""

# Django imports
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# Nautobot imports
from nautobot.apps.constants import CHARFIELD_MAX_LENGTH
from nautobot.apps.models import OrganizationalModel, PrimaryModel, extras_features

from nautobot_ai_models.choices import AIModelKindChoices, AIProviderTypeChoices, MCPTransportChoices
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


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class AIProvider(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """A remote LLM provider endpoint.

    A AIProvider records that an endpoint exists and how to reach it. It never stores a URL, a header,
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
    provider_type = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        choices=AIProviderTypeChoices,
        default=AIProviderTypeChoices.OPENAI,
        # Blank exists for one reason: the migration that added this field cannot say what a
        # provider that was not OpenAI-compatible actually speaks, so it leaves those rows empty
        # rather than guessing. `clean()` refuses a blank, so no new row can carry one.
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

        # Named AIProvider rather than Provider, because Nautobot core already defines
        # circuits.Provider, and one unqualified name for two things confuses both a reader
        # and an import.
        verbose_name = "AI Provider"
        verbose_name_plural = "AI Providers"

    def __str__(self):
        """Stringify instance."""
        return self.name

    def clean(self):
        """Refuse a provider nothing can address.

        Two checks, both about a consuming app being able to reach the right endpoint.

        A blank ``provider_type`` reaches here only on a row the migration could not answer for.
        Refusing it makes an operator answer the next time the row is saved, rather than leaving a
        consuming app to guess a dialect.

        A provider whose type is an address rather than a service needs a remote URL. A client with
        no URL for one of those falls back to a default endpoint, which is somebody else's API.
        ``MCPServer.clean()`` does the same thing for the same reason.
        """
        super().clean()

        if not self.provider_type:
            raise ValidationError(
                {"provider_type": "Say which API dialect this endpoint speaks. Nothing can address it otherwise."}
            )

        addressed_types = (AIProviderTypeChoices.OPENAI_COMPATIBLE, AIProviderTypeChoices.OLLAMA)
        if (
            self.provider_type in addressed_types
            and self.external_integration_id is not None
            and not self.external_integration.remote_url
        ):
            raise ValidationError(
                {
                    "external_integration": (
                        f"A {self.get_provider_type_display()} provider is an address, not a service. It needs an "
                        "external integration with a remote URL."
                    )
                }
            )


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class AIModel(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """A single model offered by a AIProvider.

    The num_predict and temperature fields are optional overrides. An empty value inherits the
    default from the parent AIProvider. Read the resolved values through resolved_num_predict and
    resolved_temperature.

    Everything else a call needs goes in default_parameters, behind an allowlist. Read that through
    resolved_parameters, which applies the allowlist a second time and folds the resolved
    temperature in, so one dictionary is all a consuming app has to build a request from.
    """

    # This app catalogs models. It does not group them, so opt out of Dynamic Groups.
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
            "which host answers."
        ),
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

    def clean(self):
        """Refuse a default parameter this app has not vetted.

        The allowlist is checked here and again in `resolved_parameters`. Once is not enough: a
        fixture, a data migration, or a direct ORM write never runs this method, and the read side
        is where a key that got past it would be handed to a client.
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

    @property
    def is_available(self):
        """Whether this registry offers the model at all.

        A model on a disabled provider is not on offer however the model itself is flagged. Saves a
        consuming app asking two questions, and matches `MCPTool.is_available` on the MCP half.
        """
        # pylint: disable=no-member  # pylint-django cannot resolve the ForeignKey target here.
        return self.enabled and self.provider.enabled

    @property
    def resolved_num_predict(self):
        """Return this model's num_predict, or the provider default when unset."""
        # pylint: disable=no-member  # pylint-django cannot resolve the ForeignKey target here.
        return self.num_predict if self.num_predict is not None else self.provider.num_predict

    @property
    def resolved_temperature(self):
        """Return the effective temperature: this model's column, then its parameters, then the provider.

        `temperature` is on the parameter allowlist as well as being a column, so an operator can
        set it in two places. The column wins, because it is the field they see on the form.
        `resolved_parameters` applies the same order, so both properties always agree.
        """
        # pylint: disable=no-member  # pylint-django cannot resolve the ForeignKey target here.
        if self.temperature is not None:
            return self.temperature
        from_parameters = (self.default_parameters or {}).get("temperature")
        if from_parameters is not None:
            return from_parameters
        return self.provider.temperature

    @property
    def resolved_parameters(self):
        """Return the request parameters for this model, checked against the allowlist a second time.

        The read-time half of the allowlist. `clean()` catches what a form or the REST API writes;
        this catches what a fixture, a data migration, or a direct ORM write put in the column,
        none of which run `clean()`. An unknown key is dropped rather than raised on: a consuming
        app reading the registry wants the parameters it can trust, not an exception.
        """
        parameters = {
            key: value for key, value in (self.default_parameters or {}).items() if key in ALLOWED_MODEL_PARAMETERS
        }

        temperature = self.resolved_temperature
        if temperature is not None:
            parameters["temperature"] = temperature
        else:
            parameters.pop("temperature", None)

        return parameters


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class MCPServer(PrimaryModel):  # pylint: disable=too-many-ancestors
    """An MCP server known to Nautobot, registered by an operator.

    Carries no credentials and no URL of its own. The ExternalIntegration it points at holds the
    endpoint, its headers and its TLS settings, and that integration's secrets group holds whatever
    authenticates to it. That is deliberate: an operator already manages outbound endpoints in one
    place, and a second place to look would be a second place to leak from.

    The fields below split into two groups. An operator owns name, description, external
    integration, transport, enabled, and tenant. The discovery job owns everything from
    ``protocol_version`` down, and rewrites those on every successful run.
    """

    # This app catalogs servers. It does not group them, so opt out of Dynamic Groups, as the two
    # AI models do.
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
        """A server with no URL is a server nothing can reach.

        Checked here rather than left to the first connection: an ExternalIntegration is a shared
        object, and the one being pointed at may have been made for something that did not need a
        remote URL.
        """
        super().clean()
        if self.external_integration_id is not None and not self.external_integration.remote_url:
            raise ValidationError(
                {"external_integration": "An MCP server needs an external integration with a remote URL."}
            )


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class MCPTool(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """One tool an MCP server advertises.

    Not a PrimaryModel: a tool carries no tags and belongs to no dynamic group. It is still change
    logged, because a discovery run rewrites these rows and an operator needs to see what moved.

    The two write-related fields exist separately on purpose. ``advertised_read_only`` is what the
    server claimed. ``writable`` is what a person decided. The MCP specification requires that a
    client treat a server's own annotations as untrusted, so discovery records the claim and never
    acts on it.
    """

    # This app catalogs tools. It does not group them, so opt out of Dynamic Groups.
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
        """Whether this registry offers the tool at all.

        A tool on a disabled server is not on offer however the tool itself is flagged. Read by the
        UI to explain why a tool somebody enabled is still not being handed out, and useful to a
        consuming app that would rather ask one question than two.
        """
        return self.enabled and self.mcp_server.enabled
