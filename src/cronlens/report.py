"""Rendering findings as text, JSON or SARIF 2.1.0."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import click

from cronlens import __version__
from cronlens.models import Finding, Severity
from cronlens.rules import RULES

__all__ = ["FORMATS", "ScanSummary", "render"]

FORMATS = ("text", "json", "sarif")
PROJECT_URL = "https://github.com/lukedev-0026/cronlens"

_COLOURS = {Severity.ERROR: "red", Severity.WARNING: "yellow", Severity.INFO: "cyan"}
_SARIF_LEVELS = {Severity.ERROR: "error", Severity.WARNING: "warning", Severity.INFO: "note"}


@dataclass(frozen=True)
class ScanSummary:
    jobs: int
    files: int


def render(fmt: str, findings: Sequence[Finding], summary: ScanSummary) -> str:
    if fmt == "text":
        return render_text(findings, summary)
    if fmt == "json":
        return render_json(findings, summary)
    if fmt == "sarif":
        return render_sarif(findings)
    raise ValueError(f"unknown format {fmt!r}")


def render_text(findings: Sequence[Finding], summary: ScanSummary) -> str:
    lines = []
    for f in findings:
        severity = click.style(f.severity.label, fg=_COLOURS[f.severity], bold=True)
        job = f" [{f.job}]" if f.job else ""
        lines.append(
            f"{f.location.path}:{f.location.line}: {severity} {f.rule_id} {f.rule_name}{job}"
        )
        lines.append(f"    {f.message}")
    lines.append(_summary_line(findings, summary))
    return "\n".join(lines) + "\n"


def _summary_line(findings: Sequence[Finding], summary: ScanSummary) -> str:
    counts = Counter(f.severity for f in findings)
    jobs = _plural(summary.jobs, "schedule")
    files = _plural(summary.files, "file")
    if not findings:
        return f"Checked {jobs} in {files}: no problems found."
    parts = [
        _plural(counts[Severity.ERROR], "error"),
        _plural(counts[Severity.WARNING], "warning"),
        f"{counts[Severity.INFO]} info",
    ]
    return f"Checked {jobs} in {files}: {', '.join(parts)}."


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def render_json(findings: Sequence[Finding], summary: ScanSummary) -> str:
    counts = Counter(f.severity.label for f in findings)
    payload = {
        "tool": "cronlens",
        "version": __version__,
        "summary": {
            "schedules": summary.jobs,
            "files": summary.files,
            "errors": counts["error"],
            "warnings": counts["warning"],
            "info": counts["info"],
        },
        "findings": [
            {
                "rule_id": f.rule_id,
                "rule_name": f.rule_name,
                "severity": f.severity.label,
                "message": f.message,
                "path": f.location.path,
                "line": f.location.line,
                "job": f.job,
            }
            for f in findings
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_sarif(findings: Sequence[Finding]) -> str:
    rules = list(RULES.values())
    index = {r.id: i for i, r in enumerate(rules)}
    results: list[dict[str, Any]] = [
        {
            "ruleId": f.rule_id,
            "ruleIndex": index[f.rule_id],
            "level": _SARIF_LEVELS[f.severity],
            "message": {"text": f.message if not f.job else f"{f.job}: {f.message}"},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.location.path},
                        "region": {"startLine": f.location.line},
                    }
                }
            ],
        }
        for f in findings
    ]
    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "cronlens",
                        "version": __version__,
                        "informationUri": PROJECT_URL,
                        "rules": [
                            {
                                "id": r.id,
                                "name": r.name,
                                "shortDescription": {"text": r.summary},
                                "helpUri": f"{PROJECT_URL}/blob/main/docs/rules.md#{r.id.lower()}",
                                "defaultConfiguration": {"level": _SARIF_LEVELS[r.severity]},
                            }
                            for r in rules
                        ],
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(payload, indent=2) + "\n"
