from pathlib import Path

import pytest

from cronlens.analysis import CollisionScope
from cronlens.config import Config, ConfigError, find_config, load_config, parse_settings


def test_defaults() -> None:
    assert parse_settings({}) == Config()


def test_full_settings(tmp_path: Path) -> None:
    path = tmp_path / "cronlens.toml"
    path.write_text(
        'default-timezone = "Europe/London"\n'
        "collision-threshold = 5\n"
        "collision-window-days = 14\n"
        'collision-scope = "file"\n'
        'fail-on = "error"\n'
        'disable = ["CL010", "CL012"]\n'
        'exclude = ["vendor/**"]\n'
    )
    config = load_config(path)
    assert config == Config(
        default_timezone="Europe/London",
        collision_threshold=5,
        collision_window_days=14,
        collision_scope=CollisionScope.FILE,
        fail_on="error",
        disable=("CL010", "CL012"),
        exclude=("vendor/**",),
        source=path,
    )


def test_pyproject_table(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "x"\n\n[tool.cronlens]\nfail-on = "info"\n')
    assert load_config(path).fail_on == "info"


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"colour": True}, "unknown setting(s): colour"),
        ({"default-timezone": "Moon/Base"}, "unknown time zone"),
        ({"default-timezone": 3}, "default-timezone must be a string"),
        ({"collision-threshold": 0}, "collision-threshold must be an integer from 1"),
        ({"collision-threshold": True}, "collision-threshold must be an integer"),
        ({"collision-window-days": 365}, "collision-window-days must be an integer"),
        ({"collision-scope": "planet"}, "collision-scope must be one of source, file, all"),
        ({"fail-on": "fatal"}, "fail-on must be one of"),
        ({"disable": "CL001"}, "disable must be a list of strings"),
        ({"disable": ["CL999"]}, "unknown rule(s) CL999"),
        ({"exclude": [1]}, "exclude must be a list of strings"),
    ],
)
def test_invalid_settings(settings: dict[str, object], message: str) -> None:
    with pytest.raises(ConfigError) as info:
        parse_settings(settings)
    assert message in str(info.value)


def test_invalid_toml(tmp_path: Path) -> None:
    path = tmp_path / "cronlens.toml"
    path.write_text("fail-on = \n")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(path)


def test_find_config_walks_up(tmp_path: Path) -> None:
    (tmp_path / "cronlens.toml").write_text("")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert find_config(nested) == (tmp_path / "cronlens.toml").resolve()


def test_find_config_prefers_nearest_pyproject_with_table(tmp_path: Path) -> None:
    (tmp_path / "cronlens.toml").write_text("")
    inner = tmp_path / "inner"
    inner.mkdir()
    (inner / "pyproject.toml").write_text('[project]\nname = "x"\n')
    assert find_config(inner) == (tmp_path / "cronlens.toml").resolve()
    (inner / "pyproject.toml").write_text("[tool.cronlens]\n")
    assert find_config(inner) == (inner / "pyproject.toml").resolve()
