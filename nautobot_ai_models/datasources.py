"""Load Python tools from a Git repository.

A repository that provides AI tools carries an `ai_tools` module. Nautobot clones the repository,
this module imports it, and each `@register_ai_tool` fills the in-process registry that an
installed app also fills. The sync then writes one `AITool` record of kind `git` for each tool.

A registry is per process, so only the worker that ran the sync holds the tools. `load_tool()`
imports on demand from the repository the record names, and the agent builder calls it on a miss.

A record outlives the code until the repository goes. A repository that drops a tool keeps the
record, disabled and reported, because the name may still be on an approved call.
`AITool.git_repository` cascades on a delete, and `AIAgentTool.ai_tool` protects a record that an
agent is bound to.

NOTE: A record names a repository and a fixed module in it. It never names an import path.
"""

import logging
import os

from django.conf import settings
from nautobot.apps.datasources import DatasourceContent

try:
    from nautobot.core.utils.module_loading import (
        check_name_safe_to_import_privately,
        import_modules_privately,
    )
    from nautobot.extras.datasources.git import ensure_git_repository

    GIT_SUPPORT_ERROR = None
except ImportError as error:  # pragma: no cover
    check_name_safe_to_import_privately = import_modules_privately = ensure_git_repository = None
    GIT_SUPPORT_ERROR = (
        "This Nautobot no longer exposes the private-import helpers this datasource is built on "
        f"({error}). Git-sourced AI tools are unavailable until the app is updated."
    )

from nautobot_ai_models import tools
from nautobot_ai_models.choices import AIToolKindChoices

logger = logging.getLogger(__name__)

CONTENT_IDENTIFIER = "nautobot_ai_models.aitool"

TOOLS_MODULE = "ai_tools"


def module_prefix(slug):
    """The module name a repository's tools are imported under.

    Args:
        slug: The repository slug.

    Returns:
        str: The module name, such as `my_repo.ai_tools`.
    """
    return f"{slug}.{TOOLS_MODULE}"


def provides_tools(repository):
    """Whether this repository is ticked to carry AI tools.

    Args:
        repository: The GitRepository record.

    Returns:
        bool: True when the repository provides this content.
    """
    return CONTENT_IDENTIFIER in (repository.provided_contents or [])


def has_tools_module(repository):
    """Whether the clone on this filesystem holds an `ai_tools` module.

    Args:
        repository: The GitRepository record.

    Returns:
        bool: True when `ai_tools/` or `ai_tools.py` is there.
    """
    root = repository.filesystem_path
    return os.path.isdir(os.path.join(root, TOOLS_MODULE)) or os.path.isfile(os.path.join(root, f"{TOOLS_MODULE}.py"))


def import_tools(repository, *, ignore_import_errors=True):
    """Unload this repository's tools, then import them again from the clone on disk.

    The unload is what makes a removed tool disappear. Without it, a tool that the repository
    deleted stays registered for the life of the process, and nothing ever reports its record as
    missing.

    Args:
        repository: The GitRepository record.
        ignore_import_errors: Log an import failure instead of raising it.

    Returns:
        dict: The repository's tools, keyed by name. Empty when nothing was imported.

    Raises:
        ValueError: The repository slug is not safe to import as a module name.
        FileNotFoundError: The repository provides tools and has no `ai_tools` module.
    """
    if GIT_SUPPORT_ERROR is not None:
        logger.error(GIT_SUPPORT_ERROR)
        if ignore_import_errors:
            return {}
        raise ImportError(GIT_SUPPORT_ERROR)

    permitted, reason = check_name_safe_to_import_privately(repository.slug)
    if not permitted:
        message = f"The repository slug {repository.slug!r} is invalid as it is {reason}"
        logger.error(message)
        if ignore_import_errors:
            return {}
        raise ValueError(message)

    if not provides_tools(repository):
        return {}

    prefix = module_prefix(repository.slug)
    tools.unregister_module(prefix)

    if not has_tools_module(repository):
        message = f"No `{TOOLS_MODULE}` module found in Git repository {repository}"
        logger.error(message)
        if ignore_import_errors:
            return {}
        raise FileNotFoundError(message)

    import_modules_privately(
        settings.GIT_ROOT,
        module_path=[repository.slug, TOOLS_MODULE],
        ignore_import_errors=ignore_import_errors,
    )
    return tools.tools_from_module(prefix)


def load_tool(ai_tool):
    """Find the callable for one Git-sourced record, and import its repository if this process must.

    The agent builder calls this when a lookup misses. This function makes the clone current in
    this process, imports the fixed `ai_tools` module in it, and looks the name up again.

    Args:
        ai_tool: The AITool record, of kind `git`.

    Returns:
        RegisteredTool | None: The tool, or None when the repository no longer declares it.
    """
    if ai_tool.kind != AIToolKindChoices.GIT or ai_tool.git_repository is None:
        return None

    repository = ai_tool.git_repository
    try:
        ensure_git_repository(repository, logger=logger, head=repository.current_head)
        import_tools(repository, ignore_import_errors=False)
    except Exception as error:  # pylint: disable=broad-except
        logger.error("Could not load tools from Git repository %s: %s", repository, error)
        return None

    return tools.get_registered_tool(ai_tool.name)


def _has_records(repository_record):
    """Whether this repository has AI tool records to tidy up.

    A repository that never provided tools is not this callback's business. A repository that
    provided them and stopped still is, so the guard asks both questions.

    Args:
        repository_record: The GitRepository to check.

    Returns:
        bool: True when records point at it.
    """
    from nautobot_ai_models.models import AITool  # pylint: disable=import-outside-toplevel

    return AITool.objects.filter(kind=AIToolKindChoices.GIT, git_repository=repository_record).exists()


def refresh_ai_tools(repository_record, job_result, delete=False):
    """Callback for a Git repository sync: reconcile the AI tools it declares.

    Args:
        repository_record: The GitRepository being refreshed.
        job_result: The JobResult to log against.
        delete: True when the repository is being deleted.
    """
    from nautobot_ai_models.models import AITool  # pylint: disable=import-outside-toplevel
    from nautobot_ai_models.services.tool_records import (  # pylint: disable=import-outside-toplevel
        GROUPING,
        sync_tool_records,
    )

    def log(level, message):
        """Write one message to the Job Result, under this content type's grouping.

        Args:
            level: `info`, `warning` or `error`, which are also the Nautobot log level values.
            message: What to say.
        """
        job_result.log(message, grouping=GROUPING, level_choice=level)

    if not provides_tools(repository_record) and not _has_records(repository_record):
        return

    records = AITool.objects.filter(kind=AIToolKindChoices.GIT, git_repository=repository_record)

    if delete:
        tools.unregister_module(module_prefix(repository_record.slug))
        log("warning", f"This repository is being deleted. Its {records.count()} AI tool record(s) go with it.")
        return

    if not provides_tools(repository_record):
        kept = records.update(enabled=False)
        tools.unregister_module(module_prefix(repository_record.slug))
        log(
            "warning",
            f"This repository no longer provides AI tools. Disabled and kept {kept} record(s), "
            "because an agent may still be bound to one.",
        )
        return

    try:
        found = import_tools(repository_record, ignore_import_errors=False)
    except Exception as error:  # pylint: disable=broad-except
        log("error", f"Could not load AI tools from this repository: {error}")
        return

    if not found:
        log(
            "warning",
            f"No tools were registered on loading the `{module_prefix(repository_record.slug)}` module. "
            "Did you miss a `@register_ai_tool` decorator? Or was there an error in the code?",
        )

    report = sync_tool_records(
        found,
        kind=AIToolKindChoices.GIT,
        git_repository=repository_record,
        existing=records,
        job_result=job_result,
    )
    log("info", f"AI tools: {report.summary()}")


datasource_contents = [
    (
        "extras.gitrepository",
        DatasourceContent(
            name="AI tools",
            content_identifier=CONTENT_IDENTIFIER,
            icon="mdi-tools",
            callback=refresh_ai_tools,
            weight=1000,
        ),
    ),
]
