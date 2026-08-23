"""Jobs for nautobot_ai_models.

Two discovery jobs, and both only read. Each asks a remote endpoint what it offers and writes
the answer onto the registry. Neither grants anything, and neither deletes a record unless it
is told to.
"""

from django.core.exceptions import ObjectDoesNotExist
from nautobot.apps.exceptions import SecretError
from nautobot.apps.jobs import BooleanVar, Job, ObjectVar, register_jobs

from nautobot_ai_models import discovery
from nautobot_ai_models.models import AIModel, AIProvider, MCPServer
from nautobot_ai_models.services import mcp
from nautobot_ai_models.services.exceptions import MCPError

# Nautobot reads this module-level constant to group the Jobs in the UI.
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
        description="Limit discovery to one provider. Leave empty to run against every provider.",
    )
    enable_new_models = BooleanVar(
        default=True,
        description="Mark newly discovered models as enabled.",
    )

    def run(self, *, provider, enable_new_models):  # pylint: disable=arguments-differ
        """Discover models for one provider or for all of them."""
        providers = [provider] if provider is not None else list(AIProvider.objects.all())
        if not providers:
            self.logger.warning("No AI Providers are defined. Nothing to discover.")
            return

        for each_provider in providers:
            self.discover_provider(each_provider, enable_new_models)

    def discover_provider(self, provider, enable_new_models):
        """Sync the AIModel records for a single provider. Never delete a record."""
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
            # Log the exception type only. A message may carry a URL with an embedded credential.
            self.logger.failure(
                "Model discovery request failed: %s",
                type(error).__name__,
                extra={"object": provider},
            )
            return

        created, updated = self.sync_models(provider, discovered, enable_new_models)
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

            # Never overwrite enabled, num_predict, or temperature. A user may have set them by hand.
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
        # No job input carries a credential: they come from each server's secrets group at
        # connection time. False so this job can be scheduled, which is the point of it.
        has_sensitive_variables = False

    def run(self, mcp_server=None, remove_stale=False):  # pylint: disable=arguments-differ
        """Discover one server, or every enabled one, and report what moved."""
        servers = self._targets(mcp_server)
        if not servers:
            self.logger.warning("No enabled MCP server to discover.")
            return "No enabled MCP server to discover."

        # Resolved once, up front. A deployment installed without the 'discovery' extra should say
        # so before it starts reporting a failure against every server in turn.
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
            # One unreachable server must not hide the ones that worked, so this is said at the end
            # rather than raised at the point of failure.
            self.fail(f"{summary} Failed: {', '.join(str(server) for server in failed)}.")
        return summary

    def _targets(self, mcp_server):
        """The servers this run covers: the one asked for, or every enabled one."""
        if mcp_server is not None:
            return [mcp_server]
        return list(MCPServer.objects.filter(enabled=True).select_related("external_integration"))

    def _discover_one(self, server, remove_stale):
        """Discover one server. True when it worked.

        Every failure is caught. An operator running this against twenty servers wants the other
        nineteen done, and wants to be told which one did not answer.
        """
        try:
            report = mcp.discover(server, remove_stale=remove_stale)
        except MCPError as error:
            # The message never carries a header value or a token: `MCPConnection.__repr__` hides
            # them, and nothing here formats a connection into a log line.
            self.logger.error("Discovery failed for %s: %s", server, error, extra={"object": server})
            return False

        self.logger.info("Discovered %s: %s", server, report.summary(), extra={"object": server})
        for tool in report.added:
            self.logger.info(
                "New tool %s. Review whether it writes, then enable it.", tool.name, extra={"object": tool}
            )
        for tool in report.definition_changed:
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
