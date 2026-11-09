"""Turning a cron expression into concrete run times in a time zone.

Cron schedules are written in wall-clock time. Around a daylight-saving
change, a wall-clock time can be skipped (spring forward) or occur twice
(fall back). Each :class:`ScheduledRun` records which of these applies so
that callers can report it instead of silently picking one interpretation.
"""

from __future__ import annotations

import datetime as dt
import enum
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cronlens.expr import CronExpression

__all__ = [
    "MAX_SEARCH_DAYS",
    "RunKind",
    "ScheduledRun",
    "TimezoneError",
    "iter_runs",
    "load_timezone",
    "next_runs",
    "resolve",
    "transition_days",
]

#: How far ahead to search before concluding there is no further run.
#: Twenty-nine years covers every combination of leap day and weekday.
MAX_SEARCH_DAYS = 366 * 29

UTC = dt.UTC


class TimezoneError(ValueError):
    """Raised for an unknown IANA time zone name."""


class RunKind(enum.Enum):
    """How a wall-clock run time maps onto real time."""

    NORMAL = "normal"
    #: The wall-clock time does not exist: the clocks skipped over it.
    SKIPPED = "skipped"
    #: The wall-clock time happens twice: the clocks went back over it.
    REPEATED = "repeated"


@dataclass(frozen=True)
class ScheduledRun:
    """One run of a schedule."""

    #: Wall-clock time in the schedule's time zone, without tzinfo.
    local: dt.datetime
    #: The real moment, in UTC. For a skipped time this is the moment the
    #: wall clock would show after shifting forward; for a repeated time it
    #: is the first occurrence.
    instant: dt.datetime
    kind: RunKind


@lru_cache(maxsize=256)
def load_timezone(name: str) -> ZoneInfo:
    """Load an IANA time zone, raising :class:`TimezoneError` if unknown."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise TimezoneError(f"unknown time zone {name!r}") from exc


def resolve(local: dt.datetime, zone: ZoneInfo) -> ScheduledRun:
    """Map a naive wall-clock time in ``zone`` onto a :class:`ScheduledRun`."""
    first = local.replace(tzinfo=zone, fold=0)
    second = local.replace(tzinfo=zone, fold=1)
    instant = first.astimezone(UTC)
    if first.utcoffset() == second.utcoffset():
        return ScheduledRun(local, instant, RunKind.NORMAL)
    # For a skipped time, fold=0 applies the offset from before the change,
    # which lands just past the gap (02:30 becomes 03:30 when clocks jump an
    # hour), so the round trip differs from the requested wall-clock time.
    round_trip = instant.astimezone(zone).replace(tzinfo=None)
    kind = RunKind.REPEATED if round_trip == local else RunKind.SKIPPED
    return ScheduledRun(local, instant, kind)


def iter_runs(
    expr: CronExpression,
    zone: ZoneInfo,
    start: dt.datetime,
    end: dt.datetime | None = None,
) -> Iterator[ScheduledRun]:
    """Yield runs strictly after ``start`` (and before ``end``) in wall-clock order.

    ``start`` and ``end`` must be timezone-aware. Without ``end`` the search
    stops after :data:`MAX_SEARCH_DAYS` days, so an expression that can never
    fire yields nothing rather than looping forever.
    """
    if start.tzinfo is None or (end is not None and end.tzinfo is None):
        raise ValueError("start and end must be timezone-aware")
    first_day = start.astimezone(zone).date()
    last_day = (
        end.astimezone(zone).date() + dt.timedelta(days=1)
        if end is not None
        else first_day + dt.timedelta(days=MAX_SEARCH_DAYS)
    )
    times = expr.times_of_day
    day = first_day
    while day <= last_day:
        if expr.matches_date(day):
            for time_of_day in times:
                run = resolve(dt.datetime.combine(day, time_of_day), zone)
                if run.instant <= start:
                    continue
                if end is not None and run.instant >= end:
                    continue
                yield run
        day += dt.timedelta(days=1)


def next_runs(
    expr: CronExpression,
    zone: ZoneInfo,
    start: dt.datetime,
    count: int,
) -> list[ScheduledRun]:
    """Return up to ``count`` runs after ``start``."""
    if count < 1:
        return []
    runs: list[ScheduledRun] = []
    for run in iter_runs(expr, zone, start):
        runs.append(run)
        if len(runs) == count:
            break
    return runs


def transition_days(zone: ZoneInfo, start: dt.date, days: int) -> list[dt.date]:
    """Return the local dates in ``[start, start + days)`` with a UTC-offset change."""
    result: list[dt.date] = []
    previous = _offset_at_midnight(zone, start)
    for i in range(days):
        day = start + dt.timedelta(days=i)
        following = _offset_at_midnight(zone, day + dt.timedelta(days=1))
        if following != previous:
            result.append(day)
        previous = following
    return result


def _offset_at_midnight(zone: ZoneInfo, day: dt.date) -> dt.timedelta | None:
    return dt.datetime.combine(day, dt.time(0, 0), tzinfo=zone).utcoffset()
