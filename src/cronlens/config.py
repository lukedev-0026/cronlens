"""Project configuration from ``cronlens.toml`` or ``[tool.cronlens]`` in ``pyproject.toml``.

Example::

    default-timezone = "Europe/London"
    collision-threshold = 3
    collision-window-days = 7
    collision-scope = "source"   # source | file | all
    fail-on = "warning"          # error | warning | info | never
    disable = ["CL010"]
    exclude = ["vendor/**", "charts/**"]
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cronlens.analysis import CollisionScope
from cronlens.rules import RULES
from cronlens.schedule import TimezoneError, load_timezone

__all__ = ["FAIL_ON_CHOICES", "Config", "ConfigError", "find_config", "load_config"]

FAIL_ON_CHOICES = ("error", "warning", "info", "never")
CONFIG_FILE = "cronlens.toml"


class ConfigError(ValueError):
    """Raised for a configuration file that cannot be used."""


@dataclass(frozen=True)
class Config:
    default_timezone: str = "UTC"
    collision_threshold: int = 3
    collision_window_days: int = 7
    collision_scope: CollisionScope = CollisionScope.SOURCE
    fail_on: str = "warning"
    disable: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    source: Path | None = None


def find_config(start: Path) -> Path | None:
    """Find the nearest ``cronlens.toml``, or ``pyproject.toml`` with a cronlens table."""
    for directory in [start.resolve(), *start.resolve().parents]:
        candidate = directory / CONFIG_FILE
        if candidate.is_file():
            return candidate
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file() and _has_tool_table(pyproject):
            return pyproject
    return None


def load_config(path: Path) -> Config:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: invalid TOML: {exc}") from exc

    if path.name == "pyproject.toml":
        data = data.get("tool", {}).get("cronlens", {})
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: the cronlens settings must be a table")
    return parse_settings(data, path)


def parse_settings(data: dict[str, Any], source: Path | None = None) -> Config:
    where = f"{source}: " if source else ""
    known = {
        "default-timezone",
        "collision-threshold",
        "collision-window-days",
        "collision-scope",
        "fail-on",
        "disable",
        "exclude",
    }
    unknown = sorted(set(data) - known)
    if unknown:
        raise ConfigError(f"{where}unknown setting(s): {', '.join(unknown)}")

    default_timezone = _string(data, "default-timezone", "UTC", where)
    try:
        load_timezone(default_timezone)
    except TimezoneError as exc:
        raise ConfigError(f"{where}default-timezone: {exc}") from exc

    threshold = _integer(data, "collision-threshold", 3, 1, 1000, where)
    window = _integer(data, "collision-window-days", 7, 0, 90, where)

    scope_text = _string(data, "collision-scope", "source", where)
    try:
        scope = CollisionScope(scope_text)
    except ValueError:
        choices = ", ".join(s.value for s in CollisionScope)
        raise ConfigError(f"{where}collision-scope must be one of {choices}") from None

    fail_on = _string(data, "fail-on", "warning", where)
    if fail_on not in FAIL_ON_CHOICES:
        raise ConfigError(f"{where}fail-on must be one of {', '.join(FAIL_ON_CHOICES)}")

    disable = _strings(data, "disable", where)
    bad_rules = [r for r in disable if r not in RULES]
    if bad_rules:
        raise ConfigError(f"{where}disable: unknown rule(s) {', '.join(bad_rules)}")

    return Config(
        default_timezone=default_timezone,
        collision_threshold=threshold,
        collision_window_days=window,
        collision_scope=scope,
        fail_on=fail_on,
        disable=disable,
        exclude=_strings(data, "exclude", where),
        source=source,
    )


def _has_tool_table(pyproject: Path) -> bool:
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return False
    tool = data.get("tool")
    return isinstance(tool, dict) and "cronlens" in tool


def _string(data: dict[str, Any], key: str, default: str, where: str) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(f"{where}{key} must be a string")
    return value


def _integer(data: dict[str, Any], key: str, default: int, low: int, high: int, where: str) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ConfigError(f"{where}{key} must be an integer from {low} to {high}")
    return int(value)


def _strings(data: dict[str, Any], key: str, where: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{where}{key} must be a list of strings")
    return tuple(value)
