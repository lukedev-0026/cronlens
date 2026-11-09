"""Running the checks in :mod:`cronlens.rules` over discovered jobs."""

from __future__ import annotations

import datetime as dt
import enum
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import pairwise
from zoneinfo import ZoneInfo

from cronlens.explain import join_values
from cronlens.expr import CronExpression, CronParseError, parse
from cronlens.models import Finding, Location, ScheduledJob, SourceKind
from cronlens.rules import rule
from cronlens.schedule import (
    MAX_SEARCH_DAYS,
    RunKind,
    TimezoneError,
    iter_runs,
    load_timezone,
    resolve,
    transition_days,
)
from cronlens.sources.base import SourceResult
from cronlens.sources.kubernetes import SCHEDULE_TZ_PREFIX

__all__ = ["AnalysisOptions", "AnalyzedJob", "CollisionScope", "analyze", "analyze_job"]

GITHUB_MIN_INTERVAL_MINUTES = 5
_DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


class CollisionScope(enum.Enum):
    """Which jobs can collide with each other."""

    #: Jobs read by the same kind of source (all crontabs, all workflows, ...).
    SOURCE = "source"
    #: Jobs in the same file.
    FILE = "file"
    #: Every job, regardless of where it was found.
    ALL = "all"


@dataclass(frozen=True)
class AnalysisOptions:
    #: The moment analysis starts from; DST and collision checks look ahead from here.
    now: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    #: Zone for jobs whose source leaves the zone to the host.
    default_timezone: str = "UTC"
    #: Report a collision when more than this many jobs start in one minute.
    collision_threshold: int = 3
    collision_window_days: int = 7
    collision_scope: CollisionScope = CollisionScope.SOURCE
    #: Days ahead to search for daylight-saving changes.
    dst_window_days: int = 366
    disabled: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AnalyzedJob:
    job: ScheduledJob
    expr: CronExpression
    zone_name: str
    zone: ZoneInfo


def analyze(result: SourceResult, options: AnalysisOptions | None = None) -> list[Finding]:
    """Run every enabled check and return findings ordered by location."""
    options = options or AnalysisOptions()
    findings: list[Finding] = [
        _finding("CL001", error.message, error.location) for error in result.errors
    ]
    analyzed: list[AnalyzedJob] = []
    for job in result.jobs:
        job_findings, ok = analyze_job(job, options)
        findings.extend(job_findings)
        if ok is not None:
            analyzed.append(ok)
    findings.extend(_collisions(analyzed, options))
    enabled = [f for f in findings if f.rule_id not in options.disabled]
    return sorted(enabled, key=lambda f: (f.location, f.rule_id, f.message))


def analyze_job(
    job: ScheduledJob, options: AnalysisOptions
) -> tuple[list[Finding], AnalyzedJob | None]:
    """Check one job. Returns its findings and, if it could be parsed, the parsed job."""
    findings: list[Finding] = []
    loc = job.location

    if job.source is SourceKind.KUBERNETES and SCHEDULE_TZ_PREFIX in job.extras:
        findings.append(
            _finding(
                "CL011",
                f"spec.schedule starts with a time zone "
                f"({job.extras[SCHEDULE_TZ_PREFIX]}); Kubernetes does not support this. "
                "Move it to spec.timeZone.",
                loc,
                job,
            )
        )

    try:
        expr = parse(job.schedule)
    except CronParseError as exc:
        findings.append(_finding("CL002", str(exc), loc, job))
        return findings, None

    zone_name = job.timezone or options.default_timezone
    try:
        zone = load_timezone(zone_name)
    except TimezoneError as exc:
        findings.append(_finding("CL003", str(exc), loc, job))
        return findings, None

    if job.source is SourceKind.KUBERNETES and job.timezone is None:
        findings.append(
            _finding(
                "CL012",
                "no spec.timeZone, so the schedule follows the kube-controller-manager's "
                f"local time zone (assumed {zone_name} for these checks)",
                loc,
                job,
            )
        )

    first_date = _first_matching_date(expr, options.now.astimezone(zone).date())
    if first_date is None:
        findings.append(
            _finding("CL004", f"{expr.source!r} matches no real date, so it never runs", loc, job)
        )
        return findings, None

    findings.extend(_frequency_findings(job, expr, options, zone, first_date))
    if expr.uses_or_semantics:
        findings.append(_or_finding(job, expr))
    findings.extend(_dst_findings(job, expr, zone_name, zone, options))
    if job.source is SourceKind.GITHUB_ACTIONS:
        findings.extend(_github_findings(job, expr))
    return findings, AnalyzedJob(job, expr, zone_name, zone)


def _first_matching_date(expr: CronExpression, start: dt.date) -> dt.date | None:
    day = start
    for _ in range(MAX_SEARCH_DAYS):
        if expr.matches_date(day):
            return day
        day += dt.timedelta(days=1)
    return None


def _frequency_findings(
    job: ScheduledJob,
    expr: CronExpression,
    options: AnalysisOptions,
    zone: ZoneInfo,
    first_date: dt.date,
) -> list[Finding]:
    start = options.now.astimezone(zone).date()
    span = 4 * 365 + 1
    dates = [
        start + dt.timedelta(days=i)
        for i in range(span)
        if expr.matches_date(start + dt.timedelta(days=i))
    ]
    if len(dates) >= 4:
        return []
    when = ", ".join(d.isoformat() for d in dates) if dates else f"next on {first_date}"
    return [
        _finding(
            "CL005",
            f"{expr.source!r} runs on {len(dates)} day(s) in the next four years ({when})",
            job.location,
            job,
        )
    ]


def _or_finding(job: ScheduledJob, expr: CronExpression) -> Finding:
    dom = join_values(expr.days_of_month, str)
    dow = join_values(expr.days_of_week, lambda d: _DAY_NAMES[d])
    return _finding(
        "CL006",
        f"day-of-month ({dom}) and day-of-week ({dow}) are both set, so cron runs on days "
        "matching EITHER field, not both. To require both, check one inside the command.",
        job.location,
        job,
    )


def _dst_findings(
    job: ScheduledJob,
    expr: CronExpression,
    zone_name: str,
    zone: ZoneInfo,
    options: AnalysisOptions,
) -> list[Finding]:
    # A job that runs every hour loses or repeats one hour's runs at most,
    # which the next hour covers; flag only sparser schedules.
    if len(expr.hours) == 24:
        return []
    start = options.now.astimezone(zone).date()
    affected: dict[RunKind, list[dt.datetime]] = defaultdict(list)
    for day in transition_days(zone, start, options.dst_window_days):
        if not expr.matches_date(day):
            continue
        for time_of_day in expr.times_of_day:
            run = resolve(dt.datetime.combine(day, time_of_day), zone)
            if run.kind is not RunKind.NORMAL:
                affected[run.kind].append(run.local)

    findings = []
    if affected[RunKind.SKIPPED]:
        findings.append(
            _finding(
                "CL007",
                f"{_describe_times(affected[RunKind.SKIPPED])} does not exist in {zone_name} "
                "(clocks spring forward); depending on the cron daemon the run is skipped or "
                "moved. Schedule outside the change window or use UTC.",
                job.location,
                job,
            )
        )
    if affected[RunKind.REPEATED]:
        findings.append(
            _finding(
                "CL008",
                f"{_describe_times(affected[RunKind.REPEATED])} happens twice in {zone_name} "
                "(clocks fall back); depending on the cron daemon the job runs once or twice. "
                "Schedule outside the change window or use UTC.",
                job.location,
                job,
            )
        )
    return findings


def _describe_times(moments: list[dt.datetime]) -> str:
    first = moments[0]
    text = f"{first:%H:%M} on {first:%Y-%m-%d}"
    if len(moments) > 1:
        text += f" (and {len(moments) - 1} more run time(s) in the next year)"
    return text


def _github_findings(job: ScheduledJob, expr: CronExpression) -> list[Finding]:
    findings = []
    minutes_of_day = sorted(h * 60 + m for h in expr.hours for m in expr.minutes)
    gaps = [b - a for a, b in pairwise(minutes_of_day)]
    gaps.append(minutes_of_day[0] + 24 * 60 - minutes_of_day[-1])
    shortest = min(gaps)
    if shortest < GITHUB_MIN_INTERVAL_MINUTES:
        findings.append(
            _finding(
                "CL009",
                f"runs can be {shortest} minute(s) apart, but GitHub Actions runs scheduled "
                f"workflows at most every {GITHUB_MIN_INTERVAL_MINUTES} minutes",
                job.location,
                job,
            )
        )
    if 0 in expr.minutes and len(expr.minutes) < 60:
        findings.append(
            _finding(
                "CL010",
                "runs at minute 0; GitHub notes that scheduled runs are most often delayed "
                "or dropped at the start of each hour. Consider an odd minute such as 17.",
                job.location,
                job,
            )
        )
    return findings


def _collisions(analyzed: list[AnalyzedJob], options: AnalysisOptions) -> list[Finding]:
    if "CL013" in options.disabled or options.collision_window_days <= 0:
        return []
    start = options.now.replace(second=0, microsecond=0)
    end = start + dt.timedelta(days=options.collision_window_days)

    pools: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(analyzed):
        pools[_scope_key(item.job, options.collision_scope)].append(index)

    findings: list[Finding] = []
    for members in pools.values():
        if len(members) <= options.collision_threshold:
            continue
        starts: dict[dt.datetime, set[int]] = defaultdict(set)
        for index in members:
            item = analyzed[index]
            for run in iter_runs(item.expr, item.zone, start, end):
                starts[run.instant].add(index)
        groups: dict[frozenset[int], list[dt.datetime]] = defaultdict(list)
        for instant, jobs in starts.items():
            if len(jobs) > options.collision_threshold:
                groups[frozenset(jobs)].append(instant)
        for group in _maximal(groups):
            findings.append(_collision_finding(analyzed, group, sorted(groups[group]), options))
    return findings


def _scope_key(job: ScheduledJob, scope: CollisionScope) -> str:
    if scope is CollisionScope.FILE:
        return job.location.path
    if scope is CollisionScope.SOURCE:
        return job.source.value
    return ""


def _maximal(groups: Iterable[frozenset[int]]) -> list[frozenset[int]]:
    ordered = sorted(groups, key=lambda g: (-len(g), sorted(g)))
    kept: list[frozenset[int]] = []
    for group in ordered:
        if not any(group < other for other in kept):
            kept.append(group)
    return kept


def _collision_finding(
    analyzed: list[AnalyzedJob],
    group: frozenset[int],
    instants: list[dt.datetime],
    options: AnalysisOptions,
) -> Finding:
    jobs = sorted((analyzed[i].job for i in group), key=lambda j: j.location)
    names = ", ".join(j.name for j in jobs)
    return _finding(
        "CL013",
        f"{len(jobs)} jobs start in the same minute {len(instants)} time(s) in the next "
        f"{options.collision_window_days} days, first at {instants[0]:%Y-%m-%d %H:%M} UTC: "
        f"{names}. Stagger their start minutes.",
        jobs[0].location,
    )


def _finding(
    rule_id: str, message: str, location: Location, job: ScheduledJob | None = None
) -> Finding:
    r = rule(rule_id)
    return Finding(
        rule_id=r.id,
        rule_name=r.name,
        severity=r.severity,
        message=message,
        location=location,
        job=job.name if job else None,
    )
