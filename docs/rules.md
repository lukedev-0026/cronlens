# Rules

Every check has an ID, a name and a default severity. Disable a rule with
`--disable CL010` or `disable = ["CL010"]` in the configuration file.

| ID | Name | Severity |
| --- | --- | --- |
| [CL001](#cl001) | unreadable-source | warning |
| [CL002](#cl002) | invalid-expression | error |
| [CL003](#cl003) | unknown-timezone | error |
| [CL004](#cl004) | never-fires | error |
| [CL005](#cl005) | rarely-fires | info |
| [CL006](#cl006) | dom-dow-or | warning |
| [CL007](#cl007) | dst-skipped-run | warning |
| [CL008](#cl008) | dst-repeated-run | warning |
| [CL009](#cl009) | gha-interval-too-short | warning |
| [CL010](#cl010) | gha-top-of-hour | info |
| [CL011](#cl011) | k8s-timezone-in-schedule | error |
| [CL012](#cl012) | k8s-implicit-timezone | info |
| [CL013](#cl013) | start-collision | warning |

<a id="cl001"></a>
## CL001 unreadable-source

A file that looks like it holds schedules could not be read: it is not
UTF-8, a path given on the command line does not exist, a workflow or CronJob
file is not valid YAML, a workflow schedule entry has no `cron` string, or a
CronJob has no `spec.schedule`.

YAML files that fail to parse are only reported when they sit in
`.github/workflows/` or mention `CronJob` or `schedule:`. Helm charts and
other templates are not valid YAML until rendered, so they are skipped
otherwise. To check a chart, render it first (`helm template . > rendered.yaml`)
and scan the result.

<a id="cl002"></a>
## CL002 invalid-expression

The schedule is not a valid five-field expression. The message names the
field and the problem, such as `value 60 out of range 0-59 in minute field`.
Six-field expressions with seconds (Quartz, Spring) are not supported.

<a id="cl003"></a>
## CL003 unknown-timezone

The zone in `CRON_TZ=`, `spec.timeZone`, a workflow's `timezone` or the
`default-timezone` setting is not an IANA zone name. Use names such as
`Europe/Berlin`, not abbreviations such as `CET` or `EST`.

<a id="cl004"></a>
## CL004 never-fires

No date ever matches, for example `0 0 30 2 *` (30 February) or
`0 0 31 4,6,9,11 *` (the 31st of 30-day months). Cron accepts these without
complaint, and the job silently never runs.

When both day fields are restricted, cron matches either of them (see CL006),
so `0 0 30 2 1` still runs every Monday and is not reported.

<a id="cl005"></a>
## CL005 rarely-fires

The schedule runs on fewer than four days in the next four years. In practice
this means 29 February only. It is reported because it is more often a
mistake than a deliberate choice.

<a id="cl006"></a>
## CL006 dom-dow-or

```
0 3 1 * 1   # does NOT mean "the 1st, if it is a Monday"
```

When both the day-of-month and day-of-week fields are restricted, Vixie cron
and its descendants run the job on days matching **either** field. The line
above runs on the 1st of every month and on every Monday.

A field that starts with `*` (including `*/2`) does not count as restricted,
which is why `0 0 */2 * 1` means "odd days that are Mondays". To require both
conditions, schedule on one field and test the other in the command, such as
`[ "$(date +\%d)" = 01 ]`.

<a id="cl007"></a>
## CL007 dst-skipped-run

In the next year, at least one run time does not exist in the job's zone
because the clocks jump forward over it. For example, 02:30 on 8 March 2026 in
`America/New_York`.

What happens next depends on the scheduler. Some cron daemons run the job
right after the jump and others skip it. Either way it does not run at the
time written. Move the job outside the change window (usually 01:00–03:00
local time) or schedule it in UTC.

Schedules that run every hour are not reported: they lose at most one hour's
run, and the next hour covers it.

<a id="cl008"></a>
## CL008 dst-repeated-run

In the next year, at least one run time happens twice in the job's zone
because the clocks go back over it, for example 01:30 on 1 November 2026 in
`America/New_York`. Depending on the scheduler, the job runs once or twice.
This matters for jobs that are not idempotent, such as billing runs or
exports. The fix is the same as for CL007.

<a id="cl009"></a>
## CL009 gha-interval-too-short

GitHub Actions runs scheduled workflows at most once every five minutes. A
schedule such as `*/2 * * * *` is accepted but does not run as often as
written.

<a id="cl010"></a>
## CL010 gha-top-of-hour

GitHub's documentation notes that scheduled workflows can be delayed during
high load, and that the start of every hour is a high-load time; badly
delayed runs may be dropped. Schedules that run at minute 0 at most four
times an hour get this note. Pick an off-peak minute such as 17 or 43.

<a id="cl011"></a>
## CL011 k8s-timezone-in-schedule

`spec.schedule: "CRON_TZ=Europe/Berlin 0 7 * * *"` is not supported by
Kubernetes: recent versions reject it at validation time. Use
`spec.timeZone: Europe/Berlin` with `spec.schedule: "0 7 * * *"`.

<a id="cl012"></a>
## CL012 k8s-implicit-timezone

A CronJob without `spec.timeZone` runs in the local time zone of the
kube-controller-manager, which may differ between clusters. cronlens checks
it in `default-timezone`. Set `spec.timeZone` explicitly to make the schedule
mean the same thing everywhere.

<a id="cl013"></a>
## CL013 start-collision

In the next `collision-window-days` (default 7), more than
`collision-threshold` (default 3) jobs start in the same minute. Each set of
colliding jobs is reported once, at the location of its first job, with the
number of collisions and the first time one happens.

`collision-scope` controls which jobs are compared: `source` (default)
compares jobs read from the same kind of file, `file` only jobs in the same
file, and `all` everything. Run times are compared in UTC, so jobs in
different zones that start at the same moment are counted together.
