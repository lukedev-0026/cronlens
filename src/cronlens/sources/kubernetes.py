"""Reader for Kubernetes manifests containing ``CronJob`` resources.

Reads ``spec.schedule`` and ``spec.timeZone`` from every ``CronJob`` in a
(possibly multi-document) manifest, including those inside ``kind: List``.
A ``CRON_TZ=``/``TZ=`` prefix inside ``spec.schedule`` is split off and
recorded so that a check can flag it: Kubernetes does not support it.
"""

from __future__ import annotations

import yaml
from yaml.nodes import Node

from cronlens.expr import split_timezone_prefix
from cronlens.models import Location, ScheduledJob, SourceKind
from cronlens.sources import _yaml
from cronlens.sources.base import SourceError, SourceResult

__all__ = ["SCHEDULE_TZ_PREFIX", "collect_manifest", "parse_manifests"]

#: ``ScheduledJob.extras`` key holding a time zone found inside spec.schedule.
SCHEDULE_TZ_PREFIX = "schedule_tz_prefix"


def parse_manifests(text: str, path: str) -> SourceResult:
    result = SourceResult()
    try:
        documents = _yaml.compose_documents(text)
    except yaml.YAMLError as exc:
        # Templated manifests (Helm, Kustomize patches with ${VARS}) are often
        # not valid YAML. Only report when the file clearly holds a CronJob.
        if "CronJob" in text:
            message = str(exc).strip().splitlines()[0]
            result.errors.append(
                SourceError(Location(path, _yaml.error_line(exc)), f"invalid YAML: {message}")
            )
        return result

    for document in documents:
        collect_manifest(document, path, result)
    return result


def collect_manifest(resource: Node, path: str, result: SourceResult) -> None:
    """Add the CronJobs in one manifest document (or List) to ``result``."""
    kind = _yaml.scalar(_yaml.get(resource, "kind"))
    if kind == "List":
        for item in _yaml.items(_yaml.get(resource, "items")):
            collect_manifest(item, path, result)
        return
    if kind != "CronJob":
        return

    name = _yaml.scalar(_yaml.get(_yaml.get(resource, "metadata"), "name")) or "unnamed"
    namespace = _yaml.scalar(_yaml.get(_yaml.get(resource, "metadata"), "namespace"))
    label = f"{namespace}/{name}" if namespace else name
    spec = _yaml.get(resource, "spec")
    schedule_node = _yaml.get(spec, "schedule")
    schedule = _yaml.scalar(schedule_node)
    if schedule_node is None or schedule is None:
        result.errors.append(
            SourceError(Location(path, _yaml.line_of(resource)), f"CronJob {label} has no schedule")
        )
        return

    prefix_zone, schedule = split_timezone_prefix(schedule)
    zone = _yaml.scalar(_yaml.get(spec, "timeZone")) or prefix_zone
    extras = {SCHEDULE_TZ_PREFIX: prefix_zone} if prefix_zone else {}
    result.jobs.append(
        ScheduledJob(
            name=f"CronJob {label}",
            schedule=schedule,
            source=SourceKind.KUBERNETES,
            location=Location(path, _yaml.line_of(schedule_node)),
            timezone=zone,
            extras=extras,
        )
    )
