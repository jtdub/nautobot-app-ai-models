"""Discovery and maintenance jobs.

Each of the three discovery jobs asks a source what it offers, then writes the answer onto the
registry. A discovery job deletes no record unless you tell it to, because a source that has a bad
minute must not erase a reviewed registry.

The fourth job deletes, and it is the only one that does. The LangGraph checkpointer writes into
tables that Django does not manage, nothing cascades into them, and every shipped saver refuses to
prune them.
"""

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError
from nautobot.apps.exceptions import SecretError
from nautobot.apps.jobs import BooleanVar, IntegerVar, Job, ObjectVar, register_jobs
from nautobot.extras.models import GitRepository

from nautobot_ai_models import discovery, tools
from nautobot_ai_models.choices import AIToolKindChoices
from nautobot_ai_models.datasources import CONTENT_IDENTIFIER, module_prefix
from nautobot_ai_models.models import AIModel, AIProvider, AITool, MCPServer
from nautobot_ai_models.services import checkpoints, mcp
from nautobot_ai_models.services.exceptions import MCPError
from nautobot_ai_models.services.tool_records import sync_tool_records

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
        query_params={"enabled": True},
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


class SyncAITools(Job):
    """Write an AITool record for every Python tool an installed app registered.

    This is discovery, with the registry in place of a remote endpoint. A consuming app declares
    its tools with `@register_ai_tool` at import time, and this Job reconciles the table against
    what it declared.

    A tool that a Git repository declared belongs to the repository sync, not to this Job. Both
    write through `services.tool_records`, so both apply one policy.

    This Job reports a tool that is no longer registered. It never deletes one, because the name
    may still be on an approved call.
    """

    class Meta:  # pylint: disable=too-few-public-methods
        """Meta attributes."""

        name = "Sync AI Tools"
        description = "Reconcile AITool records with the Python tools registered in this process."
        has_sensitive_variables = False
        soft_time_limit = 120
        time_limit = 300

    dry_run = BooleanVar(
        default=False,
        label="Dry run",
        description="Report what would change and write nothing.",
    )

    def run(self, *, dry_run):  # pylint: disable=arguments-differ
        """Reconcile the AITool table with the in-process registry.

        This Job leaves a Git-sourced tool alone. The repository sync owns it, and a claim here would
        rewrite its record as `registered` and drop the repository it came from.

        Args:
            dry_run: Report only.

        Returns:
            str: A one-line summary.
        """
        registered = self._tools_this_job_owns()
        self.logger.info("%s tool(s) registered in this process, outside a Git repository.", len(registered))

        report = sync_tool_records(
            registered,
            kind=AIToolKindChoices.REGISTERED,
            existing=AITool.objects.filter(kind=AIToolKindChoices.REGISTERED),
            dry_run=dry_run,
            job_result=self.job_result,
        )
        return f"Dry run: {report.summary()}" if dry_run else report.summary()

    @staticmethod
    def _tools_this_job_owns():
        """Every registered tool that did not come from a Git repository.

        Returns:
            dict: The tools, keyed by name.
        """
        prefixes = tuple(
            module_prefix(slug)
            for slug in GitRepository.objects.filter(provided_contents__contains=CONTENT_IDENTIFIER).values_list(
                "slug", flat=True
            )
        )
        return {
            tool_name: tool
            for tool_name, tool in tools.registered_tools().items()
            if not any(tool.module == prefix or tool.module.startswith(f"{prefix}.") for prefix in prefixes)
        }


class PruneAgentThreads(Job):
    """Delete the LangGraph checkpoints of agent threads past the retention window.

    This is the only Job here that deletes anything. The checkpoint tables belong to the saver:
    Django never migrates them, no foreign key reaches them, and every shipped saver raises
    NotImplementedError from `prune`.

    This Job leaves a running thread alone, and a thread that waits for a person alone, whatever
    their age. A waiting thread holds the decision somebody was asked to make.
    """

    class Meta:  # pylint: disable=too-few-public-methods
        """Meta attributes."""

        name = "Prune Agent Threads"
        description = "Delete the checkpoints of finished agent threads past the retention window."
        has_sensitive_variables = False
        soft_time_limit = 600
        time_limit = 900

    days = IntegerVar(
        required=False,
        min_value=1,
        label="Retention days",
        description="Override the configured window for this run.",
    )
    delete_rows = BooleanVar(
        default=True,
        label="Delete the thread records too",
        description="Untick to drop only the checkpoint state and keep the record that the run happened.",
    )
    dry_run = BooleanVar(
        default=False,
        label="Dry run",
        description="Report what would be deleted and delete nothing.",
    )

    def run(self, *, days, delete_rows, dry_run):  # pylint: disable=arguments-differ
        """Prune expired threads.

        Args:
            days: Override the configured window.
            delete_rows: Also delete the AIAgentThread records.
            dry_run: Report only.

        Returns:
            str: A one-line summary.
        """
        window = days or checkpoints.retention_days()
        expired = checkpoints.expired_threads(days=window)
        count = expired.count()
        self.logger.info("%s finished thread(s) older than %s day(s).", count, window)

        if dry_run:
            for thread in expired[:20]:
                self.logger.info("Would prune %s.", thread, extra={"object": thread.agent})
            return f"Dry run: {count} thread(s) would be pruned."

        result = checkpoints.prune(days=window, delete_rows=delete_rows)
        return f"Pruned {result['threads']} thread(s) and {result['rows']} checkpoint row(s)."


jobs = [DiscoverAIModels, MCPServerDiscovery, SyncAITools, PruneAgentThreads]
register_jobs(*jobs)
