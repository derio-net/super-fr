"""Uniform legacy-layout hard-stop (2026-06-05 dispatch-guards spec, Phase 3).

Every vk verb that resolves the superpowers tree must exit 2 when the
legacy `docs/superpowers/archived-plans/` directory exists, pointing the
operator at `vk migrate dirs --yes`. Read verbs hard-stop too — banners
get overlooked; migration should happen at first use of the new version.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vk.cli import app

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _legacy_repo(tmp_path: Path) -> Path:
    """A superpowers tree with a legacy archived-plans/ dir and one plan."""
    (tmp_path / "docs" / "superpowers" / "archived-plans").mkdir(parents=True)
    plan = tmp_path / "docs" / "superpowers" / "plans" / "2026-05-09-fixture-minimal"
    shutil.copytree(FIXTURE, plan)
    return tmp_path


def test_require_migrated_layout_raises_on_legacy(tmp_path):
    from vk.commands.common import require_migrated_layout

    _legacy_repo(tmp_path)
    with pytest.raises(Exception) as exc_info:
        require_migrated_layout(tmp_path)
    assert getattr(exc_info.value, "exit_code", None) == 2


def test_require_migrated_layout_noop_when_migrated(tmp_path):
    from vk.commands.common import require_migrated_layout

    (tmp_path / "docs" / "superpowers" / "implemented" / "plans").mkdir(parents=True)
    require_migrated_layout(tmp_path)  # must not raise


def test_require_migrated_layout_noop_without_superpowers_tree(tmp_path):
    from vk.commands.common import require_migrated_layout

    require_migrated_layout(tmp_path)  # no docs/superpowers at all -> no-op


@pytest.mark.parametrize(
    "argv",
    [
        ["apply", "docs/superpowers/plans/2026-05-09-fixture-minimal"],
        ["apply", "docs/superpowers/plans/2026-05-09-fixture-minimal", "--yes"],
        ["pickup", "docs/superpowers/plans/2026-05-09-fixture-minimal", "--phase", "1"],
        ["plan", "self-review", "docs/superpowers/plans/2026-05-09-fixture-minimal"],
    ],
)
def test_verbs_hard_stop_on_legacy_layout(tmp_path, monkeypatch, argv):
    repo = _legacy_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))

    result = CliRunner().invoke(app, argv)
    assert result.exit_code == 2, f"{argv}: rc={result.exit_code}\n{result.output}"
    assert "vk migrate dirs" in result.output


def test_spec_status_hard_stops_on_legacy_layout(tmp_path, monkeypatch):
    repo = _legacy_repo(tmp_path)
    spec = repo / "docs" / "superpowers" / "specs"
    spec.mkdir(parents=True)
    spec_file = spec / "2026-05-09-x-design.md"
    spec_file.write_text(
        "# X\n\n## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|---|---|---|---|\n"
    )
    monkeypatch.chdir(repo)
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))

    result = CliRunner().invoke(app, ["spec", "status", str(spec_file)])
    assert result.exit_code == 2, result.output
    assert "vk migrate dirs" in result.output
