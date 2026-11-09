import datetime as dt

import pytest

from cronlens.expr import parse
from cronlens.schedule import (
    RunKind,
    TimezoneError,
    iter_runs,
    load_timezone,
    next_runs,
    resolve,
    transition_days,
)

UTC = dt.UTC
NEW_YORK = load_timezone("America/New_York")


def at(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=UTC)


def test_next_runs_utc() -> None:
    runs = next_runs(parse("*/20 * * * *"), load_timezone("UTC"), at(2026, 11, 9, 10, 5), 4)
    assert [r.local for r in runs] == [
        dt.datetime(2026, 11, 9, 10, 20),
        dt.datetime(2026, 11, 9, 10, 40),
        dt.datetime(2026, 11, 9, 11, 0),
        dt.datetime(2026, 11, 9, 11, 20),
    ]
    assert all(r.kind is RunKind.NORMAL for r in runs)


def test_start_is_exclusive() -> None:
    runs = next_runs(parse("0 * * * *"), load_timezone("UTC"), at(2026, 11, 9, 10, 0), 1)
    assert runs[0].local == dt.datetime(2026, 11, 9, 11, 0)


def test_next_runs_in_zone_reports_utc_instant() -> None:
    runs = next_runs(parse("0 9 * * *"), NEW_YORK, at(2026, 11, 9, 0, 0), 1)
    assert runs[0].local == dt.datetime(2026, 11, 9, 9, 0)
    assert runs[0].instant == at(2026, 11, 9, 14, 0)  # EST is UTC-5


def test_weekday_schedule_skips_weekend() -> None:
    runs = next_runs(parse("0 9 * * MON-FRI"), load_timezone("UTC"), at(2026, 11, 6, 12, 0), 2)
    # 2026-11-06 is a Friday; the next weekday runs are Monday and Tuesday.
    assert [r.local.date() for r in runs] == [dt.date(2026, 11, 9), dt.date(2026, 11, 10)]


def test_leap_day_schedule_finds_2028() -> None:
    runs = next_runs(parse("0 0 29 2 *"), load_timezone("UTC"), at(2026, 11, 9), 1)
    assert runs[0].local == dt.datetime(2028, 2, 29, 0, 0)


def test_never_firing_schedule_yields_nothing() -> None:
    assert next_runs(parse("0 0 30 2 *"), load_timezone("UTC"), at(2026, 11, 9), 1) == []


def test_zero_count() -> None:
    assert next_runs(parse("* * * * *"), load_timezone("UTC"), at(2026, 11, 9), 0) == []


def test_spring_forward_gap_is_skipped_kind() -> None:
    # 2026-03-08: New York clocks jump from 02:00 to 03:00.
    run = resolve(dt.datetime(2026, 3, 8, 2, 30), NEW_YORK)
    assert run.kind is RunKind.SKIPPED
    assert run.instant == at(2026, 3, 8, 7, 30)  # shown as 03:30 EDT


def test_fall_back_overlap_is_repeated_kind() -> None:
    # 2026-11-01: New York clocks go back from 02:00 to 01:00.
    run = resolve(dt.datetime(2026, 11, 1, 1, 30), NEW_YORK)
    assert run.kind is RunKind.REPEATED
    assert run.instant == at(2026, 11, 1, 5, 30)  # first occurrence, EDT


def test_daily_run_inside_gap() -> None:
    runs = list(
        iter_runs(parse("30 2 * * *"), NEW_YORK, at(2026, 3, 7, 0, 0), at(2026, 3, 10, 0, 0))
    )
    kinds = {r.local.date(): r.kind for r in runs}
    assert kinds == {
        dt.date(2026, 3, 7): RunKind.NORMAL,
        dt.date(2026, 3, 8): RunKind.SKIPPED,
        dt.date(2026, 3, 9): RunKind.NORMAL,
    }


def test_end_bound_is_exclusive() -> None:
    runs = list(
        iter_runs(parse("0 * * * *"), load_timezone("UTC"), at(2026, 1, 1), at(2026, 1, 1, 3))
    )
    assert [r.local.hour for r in runs] == [1, 2]


def test_naive_start_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        next(iter_runs(parse("* * * * *"), NEW_YORK, dt.datetime(2026, 1, 1)))


def test_unknown_timezone() -> None:
    with pytest.raises(TimezoneError, match="Mars/Olympus"):
        load_timezone("Mars/Olympus")


def test_transition_days_new_york_2026() -> None:
    assert transition_days(NEW_YORK, dt.date(2026, 1, 1), 365) == [
        dt.date(2026, 3, 8),
        dt.date(2026, 11, 1),
    ]


def test_transition_days_europe_2026() -> None:
    london = load_timezone("Europe/London")
    assert transition_days(london, dt.date(2026, 1, 1), 365) == [
        dt.date(2026, 3, 29),
        dt.date(2026, 10, 25),
    ]


def test_utc_has_no_transitions() -> None:
    assert transition_days(load_timezone("UTC"), dt.date(2026, 1, 1), 365) == []
