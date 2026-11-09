"""Command-line interface."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path

import click

from cronlens import __version__
from cronlens.analysis import AnalysisOptions, CollisionScope, analyze
from cronlens.config import FAIL_ON_CHOICES, Config, ConfigError, find_config, load_config
from cronlens.explain import describe
from cronlens.expr import CronParseError, parse
from cronlens.models import Severity
from cronlens.report import FORMATS, ScanSummary, render
from cronlens.rules import RULES
from cronlens.schedule import RunKind, TimezoneError, load_timezone, next_runs
from cronlens.sources import discover

_RUN_NOTES = {
    RunKind.NORMAL: "",
    RunKind.SKIPPED: "  (time skipped by DST change)",
    RunKind.REPEATED: "  (time occurs twice: DST change)",
}


def _parse_moment(value: str | None) -> dt.datetime:
    if value is None:
        return dt.datetime.now(dt.UTC)
    try:
        moment = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise click.BadParameter(f"not an ISO 8601 date-time: {value!r}") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.UTC)
    return moment


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="cronlens")
def main() -> None:
    """Find problems in cron schedules before they cost you a missed job."""


@main.command()
@click.argument("expression")
@click.option("--tz", "timezone", default="UTC", show_default=True, help="IANA time zone.")
@click.option(
    "-n",
    "--count",
    default=5,
    show_default=True,
    type=click.IntRange(0, 1000),
    help="Number of upcoming runs to list.",
)
@click.option("--from", "start", metavar="DATETIME", help="ISO 8601 start time (default: now).")
def explain(expression: str, timezone: str, count: int, start: str | None) -> None:
    """Describe EXPRESSION in plain English and list its next runs."""
    try:
        expr = parse(expression)
        zone = load_timezone(timezone)
    except (CronParseError, TimezoneError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(describe(expr) + f" ({timezone})")
    if expr.uses_or_semantics:
        click.echo(
            "Note: both day-of-month and day-of-week are set, so a day matches if EITHER does."
        )
    if count == 0:
        return
    runs = next_runs(expr, zone, _parse_moment(start), count)
    if not runs:
        click.echo("This expression never fires.")
        return
    click.echo("Next runs:")
    for run in runs:
        local = run.local.strftime("%a %Y-%m-%d %H:%M")
        utc = run.instant.strftime("%Y-%m-%d %H:%M UTC")
        click.echo(f"  {local}  ({utc}){_RUN_NOTES[run.kind]}")


class _ConfigProblem(click.ClickException):
    exit_code = 2


def _load_settings(config_path: Path | None) -> Config:
    try:
        path = config_path or find_config(Path.cwd())
        return load_config(path) if path else Config()
    except ConfigError as exc:
        raise _ConfigProblem(str(exc)) from exc


def _check_timezone(name: str | None) -> None:
    if name is None:
        return
    try:
        load_timezone(name)
    except TimezoneError as exc:
        raise click.BadParameter(str(exc), param_hint="--default-tz") from exc


_PATHS = click.argument("paths", nargs=-1, type=click.Path(path_type=Path), metavar="[PATH]...")
_CONFIG = click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    envvar="CRONLENS_CONFIG",
    help="Settings file (default: nearest cronlens.toml or pyproject.toml).",
)
_DEFAULT_TZ = click.option(
    "--default-tz",
    metavar="ZONE",
    envvar="CRONLENS_DEFAULT_TZ",
    help="Zone for crontabs and CronJobs that do not name one (default: UTC).",
)
_EXCLUDE = click.option(
    "--exclude", multiple=True, metavar="GLOB", help="Skip paths matching GLOB. Repeatable."
)


@main.command()
@_PATHS
@click.option(
    "-f", "--format", "fmt", type=click.Choice(FORMATS), default="text", show_default=True
)
@click.option(
    "-o", "--output", type=click.Path(dir_okay=False, path_type=Path), help="Write report here."
)
@_CONFIG
@_DEFAULT_TZ
@_EXCLUDE
@click.option(
    "--fail-on",
    type=click.Choice(FAIL_ON_CHOICES),
    envvar="CRONLENS_FAIL_ON",
    help="Lowest severity that makes the exit code 1 (default: warning).",
)
@click.option("--disable", multiple=True, metavar="RULE", help="Turn off a rule. Repeatable.")
@click.option(
    "--collision-threshold",
    type=click.IntRange(1, 1000),
    metavar="N",
    help="Report minutes where more than N jobs start (default: 3).",
)
@click.option(
    "--collision-scope",
    type=click.Choice([s.value for s in CollisionScope]),
    help="Which jobs can collide: same source kind, same file, or all (default: source).",
)
@click.option("--now", metavar="DATETIME", help="Analyse as if it were this ISO 8601 time.")
def scan(
    paths: tuple[Path, ...],
    fmt: str,
    output: Path | None,
    config_path: Path | None,
    default_tz: str | None,
    exclude: tuple[str, ...],
    fail_on: str | None,
    disable: tuple[str, ...],
    collision_threshold: int | None,
    collision_scope: str | None,
    now: str | None,
) -> None:
    """Check every schedule found under PATH (default: the current directory).

    Exit status: 0 when nothing reaches --fail-on, 1 when something does,
    2 for usage or configuration errors.
    """
    settings = _load_settings(config_path)
    _check_timezone(default_tz)
    unknown = [r for r in disable if r not in RULES]
    if unknown:
        raise click.BadParameter(f"unknown rule(s) {', '.join(unknown)}", param_hint="--disable")

    settings = dataclasses.replace(
        settings,
        default_timezone=default_tz or settings.default_timezone,
        fail_on=fail_on or settings.fail_on,
        collision_threshold=collision_threshold or settings.collision_threshold,
        collision_scope=(
            CollisionScope(collision_scope) if collision_scope else settings.collision_scope
        ),
        disable=settings.disable + disable,
        exclude=settings.exclude + exclude,
    )

    result = discover(list(paths) or [Path()], exclude=settings.exclude)
    options = AnalysisOptions(
        now=_parse_moment(now),
        default_timezone=settings.default_timezone,
        collision_threshold=settings.collision_threshold,
        collision_window_days=settings.collision_window_days,
        collision_scope=settings.collision_scope,
        disabled=frozenset(settings.disable),
    )
    findings = analyze(result, options)
    summary = ScanSummary(jobs=len(result.jobs), files=len({j.location.path for j in result.jobs}))
    report = render(fmt, findings, summary)
    if output:
        output.write_text(click.unstyle(report), encoding="utf-8")
    else:
        click.echo(report, nl=False)

    if settings.fail_on != "never":
        threshold = Severity.from_label(settings.fail_on)
        if any(f.severity >= threshold for f in findings):
            raise SystemExit(1)


@main.command(name="list")
@_PATHS
@_CONFIG
@_DEFAULT_TZ
@_EXCLUDE
@click.option("--json", "as_json", is_flag=True, help="Print JSON instead of a table.")
@click.option("--now", metavar="DATETIME", help="Compute next runs from this ISO 8601 time.")
def list_jobs(
    paths: tuple[Path, ...],
    config_path: Path | None,
    default_tz: str | None,
    exclude: tuple[str, ...],
    as_json: bool,
    now: str | None,
) -> None:
    """List every schedule found under PATH with its next run."""
    settings = _load_settings(config_path)
    _check_timezone(default_tz)
    zone_default = default_tz or settings.default_timezone
    start = _parse_moment(now)
    result = discover(list(paths) or [Path()], exclude=settings.exclude + exclude)

    rows = []
    for job in result.jobs:
        zone_name = job.timezone or zone_default
        row = {
            "path": job.location.path,
            "line": job.location.line,
            "source": job.source.value,
            "name": job.name,
            "schedule": job.schedule,
            "timezone": zone_name,
            "timezone_explicit": job.timezone is not None,
            "description": None,
            "next_run_utc": None,
        }
        try:
            expr = parse(job.schedule)
            runs = next_runs(expr, load_timezone(zone_name), start, 1)
        except (CronParseError, TimezoneError) as exc:
            row["description"] = f"invalid: {exc}"
        else:
            row["description"] = describe(expr)
            if runs:
                row["next_run_utc"] = runs[0].instant.isoformat()
        rows.append(row)

    if as_json:
        click.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        click.echo("No schedules found.")
        return
    for row in rows:
        zone = row["timezone"] if row["timezone_explicit"] else f"{row['timezone']} (assumed)"
        next_run = row["next_run_utc"] or "never"
        click.echo(f"{row['path']}:{row['line']}  {row['name']}")
        click.echo(f"    {row['schedule']}  [{zone}]  {row['description']}")
        click.echo(f"    next run: {next_run}")


@main.command(name="rules")
def list_rules() -> None:
    """List the checks cronlens runs."""
    for r in RULES.values():
        click.echo(f"{r.id}  {r.name:<26} {r.severity.label:<8} {r.summary}")
