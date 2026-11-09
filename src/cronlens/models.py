"""Data types shared across sources, checks and reporters."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

__all__ = ["Finding", "Location", "ScheduledJob", "Severity", "SourceKind"]


class SourceKind(enum.Enum):
    CRONTAB = "crontab"
    GITHUB_ACTIONS = "github-actions"
    KUBERNETES = "kubernetes"


class Severity(enum.IntEnum):
    INFO = 1
    WARNING = 2
    ERROR = 3

    @property
    def label(self) -> str:
        return self.name.lower()

    @classmethod
    def from_label(cls, label: str) -> Severity:
        try:
            return cls[label.upper()]
        except KeyError:
            raise ValueError(f"unknown severity {label!r}") from None


@dataclass(frozen=True, order=True)
class Location:
    """A position in a file. ``path`` is as given or discovered (POSIX separators)."""

    path: str
    line: int = 1


@dataclass(frozen=True)
class ScheduledJob:
    """A schedule found in a source file."""

    name: str
    schedule: str
    source: SourceKind
    location: Location
    #: IANA zone the scheduler applies, or None when the source leaves it
    #: to the host (crontab without CRON_TZ, CronJob without timeZone).
    timezone: str | None = None
    command: str | None = None
    #: Source-specific facts that checks may use, such as a time zone
    #: written into a Kubernetes schedule string.
    extras: dict[str, str] = field(default_factory=dict, compare=False, hash=False)


@dataclass(frozen=True)
class Finding:
    rule_id: str
    rule_name: str
    severity: Severity
    message: str
    location: Location
    job: str | None = None
