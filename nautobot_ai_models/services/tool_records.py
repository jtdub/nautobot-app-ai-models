"""Reconcile `AITool` records against the tools registered in this process.

The Sync AI Tools Job and the Git datasource both write these records. The policy lives here once,
so the two paths write them the same way:

* The sync creates a missing record with `enabled` set from `new_tools_enabled`.
* The sync reports a record whose definition digest moved. It disables that record when
  `disable_on_definition_change` is on.
* The sync reports a record whose tool is no longer registered, and leaves it alone. The name may
  still be on an approved call.
* The sync reports a record that belongs to another source, and leaves it alone. One name means
  one callable.
* The sync writes `writable` once, when it creates the record. A person decides it after that. The
  sync writes what the tool says about itself into `advertised_read_only`.
"""

import logging
from dataclasses import dataclass, field

from django.utils import timezone

from nautobot_ai_models.app_settings import DISABLE_ON_DEFINITION_CHANGE, NEW_TOOLS_ENABLED, app_setting
from nautobot_ai_models.models import AITool

logger = logging.getLogger(__name__)

GROUPING = "ai tools"


@dataclass
class SyncReport:
    """What one reconciliation did."""

    added: list = field(default_factory=list)
    seen: list = field(default_factory=list)
    changed: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    conflicted: list = field(default_factory=list)

    def summary(self):
        """One line, for a Job return value or a log record.

        Returns:
            str: The counts.
        """
        counts = (
            f"{len(self.added)} added, {len(self.seen)} seen, "
            f"{len(self.changed)} changed, {len(self.missing)} no longer registered"
        )
        if self.conflicted:
            counts += f", {len(self.conflicted)} left to another source"
        return f"{counts}."


def sync_tool_records(  # pylint: disable=too-many-arguments,too-many-locals
    registered, *, kind, existing, git_repository=None, dry_run=False, job_result=None
):
    """Reconcile the `AITool` table against a set of registered tools.

    Args:
        registered: The tools to write, keyed by name, as `tools.registered_tools()` returns them.
        kind: The `AIToolKindChoices` value these tools came from.
        existing: The records this set is responsible for, as a queryset. What is in it and not in
            `registered` is what has stopped being declared.
        git_repository: The repository they came from, for a Git sync.
        dry_run: Report what would change and write nothing.
        job_result: A JobResult to log against, as well as to the module logger.

    Returns:
        SyncReport: What changed, and what is no longer registered.
    """
    report = SyncReport()
    new_enabled = bool(app_setting(NEW_TOOLS_ENABLED))
    disable_on_change = bool(app_setting(DISABLE_ON_DEFINITION_CHANGE))
    now = timezone.now()

    by_name = AITool.objects.filter(name__in=registered).in_bulk(field_name="name")
    git_repository_id = git_repository.pk if git_repository is not None else None

    def report_it(level, message, record=None):
        getattr(logger, level)(message)
        if job_result is not None:
            job_result.log(message, obj=record, grouping=GROUPING, level_choice=level)

    for name, tool in registered.items():
        record = by_name.get(name)

        if record is not None and (record.kind != kind or record.git_repository_id != git_repository_id):
            report.conflicted.append(name)
            report_it(
                "warning",
                f"Tool {name} from {tool.module} is already recorded as "
                f"{record.get_kind_display()}{f' from {record.git_repository}' if record.git_repository else ''}. "
                "Leaving that record alone. Two sources cannot share a name; rename one of them.",
                record,
            )
            continue

        if record is None:
            report.added.append(name)
            report_it(
                "info",
                f"New tool {name} from {tool.module}. It arrives "
                f"{'enabled' if new_enabled else 'disabled, waiting for a review'}.",
            )
            if not dry_run:
                _create(tool, kind=kind, git_repository=git_repository, enabled=new_enabled, now=now)
            continue

        moved = record.definition_fingerprint != tool.definition_fingerprint
        if moved:
            report.changed.append(name)
            report_it(
                "warning",
                f"Tool {name} has changed since it was last seen."
                f"{' Disabling it.' if disable_on_change and record.enabled else ''}",
                record,
            )
        report.seen.append(name)
        if not dry_run:
            _update(
                record,
                tool,
                kind=kind,
                git_repository=git_repository,
                moved=moved,
                disable_on_change=disable_on_change,
                now=now,
            )

    for record in existing.exclude(name__in=registered):
        report.missing.append(record.name)
        report_it("warning", f"Tool {record.name} is no longer registered. Leaving the record in place.", record)

    return report


def _create(tool, *, kind, git_repository, enabled, now):
    """Write one new `AITool` record.

    Args:
        tool: The registered tool.
        kind: The `AIToolKindChoices` value.
        git_repository: The repository it came from, or None.
        enabled: What `new_tools_enabled` says.
        now: The timestamp to stamp `last_seen_at` with.
    """
    AITool(
        name=tool.name,
        description=tool.description,
        argument_schema=tool.argument_schema,
        kind=kind,
        module=tool.module,
        git_repository=git_repository,
        enabled=enabled,
        writable=tool.writable,
        advertised_read_only=not tool.writable,
        definition_fingerprint=tool.definition_fingerprint,
        last_seen_at=now,
    ).validated_save()


def _update(record, tool, *, kind, git_repository, moved, disable_on_change, now):  # pylint: disable=too-many-arguments
    """Refresh one `AITool` record from what is registered now.

    Args:
        record: The record to refresh.
        tool: The registered tool.
        kind: The `AIToolKindChoices` value.
        git_repository: The repository it came from, or None.
        moved: Whether the definition digest changed.
        disable_on_change: What `disable_on_definition_change` says.
        now: The timestamp to stamp `last_seen_at` with.
    """
    record.description = tool.description
    record.argument_schema = tool.argument_schema
    record.kind = kind
    record.module = tool.module
    record.git_repository = git_repository
    record.advertised_read_only = not tool.writable
    record.definition_fingerprint = tool.definition_fingerprint
    record.last_seen_at = now
    if moved and disable_on_change:
        record.enabled = False
    record.validated_save()
