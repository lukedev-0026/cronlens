import datetime as dt

import pytest

from cronlens.expr import CronParseError, parse, split_timezone_prefix


def test_every_minute() -> None:
    expr = parse("* * * * *")
    assert expr.minutes == frozenset(range(60))
    assert expr.hours == frozenset(range(24))
    assert expr.days_of_month == frozenset(range(1, 32))
    assert expr.months == frozenset(range(1, 13))
    assert expr.days_of_week == frozenset(range(7))
    assert not expr.dom_restricted
    assert not expr.dow_restricted


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        ("*/15 * * * *", {0, 15, 30, 45}),
        ("5,10 * * * *", {5, 10}),
        ("10-12 * * * *", {10, 11, 12}),
        ("10-30/10 * * * *", {10, 20, 30}),
        ("50/5 * * * *", {50, 55}),
        ("0,30-32 * * * *", {0, 30, 31, 32}),
    ],
)
def test_minute_forms(text: str, minutes: set[int]) -> None:
    assert parse(text).minutes == frozenset(minutes)


def test_names_are_case_insensitive() -> None:
    expr = parse("0 9 * jan-Mar MON-fri")
    assert expr.months == frozenset({1, 2, 3})
    assert expr.days_of_week == frozenset({1, 2, 3, 4, 5})


def test_seven_is_sunday() -> None:
    assert parse("0 0 * * 7").days_of_week == frozenset({0})
    assert parse("0 0 * * 5-7").days_of_week == frozenset({5, 6, 0})


def test_dow_step_from_value_stops_at_saturday() -> None:
    assert parse("0 0 * * 1/2").days_of_week == frozenset({1, 3, 5})


@pytest.mark.parametrize(
    ("macro", "equivalent"),
    [
        ("@yearly", "0 0 1 1 *"),
        ("@annually", "0 0 1 1 *"),
        ("@monthly", "0 0 1 * *"),
        ("@weekly", "0 0 * * 0"),
        ("@daily", "0 0 * * *"),
        ("@midnight", "0 0 * * *"),
        ("@HOURLY", "0 * * * *"),
    ],
)
def test_macros(macro: str, equivalent: str) -> None:
    a, b = parse(macro), parse(equivalent)
    assert (a.minutes, a.hours, a.days_of_month, a.months, a.days_of_week) == (
        b.minutes,
        b.hours,
        b.days_of_month,
        b.months,
        b.days_of_week,
    )
    assert a.source == macro


def test_question_mark_in_day_fields() -> None:
    expr = parse("0 0 ? * MON")
    assert not expr.dom_restricted
    assert expr.dow_restricted


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("", "empty expression"),
        ("* * * *", "expected 5 fields, got 4"),
        ("0 * * * * *", "six-field"),
        ("60 * * * *", "out of range"),
        ("* 24 * * *", "out of range"),
        ("* * 0 * *", "out of range"),
        ("* * * 13 *", "out of range"),
        ("* * * * 8", "out of range"),
        ("*/0 * * * *", "invalid step"),
        ("*/x * * * *", "invalid step"),
        ("5-1 * * * *", "runs backwards"),
        ("1,,2 * * * *", "empty list item"),
        ("abc * * * *", "invalid value"),
        ("? * * * *", "invalid value"),
        ("0 0 ?/2 * *", "cannot take a step"),
        ("@fortnightly", "unknown macro"),
        ("@reboot", "@reboot"),
        ("0 0 * foo *", "invalid value"),
        ("1- * * * *", "missing value"),
    ],
)
def test_parse_errors(text: str, fragment: str) -> None:
    with pytest.raises(CronParseError) as info:
        parse(text)
    assert fragment in str(info.value)


def test_parse_error_names_field() -> None:
    with pytest.raises(CronParseError) as info:
        parse("0 25 * * *")
    assert info.value.field == "hour"


def test_dom_dow_or_semantics() -> None:
    expr = parse("0 0 13 * 5")  # the 13th, or any Friday
    assert expr.uses_or_semantics
    assert expr.matches_date(dt.date(2026, 11, 13))  # Friday the 13th
    assert expr.matches_date(dt.date(2026, 11, 6))  # a Friday
    assert expr.matches_date(dt.date(2026, 10, 13))  # a Tuesday the 13th
    assert not expr.matches_date(dt.date(2026, 11, 10))


def test_star_step_in_dom_keeps_and_semantics() -> None:
    expr = parse("0 0 */2 * 1")
    assert not expr.uses_or_semantics
    assert expr.matches_date(dt.date(2026, 11, 9))  # Monday the 9th (odd day)
    assert not expr.matches_date(dt.date(2026, 11, 16))  # Monday the 16th (even day)


def test_matches_minute() -> None:
    expr = parse("30 9 * * 1-5")
    assert expr.matches(dt.datetime(2026, 11, 9, 9, 30))
    assert not expr.matches(dt.datetime(2026, 11, 8, 9, 30))  # Sunday
    assert not expr.matches(dt.datetime(2026, 11, 9, 9, 31))


def test_times_of_day_sorted() -> None:
    assert parse("15,0 17,9 * * *").times_of_day == [
        dt.time(9, 0),
        dt.time(9, 15),
        dt.time(17, 0),
        dt.time(17, 15),
    ]


@pytest.mark.parametrize(
    ("schedule", "expected"),
    [
        ("CRON_TZ=Europe/Paris 0 9 * * *", ("Europe/Paris", "0 9 * * *")),
        ("TZ=UTC @daily", ("UTC", "@daily")),
        ("  0 9 * * *  ", (None, "0 9 * * *")),
    ],
)
def test_split_timezone_prefix(schedule: str, expected: tuple[str | None, str]) -> None:
    assert split_timezone_prefix(schedule) == expected
