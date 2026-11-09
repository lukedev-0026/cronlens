# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-09

First release.

### Added

- Five-field cron expression parser with Vixie cron semantics: names, ranges,
  steps, lists, `7` as Sunday, `?` in the day fields, `@` macros, and the
  day-of-month OR day-of-week rule.
- Run-time calculation in any IANA time zone, marking runs that daylight
  saving skips or repeats.
- `cronlens explain` for plain-English descriptions and upcoming runs.
- Readers for crontabs (user and system formats, `CRON_TZ=`), Kubernetes
  CronJobs (multi-document files, `List`, `spec.timeZone`) and GitHub
  Actions workflow schedules.
- Checks CL001–CL013, documented in `docs/rules.md`.
- `cronlens scan` with text, JSON and SARIF 2.1.0 output, and `--fail-on`
  exit codes for CI.
- `cronlens list` and `cronlens rules`.
- Configuration in `cronlens.toml` or `[tool.cronlens]`, and the
  `CRONLENS_CONFIG`, `CRONLENS_DEFAULT_TZ` and `CRONLENS_FAIL_ON` environment
  variables.
- GitHub Action (`action.yml`) and pre-commit hook.

[Unreleased]: https://github.com/lukedev-0026/cronlens/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lukedev-0026/cronlens/releases/tag/v0.1.0
