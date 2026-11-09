# Roadmap

This is the plan after 0.1.0. Estimates are for one developer and include
tests and documentation. Priorities: **P1** next, **P2** soon, **P3** later.
Each item will be tracked as a GitHub issue.

Total estimated remaining work: **about 52 hours**.

## Milestone 0.2: more sources (≈16 h)

| Item | Priority | Estimate | Acceptance criteria |
| --- | --- | --- | --- |
| systemd timers (`OnCalendar=`) | P1 | 8 h | `*.timer` files are discovered; the common calendar forms (`daily`, `Mon..Fri *-*-* 09:00`, `*:0/15`, explicit dates, time zones) are parsed or reported as unsupported; DST and collision checks apply; tests cover the forms `systemd-analyze calendar` documents. |
| Read from standard input (`cronlens scan -`) with `--type` | P1 | 3 h | `helm template . \| cronlens scan - --type kubernetes` works; line numbers refer to the stream; documented in the README. |
| Jenkins `triggers { cron(...) }` including `H` hashing | P2 | 5 h | Jenkinsfiles are discovered; `H` is expanded the way Jenkins does for a given job name, or reported with a clear message when the job name is unknown. |

## Milestone 0.3: precision (≈14 h)

| Item | Priority | Estimate | Acceptance criteria |
| --- | --- | --- | --- |
| Scheduler profiles for DST behaviour | P1 | 5 h | A `scheduler` setting (`cronie`, `vixie`, `kubernetes`, `systemd`) makes CL007/CL008 say exactly whether the run is skipped, moved or doubled, with behaviour checked against each scheduler's source or documentation and cited in `docs/rules.md`. |
| Inline suppressions (`# cronlens: disable=CL013`) | P1 | 4 h | A comment on the line before or on the same line silences the named rules for that job, in crontabs and YAML; unused suppressions are reported. |
| Baseline file | P2 | 3 h | `cronlens scan --write-baseline` records current findings; later scans report only new ones; baseline entries survive line moves. |
| Six-field expressions (seconds) as an opt-in | P3 | 2 h | `--seconds` accepts Quartz/Spring-style six fields; the default stays five-field. |

## Milestone 0.4: insight (≈12 h)

| Item | Priority | Estimate | Acceptance criteria |
| --- | --- | --- | --- |
| `cronlens timeline` | P2 | 6 h | Prints a per-hour heat map of job starts for a chosen day and zone in the terminal, with an `--html` option producing a self-contained page. |
| Overlapping runs from declared durations | P2 | 4 h | A `duration` hint (comment or config) lets cronlens report a job whose next run starts before the previous one would finish, and jobs whose run windows overlap. |
| Suggested fixes | P3 | 2 h | Findings for CL007/CL008/CL010/CL013 include a concrete replacement expression in text, JSON and SARIF (`fixes`). |

## Milestone 1.0: hardening and distribution (≈10 h)

| Item | Priority | Estimate | Acceptance criteria |
| --- | --- | --- | --- |
| Publish to PyPI with trusted publishing | P1 | 2 h | Tagged releases upload to PyPI from the release workflow without stored tokens; README install instructions updated. |
| Pin GitHub Actions to commit SHAs | P1 | 1 h | All `uses:` lines reference full SHAs with version comments; Dependabot keeps them current. |
| Property-based tests against a reference | P2 | 3 h | Hypothesis generates expressions; next-run results match an independent implementation (for example cronie's matching logic ported in tests) for thousands of cases. |
| Performance for large repositories | P2 | 2 h | Scanning 2,000 jobs, including every-minute jobs, finishes in under 5 s on CI hardware; a benchmark runs in CI. |
| Documentation site | P3 | 2 h | Rules, configuration and recipes are published with GitHub Pages from `docs/`. |

## Not planned

- Running or scheduling jobs. cronlens only reads configuration.
- Hosted scheduler APIs (such as AWS EventBridge or Google Cloud Scheduler)
  that are configured outside the repository. Infrastructure-as-code readers
  for them (Terraform, CloudFormation) may be considered after 1.0.
