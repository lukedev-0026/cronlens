"""Shared types for source readers."""

from __future__ import annotations

from dataclasses import dataclass, field

from cronlens.models import Location, ScheduledJob

__all__ = ["SourceError", "SourceResult"]


@dataclass(frozen=True)
class SourceError:
    """A file that looked relevant but could not be read."""

    location: Location
    message: str


@dataclass
class SourceResult:
    jobs: list[ScheduledJob] = field(default_factory=list)
    errors: list[SourceError] = field(default_factory=list)

    def extend(self, other: SourceResult) -> None:
        self.jobs.extend(other.jobs)
        self.errors.extend(other.errors)
