from click.testing import CliRunner

from cronlens import __version__
from cronlens.cli import main


def run(*args: str) -> tuple[int, str]:
    result = CliRunner().invoke(main, list(args))
    return result.exit_code, result.output


def test_version() -> None:
    code, out = run("--version")
    assert code == 0
    assert __version__ in out


def test_explain_lists_runs() -> None:
    code, out = run("explain", "0 9 * * 1-5", "--from", "2026-11-06T12:00:00", "-n", "2")
    assert code == 0
    assert "At 09:00 on Monday through Friday (UTC)" in out
    assert "Mon 2026-11-09 09:00" in out
    assert "Tue 2026-11-10 09:00" in out


def test_explain_marks_dst_gap() -> None:
    code, out = run(
        "explain",
        "30 2 * * *",
        "--tz",
        "America/New_York",
        "--from",
        "2026-03-07T12:00:00Z",
        "-n",
        "1",
    )
    assert code == 0
    assert "Sun 2026-03-08 02:30" in out
    assert "skipped by DST change" in out


def test_explain_or_note() -> None:
    _, out = run("explain", "0 0 13 * 5", "-n", "0")
    assert "EITHER" in out


def test_explain_never_fires() -> None:
    _, out = run("explain", "0 0 31 4 *")
    assert "never fires" in out


def test_explain_bad_expression() -> None:
    code, out = run("explain", "61 * * * *")
    assert code == 1
    assert "out of range" in out


def test_explain_bad_timezone() -> None:
    code, out = run("explain", "* * * * *", "--tz", "Nowhere/Land")
    assert code == 1
    assert "unknown time zone" in out


def test_explain_bad_start() -> None:
    code, out = run("explain", "* * * * *", "--from", "yesterday")
    assert code == 2
    assert "ISO 8601" in out
