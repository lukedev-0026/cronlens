import json

import click

from cronlens.models import Finding, Location, Severity
from cronlens.report import ScanSummary, render
from cronlens.rules import RULES

FINDINGS = [
    Finding("CL004", "never-fires", Severity.ERROR, "never runs", Location("a.cron", 2), "job-a"),
    Finding("CL006", "dom-dow-or", Severity.WARNING, "either day", Location("a.cron", 5)),
    Finding("CL010", "gha-top-of-hour", Severity.INFO, "minute 0", Location(".github/w.yml", 7)),
]
SUMMARY = ScanSummary(jobs=4, files=2)


def test_text_report() -> None:
    text = click.unstyle(render("text", FINDINGS, SUMMARY))
    assert "a.cron:2: error CL004 never-fires [job-a]\n    never runs\n" in text
    assert "a.cron:5: warning CL006 dom-dow-or\n" in text
    assert text.endswith("Checked 4 schedules in 2 files: 1 error, 1 warning, 1 info.\n")


def test_text_report_clean() -> None:
    text = render("text", [], ScanSummary(jobs=1, files=1))
    assert text == "Checked 1 schedule in 1 file: no problems found.\n"


def test_json_report() -> None:
    data = json.loads(render("json", FINDINGS, SUMMARY))
    assert data["summary"] == {"schedules": 4, "files": 2, "errors": 1, "warnings": 1, "info": 1}
    assert data["findings"][0] == {
        "rule_id": "CL004",
        "rule_name": "never-fires",
        "severity": "error",
        "message": "never runs",
        "path": "a.cron",
        "line": 2,
        "job": "job-a",
    }


def test_sarif_report() -> None:
    data = json.loads(render("sarif", FINDINGS, SUMMARY))
    assert data["version"] == "2.1.0"
    run = data["runs"][0]
    rules = run["tool"]["driver"]["rules"]
    assert [r["id"] for r in rules] == list(RULES)
    results = run["results"]
    assert [r["level"] for r in results] == ["error", "warning", "note"]
    assert results[0]["message"]["text"] == "job-a: never runs"
    assert rules[results[2]["ruleIndex"]]["id"] == "CL010"
    location = results[2]["locations"][0]["physicalLocation"]
    assert location == {"artifactLocation": {"uri": ".github/w.yml"}, "region": {"startLine": 7}}
