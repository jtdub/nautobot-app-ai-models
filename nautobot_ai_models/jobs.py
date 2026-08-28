"""Discovery jobs. Both only read.

Each asks a remote endpoint what it offers and writes the answer onto the registry. Neither
deletes a record unless it is told to.
"""

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError
from nautobot.apps.exceptions import SecretError
from nautobot.apps.jobs import BooleanVar, Job, ObjectVar, register_jobs

from nautobot_ai_models import discovery
from nautobot_ai_models.models import AIModel, AIProvider, MCPServer
from nautobot_ai_models.services import mcp
from nautobot_ai_models.services.exceptions import MCPError

name = "AI Models"  # pylint: disable=invalid-name


class DiscoverAIModels(Job):
    """Read the model catalog from each OpenAI-compatible provider and sync AIModel records."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Meta attributes."""

        name = "Discover AI Models"
        description = "Query OpenAI-compatible providers and create or update AIModel records."
        has_sensitive_variables = False
        soft_time_limit = 300
        time_limit = 600

    provider = ObjectVar(
        model=AIProvider,
        required=False,
        label="AI Provider",
        description="Limit discovery to one provider. Leave empty to run against every enabled provider.",
    )
    enable_new_models = BooleanVar(
        default=True,
        description="Mark newly discovered models as enabled.",
    )

    def run(self, *, provider, enable_new_models):  # pylint: disable=arguments-differ
        """Discover models for one provider or for all of them."""
        providers = [provider] if provider is not None else list(AIProvider.objects.filter(enabled=True))
        if not providers:
            self.logger.warning("No enabled AI Provider to discover.")
            return

        for each_provider in providers:
            self.discover_provider(each_provider, enable_new_models)

    def discover_provider(self, provider, enable_new_models):
        """Sync the AIModel records for a single provider. Never delete a record."""
        if not provider.enabled:
            self.logger.warning(
                "Skipped. This provider is disabled.",
                extra={"object": provider},
            )
            return

        if not provider.openai_compatible:
            self.logger.warning(
                "Skipped. No standard model-discovery endpoint exists for a provider that is not OpenAI-compatible.",
                extra={"object": provider},
            )
            return

        try:
            discovered = discovery.fetch_models(provider)
        except (SecretError, ObjectDoesNotExist) as error:
            self.logger.failure(
                "Could not read the API token for this provider: %s",
                type(error).__name__,
                extra={"object": provider},
            )
            return
        except Exception as error:  # pylint: disable=broad-except
            self.logger.failure(
                "Model discovery request failed: %s",
                type(error).__name__,
                extra={"object": provider},
            )
            return

        try:
            created, updated = self.sync_models(provider, discovered, enable_new_models)
        except (ValidationError, IntegrityError) as error:
            self.logger.failure(
                "This provider offered a model this registry cannot hold: %s",
                type(error).__name__,
                extra={"object": provider},
            )
            return

        self.report_missing(provider, discovered)
        self.logger.success(
            "Discovery complete. Found %d models. Created %d. Updated %d.",
            len(discovered),
            created,
            updated,
            extra={"object": provider},
        )

    def sync_models(self, provider, discovered, enable_new_models):
        """Create missing AIModel records and update existing ones. Return the two counts."""
        existing = {each.name: each for each in provider.ai_models.all()}
        created = 0
        updated = 0

        for entry in discovered:
            ai_model = existing.get(entry["name"])
            if ai_model is None:
                ai_model = AIModel(
                    provider=provider,
                    name=entry["name"],
                    description=entry["description"],
                    enabled=enable_new_models,
                )
                ai_model.validated_save()
                created += 1
                self.logger.info("Created AI Model.", extra={"object": ai_model})
                continue

            if entry["description"] and not ai_model.description:
                ai_model.description = entry["description"]
                ai_model.validated_save()
                updated += 1
                self.logger.info("Updated the description.", extra={"object": ai_model})

        return created, updated

    def report_missing(self, provider, discovered):
        """Log every AIModel record the provider no longer offers. Delete nothing."""
        discovered_names = {entry["name"] for entry in discovered}
        for ai_model in provider.ai_models.all():
            if ai_model.name not in discovered_names:
                self.logger.warning(
                    "The provider no longer offers this model. The record was kept.",
                    extra={"object": ai_model},
                )


class MCPServerDiscovery(Job):
    """Read each MCP server's advertised capabilities and record them."""

    mcp_server = ObjectVar(
        model=MCPServer,
        required=False,
        label="MCP Server",
        description="Leave blank to discover every enabled server.",
    )
    remove_stale = BooleanVar(
        default=False,
        label="Remove stale tools",
        description=(
            "Delete tools the server no longer advertises instead of disabling them. Off by "
            "default: a server having a bad minute should not erase a reviewed registry."
        ),
    )

    class Meta:  # pylint: disable=too-few-public-methods
        """Job metadata."""

        name = "MCP Server Discovery"
        description = "Read each MCP server's tool list and record what it advertises."
        has_sensitive_variables = False
        soft_time_limit = 1800
        time_limit = 2100

    def run(self, *, mcp_server=None, remove_stale=False):  # pylint: disable=arguments-differ
        """Discover one server, or every enabled one, and report what moved."""
        servers = self._targets(mcp_server)
        if not servers:
            self.logger.warning("No enabled MCP server to discover.")
            return "No enabled MCP server to discover."

        mcp.require_client()

        succeeded, skipped, failed = [], [], []
        for server in servers:
            if server.transport not in mcp.DISCOVERABLE_TRANSPORTS:
                self.logger.warning(
                    "Skipped %s: a Nautobot worker cannot open the '%s' transport. Register its tools by hand.",
                    server,
                    server.transport,
                    extra={"object": server},
                )
                skipped.append(server)
                continue
            if self._discover_one(server, remove_stale):
                succeeded.append(server)
            else:
                failed.append(server)

        summary = f"{len(succeeded)} server(s) discovered, {len(skipped)} skipped, {len(failed)} failed."
        if failed:
            self.fail(f"{summary} Failed: {', '.join(str(server) for server in failed)}.")
        return summary

    def _targets(self, mcp_server):
        """Return the servers this run covers: the one asked for, or every enabled one."""
        if mcp_server is not None:
            return [mcp_server]
        return list(MCPServer.objects.filter(enabled=True).select_related("external_integration"))

    def _discover_one(self, server, remove_stale):
        """Discover one server, catching every failure.

        Args:
            server: The MCPServer to read.
            remove_stale: Delete tools the server no longer advertises.

        Returns:
            bool: True when the run succeeded.
        """
        try:
            report = mcp.discover(server, remove_stale=remove_stale)
        except MCPError as error:
            self.logger.error("Discovery failed for %s: %s", server, error, extra={"object": server})
            return False

        self.logger.info("Discovered %s: %s", server, report.summary(), extra={"object": server})
        for tool in report.added:
            self.logger.info(
                "New tool %s. Review whether it writes.%s",
                tool.name,
                "" if tool.enabled else " It is disabled until somebody enables it.",
                extra={"object": tool},
            )
        disabled_by_change = set(report.disabled_by_change)
        for tool in report.definition_changed:
            if tool in disabled_by_change:
                self.logger.warning(
                    "Tool %s changed its definition and has been disabled. Review it, then enable it again.",
                    tool.name,
                    extra={"object": tool},
                )
                continue
            self.logger.warning(
                "Tool %s changed its definition since it was last read. Review it again.",
                tool.name,
                extra={"object": tool},
            )
        for tool in report.missing:
            self.logger.warning(
                "Tool %s is no longer advertised and has been disabled.", tool.name, extra={"object": tool}
            )
        for label in report.removed:
            self.logger.warning("Deleted %s: no longer advertised.", label, extra={"object": server})
        return True


jobs = [DiscoverAIModels, MCPServerDiscovery]
register_jobs(*jobs)
