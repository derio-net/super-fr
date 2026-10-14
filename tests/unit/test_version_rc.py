"""RC version spellings across the release tooling (spec 2026-10-14-exit-gates R25, R26).

An RC is `X.Y.Z-rc.N` (semver) on the JSON surfaces and `X.Y.ZrcN` (PEP 440) on the
Python ones. `bump-version.py` takes either and writes each surface its own spelling,
its `--check` compares the normalized version, and `changes.bumped` /
`floors.parse_version` treat an RC as based on the last final, never by int-splitting
the RC string. `fr.version_floor.admits` lets an RC of X.Y.Z through a floor naming
X.Y.Z (R26). Every case runs in a temp tree, never this checkout.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fr.version_floor import admits

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, file: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


vs = _load("version_surfaces", "version_surfaces.py")
changes = _load("changes", "changes.py")
floors = _load("floors", "floors.py")
bump_version = _load("bump_version_script", "bump-version.py")


def _lock(version: str) -> str:
    return (
        "version = 1\n\n"
        "[[package]]\n"
        'name = "demo"\n'
        f'version = "{version}"\n'
        'source = { editable = "packages/demo" }\n\n'
        "[[package]]\n"
        'name = "requests"\n'
        'version = "2.31.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
    )


def _seed(repo: Path, py: str, js: str) -> None:
    files = {
        "pyproject.toml": f'[project]\nname = "ws"\nversion = "{py}"\n',
        "packages/demo/pyproject.toml": f'[project]\nname = "demo"\nversion = "{py}"\n',
        "packages/fr-opencode-plugin/package.json": json.dumps({"version": js}, indent=2) + "\n",
        "plugins/super-fr/.claude-plugin/plugin.json": json.dumps({"version": js}, indent=4) + "\n",
        ".claude-plugin/marketplace.json": json.dumps({"plugins": [{"version": js}]}, indent=4)
        + "\n",
        "uv.lock": _lock(py),
    }
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def _values(repo: Path) -> dict[str, str]:
    return {f"{s.file}:{s.locator}": s.value for s in vs.version_surfaces(repo)}


# -- writing ---------------------------------------------------------------------


def test_write_version_writes_pep440_to_python_surfaces_and_semver_to_the_rest(
    tmp_path: Path,
) -> None:
    _seed(tmp_path, "5.26.0", "5.26.0")

    vs.write_version(tmp_path, "5.27.0-rc.1")

    values = _values(tmp_path)
    assert values["pyproject.toml:project.version"] == "5.27.0rc1"
    assert values["packages/demo/pyproject.toml:project.version"] == "5.27.0rc1"
    assert values["uv.lock:package[demo].version"] == "5.27.0rc1"
    assert values["plugins/super-fr/.claude-plugin/plugin.json:version"] == "5.27.0-rc.1"
    assert values[".claude-plugin/marketplace.json:plugins[0].version"] == "5.27.0-rc.1"
    assert values["packages/fr-opencode-plugin/package.json:version"] == "5.27.0-rc.1"


def test_write_version_takes_the_pep440_spelling_too(tmp_path: Path) -> None:
    _seed(tmp_path, "5.26.0", "5.26.0")
    vs.write_version(tmp_path, "5.27.0rc2")
    assert set(_values(tmp_path).values()) == {"5.27.0rc2", "5.27.0-rc.2"}


def test_a_final_after_an_rc_is_one_spelling_everywhere(tmp_path: Path) -> None:
    _seed(tmp_path, "5.27.0rc1", "5.27.0-rc.1")
    vs.write_version(tmp_path, "5.27.0")
    assert set(_values(tmp_path).values()) == {"5.27.0"}


# -- bump-version.py -----------------------------------------------------------------


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(bump_version, "REPO", tmp_path)
    return tmp_path


def test_check_passes_on_an_rc_spelled_per_surface(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tree, "5.27.0rc1", "5.27.0-rc.1")
    assert bump_version.check() == 0
    assert "ok" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("py", "js"),
    [
        ("5.27.0rc1", "5.27.0-rc.2"),  # a different RC
        ("5.27.0rc1", "5.27.0"),  # the final on one side
        ("5.27.0", "5.27.1"),  # plain drift
        ("5.27.0rc1", "5.27.0rc1"),  # the PEP 440 spelling on a JSON surface
    ],
)
def test_check_fails_on_real_drift(tree: Path, py: str, js: str) -> None:
    _seed(tree, py, js)
    assert bump_version.check() == 1


@pytest.mark.parametrize(
    ("old", "arg", "new"),
    [
        ("5.26.0", "5.27.0-rc.1", "5.27.0-rc.1"),
        ("5.26.0", "5.27.0rc1", "5.27.0-rc.1"),
        ("5.26.0", "5.27.0", "5.27.0"),
        ("5.26.0", "minor", "5.27.0"),
        # From an RC, a bump the RC already carries lands on its final.
        ("5.27.0rc1", "patch", "5.27.0"),
        ("5.27.0rc1", "minor", "5.27.0"),
        ("5.27.0rc1", "major", "6.0.0"),
        ("5.26.1rc1", "minor", "5.27.0"),
    ],
)
def test_compute_new_accepts_rcs_and_bumps_from_one(old: str, arg: str, new: str) -> None:
    assert bump_version.compute_new(old, arg) == new


def test_compute_new_refuses_a_malformed_rc() -> None:
    with pytest.raises(SystemExit):
        bump_version.compute_new("5.26.0", "5.27.0-rc")


# -- changes.bumped / floors.parse_version -------------------------------------------


@pytest.mark.parametrize(
    ("version", "bump", "expected"),
    [
        # An RC of X.Y.Z is based on the last final it implies: the bump it carries
        # (or a smaller one) lands on X.Y.Z, a bigger one moves past it.
        ("5.27.0-rc.1", "patch", "5.27.0"),
        ("5.27.0-rc.1", "minor", "5.27.0"),
        ("5.27.0-rc.1", "major", "6.0.0"),
        ("5.26.1-rc.3", "patch", "5.26.1"),
        ("5.26.1-rc.3", "minor", "5.27.0"),
        ("6.0.0rc1", "minor", "6.0.0"),
        ("5.27.0-rc.1", None, "5.27.0"),
    ],
)
def test_bumped_treats_an_rc_as_based_on_the_last_final(
    version: str, bump: str | None, expected: str
) -> None:
    assert changes.bumped(version, bump) == expected


def test_floors_parse_version_orders_an_rc_below_its_final_and_above_the_last() -> None:
    rc = floors.parse_version("5.27.0-rc.1")
    assert floors.parse_version("5.26.0") < rc < floors.parse_version("5.27.0")
    assert floors.parse_version("5.27.0rc1") == rc
    assert floors.parse_version("5.27.0-rc.1") < floors.parse_version("5.27.0-rc.2")
    assert floors.parse_version("5.27.0")[0] == 5


def test_a_floor_naming_the_final_is_ok_at_its_rc() -> None:
    assert floors.lower_bound_ok("5.27.0", "5.26.0", "5.27.0")


# -- fr.version_floor.admits (R26) -----------------------------------------------------


@pytest.mark.parametrize(
    ("constraint", "version", "expected"),
    [
        (">=5.27.0", "5.27.0rc1", True),
        (">=5.27.0,<6.0.0", "5.27.0rc1", True),
        (">=5.27.1", "5.27.0rc1", False),
        (">=5.27.0,<6.0.0", "5.28.0rc1", True),
        (">=5.28.0,<6.0.0", "5.27.0rc1", False),
        ("<5.27.0", "5.27.0rc1", False),
        (">=5.0.0,<6.0.0", "6.0.0rc1", False),
        ("==5.27.0", "5.27.0rc1", True),
        (">=5.26.0,<6.0.0", "5.26.0", True),
        (">=5.27.0", "5.26.0", False),
    ],
)
def test_an_rc_of_x_y_z_satisfies_a_floor_naming_x_y_z(
    constraint: str, version: str, expected: bool
) -> None:
    assert admits(constraint, version) is expected
