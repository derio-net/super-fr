"""One version-surface list (spec 2026-09-26-version-bump-churn §3.B, §7 item 9).

`scripts/version_surfaces.py` is the single list of every place the workspace
version is written. `bump-version.py`, the change-fragment gate and the release
script all read it; the tripwire below fails when a manifest carries a version
the list does not know about.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "version_surfaces.py"
spec = importlib.util.spec_from_file_location("version_surfaces", SCRIPT)
assert spec and spec.loader
vs = importlib.util.module_from_spec(spec)
sys.modules["version_surfaces"] = vs
spec.loader.exec_module(vs)

MANIFEST_NAMES = {"pyproject.toml", "package.json", "plugin.json", "marketplace.json"}


def _root_version() -> str:
    return tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["version"]


def _lock_members() -> set[str]:
    lock = tomllib.loads((REPO / "uv.lock").read_text())
    return {
        p["name"]
        for p in lock["package"]
        if "editable" in p.get("source", {}) or "virtual" in p.get("source", {})
    }


def test_surfaces_cover_every_known_manifest_in_this_repo() -> None:
    files = {s.file for s in vs.version_surfaces(REPO)}
    expected = {"pyproject.toml", "packages/fr-opencode-plugin/package.json"}
    expected |= {str(p.relative_to(REPO)) for p in (REPO / "packages").glob("*/pyproject.toml")}
    expected |= {
        str(p.relative_to(REPO)) for p in (REPO / "plugins").glob("*/.claude-plugin/plugin.json")
    }
    expected |= {".claude-plugin/marketplace.json", "uv.lock"}
    assert expected <= files


def test_both_marketplace_plugin_entries_are_surfaces() -> None:
    market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
    entries = [s for s in vs.version_surfaces(REPO) if s.file == ".claude-plugin/marketplace.json"]
    assert len(entries) == len(market["plugins"]) >= 2
    assert len({s.locator for s in entries}) == len(entries)


def test_one_uv_lock_entry_per_workspace_member() -> None:
    lock_entries = [s for s in vs.version_surfaces(REPO) if s.file == "uv.lock"]
    members = _lock_members()
    assert members, "this repo's uv.lock has workspace members"
    assert len(lock_entries) == len(members)
    assert all(any(m in s.locator for s in lock_entries) for m in members)


def test_every_surface_value_equals_the_root_version() -> None:
    root = _root_version()
    surfaces = vs.version_surfaces(REPO)
    assert surfaces
    assert {s.value for s in surfaces} == {root}


def test_surface_is_a_frozen_file_locator_value_record() -> None:
    s = vs.version_surfaces(REPO)[0]
    assert all((s.file, s.locator, s.value))
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.value = "0.0.0"  # type: ignore[misc]


def _write_tmp_repo(root: Path) -> None:
    (root / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "1.2.3"\n')
    (root / "packages" / "a").mkdir(parents=True)
    (root / "packages" / "a" / "pyproject.toml").write_text(
        '[project]\nname = "a"\nversion = "1.2.3"\n'
    )
    (root / "uv.lock").write_text(
        "version = 1\n\n"
        '[[package]]\nname = "a"\nversion = "1.2.3"\nsource = { editable = "packages/a" }\n\n'
        '[[package]]\nname = "demo"\nversion = "1.2.3"\nsource = { virtual = "." }\n\n'
        '[[package]]\nname = "pydantic"\nversion = "2.11.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
    )


def test_registry_packages_in_uv_lock_are_not_surfaces(tmp_path: Path) -> None:
    _write_tmp_repo(tmp_path)
    lock_entries = [s for s in vs.version_surfaces(tmp_path) if s.file == "uv.lock"]
    assert len(lock_entries) == 2
    assert all("pydantic" not in s.locator for s in lock_entries)
    assert {s.value for s in lock_entries} == {"1.2.3"}


def test_write_version_moves_every_surface_and_leaves_registry_packages(tmp_path: Path) -> None:
    _write_tmp_repo(tmp_path)
    vs.write_version(tmp_path, "1.3.0")
    assert {s.value for s in vs.version_surfaces(tmp_path)} == {"1.3.0"}
    lock = tomllib.loads((tmp_path / "uv.lock").read_text())
    pyd = next(p for p in lock["package"] if p["name"] == "pydantic")
    assert pyd["version"] == "2.11.0"


def _carries_version(path: Path) -> bool:
    text = path.read_text()
    if path.name == "pyproject.toml":
        return "version" in tomllib.loads(text).get("project", {})
    data = json.loads(text)
    if "version" in data:
        return True
    return any("version" in p for p in data.get("plugins", []) if isinstance(p, dict))


def test_tripwire_every_versioned_manifest_is_a_surface() -> None:
    """§7 item 9: a manifest carrying a version outside version_surfaces() fails."""
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    manifests = [
        f for f in tracked if Path(f).name in MANIFEST_NAMES and not f.startswith("tests/fixtures/")
    ]
    assert manifests
    covered = {s.file for s in vs.version_surfaces(REPO)}
    stray = [f for f in manifests if _carries_version(REPO / f) and f not in covered]
    assert not stray, (
        f"manifests carry a version outside scripts/version_surfaces.py: {stray} — "
        "add them to version_surfaces()"
    )


def test_bump_version_check_reports_uv_lock_members() -> None:
    out = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "bump-version.py"), "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert "uv.lock" in out.stdout
    assert "ok — versions agree" in out.stdout
