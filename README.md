# cronlens

[![CI](https://github.com/luke-taaffe/cronlens/actions/workflows/ci.yml/badge.svg)](https://github.com/luke-taaffe/cronlens/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

cronlens finds mistakes in cron schedules across a whole repository: crontabs,
Kubernetes CronJobs and GitHub Actions workflows, checked together in one pass.

Cron mistakes are quiet. A job scheduled for 30 April simply never runs. A
backup at 02:30 in New York is skipped one night every March. Five jobs that
all start at minute 0 slow each other down. cronlens reports these before they
reach production, and it can fail CI or annotate pull requests through GitHub
code scanning.

## Who it is for

- **DevOps engineers and SREs** who own scheduled jobs spread across hosts,
  clusters and CI.
- **Platform teams** who want a CI gate on schedule changes.
- **Anyone with a scheduled GitHub workflow** who wants to know why it ran late
  or not at all.

## Features

- Reads crontab files (user and system formats, `@daily`-style macros,
  `CRON_TZ=`), Kubernetes manifests (multi-document files and `List`
  resources, `spec.timeZone`), and GitHub Actions workflows (`on.schedule`).
- Explains any expression in plain English and lists its next runs in any IANA
  time zone, marking runs that daylight saving skips or repeats.
- Runs 13 checks (see [docs/rules.md](docs/rules.md)), including:
  - dates that never occur, such as 31 April;
  - run times that a daylight-saving change skips or repeats in the next year;
  - Vixie cron's day-of-month OR day-of-week rule;
  - GitHub Actions' 5-minute minimum interval and busy top-of-hour slot;
  - `CRON_TZ=` in a Kubernetes schedule, which Kubernetes rejects;
  - minutes where too many jobs start at once.
- Text, JSON and SARIF 2.1.0 output; exit codes for CI gating.
- Configuration in `cronlens.toml` or `[tool.cronlens]` in `pyproject.toml`.
- A GitHub Action and a pre-commit hook.

## Stack

Python 3.11+, [click](https://click.palletsprojects.com/) for the CLI,
[PyYAML](https://pyyaml.org/) for manifests and workflows, and the standard
library's `zoneinfo` (with `tzdata` for platforms without a zone database).
Development uses [uv](https://docs.astral.sh/uv/), pytest, ruff and mypy
(strict).

## Installation

cronlens is not on PyPI yet. Install it from GitHub:

```sh
pipx install git+https://github.com/luke-taaffe/cronlens
# or
uv tool install git+https://github.com/luke-taaffe/cronlens
```

## Usage

### Explain one expression

```console
$ cronlens explain "30 2 * * *" --tz America/New_York --from 2026-03-06T00:00:00Z -n 4
At 02:30 (America/New_York)
Next runs:
  Fri 2026-03-06 02:30  (2026-03-06 07:30 UTC)
  Sat 2026-03-07 02:30  (2026-03-07 07:30 UTC)
  Sun 2026-03-08 02:30  (2026-03-08 07:30 UTC)  (time skipped by DST change)
  Mon 2026-03-09 02:30  (2026-03-09 06:30 UTC)
```

### Scan a repository

```console
$ cd examples/demo-repo
$ cronlens scan --now 2026-11-09T12:00:00Z
...
ops/app.cron:15: error CL004 never-fires [quarter-close]
    '0 0 31 4 *' matches no real date, so it never runs
ops/app.cron:18: warning CL006 dom-dow-or [purge-tmp]
    day-of-month (1) and day-of-week (Mon) are both set, so cron runs on days matching EITHER field, not both. ...
ops/app.cron:25: warning CL007 dst-skipped-run [export-ledger]
    01:15 on 2027-03-28 does not exist in Europe/London (clocks spring forward); ...
Checked 14 schedules in 3 files: 2 errors, 6 warnings, 4 info.
```

`--now` is only there to make the example repeatable; normally the checks
look ahead from the current time.

Scanning walks the given paths (default `.`), skipping `.git`,
`node_modules`, virtual environments and tool caches. It reads:

| Source | Files |
| --- | --- |
| GitHub Actions | any YAML file with `on:` and `jobs:` keys |
| Kubernetes | any YAML file containing `kind: CronJob` |
| crontab | files named `crontab`, `*.cron`, `*.crontab`, or anything in a `cron.d` directory |

A file passed explicitly on the command line is always read; a non-YAML file
passed that way is read as a crontab.

### Other commands

```sh
cronlens list [PATH]...   # every schedule found, its zone and next run (--json available)
cronlens rules            # the checks and their default severities
```

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | No finding at or above `--fail-on` (default `warning`) |
| 1 | At least one finding at or above `--fail-on` |
| 2 | Usage or configuration error |

## Configuration

cronlens uses the nearest `cronlens.toml`, or a `[tool.cronlens]` table in
`pyproject.toml`, searching upward from the working directory. Command-line
flags override the file.

```toml
default-timezone = "Europe/London"  # zone for crontabs/CronJobs that do not name one
collision-threshold = 3             # report minutes where more than 3 jobs start
collision-window-days = 7           # how far ahead to look for collisions (0 disables)
collision-scope = "source"          # source | file | all
fail-on = "warning"                 # error | warning | info | never
disable = ["CL010"]
exclude = ["vendor/**", "charts/**"]
```

Three environment variables are also read: `CRONLENS_CONFIG`,
`CRONLENS_DEFAULT_TZ` and `CRONLENS_FAIL_ON` (see [.env.example](.env.example)).
cronlens needs no credentials and makes no network requests.

**Time zones.** GitHub Actions schedules run in UTC unless the entry sets
`timezone`. Crontabs without `CRON_TZ=` and CronJobs without `spec.timeZone`
run in the host's or controller's local zone, which cronlens cannot see, so it
assumes `default-timezone` (UTC unless you set it). Set it to your servers'
zone to get daylight-saving checks for those jobs.

## GitHub Action

```yaml
name: Check schedules
on: [pull_request]
permissions:
  contents: read
  security-events: write
jobs:
  cronlens:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: luke-taaffe/cronlens@v0.1.0
        with:
          fail-on: error
          sarif-file: cronlens.sarif
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: cronlens.sarif
```

Inputs: `paths` (default `.`), `fail-on`, `sarif-file`, and `args` for extra
`cronlens scan` flags.

## pre-commit

```yaml
repos:
  - repo: https://github.com/luke-taaffe/cronlens
    rev: v0.1.0
    hooks:
      - id: cronlens
```

## Development and testing

```sh
git clone https://github.com/luke-taaffe/cronlens
cd cronlens
uv sync                      # creates .venv with runtime and dev dependencies
uv run pytest                # unit and end-to-end tests
uv run ruff check . && uv run ruff format --check .
uv run mypy                  # strict type checking
```

The end-to-end tests scan [examples/demo-repo](examples/demo-repo), a
synthetic repository with deliberate mistakes, at a fixed time.

## Contributing

Bug reports, new sources and new checks are welcome. Read
[CONTRIBUTING.md](CONTRIBUTING.md) first, and see [ROADMAP.md](ROADMAP.md) for
planned work. Report security issues as described in [SECURITY.md](SECURITY.md).

## Project history

cronlens was started on 9 November 2026. See
[PROJECT_HISTORY.md](PROJECT_HISTORY.md) and [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE) © 2026 Luke Taaffe
