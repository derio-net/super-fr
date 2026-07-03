"""CI tripwire: no merged-but-unarchived plan may linger in plans/ (#334).

The fr lifecycle moves a completed plan from docs/superpowers/plans/ to
implemented/plans/. That archive step kept getting skipped (issue #334). This
guard fails loud when any plan under plans/ is fully locally complete — CI
stays red until it is archived, so the archive can never be silently forgotten.

Uses the same gh-free `fr.archive.completed_unarchived_plans` predicate as the
`fr status` sweep, so the CLI and the gate can't disagree. Offline by design
(no gh observation) so plain `pytest` enforces it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml as _yaml
from fr.archive import completed_unarchived_plans

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _add_plan(repo: Path, slug: str, *, complete: bool) -> None:
    plan_dir = repo / "docs" / "superpowers" / "plans" / slug
    shutil.copytree(FIXTURE, plan_dir)
    meta = _yaml.safe_load((plan_dir / "_meta.yaml").read_text())
    meta["plan"] = slug
    (plan_dir / "_meta.yaml").write_text(_yaml.safe_dump(meta, sort_keys=False))
    if complete:
        phase = plan_dir / "01.yaml"
        phase.write_text(phase.read_text().replace('state: " "', "state: x"))


def test_predicate_flags_completed_plan(tmp_path: Path) -> None:
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-01-01-done", complete=True)
    assert completed_unarchived_plans(tmp_path) == ["2026-01-01-done"]


def test_predicate_ignores_in_progress_plan(tmp_path: Path) -> None:
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-01-02-wip", complete=False)
    assert completed_unarchived_plans(tmp_path) == []


def test_live_plans_dir_has_no_unarchived_completed_plans() -> None:
    """The backstop. If this fails, a completed plan is stranded in plans/ —
    run `fr archive --all` (or `fr status` to see which) and commit the move."""
    offenders = completed_unarchived_plans(REPO_ROOT)
    assert offenders == [], (
        "merged-but-unarchived plan(s) in docs/superpowers/plans/: "
        f"{offenders}. Run `fr archive --all` to move them to implemented/."
    )
