"""Command-line interface."""

from __future__ import annotations

import datetime as dt

import click

from cronlens import __version__
from cronlens.explain import describe
from cronlens.expr import CronParseError, parse
from cronlens.schedule import RunKind, TimezoneError, load_timezone, next_runs

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
