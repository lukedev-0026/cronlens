# Project history

## Start

cronlens was started by Luke Taaffe on **9 November 2026**. It was chosen
from a short list of candidate open-source tools as the one with the clearest
users and the most room to grow. The commit history in this repository is the
complete development record. Every commit carries the date it was actually
made, and none have been rewritten or backdated.

## Timeline

| Date | Milestone |
| --- | --- |
| 2026-11-09 | Project skeleton, packaging and MIT license |
| 2026-11-09 | Cron expression parser with Vixie cron semantics |
| 2026-11-09 | Time-zone-aware run calculation with DST gap and overlap detection |
| 2026-11-09 | Plain-English descriptions and `cronlens explain` |
| 2026-11-09 | Readers for crontabs, GitHub Actions workflows and Kubernetes CronJobs |
| 2026-11-09 | Checks CL001–CL013 |
| 2026-11-09 | `scan`, `list` and `rules` commands; text, JSON and SARIF output; configuration files |
| 2026-11-09 | Demo repository and end-to-end tests |
| 2026-11-09 | CI on three operating systems, release workflow, GitHub Action, pre-commit hook |
| 2026-11-09 | Documentation and version 0.1.0 |

Planned work is in [ROADMAP.md](ROADMAP.md) and released changes are in
[CHANGELOG.md](CHANGELOG.md).

## How it was built

The code was written with the help of an AI coding assistant (Claude Code),
under the direction and review of the maintainer. Commits made this way carry
a `Co-Authored-By` trailer.
