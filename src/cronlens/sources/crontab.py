"""Reader for crontab files.

Handles user crontabs (five schedule fields, then the command) and system
crontabs such as ``/etc/crontab`` and ``/etc/cron.d/*`` (five schedule
fields, a user name, then the command). ``CRON_TZ=Zone`` lines, as supported
by cronie, set the time zone for the lines that follow.
"""

from __future__ import annotations

import re

from cronlens.models import Location, ScheduledJob, SourceKind
from cronlens.sources.base import SourceResult

__all__ = ["parse_crontab"]

_ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def parse_crontab(text: str, path: str, *, system: bool = False) -> SourceResult:
    """Extract jobs from crontab ``text``. ``system`` selects the format with a user field."""
    result = SourceResult()
    zone: str | None = None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        assignment = _ASSIGNMENT.match(line)
        if assignment:
            if assignment.group(1) == "CRON_TZ":
                zone = _unquote(assignment.group(2).strip()) or None
            continue

        if line.startswith("@"):
            macro, _, rest = line.partition(" ")
            if macro.lower() == "@reboot":
                continue
            schedule, command = macro, rest.strip()
        else:
            parts = line.split(None, 5)
            schedule = " ".join(parts[:5])
            command = parts[5] if len(parts) > 5 else ""

        if system and command:
            _user, _, command = command.partition(" ")
            command = command.strip()

        result.jobs.append(
            ScheduledJob(
                name=_job_name(command, path, number),
                schedule=schedule,
                source=SourceKind.CRONTAB,
                location=Location(path, number),
                timezone=zone,
                command=command or None,
            )
        )
    return result


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _job_name(command: str, path: str, line: int) -> str:
    if command:
        program = command.split()[0].rsplit("/", 1)[-1]
        return f"{program} ({path}:{line})"
    return f"{path}:{line}"
