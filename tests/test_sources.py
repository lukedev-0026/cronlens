from pathlib import Path

import pytest

from cronlens.models import SourceKind
from cronlens.sources import discover, parse_crontab, parse_manifests, parse_workflow
from cronlens.sources.kubernetes import SCHEDULE_TZ_PREFIX

CRONTAB = """\
# m h dom mon dow command
SHELL=/bin/bash
MAILTO=""
*/5 * * * * /usr/local/bin/poll-queue --batch 50

CRON_TZ=Europe/Berlin
30 2 * * * /opt/backup/run.sh
@daily   /usr/bin/rotate-logs
@reboot  /usr/bin/warm-cache
CRON_TZ="America/Chicago"
0 0 31 2 * echo never
"""


def test_crontab_jobs_and_timezones() -> None:
    result = parse_crontab(CRONTAB, "deploy/app.cron")
    assert result.errors == []
    jobs = result.jobs
    assert [(j.schedule, j.timezone, j.location.line) for j in jobs] == [
        ("*/5 * * * *", None, 4),
        ("30 2 * * *", "Europe/Berlin", 7),
        ("@daily", "Europe/Berlin", 8),
        ("0 0 31 2 *", "America/Chicago", 11),
    ]
    assert jobs[0].command == "/usr/local/bin/poll-queue --batch 50"
    assert jobs[0].name == "poll-queue (deploy/app.cron:4)"
    assert all(j.source is SourceKind.CRONTAB for j in jobs)


def test_system_crontab_drops_user_field() -> None:
    result = parse_crontab(
        "17 * * * * root cd / && run-parts /etc/cron.hourly\n", "etc/crontab", system=True
    )
    assert result.jobs[0].command == "cd / && run-parts /etc/cron.hourly"
    assert result.jobs[0].name.startswith("cd ")


def test_crontab_short_line_keeps_schedule_for_checks() -> None:
    job = parse_crontab("0 9 * *\n", "x.cron").jobs[0]
    assert job.schedule == "0 9 * *"
    assert job.command is None


WORKFLOW = """\
name: Nightly
on:
  push:
    branches: [main]
  schedule:
    - cron: "0 3 * * *"
    - cron: '*/2 * * * *'
    - cron: "30 9 * * 1"
      timezone: "Europe/London"
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""


def test_workflow_schedules() -> None:
    result = parse_workflow(WORKFLOW, ".github/workflows/nightly.yml")
    assert result.errors == []
    assert [(j.name, j.schedule, j.timezone, j.location.line) for j in result.jobs] == [
        ("Nightly (schedule #1)", "0 3 * * *", "UTC", 6),
        ("Nightly (schedule #2)", "*/2 * * * *", "UTC", 7),
        ("Nightly (schedule #3)", "30 9 * * 1", "Europe/London", 8),
    ]


def test_workflow_without_schedule() -> None:
    result = parse_workflow("on: [push]\njobs: {}\n", "ci.yml")
    assert result.jobs == [] and result.errors == []


def test_workflow_bad_entry_and_bad_yaml() -> None:
    result = parse_workflow("on:\n  schedule:\n    - crn: '0 0 * * *'\njobs: {}\n", "w.yml")
    assert result.errors[0].message == "schedule entry has no 'cron' string"
    assert result.errors[0].location.line == 3

    result = parse_workflow("on: [push\n", "w.yml")
    assert result.errors[0].message.startswith("invalid YAML")


MANIFEST = """\
apiVersion: v1
kind: ConfigMap
metadata:
  name: settings
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: report
  namespace: billing
spec:
  schedule: "0 6 * * *"
  timeZone: "Asia/Tokyo"
  jobTemplate: {}
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: cleanup
spec:
  schedule: "CRON_TZ=Europe/Paris 15 1 * * *"
  jobTemplate: {}
---
apiVersion: v1
kind: List
items:
  - apiVersion: batch/v1
    kind: CronJob
    metadata:
      name: listed
    spec:
      schedule: "@hourly"
"""


def test_manifest_cronjobs() -> None:
    result = parse_manifests(MANIFEST, "k8s/jobs.yaml")
    assert result.errors == []
    jobs = result.jobs
    assert [(j.name, j.schedule, j.timezone, j.location.line) for j in jobs] == [
        ("CronJob billing/report", "0 6 * * *", "Asia/Tokyo", 12),
        ("CronJob cleanup", "15 1 * * *", "Europe/Paris", 21),
        ("CronJob listed", "@hourly", None, 32),
    ]
    assert jobs[1].extras == {SCHEDULE_TZ_PREFIX: "Europe/Paris"}
    assert jobs[0].extras == {}


def test_manifest_without_schedule() -> None:
    result = parse_manifests("kind: CronJob\nmetadata:\n  name: x\nspec: {}\n", "a.yaml")
    assert result.errors[0].message == "CronJob x has no schedule"


def test_templated_manifest_is_ignored_unless_it_holds_a_cronjob() -> None:
    assert parse_manifests("name: {{ .Values.name }\n", "t.yaml").errors == []
    bad = parse_manifests("kind: CronJob\nname: {{ .Values.name }\n", "t.yaml")
    assert bad.errors and bad.errors[0].message.startswith("invalid YAML")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "nightly.yml").write_text(WORKFLOW)
    (tmp_path / "k8s").mkdir()
    (tmp_path / "k8s" / "jobs.yaml").write_text(MANIFEST)
    (tmp_path / "k8s" / "chart.yaml").write_text("name: {{ broken\n")
    (tmp_path / "etc" / "cron.d").mkdir(parents=True)
    (tmp_path / "etc" / "cron.d" / "backup").write_text("0 1 * * * backup /bin/backup\n")
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops" / "app.cron").write_text(CRONTAB)
    (tmp_path / "ops" / "notes.txt").write_text("0 0 * * * not a crontab\n")
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "x.cron").write_text("* * * * * ignored\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_discover_walks_repository(repo: Path) -> None:
    result = discover([Path()])
    assert result.errors == []
    paths = sorted({j.location.path for j in result.jobs})
    assert paths == [
        ".github/workflows/nightly.yml",
        "etc/cron.d/backup",
        "k8s/jobs.yaml",
        "ops/app.cron",
    ]
    backup = next(j for j in result.jobs if j.location.path == "etc/cron.d/backup")
    assert backup.command == "/bin/backup"
    assert len(result.jobs) == 3 + 1 + 3 + 4


def test_discover_exclude_and_explicit_file(repo: Path) -> None:
    result = discover([Path()], exclude=["k8s/*", "ops/*"])
    assert {j.location.path for j in result.jobs} == {
        ".github/workflows/nightly.yml",
        "etc/cron.d/backup",
    }
    explicit = discover([Path("ops/notes.txt")])
    assert [j.schedule for j in explicit.jobs] == ["0 0 * * *"]


def test_discover_missing_path_and_duplicates(repo: Path) -> None:
    result = discover([Path("missing"), Path("ops/app.cron"), Path("ops")])
    assert [e.message for e in result.errors] == ["path does not exist"]
    assert len(result.jobs) == 4
