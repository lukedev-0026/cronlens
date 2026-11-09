"""Parsing of standard five-field cron expressions.

The accepted syntax follows Vixie cron and its descendants (cronie, the
Debian cron package), which is also what Kubernetes and GitHub Actions accept:

* five fields: minute, hour, day of month, month, day of week;
* ``*``, single values, ranges ``a-b``, lists ``a,b`` and steps ``*/n``,
  ``a-b/n`` and ``a/n`` (the last meaning ``a-max/n``);
* three-letter month and weekday names, case-insensitive;
* ``7`` as an alias for Sunday;
* ``?`` as an alias for ``*`` in the two day fields (Kubernetes accepts it);
* the macros ``@yearly``, ``@annually``, ``@monthly``, ``@weekly``,
  ``@daily``, ``@midnight`` and ``@hourly``.

When both the day-of-month and day-of-week fields are restricted, a day
matches if *either* field matches. Following Vixie cron, a field counts as
restricted only if it does not start with ``*``, so ``*/2`` in the
day-of-month field keeps the usual "both must match" behaviour.
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass

__all__ = [
    "MACROS",
    "CronExpression",
    "CronParseError",
    "parse",
    "split_timezone_prefix",
]

MACROS: Mapping[str, str] = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

_MONTH_NAMES = {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name}
_DAY_NAMES = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}


class CronParseError(ValueError):
    """Raised when a cron expression cannot be parsed."""

    def __init__(self, message: str, expression: str, field: str | None = None) -> None:
        self.message = message
        self.expression = expression
        self.field = field
        where = f" in {field} field" if field else ""
        super().__init__(f"{message}{where}: {expression!r}")


@dataclass(frozen=True)
class _FieldSpec:
    name: str
    low: int
    high: int
    names: Mapping[str, int]
    star_high: int
    allows_question: bool = False


_FIELDS = (
    _FieldSpec("minute", 0, 59, {}, 59),
    _FieldSpec("hour", 0, 23, {}, 23),
    _FieldSpec("day-of-month", 1, 31, {}, 31, allows_question=True),
    _FieldSpec("month", 1, 12, _MONTH_NAMES, 12),
    _FieldSpec("day-of-week", 0, 7, _DAY_NAMES, 6, allows_question=True),
)


@dataclass(frozen=True)
class CronExpression:
    """A parsed cron expression.

    ``days_of_week`` uses 0 for Sunday through 6 for Saturday.
    """

    source: str
    minutes: frozenset[int]
    hours: frozenset[int]
    days_of_month: frozenset[int]
    months: frozenset[int]
    days_of_week: frozenset[int]
    dom_restricted: bool
    dow_restricted: bool

    @property
    def uses_or_semantics(self) -> bool:
        """True when a day matches if either day field matches."""
        return self.dom_restricted and self.dow_restricted

    def matches_date(self, day: dt.date) -> bool:
        """Return True if the expression fires at some time on ``day``."""
        if day.month not in self.months:
            return False
        dom_ok = day.day in self.days_of_month
        dow_ok = (day.weekday() + 1) % 7 in self.days_of_week
        if self.uses_or_semantics:
            return dom_ok or dow_ok
        return dom_ok and dow_ok

    def matches(self, moment: dt.datetime) -> bool:
        """Return True if the expression fires at the wall-clock minute of ``moment``."""
        return (
            moment.minute in self.minutes
            and moment.hour in self.hours
            and self.matches_date(moment.date())
        )

    @property
    def times_of_day(self) -> list[dt.time]:
        """Every wall-clock time at which the expression fires on a matching day."""
        return [dt.time(h, m) for h in sorted(self.hours) for m in sorted(self.minutes)]


def split_timezone_prefix(schedule: str) -> tuple[str | None, str]:
    """Split a leading ``CRON_TZ=Zone`` or ``TZ=Zone`` from a schedule.

    Returns ``(zone, rest)``; ``zone`` is None when there is no prefix.
    """
    stripped = schedule.strip()
    for prefix in ("CRON_TZ=", "TZ="):
        if stripped.startswith(prefix):
            zone, _, rest = stripped[len(prefix) :].partition(" ")
            return zone, rest.strip()
    return None, stripped


def parse(expression: str) -> CronExpression:
    """Parse a five-field cron expression or macro."""
    text = expression.strip()
    if not text:
        raise CronParseError("empty expression", expression)

    if text.startswith("@"):
        macro = text.lower()
        if macro == "@reboot":
            raise CronParseError("@reboot runs at startup and has no time schedule", expression)
        if macro not in MACROS:
            raise CronParseError(f"unknown macro {text}", expression)
        text = MACROS[macro]

    parts = text.split()
    if len(parts) != 5:
        hint = " (six-field expressions with seconds are not supported)" if len(parts) == 6 else ""
        raise CronParseError(f"expected 5 fields, got {len(parts)}{hint}", expression)

    values = [
        _parse_field(part, spec, expression) for part, spec in zip(parts, _FIELDS, strict=True)
    ]
    days_of_week = frozenset(0 if v == 7 else v for v in values[4])

    return CronExpression(
        source=expression.strip(),
        minutes=frozenset(values[0]),
        hours=frozenset(values[1]),
        days_of_month=frozenset(values[2]),
        months=frozenset(values[3]),
        days_of_week=days_of_week,
        dom_restricted=not _is_star(parts[2]),
        dow_restricted=not _is_star(parts[4]),
    )


def _is_star(field: str) -> bool:
    return field.startswith(("*", "?"))


def _parse_field(text: str, spec: _FieldSpec, expression: str) -> set[int]:
    values: set[int] = set()
    for item in text.split(","):
        if not item:
            raise CronParseError("empty list item", expression, spec.name)
        base, slash, step_text = item.partition("/")
        step = 1
        if slash:
            if not step_text.isdigit() or int(step_text) == 0:
                raise CronParseError(f"invalid step {step_text!r}", expression, spec.name)
            step = int(step_text)

        if base == "*" or (base == "?" and spec.allows_question):
            if base == "?" and slash:
                raise CronParseError("'?' cannot take a step", expression, spec.name)
            low, high = spec.low, spec.star_high
        elif "-" in base:
            start_text, _, end_text = base.partition("-")
            low = _parse_value(start_text, spec, expression)
            high = _parse_value(end_text, spec, expression)
            if low > high:
                raise CronParseError(f"range {base!r} runs backwards", expression, spec.name)
        else:
            low = _parse_value(base, spec, expression)
            high = spec.high if slash else low
            if slash and spec.name == "day-of-week":
                high = 6

        values.update(range(low, high + 1, step))
    return values


def _parse_value(text: str, spec: _FieldSpec, expression: str) -> int:
    if not text:
        raise CronParseError("missing value", expression, spec.name)
    lowered = text.lower()
    if lowered in spec.names:
        return spec.names[lowered]
    if not text.isdigit():
        raise CronParseError(f"invalid value {text!r}", expression, spec.name)
    value = int(text)
    if not spec.low <= value <= spec.high:
        raise CronParseError(
            f"value {value} out of range {spec.low}-{spec.high}", expression, spec.name
        )
    return value
