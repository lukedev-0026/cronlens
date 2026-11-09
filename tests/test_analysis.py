import datetime as dt

import pytest

from cronlens.analysis import AnalysisOptions, CollisionScope, analyze
from cronlens.models import Finding, Location, ScheduledJob, Severity, SourceKind
from cronlens.rules import RULES
from cronlens.sources.base import SourceError, SourceResult
from cronlens.sources.kubernetes import SCHEDULE_TZ_PREFIX

NOW = dt.datetime(2026, 11, 9, 12, 0, tzinfo=dt.UTC)
OPTIONS = AnalysisOptions(now=NOW)


def job(
    schedule: str,
    *,
    source: SourceKind = SourceKind.CRONTAB,
    tz: str | None = None,
    name: str = "job",
    path: str = "a.cron",
    line: int = 1,
    extras: dict[str, str] | None = None,
) -> ScheduledJob:
    return ScheduledJob(
        name=name,
        schedule=schedule,
        source=source,
        location=Location(path, line),
        timezone=tz,
        extras=extras or {},
    )


def run(*jobs: ScheduledJob, options: AnalysisOptions = OPTIONS) -> list[Finding]:
    return analyze(SourceResult(jobs=list(jobs)), options)


def ids(findings: list[Finding]) -> list[str]:
    return [f.rule_id for f in findings]


def test_rule_catalogue_is_consistent() -> None:
    assert list(RULES) == [f"CL{n:03d}" for n in range(1, 14)]
    assert len({r.name for r in RULES.values()}) == len(RULES)


def test_clean_job_has_no_findings() -> None:
    assert run(job("17 4 * * *")) == []


def test_source_error_becomes_cl001() -> None:
    result = SourceResult(errors=[SourceError(Location("x.yaml", 3), "invalid YAML: oops")])
    findings = analyze(result, OPTIONS)
    assert ids(findings) == ["CL001"]
    assert findings[0].severity is Severity.WARNING
    assert findings[0].location == Location("x.yaml", 3)


def test_invalid_expression() -> None:
    findings = run(job("0 9 * *"))
    assert ids(findings) == ["CL002"]
    assert "expected 5 fields" in findings[0].message
    assert findings[0].job == "job"


def test_unknown_timezone() -> None:
    assert ids(run(job("0 9 * * *", tz="Europe/Atlantis"))) == ["CL003"]


def test_unknown_default_timezone_is_reported_per_job() -> None:
    options = AnalysisOptions(now=NOW, default_timezone="Bad/Zone")
    assert ids(run(job("0 9 * * *"), options=options)) == ["CL003"]


@pytest.mark.parametrize("schedule", ["0 0 30 2 *", "0 0 31 4,6,9,11 *", "0 0 31 2 *"])
def test_never_fires(schedule: str) -> None:
    findings = run(job(schedule))
    assert ids(findings) == ["CL004"]
    assert findings[0].severity is Severity.ERROR


def test_never_fires_not_reported_with_or_semantics() -> None:
    # 30 February OR any Monday: fires every Monday.
    assert "CL004" not in ids(run(job("0 0 30 2 1")))


def test_rarely_fires_on_leap_day() -> None:
    findings = run(job("0 0 29 2 *"))
    assert ids(findings) == ["CL005"]
    assert "2028-02-29" in findings[0].message


def test_dom_dow_or() -> None:
    findings = run(job("0 0 1 * MON"))
    assert ids(findings) == ["CL006"]
    assert "day-of-month (1) and day-of-week (Mon)" in findings[0].message


def test_dst_skipped_run() -> None:
    findings = run(job("30 2 * * *", tz="America/New_York"))
    assert ids(findings) == ["CL007"]
    assert "02:30 on 2027-03-14" in findings[0].message


def test_dst_repeated_run() -> None:
    findings = run(job("30 1 * * *", tz="America/New_York"))
    assert ids(findings) == ["CL008"]
    assert "01:30 on 2027-11-07" in findings[0].message


def test_dst_uses_default_timezone_for_crontab() -> None:
    options = AnalysisOptions(now=NOW, default_timezone="Europe/London")
    findings = run(job("30 1 * * *"), options=options)
    assert ids(findings) == ["CL007", "CL008"]


def test_dst_ignores_hourly_jobs_and_utc() -> None:
    assert run(job("30 * * * *", tz="America/New_York")) == []
    assert run(job("30 2 * * *", tz="UTC")) == []


def test_dst_only_when_job_runs_on_change_day() -> None:
    # 2027-03-14 is a Sunday; a weekday-only job is unaffected.
    assert run(job("30 2 * * 1-5", tz="America/New_York")) == []


def test_github_short_interval_and_top_of_hour() -> None:
    findings = run(job("*/2 * * * *", source=SourceKind.GITHUB_ACTIONS, tz="UTC"))
    assert ids(findings) == ["CL009"]
    assert "2 minute(s) apart" in findings[0].message
    assert ids(run(job("0 6 * * *", source=SourceKind.GITHUB_ACTIONS))) == ["CL010"]
    assert ids(run(job("*/15 * * * *", source=SourceKind.GITHUB_ACTIONS))) == ["CL010"]


def test_github_interval_counts_day_wrap() -> None:
    findings = run(job("0,58 23 * * *", source=SourceKind.GITHUB_ACTIONS, tz="UTC"))
    assert "CL009" not in ids(findings)
    findings = run(job("59 23 * * *", source=SourceKind.GITHUB_ACTIONS, tz="UTC"))
    assert findings == []


def test_github_rules_only_apply_to_workflows() -> None:
    assert run(job("*/2 * * * *")) == []


def test_kubernetes_timezone_rules() -> None:
    prefixed = job(
        "15 1 * * *",
        source=SourceKind.KUBERNETES,
        tz="UTC",
        extras={SCHEDULE_TZ_PREFIX: "UTC"},
    )
    assert ids(run(prefixed)) == ["CL011"]
    implicit = job("15 1 * * *", source=SourceKind.KUBERNETES)
    findings = run(implicit)
    assert ids(findings) == ["CL012"]
    assert "assumed UTC" in findings[0].message


def test_collisions_reported_once_per_maximal_group() -> None:
    jobs = [job("0 * * * *", name=f"hourly-{i}", line=i) for i in range(1, 4)]
    jobs.append(job("0 0 * * *", name="midnight", line=4))
    findings = run(*jobs)
    assert ids(findings) == ["CL013"]
    message = findings[0].message
    assert message.startswith("4 jobs start in the same minute 7 time(s) in the next 7 days")
    assert "first at 2026-11-10 00:00 UTC" in message
    assert findings[0].location == Location("a.cron", 1)


def test_collision_threshold_and_scope() -> None:
    jobs = [job("0 * * * *", name=f"j{i}", line=i) for i in range(1, 5)]
    assert run(*jobs, options=AnalysisOptions(now=NOW, collision_threshold=4)) == []

    mixed = [
        job("0 * * * *", name="a", path="one.cron"),
        job("0 * * * *", name="b", path="one.cron", line=2),
        job("0 * * * *", name="c", path="two.cron"),
        job("0 * * * *", name="d", path="two.cron", line=2),
    ]
    assert ids(run(*mixed)) == ["CL013"]
    by_file = AnalysisOptions(now=NOW, collision_scope=CollisionScope.FILE)
    assert run(*mixed, options=by_file) == []


def test_collisions_respect_time_zones() -> None:
    # 09:00 in Tokyo is 00:00 UTC, so these all start together.
    jobs = [
        job("0 0 * * *", name="a", tz="UTC", line=1),
        job("0 9 * * *", name="b", tz="Asia/Tokyo", line=2),
        job("0 0 * * *", name="c", tz="UTC", line=3),
        job("0 19 * * *", name="d", tz="America/New_York", line=4),
    ]
    assert ids(run(*jobs)) == ["CL013"]


def test_disabled_rules() -> None:
    options = AnalysisOptions(now=NOW, disabled=frozenset({"CL006"}))
    assert run(job("0 0 1 * MON"), options=options) == []


def test_findings_sorted_by_location() -> None:
    findings = run(
        job("0 0 30 2 *", path="b.cron"),
        job("bad", path="a.cron", line=9),
        job("0 0 30 2 *", path="a.cron", line=2),
    )
    assert [(f.location.path, f.location.line) for f in findings] == [
        ("a.cron", 2),
        ("a.cron", 9),
        ("b.cron", 1),
    ]
