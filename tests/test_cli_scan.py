import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from cronlens.cli import main

DEMO = Path(__file__).resolve().parent.parent / "examples" / "demo-repo"
NOW = "2026-11-09T12:00:00Z"


def invoke(*args: str) -> tuple[int, str]:
    result = CliRunner().invoke(main, list(args))
    return result.exit_code, result.output


@pytest.fixture
def in_demo(monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(DEMO)
    return DEMO


def test_demo_repository_findings(in_demo: Path) -> None:
    code, out = invoke("scan", "--now", NOW, "--format", "json")
    assert code == 1
    data = json.loads(out)
    found = {(f["path"], f["line"], f["rule_id"]) for f in data["findings"]}
    assert found == {
        (".github/workflows/nightly.yml", 5, "CL010"),
        (".github/workflows/nightly.yml", 6, "CL009"),
        ("k8s/cronjobs.yaml", 8, "CL007"),
        ("k8s/cronjobs.yaml", 25, "CL011"),
        ("k8s/cronjobs.yaml", 41, "CL012"),
        ("ops/app.cron", 6, "CL013"),
        ("ops/app.cron", 15, "CL004"),
        ("ops/app.cron", 18, "CL006"),
        ("ops/app.cron", 21, "CL005"),
        ("ops/app.cron", 25, "CL007"),
        ("ops/app.cron", 25, "CL008"),
    }
    assert data["summary"]["schedules"] == 14
    assert data["summary"]["files"] == 3


def test_fail_on_levels(in_demo: Path) -> None:
    assert invoke("scan", "--now", NOW, "--fail-on", "never")[0] == 0
    assert invoke("scan", "--now", NOW, "--fail-on", "error")[0] == 1
    code, _ = invoke(
        "scan", "--now", NOW, "--fail-on", "error", "--disable", "CL004", "--disable", "CL011"
    )
    assert code == 0


def test_text_output_and_summary(in_demo: Path) -> None:
    _, out = invoke("scan", "--now", NOW, "ops/app.cron")
    assert "ops/app.cron:15: error CL004 never-fires [quarter-close]" in out
    assert out.rstrip().endswith("Checked 9 schedules in 1 file: 1 error, 4 warnings, 1 info.")


def test_sarif_to_file(in_demo: Path, tmp_path: Path) -> None:
    target = tmp_path / "out.sarif"
    code, out = invoke("scan", "--now", NOW, "-f", "sarif", "-o", str(target))
    assert code == 1
    assert out == ""
    data = json.loads(target.read_text(encoding="utf-8"))
    assert len(data["runs"][0]["results"]) == 11


def test_exclude_and_default_tz(in_demo: Path) -> None:
    code, out = invoke(
        "scan", "--now", NOW, "--exclude", "ops/*", "--exclude", ".github/*",
        "--default-tz", "Europe/Paris", "-f", "json",
    )  # fmt: skip
    assert code == 1
    messages = [f["message"] for f in json.loads(out)["findings"]]
    assert any("assumed Europe/Paris" in m for m in messages)
    assert all("ops/app.cron" not in m for m in messages)


def test_clean_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ok.cron").write_text("17 4 * * * /bin/true\n")
    code, out = invoke("scan", "--now", NOW)
    assert code == 0
    assert out == "Checked 1 schedule in 1 file: no problems found.\n"


def test_config_file_settings_apply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cronlens.toml").write_text('disable = ["CL004"]\nfail-on = "error"\n')
    (tmp_path / "x.cron").write_text("0 0 30 2 * /bin/true\n")
    assert invoke("scan", "--now", NOW)[0] == 0


@pytest.mark.parametrize(
    ("args", "code", "message"),
    [
        (["--disable", "CL999"], 2, "unknown rule(s) CL999"),
        (["--default-tz", "Atlantis/City"], 2, "unknown time zone"),
        (["--now", "soon"], 2, "ISO 8601"),
        (["--format", "xml"], 2, "Invalid value"),
    ],
)
def test_usage_errors(args: list[str], code: int, message: str, tmp_path: Path,
                      monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.chdir(tmp_path)
    actual, out = invoke("scan", *args)
    assert actual == code
    assert message in out


def test_bad_config_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cronlens.toml").write_text("colour = true\n")
    code, out = invoke("scan")
    assert code == 2
    assert "unknown setting(s): colour" in out


def test_missing_path_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    code, out = invoke("scan", "nope")
    assert code == 1
    assert "nope:1: warning CL001 unreadable-source" in out


def test_list_command(in_demo: Path) -> None:
    code, out = invoke("list", "--now", NOW, "k8s")
    assert code == 0
    assert "k8s/cronjobs.yaml:41  CronJob ops/cache-warm" in out
    assert "45 4 * * *  [UTC (assumed)]  At 04:45" in out
    assert "next run: 2026-11-10T04:45:00+00:00" in out


def test_list_json_marks_invalid_and_never(in_demo: Path) -> None:
    code, out = invoke("list", "--now", NOW, "--json", "ops/app.cron")
    assert code == 0
    rows = {row["line"]: row for row in json.loads(out)}
    assert rows[15]["next_run_utc"] is None
    assert rows[25]["timezone"] == "Europe/London"
    assert rows[25]["timezone_explicit"] is True


def test_list_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert invoke("list") == (0, "No schedules found.\n")


def test_rules_command() -> None:
    code, out = invoke("rules")
    assert code == 0
    assert out.count("\n") == 13
    assert "CL013  start-collision" in out
