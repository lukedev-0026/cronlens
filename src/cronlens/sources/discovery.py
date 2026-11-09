"""Finding schedule-bearing files under a set of paths."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterable, Sequence
from pathlib import Path

import yaml

from cronlens.models import Location
from cronlens.sources import _yaml
from cronlens.sources.base import SourceError, SourceResult
from cronlens.sources.crontab import parse_crontab
from cronlens.sources.github_actions import collect_workflow, is_workflow
from cronlens.sources.kubernetes import collect_manifest

__all__ = ["SKIP_DIRS", "discover", "display_path", "load_file"]

SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
    }
)
_YAML_SUFFIXES = (".yml", ".yaml")
_CRONTAB_SUFFIXES = (".cron", ".crontab")


def discover(paths: Iterable[Path], exclude: Sequence[str] = ()) -> SourceResult:
    """Read every recognised file under ``paths``.

    Directories are walked recursively. Files given explicitly are always
    read; a non-YAML file given explicitly is read as a crontab.
    ``exclude`` holds glob patterns matched against the displayed path.
    """
    result = SourceResult()
    seen: set[Path] = set()
    for root in paths:
        if root.is_file():
            _load_once(root, explicit=True, exclude=exclude, seen=seen, result=result)
        elif root.is_dir():
            for file in _walk(root):
                _load_once(file, explicit=False, exclude=exclude, seen=seen, result=result)
        else:
            result.errors.append(SourceError(Location(display_path(root)), "path does not exist"))
    return result


def load_file(path: Path, *, explicit: bool = True) -> SourceResult:
    """Read one file, choosing the reader from its name and content."""
    shown = display_path(path)
    result = SourceResult()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        result.errors.append(SourceError(Location(shown), f"cannot read file: {exc}"))
        return result

    if path.suffix.lower() in _YAML_SUFFIXES:
        return _load_yaml(text, shown, in_workflows_dir=_in_workflows_dir(path))
    if explicit or _looks_like_crontab(path):
        return parse_crontab(text, shown, system=_is_system_crontab(path))
    return result


def display_path(path: Path) -> str:
    """Return ``path`` relative to the working directory when possible, with ``/``."""
    try:
        relative = path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return path.as_posix()
    return relative.as_posix()


def _load_once(
    path: Path,
    *,
    explicit: bool,
    exclude: Sequence[str],
    seen: set[Path],
    result: SourceResult,
) -> None:
    resolved = path.resolve()
    if resolved in seen:
        return
    seen.add(resolved)
    shown = display_path(path)
    if any(fnmatch.fnmatch(shown, pattern) for pattern in exclude):
        return
    if not explicit and not (path.suffix.lower() in _YAML_SUFFIXES or _looks_like_crontab(path)):
        return
    result.extend(load_file(path, explicit=explicit))


def _walk(root: Path) -> Iterable[Path]:
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = sorted(d for d in subdirs if d not in SKIP_DIRS)
        for name in sorted(files):
            yield Path(directory) / name


def _load_yaml(text: str, shown: str, *, in_workflows_dir: bool) -> SourceResult:
    result = SourceResult()
    try:
        documents = _yaml.compose_documents(text)
    except yaml.YAMLError as exc:
        # Many YAML files in a repository are templates (Helm, Jinja). Only
        # report a parse failure when the file plausibly holds a schedule.
        if in_workflows_dir or "CronJob" in text or "schedule:" in text:
            message = str(exc).strip().splitlines()[0]
            result.errors.append(
                SourceError(Location(shown, _yaml.error_line(exc)), f"invalid YAML: {message}")
            )
        return result

    for document in documents:
        if is_workflow(document):
            collect_workflow(document, shown, result)
        else:
            collect_manifest(document, shown, result)
    return result


def _in_workflows_dir(path: Path) -> bool:
    return path.parent.name == "workflows" and path.parent.parent.name == ".github"


def _looks_like_crontab(path: Path) -> bool:
    return (
        path.name == "crontab"
        or path.suffix.lower() in _CRONTAB_SUFFIXES
        or path.parent.name == "cron.d"
    )


def _is_system_crontab(path: Path) -> bool:
    return (path.name == "crontab" and path.parent.name == "etc") or path.parent.name == "cron.d"
