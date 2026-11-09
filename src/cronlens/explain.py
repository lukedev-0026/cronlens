"""Plain-English descriptions of cron expressions."""

from __future__ import annotations

import calendar
from collections.abc import Callable, Iterable

from cronlens.expr import CronExpression

__all__ = ["describe", "join_values"]

_DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
_ALL_MINUTES = frozenset(range(60))
_ALL_HOURS = frozenset(range(24))
_ALL_DOM = frozenset(range(1, 32))
_ALL_MONTHS = frozenset(range(1, 13))
_ALL_DOW = frozenset(range(7))
_MAX_LISTED_TIMES = 8


def describe(expr: CronExpression) -> str:
    """Describe when ``expr`` fires, for example ``"At 09:00 on Monday through Friday"``."""
    pieces = [_time_phrase(expr)]
    day = _day_phrase(expr)
    if day:
        pieces.append(day)
    if expr.months != _ALL_MONTHS:
        pieces.append("in " + join_values(expr.months, _month_name))
    text = " ".join(pieces)
    return text[0].upper() + text[1:]


def _time_phrase(expr: CronExpression) -> str:
    minutes, hours = expr.minutes, expr.hours
    if minutes == _ALL_MINUTES:
        if hours == _ALL_HOURS:
            return "every minute"
        if len(hours) == 1:
            hour = next(iter(hours))
            return f"every minute from {hour:02d}:00 to {hour:02d}:59"
        return "every minute during hours " + join_values(hours, str)

    minute_step = _step_of(minutes, 0, 59)
    if hours == _ALL_HOURS:
        if minute_step and minute_step > 1:
            return f"every {minute_step} minutes"
        if len(minutes) == 1:
            return f"at minute {next(iter(minutes))} past every hour"
        return f"at minutes {join_values(minutes, str)} past every hour"

    if len(minutes) * len(hours) <= _MAX_LISTED_TIMES:
        return "at " + _join([f"{h:02d}:{m:02d}" for h in sorted(hours) for m in sorted(minutes)])

    hour_step = _step_of(hours, 0, 23)
    if hour_step and hour_step > 1 and len(minutes) == 1:
        return f"at minute {next(iter(minutes))} past every {hour_step} hours"
    minute_word = "minute" if len(minutes) == 1 else "minutes"
    return f"at {minute_word} {join_values(minutes, str)} past hours {join_values(hours, str)}"


def _day_phrase(expr: CronExpression) -> str:
    dom_phrase = ""
    if expr.days_of_month != _ALL_DOM:
        dom_phrase = "on the " + join_values(expr.days_of_month, _ordinal) + " of the month"
    dow_phrase = ""
    if expr.days_of_week != _ALL_DOW:
        dow_phrase = "on " + join_values(expr.days_of_week, lambda d: _DAY_NAMES[d])

    if dom_phrase and dow_phrase:
        joiner = " or " if expr.uses_or_semantics else " if it is also "
        if expr.uses_or_semantics:
            return f"{dom_phrase}{joiner}{dow_phrase}"
        return f"{dom_phrase}{joiner}{dow_phrase.removeprefix('on ')}"
    return dom_phrase or dow_phrase


def _step_of(values: frozenset[int], low: int, high: int) -> int | None:
    """Return n if ``values`` is exactly ``low-high/n`` starting at ``low``."""
    ordered = sorted(values)
    if len(ordered) < 2 or ordered[0] != low:
        return None
    step = ordered[1] - ordered[0]
    if list(range(low, high + 1, step)) == ordered:
        return step
    return None


def join_values(values: Iterable[int], name: Callable[[int], str]) -> str:
    """Join sorted values, collapsing runs of three or more into ranges."""
    ordered = sorted(values)
    groups: list[str] = []
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[j] + 1:
            j += 1
        if j - i >= 2:
            groups.append(f"{name(ordered[i])} through {name(ordered[j])}")
        else:
            groups.extend(name(v) for v in ordered[i : j + 1])
        i = j + 1
    return _join(groups)


def _join(items: list[str]) -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _month_name(n: int) -> str:
    return calendar.month_name[n]
