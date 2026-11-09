# Contributing to cronlens

Thanks for your interest. Bug reports, new checks, new sources and
documentation fixes are all welcome.

## Before you start

- For anything larger than a small fix, open an issue first so we can agree
  on the approach.
- Check [ROADMAP.md](ROADMAP.md) and the open issues; someone may already be
  working on it.
- By contributing you agree that your work is released under the
  [MIT License](LICENSE), and you confirm you have the right to submit it.
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Setting up

You need Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/luke-taaffe/cronlens
cd cronlens
uv sync
```

## Checks to run before a pull request

```sh
uv run ruff format .
uv run ruff check .
uv run mypy
uv run pytest
```

CI runs the same checks on Linux, Windows and macOS with Python 3.11–3.13.

## Code layout

| Path | Contents |
| --- | --- |
| `src/cronlens/expr.py` | Cron expression parser |
| `src/cronlens/schedule.py` | Run-time calculation, time zones, DST |
| `src/cronlens/explain.py` | Plain-English descriptions |
| `src/cronlens/sources/` | Readers for each file type, and discovery |
| `src/cronlens/rules.py` | The rule catalogue |
| `src/cronlens/analysis.py` | The checks themselves |
| `src/cronlens/report.py` | Text, JSON and SARIF output |
| `src/cronlens/config.py` | Configuration files |
| `src/cronlens/cli.py` | Command-line interface |
| `examples/demo-repo/` | Synthetic repository used by end-to-end tests |

## Adding a check

1. Add a `Rule` to `rules.py` with the next free ID. Never reuse or renumber
   an ID, because users disable rules by ID.
2. Implement it in `analysis.py`.
3. Add unit tests in `tests/test_analysis.py` that cover both a case that
   triggers it and a near miss that does not.
4. Document it in `docs/rules.md`, including why it matters and how to fix it.
5. If the demo repository should show it, add an example and update
   `tests/test_cli_scan.py`.

## Adding a source

Add a reader in `src/cronlens/sources/` that returns a `SourceResult`, keep
line numbers for every job, hook it into `discovery.py`, and add tests with
realistic, synthetic input. Never commit real configuration from a company or
client.

## Commit messages

Use an imperative summary of 72 characters or fewer ("Add systemd timer
reader"), a blank line, then what changed and why. Keep each commit focused
on one change.

## Releasing (maintainers)

1. Update `__version__` in `src/cronlens/__init__.py` and move the
   `Unreleased` entries in `CHANGELOG.md` under the new version.
2. Commit, then tag `vX.Y.Z` and push the tag. The release workflow checks the
   tag matches the version, runs the tests, builds the package and creates
   the GitHub release.
