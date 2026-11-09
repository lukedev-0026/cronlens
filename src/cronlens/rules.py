"""The catalogue of checks cronlens runs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from cronlens.models import Severity

__all__ = ["RULES", "Rule", "rule"]


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    severity: Severity
    summary: str


_ALL = [
    Rule("CL001", "unreadable-source", Severity.WARNING,
         "A file that looks like it holds schedules could not be read or parsed."),
    Rule("CL002", "invalid-expression", Severity.ERROR,
         "The cron expression is not valid five-field cron syntax."),
    Rule("CL003", "unknown-timezone", Severity.ERROR,
         "The time zone is not a known IANA zone name."),
    Rule("CL004", "never-fires", Severity.ERROR,
         "The expression names dates that do not exist, such as 30 February."),
    Rule("CL005", "rarely-fires", Severity.INFO,
         "The expression fires less than once a year, usually only on 29 February."),
    Rule("CL006", "dom-dow-or", Severity.WARNING,
         "Both day fields are restricted, so cron runs on days matching EITHER of them."),
    Rule("CL007", "dst-skipped-run", Severity.WARNING,
         "A run time falls in a daylight-saving gap and does not exist on that day."),
    Rule("CL008", "dst-repeated-run", Severity.WARNING,
         "A run time falls in a daylight-saving overlap and happens twice on that day."),
    Rule("CL009", "gha-interval-too-short", Severity.WARNING,
         "GitHub Actions runs scheduled workflows at most once every 5 minutes."),
    Rule("CL010", "gha-top-of-hour", Severity.INFO,
         "GitHub Actions schedules at minute 0 are the most likely to be delayed or dropped."),
    Rule("CL011", "k8s-timezone-in-schedule", Severity.ERROR,
         "Kubernetes does not support CRON_TZ= or TZ= inside spec.schedule."),
    Rule("CL012", "k8s-implicit-timezone", Severity.INFO,
         "A CronJob without spec.timeZone uses the controller manager's local time zone."),
    Rule("CL013", "start-collision", Severity.WARNING,
         "More jobs than the configured threshold start in the same minute."),
]  # fmt: skip

RULES: Mapping[str, Rule] = {r.id: r for r in _ALL}


def rule(rule_id: str) -> Rule:
    return RULES[rule_id]
