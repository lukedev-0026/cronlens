"""Reader for GitHub Actions workflow files (``on.schedule[].cron``).

GitHub evaluates workflow schedules in UTC unless the schedule entry
names a ``timezone``.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import yaml
from yaml.nodes import Node

from cronlens.models import Location, ScheduledJob, SourceKind
from cronlens.sources import _yaml
from cronlens.sources.base import SourceError, SourceResult

__all__ = ["collect_workflow", "is_workflow", "parse_workflow"]


def parse_workflow(text: str, path: str) -> SourceResult:
    result = SourceResult()
    try:
        documents = _yaml.compose_documents(text)
    except yaml.YAMLError as exc:
        result.errors.append(
            SourceError(Location(path, _yaml.error_line(exc)), f"invalid YAML: {_first_line(exc)}")
        )
        return result

    for document in documents:
        collect_workflow(document, path, result)
    return result


def is_workflow(document: Node) -> bool:
    """True if a YAML document looks like a GitHub Actions workflow."""
    return _yaml.get(document, "on") is not None and _yaml.get(document, "jobs") is not None


def collect_workflow(document: Node, path: str, result: SourceResult) -> None:
    """Add the scheduled triggers of one workflow document to ``result``."""
    workflow = _yaml.scalar(_yaml.get(document, "name")) or PurePosixPath(path).stem
    schedule = _yaml.get(_yaml.get(document, "on"), "schedule")
    for index, entry in enumerate(_yaml.items(schedule)):
        cron_node = _yaml.get(entry, "cron")
        cron = _yaml.scalar(cron_node)
        if cron_node is None or cron is None:
            result.errors.append(
                SourceError(
                    Location(path, _yaml.line_of(entry)),
                    "schedule entry has no 'cron' string",
                )
            )
            continue
        zone = _yaml.scalar(_yaml.get(entry, "timezone"))
        result.jobs.append(
            ScheduledJob(
                name=f"{workflow} (schedule #{index + 1})",
                schedule=cron,
                source=SourceKind.GITHUB_ACTIONS,
                location=Location(path, _yaml.line_of(cron_node)),
                timezone=zone or "UTC",
            )
        )


def _first_line(error: yaml.YAMLError) -> str:
    return str(error).strip().splitlines()[0]
