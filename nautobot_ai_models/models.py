"""Registry models: what a model is, where a tool comes from, and what an agent is made of.

Every model keeps its endpoint, headers, TLS settings, and credentials in a Nautobot
ExternalIntegration. No model here calls anything.

The agent half of this module describes an agent. It does not run one. `services/agents.py` turns
these rows into a LangChain agent, and even that module only builds the agent.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from nautobot.apps.constants import CHARFIELD_MAX_LENGTH
from nautobot.apps.models import OrganizationalModel, PrimaryModel, extras_features

from nautobot_ai_models.choices import (
    AIAgentPatternChoices,
    AIAgentThreadStatusChoices,
    AIModelKindChoices,
    AIProviderTypeChoices,
    AIToolKindChoices,
    MCPTransportChoices,
    SubagentInputModeChoices,
)
from nautobot_ai_models.constants import (
    ADDRESSED_PROVIDER_TYPES,
    ALLOWED_MODEL_PARAMETERS,
    COST_DECIMAL_PLACES,
    COST_MAX_DIGITS,
    DEFAULT_BINDING_WEIGHT,
    DEFAULT_MAX_ITERATIONS,
    MAX_TEMPERATURE,
    MIN_COST,
    MIN_MAX_ITERATIONS,
    MIN_NUM_PREDICT,
    MIN_TEMPERATURE,
    TEMPERATURE_DECIMAL_PLACES,
    TEMPERATURE_MAX_DIGITS,
)
from nautobot_ai_models.integrations import canonical_digest
from nautobot_ai_models.tools import get_registered_tool


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

    This record says that an endpoint exists and how to reach it. The related ExternalIntegration
    owns the URL, the headers, the TLS settings, and the credentials.
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

        ``blank=True`` lets the migration leave a legacy row unanswered, and lets the form show an
        empty option for that row. Without it the select shows the first choice, and a save writes
        the dialect that the migration refused to guess.

        Raises:
            ValidationError: The dialect is unanswered, or the provider type is in
                ``ADDRESSED_PROVIDER_TYPES`` and its integration carries no remote URL. A client
                would then fall back to another company's endpoint.
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
        """Meta class.

        The foreign key comes last in ``unique_together``. Nautobot derives the natural key from
        the first uniqueness constraint, and a trailing related field keeps ``natural_key()`` and
        ``get_by_natural_key()`` correct.
        """

        ordering = ["provider", "name"]
        unique_together = [["name", "provider"]]
        verbose_name = "AI Model"
        verbose_name_plural = "AI Models"

    def __str__(self):
        """Stringify instance."""
        return f"{self.provider.name}: {self.name}"

    def clean(self):
        """Check ``default_parameters`` against the allowlist.

        :attr:`resolved_parameters` checks the value again, because a fixture, a data migration, or
        a direct ORM write never runs this method.

        An empty value becomes an empty object, because the edit form renders an empty textarea as
        None, and a refusal would make an optional field impossible to clear.

        This check applies the same temperature range as the column of that name, so the JSON field
        cannot get past the validators on that column.

        Raises:
            ValidationError: The value is not a mapping, a key is not in
                ``ALLOWED_MODEL_PARAMETERS``, or the temperature is not a number in range.
        """
        super().clean()

        if not self.default_parameters:
            self.default_parameters = {}

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
        # pylint: disable=no-member
        return self.enabled and self.provider.enabled

    @property
    def resolved_num_predict(self):
        """The model's ``num_predict``, or the provider default when unset.

        Returns:
            int | None: The effective token limit.
        """
        # pylint: disable=no-member
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
        # pylint: disable=no-member
        if self.temperature is not None:
            return self.temperature
        from_parameters = self._stored_parameters.get("temperature")
        if from_parameters is not None:
            return from_parameters
        return self.provider.temperature

    @property
    def resolved_parameters(self):
        """The request parameters to send with a call to this model.

        This property applies the allowlist a second time and drops any key that got past
        :meth:`clean`. It folds :attr:`resolved_temperature` in as a float, so the result is JSON
        serialisable.

        It never raises. A consuming app and the REST API both read this on a list, so one unusable
        row must not take the whole response with it.

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
    group. An operator owns the fields above ``protocol_version``. Discovery owns the rest and
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
    The MCP specification requires a client to treat a server's annotations as untrusted, so
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


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class AITool(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """A tool an agent may call that did not come from an MCP server.

    This model has the same shape as :class:`MCPTool`, field for field where it can. An agent's
    gate asks three questions of every tool: is this offered, does it need a person, and did its
    definition move. A second tool source that could not answer them would walk past that gate.

    Discovery writes these rows, never a person. `SyncAITools` reads the in-process registry
    that `tools.register_ai_tool` fills, under the same policy that governs MCP tools.
    """

    is_dynamic_group_associable_model = False

    natural_key_field_names = ["name"]

    name = models.CharField(max_length=CHARFIELD_MAX_LENGTH, unique=True)
    description = models.TextField(
        blank=True,
        help_text=(
            "What the model reads when it decides whether to call this. Write it for a new "
            "colleague on their first day: what the tool does, and what to send it."
        ),
    )
    argument_schema = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Argument schema",
        help_text="The tool's parameters as JSON Schema, read from the callable's type hints.",
    )
    kind = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        choices=AIToolKindChoices,
        default=AIToolKindChoices.REGISTERED,
        db_index=True,
        help_text="Where this tool came from. Discovery sets it; changing it by hand will not move the code.",
    )
    module = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        blank=True,
        help_text="The module the callable was found in. Recorded so an operator can find the source.",
    )
    git_repository = models.ForeignKey(
        to="extras.GitRepository",
        on_delete=models.CASCADE,
        related_name="ai_tools",
        null=True,
        blank=True,
        verbose_name="Git Repository",
        help_text="The repository this tool was synced from, when it came from one.",
    )
    job = models.ForeignKey(
        to="extras.Job",
        on_delete=models.PROTECT,
        related_name="ai_tools",
        null=True,
        blank=True,
        help_text="The Job this tool starts. Starting it is all the tool does; it does not wait for the result.",
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Consumers should ignore a disabled tool. Discovery sets this from new_tools_enabled.",
    )
    writable = models.BooleanField(
        default=True,
        help_text=(
            "Whether calling this changes something. True by default for the reason MCP tools are: "
            "guessing wrong this way costs a review, and guessing wrong the other way tells every "
            "consuming app a tool is safe when it is not."
        ),
    )
    advertised_read_only = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Advertised read-only",
        help_text=(
            "What the tool said about itself, against what a person decided in Writable. Unset "
            "means it said nothing."
        ),
    )
    definition_fingerprint = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        blank=True,
        verbose_name="Definition fingerprint",
        help_text="A digest of the name, description and argument schema, so a changed tool is visible.",
    )
    last_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last seen at",
        help_text="When discovery last found this tool. A row that stops being found is reported, not deleted.",
    )

    class Meta:
        """Meta class."""

        ordering = ["name"]
        verbose_name = "AI Tool"
        verbose_name_plural = "AI Tools"

    def __str__(self):
        """Stringify instance."""
        return self.name

    def clean(self):
        """Check that the row names the one source its kind says it has, and that the source is there.

        This check tests a registered tool against the registry instead of trusting it. The row is a
        claim that code exists under that name, and a row that outlived its app must not save.

        Raises:
            ValidationError: A Job tool names no Job, a tool of another kind names one, a Git tool
                names no repository, or a registered tool names something nothing registered.
        """
        super().clean()

        if self.kind == AIToolKindChoices.JOB and self.job_id is None:
            raise ValidationError({"job": "A Job tool has to name the Job it starts."})
        if self.present_in_database:
            was = AITool.objects.filter(pk=self.pk).values_list("job_id", flat=True).first()
            if was != self.job_id:
                raise ValidationError(
                    {
                        "job": "The Job cannot be changed. Delete this tool and add another, so anything that "
                        "approved the old one has to look at the new one."
                    }
                )
        if self.kind != AIToolKindChoices.JOB and self.job_id is not None:
            raise ValidationError({"job": f"A '{self.get_kind_display()}' tool does not start a Job."})
        if self.kind != AIToolKindChoices.GIT and self.git_repository_id is not None:
            raise ValidationError(
                {"git_repository": f"A '{self.get_kind_display()}' tool did not come from a repository."}
            )
        if self.kind == AIToolKindChoices.GIT and self.git_repository_id is None:
            raise ValidationError({"git_repository": "A Git tool has to name the repository it came from."})

        if (
            self.kind == AIToolKindChoices.REGISTERED
            and not self.present_in_database
            and get_registered_tool(self.name) is None
        ):
            raise ValidationError(
                {
                    "name": (
                        f"Nothing registered a tool called '{self.name}'. A registered tool is "
                        "declared in code with @register_ai_tool and written here by the Sync AI "
                        "Tools Job; it is not created by hand."
                    )
                }
            )

    @property
    def is_available(self):
        """Whether the registry offers this tool at all.

        Returns:
            bool: True when the tool is enabled.
        """
        return self.enabled


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class AIAgent(PrimaryModel):  # pylint: disable=too-many-ancestors
    """One agent: a model, a system prompt, and the tools it may reach.

    An operator writes this, so it is a PrimaryModel and it carries tags. Every part of an agent
    is a row: the prompt is a column, the tool list is a table, and the specialists are another
    table. No part of an agent is a Python constant.
    """

    is_dynamic_group_associable_model = False

    name = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        unique=True,
        help_text="Also the name a supervisor calls this agent by, unless a binding overrides it.",
    )
    description = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        blank=True,
        help_text=(
            "What this agent is for, in one or two sentences. When a supervisor delegates to this "
            "agent, this is the tool description it reads, and that text decides whether the call "
            "is made at all."
        ),
    )
    system_prompt = models.TextField(
        verbose_name="System prompt",
        help_text=(
            "The agent's standing instructions. A rule here holds more firmly than the same rule "
            "delivered as a tool result, so put anything that must hold in this field."
        ),
    )
    model = models.ForeignKey(
        to="nautobot_ai_models.AIModel",
        on_delete=models.PROTECT,
        related_name="agents",
        verbose_name="AI Model",
        help_text="The chat model this agent runs on.",
    )
    pattern = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        choices=AIAgentPatternChoices,
        default=AIAgentPatternChoices.SINGLE,
        db_index=True,
        help_text=(
            "How this agent is built. Start with a single agent holding every tool; move to "
            "subagents when one prompt can no longer hold every rule."
        ),
    )
    enabled = models.BooleanField(default=True, help_text="Consumers should ignore a disabled agent.")
    temperature = models.DecimalField(
        max_digits=TEMPERATURE_MAX_DIGITS,
        decimal_places=TEMPERATURE_DECIMAL_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(MIN_TEMPERATURE), MaxValueValidator(MAX_TEMPERATURE)],
        help_text="Overrides the model's temperature for this agent. Unset falls back to the model, then the provider.",
    )
    num_predict = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(MIN_NUM_PREDICT)],
        verbose_name="num_predict",
        help_text="Overrides the model's token limit for this agent. -1 means unlimited.",
    )
    max_iterations = models.PositiveIntegerField(
        default=DEFAULT_MAX_ITERATIONS,
        validators=[MinValueValidator(MIN_MAX_ITERATIONS)],
        verbose_name="Max iterations",
        help_text="How many model calls one run may spend before it stops with what it has.",
    )
    tenant = models.ForeignKey(
        to="tenancy.Tenant",
        on_delete=models.PROTECT,
        related_name="ai_agents",
        null=True,
        blank=True,
    )

    class Meta:
        """Meta class."""

        ordering = ["name"]
        verbose_name = "AI Agent"
        verbose_name_plural = "AI Agents"

    def __str__(self):
        """Stringify instance."""
        return self.name

    def clean(self):
        """Check that the agent can be built.

        The pattern checks run on a saved row only, because a binding cannot exist before its agent
        does, and a create would otherwise be impossible.

        Raises:
            ValidationError: The model is not a chat model, or the pattern needs bindings the agent
                does not have.
        """
        super().clean()

        # pylint: disable=no-member
        if self.model_id is not None and self.model.kind != AIModelKindChoices.CHAT:
            raise ValidationError(
                {
                    "model": (
                        f"An agent needs a chat model. '{self.model}' is registered as "
                        f"{self.model.get_kind_display()}."
                    )
                }
            )

        if self._state.adding:
            return

        was = AIAgent.objects.filter(pk=self.pk).values_list("pattern", flat=True).first()
        if self.pattern == was:
            return

        if self.pattern == AIAgentPatternChoices.SUBAGENTS and not self.subagent_bindings.exists():
            raise ValidationError({"pattern": "A subagents agent needs at least one subagent. Add one first."})
        if self.pattern == AIAgentPatternChoices.SKILLS and not self.skill_bindings.exists():
            raise ValidationError({"pattern": "A skills agent needs at least one skill. Add one first."})

    @property
    def is_available(self):
        """Whether this agent can be built and run.

        Returns:
            bool: True when the agent, its model and its model's provider are all enabled.
        """
        # pylint: disable=no-member
        return self.enabled and self.model.is_available

    @property
    def resolved_temperature(self):
        """The effective temperature: this agent, then the model, then the provider.

        Returns:
            Decimal | float | None: The effective temperature, in the type its source held.
        """
        # pylint: disable=no-member
        if self.temperature is not None:
            return self.temperature
        return self.model.resolved_temperature

    @property
    def resolved_num_predict(self):
        """The effective token limit: this agent, then the model, then the provider.

        Returns:
            int | None: The effective limit.
        """
        # pylint: disable=no-member
        if self.num_predict is not None:
            return self.num_predict
        return self.model.resolved_num_predict


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class AIAgentTool(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """One tool an agent may call, and what the agent is told about it.

    The overrides are the point of this model. A tool's name and its description decide whether
    the model calls it at all, and a wrong pair fails in silence. An operator fixes that here,
    on the binding, without an edit to the MCP server or to the code that registered the tool.

    A property on this row answers every question the gate asks, whatever source the tool came
    from.
    """

    is_dynamic_group_associable_model = False

    agent = models.ForeignKey(
        to="nautobot_ai_models.AIAgent",
        on_delete=models.CASCADE,
        related_name="tool_bindings",
        verbose_name="AI Agent",
    )
    mcp_tool = models.ForeignKey(
        to="nautobot_ai_models.MCPTool",
        on_delete=models.PROTECT,
        related_name="agent_bindings",
        null=True,
        blank=True,
        verbose_name="MCP Tool",
    )
    ai_tool = models.ForeignKey(
        to="nautobot_ai_models.AITool",
        on_delete=models.PROTECT,
        related_name="agent_bindings",
        null=True,
        blank=True,
        verbose_name="AI Tool",
    )
    name_override = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        blank=True,
        verbose_name="Name override",
        help_text="What this agent calls the tool. Empty uses the tool's own name.",
    )
    description_override = models.TextField(
        blank=True,
        verbose_name="Description override",
        help_text=(
            "What this agent is told the tool does. Empty uses the tool's own description. Set it "
            "when the tool's own wording is not what this agent needs to read."
        ),
    )
    weight = models.PositiveIntegerField(
        default=DEFAULT_BINDING_WEIGHT,
        help_text="The order tools are offered in. Lower comes first.",
    )

    class Meta:
        """Meta class."""

        ordering = ["agent__name", "weight", "pk"]
        verbose_name = "AI Agent Tool"
        verbose_name_plural = "AI Agent Tools"
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "mcp_tool"],
                name="nautobot_ai_models_aiagenttool_unique_agent_mcp_tool",
            ),
            models.UniqueConstraint(
                fields=["agent", "ai_tool"],
                name="nautobot_ai_models_aiagenttool_unique_agent_ai_tool",
            ),
        ]

    def __str__(self):
        """Stringify instance."""
        return f"{self.agent.name}: {self.wire_name}"

    def clean(self):
        """Check that the binding names exactly one tool.

        Raises:
            ValidationError: The row names neither tool or both of them.
        """
        super().clean()

        named = [field for field in ("mcp_tool", "ai_tool") if getattr(self, f"{field}_id") is not None]
        if not named:
            raise ValidationError("A tool binding has to name an MCP tool or an AI tool.")
        if len(named) > 1:
            raise ValidationError("A tool binding names one tool. This one names both.")

    @property
    def target(self):
        """The tool this binding points at, whichever kind it is.

        Returns:
            MCPTool | AITool: The bound tool.

        Raises:
            ValueError: The row names no tool, which `clean()` refuses and a direct write can still
                produce.
        """
        if self.mcp_tool_id is not None:
            return self.mcp_tool
        if self.ai_tool_id is not None:
            return self.ai_tool
        raise ValueError(f"Tool binding {self.pk} names no tool.")

    @property
    def wire_name(self):
        """The name this agent calls the tool by.

        Returns:
            str: The override, or the tool's own name.
        """
        return self.name_override or self.target.name

    @property
    def wire_description(self):
        """What this agent is told the tool does.

        Returns:
            str: The override, or the tool's own description.
        """
        return self.description_override or self.target.description

    @property
    def writable(self):
        """Whether a call to this tool changes something.

        This property reads through to the tool instead of a second stored answer, so the two cannot
        drift.

        Returns:
            bool: True when the bound tool is writable.
        """
        return self.target.writable

    @property
    def fingerprint(self):
        """A digest of what this binding offers, for an approval to be checked against.

        The digest covers the effective definition, not the target's stored digest, which answers a
        different question. The stored digest would miss two things:

        * `name_override` and `description_override` are what the model is told. A rewritten
          description changes what the model believes the tool does, and the target's digest does
          not move.
        * A `job` tool has no stored digest, so the comparison would be `"" == ""` forever.

        Returns:
            str: A hex SHA-256 digest of the name, the description, and the argument schema a model
                would be given.
        """
        target = self.target
        return canonical_digest(
            {
                "name": self.wire_name,
                "description": self.wire_description,
                "argument_schema": self._target_schema(target),
            }
        )

    @staticmethod
    def _target_schema(target):
        """The argument schema of either kind of target.

        Args:
            target: The MCPTool or AITool this binding points at.

        Returns:
            dict: The schema, or an empty one when the target carries none.
        """
        return getattr(target, "argument_schema", None) or getattr(target, "input_schema", None) or {}

    @property
    def is_available(self):
        """Whether this binding can be offered to a model.

        Returns:
            bool: True when the agent and the bound tool are both available.
        """
        return self.agent.is_available and self.target.is_available  # pylint: disable=no-member


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class AIAgentSubagent(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """One specialist a supervisor may delegate to, and how it is described and addressed.

    ``tool_name`` and ``tool_description`` are separate from the subagent's own name and
    description, because they decide whether the specialist is ever called. A name or a
    description that reads badly to the model produces no error and no log line, only an empty
    answer.

    ``input_mode`` sends the task alone by default. The user's question looks like a free
    improvement and is not: every added string can activate a rule in the specialist's own
    prompt, and the specialist then answers the question it saw instead of the task it was given.
    """

    is_dynamic_group_associable_model = False

    parent = models.ForeignKey(
        to="nautobot_ai_models.AIAgent",
        on_delete=models.CASCADE,
        related_name="subagent_bindings",
        help_text="The supervisor.",
    )
    subagent = models.ForeignKey(
        to="nautobot_ai_models.AIAgent",
        on_delete=models.PROTECT,
        related_name="supervisor_bindings",
        help_text="The specialist the supervisor may delegate to.",
    )
    tool_name = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        blank=True,
        verbose_name="Tool name",
        help_text=(
            "What the supervisor calls this specialist. Empty uses the specialist's own name. Keep "
            "it plain: a name the model does not recognise as an action is not called."
        ),
    )
    tool_description = models.TextField(
        blank=True,
        verbose_name="Tool description",
        help_text=(
            "What the supervisor reads when it decides to delegate. Empty uses the specialist's "
            "own description. Keep it to one or two sentences on one line; a bulleted, multi-line "
            "description measurably stopped the tool being called at all."
        ),
    )
    input_mode = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        choices=SubagentInputModeChoices,
        default=SubagentInputModeChoices.TASK_ONLY,
        verbose_name="Input mode",
        help_text=(
            "What the supervisor sends. Read the specialist's own system prompt before you widen "
            "this: added context can activate a rule in that prompt and make the specialist refuse."
        ),
    )
    weight = models.PositiveIntegerField(
        default=DEFAULT_BINDING_WEIGHT,
        help_text="The order specialists are offered in. Lower comes first.",
    )

    class Meta:
        """Meta class."""

        ordering = ["parent__name", "weight", "pk"]
        verbose_name = "AI Agent Subagent"
        verbose_name_plural = "AI Agent Subagents"
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "subagent"],
                name="nautobot_ai_models_aiagentsubagent_unique_parent_subagent",
            ),
        ]

    def __str__(self):
        """Stringify instance."""
        return f"{self.parent.name} -> {self.wire_name}"

    def clean(self):
        """Refuse an agent that delegates to itself, and refuse a cycle.

        A walk over these rows builds the graph, so a cycle in them is a build that never returns.

        Raises:
            ValidationError: The supervisor is the specialist, or delegation already runs the other
                way somewhere up the chain.
        """
        super().clean()

        if self.parent_id is None or self.subagent_id is None:
            return

        if self.parent_id == self.subagent_id:
            raise ValidationError({"subagent": "An agent cannot delegate to itself."})

        if self._reaches(self.subagent_id, self.parent_id):
            raise ValidationError(
                {"subagent": f"'{self.subagent}' already delegates to '{self.parent}', so this would make a cycle."}
            )

    @staticmethod
    def _reaches(start_id, target_id):
        """Whether delegation from one agent reaches another by any route.

        Args:
            start_id: The agent to start walking from.
            target_id: The agent to look for.

        Returns:
            bool: True when a chain of subagent bindings leads from start to target.
        """
        seen, pending = set(), [start_id]
        while pending:
            current = pending.pop()
            if current == target_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            pending.extend(AIAgentSubagent.objects.filter(parent_id=current).values_list("subagent_id", flat=True))
        return False

    @property
    def wire_name(self):
        """The name the supervisor calls this specialist by.

        Returns:
            str: The override, or the specialist's own name.
        """
        return self.tool_name or self.subagent.name

    @property
    def wire_description(self):
        """What the supervisor reads when it decides to delegate.

        Returns:
            str: The override, or the specialist's own description.
        """
        return self.tool_description or self.subagent.description


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class AISkill(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """A block of domain rules an agent can load part-way through a run.

    A skill is a prompt that arrives as a tool result, not as a system prompt. That makes it
    cheap and it makes it weak. An agent with twenty skills still loads one, so the prompt stays
    small. A measurement showed an agent read a rule delivered this way and then broke it, where
    the same rule held in a system prompt.

    Use a skill where a broken rule is cheap. Where a rule must hold, put it in an agent's system
    prompt, or give the work to a subagent whose prompt carries it.
    """

    is_dynamic_group_associable_model = False

    name = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        unique=True,
        help_text="The name the agent loads this skill by.",
    )
    description = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        blank=True,
        help_text="What area of work this covers, in a few words. The agent reads this to choose a skill.",
    )
    body = models.TextField(
        help_text="The rules themselves. This text is handed to the agent when it loads the skill.",
    )
    enabled = models.BooleanField(default=True, help_text="A disabled skill is not offered.")

    class Meta:
        """Meta class."""

        ordering = ["name"]
        verbose_name = "AI Skill"
        verbose_name_plural = "AI Skills"

    def __str__(self):
        """Stringify instance."""
        return self.name

    @property
    def is_available(self):
        """Whether this skill is offered at all.

        Returns:
            bool: True when the skill is enabled.
        """
        return self.enabled


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class AIAgentSkill(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """One skill an agent may load."""

    is_dynamic_group_associable_model = False

    agent = models.ForeignKey(
        to="nautobot_ai_models.AIAgent",
        on_delete=models.CASCADE,
        related_name="skill_bindings",
        verbose_name="AI Agent",
    )
    skill = models.ForeignKey(
        to="nautobot_ai_models.AISkill",
        on_delete=models.PROTECT,
        related_name="agent_bindings",
        verbose_name="AI Skill",
    )
    weight = models.PositiveIntegerField(
        default=DEFAULT_BINDING_WEIGHT,
        help_text="The order skills are listed in. Lower comes first.",
    )

    class Meta:
        """Meta class."""

        ordering = ["agent__name", "weight", "pk"]
        verbose_name = "AI Agent Skill"
        verbose_name_plural = "AI Agent Skills"
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "skill"],
                name="nautobot_ai_models_aiagentskill_unique_agent_skill",
            ),
        ]

    def __str__(self):
        """Stringify instance."""
        return f"{self.agent.name}: {self.skill.name}"

    @property
    def is_available(self):
        """Whether this skill can be offered to this agent.

        Returns:
            bool: True when the agent and the skill are both available.
        """
        return self.agent.is_available and self.skill.is_available  # pylint: disable=no-member


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class AIAgentThread(OrganizationalModel):  # pylint: disable=too-many-ancestors
    """One LangGraph conversation, and where it got to.

    The row is a handle, not the state. The LangGraph checkpointer holds the state, in tables it
    creates and owns outside Django's migrations. This row adds a thread an operator can find, an
    agent to attribute it to, and a date for retention to work from.

    This is an OrganizationalModel, not a plain BaseModel. The volume decides it: a thread
    changes state two or three times over a whole run, so change logging costs a few rows, and
    every generic Nautobot surface works on it.
    """

    is_dynamic_group_associable_model = False

    natural_key_field_names = ["pk"]

    agent = models.ForeignKey(
        to="nautobot_ai_models.AIAgent",
        on_delete=models.PROTECT,
        related_name="threads",
        verbose_name="AI Agent",
        help_text="The agent that ran. PROTECT, so deleting an agent cannot orphan its history.",
    )
    thread_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="Thread ID",
        help_text=(
            "The LangGraph thread_id this conversation is checkpointed under. A UUID because that "
            "column is capped at 255 characters and a deterministic identifier is wanted."
        ),
    )
    status = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        choices=AIAgentThreadStatusChoices,
        default=AIAgentThreadStatusChoices.RUNNING,
        db_index=True,
    )
    interrupt_payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Interrupt payload",
        help_text="What the graph asked when it paused, so a person can be shown the question.",
    )
    started_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="Started at")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Finished at")

    class Meta:
        """Meta class."""

        ordering = ["-started_at"]
        get_latest_by = "started_at"
        verbose_name = "AI Agent Thread"
        verbose_name_plural = "AI Agent Threads"

    def __str__(self):
        """Stringify instance."""
        return f"{self.agent.name}: {self.thread_id}"

    @property
    def is_live(self):
        """Whether this thread could still go on.

        Returns:
            bool: True while the thread is running or waiting for a person.
        """
        return self.status in (AIAgentThreadStatusChoices.RUNNING, AIAgentThreadStatusChoices.WAITING)
