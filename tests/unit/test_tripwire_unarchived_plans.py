"""CI reminder: merged-but-unarchived plans lingering in plans/ (#334).

The fr lifecycle moves a completed plan from docs/superpowers/plans/ to
implemented/plans/. That archive step kept getting skipped (issue #334). This
check names every plan that merged COMPLETE to origin/main and is still sitting
in plans/, while in-progress work is deliberately NOT flagged.

It WARNS, it does not fail (2026-09-26). A plan with no manual phase is complete
the moment its PR merges, so a failing check turned CI red for every unrelated
PR (and main) from that merge until someone's closeout landed. That is a normal
state, not a forgotten one: a closeout (`fr pickup --run <id>`) can finish a
plan at any time, and a batch merge (#667) deliberately defers it. A red CI also
pushed closeouts to `fr archive --all`, which archived another run's plan out
from under its own closeout (#660/#664). `fr status` lists the same plans.

Signal = "complete on the default ref" ∩ "still present in the working-tree
plans/":
- the ref arm is `fr.archive.merge_evidence(...).complete_on_ref` — the ONE
  definition of "merged" (spec 2026-09-23 §3.A), shared with `fr status` and
  `fr archive`. It fires only on plans that genuinely merged complete —
  excluding a brand-new plan (not on main) AND the PR that FINISHES a multi-PR
  plan whose dir landed on main incomplete (main is still incomplete there);
- the working-tree arm lets the PR that ARCHIVES/removes a stale plan pass (the
  dir is gone from the tree).
Offline (`fetch=False`: reads the local remote-tracking ref, which CI fetches
via fetch-depth: 0); skips explicitly when no default ref resolves.
"""

from __future__ import annotations

import shutil
import subprocess
import warnings
from pathlib import Path

import pytest
import yaml as _yaml
from fr.archive import completed_unarchived_plans, merge_evidence

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


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
    )


def _offenders(repo: Path) -> list[str] | None:
    """Plans complete on the default ref and still in the working tree's
    plans/, or `None` when no default ref resolves (the caller skips)."""
    evidence = merge_evidence(repo, fetch=False)
    if evidence.ref is None:
        return None
    plans_dir = repo / "docs" / "superpowers" / "plans"
    return sorted(n for n in evidence.complete_on_ref if (plans_dir / n / "_meta.yaml").exists())


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_incomplete_on_main_completed_in_tree_is_not_flagged(tmp_path: Path) -> None:
    """Finding #1: the PR that FINISHES a plan landed incomplete on main must
    not be red-flagged — main is still incomplete there."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-03-01-multi", complete=False)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "land plan incomplete")
    _git(tmp_path, "remote", "add", "origin", str(tmp_path))
    _git(tmp_path, "fetch", "-q", "origin")
    # Complete it in the working tree (this branch finishes the work).
    phase = tmp_path / "docs" / "superpowers" / "plans" / "2026-03-01-multi" / "01.yaml"
    phase.write_text(phase.read_text().replace('state: " "', "state: x"))
    assert completed_unarchived_plans(tmp_path) == ["2026-03-01-multi"]  # complete in tree
    assert _offenders(tmp_path) == []  # but not complete on main → not an offender


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_complete_on_main_still_in_tree_is_flagged(tmp_path: Path) -> None:
    """A plan complete on origin/main and still sitting in plans/ is the
    merged-but-unarchived offender."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-03-02-done", complete=True)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "land plan complete, unarchived")
    _git(tmp_path, "remote", "add", "origin", str(tmp_path))
    _git(tmp_path, "fetch", "-q", "origin")
    assert _offenders(tmp_path) == ["2026-03-02-done"]


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_complete_on_main_but_archived_in_tree_is_not_flagged(tmp_path: Path) -> None:
    """The PR that ARCHIVES a stale plan passes: the dir is gone from the
    working-tree plans/, so it is not an offender even though main still has
    it complete."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "implemented" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-03-03-done", complete=True)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "land plan complete, unarchived")
    _git(tmp_path, "remote", "add", "origin", str(tmp_path))
    _git(tmp_path, "fetch", "-q", "origin")
    # This branch archives it → removed from plans/ in the working tree.
    shutil.rmtree(tmp_path / "docs" / "superpowers" / "plans" / "2026-03-03-done")
    assert _offenders(tmp_path) == []


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_no_default_ref_means_skip_not_pass(tmp_path: Path) -> None:
    """A checkout with no remote-tracking default ref must SKIP the backstop,
    never pass it silently: `_offenders` answers None, not []."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-03-04-done", complete=True)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "local main only, no remote")
    assert _offenders(tmp_path) is None


def _reminder(offenders: list[str]) -> str | None:
    """The reminder text for *offenders*, or None when there are none.

    Names one `fr archive <plan-dir>` per plan, never `fr archive --all`: the
    blanket form is how one closeout archived another run's plan (#660/#664)."""
    if not offenders:
        return None
    commands = "; ".join(f"fr archive docs/superpowers/plans/{name}" for name in offenders)
    return (
        "merged-but-unarchived plan(s), complete on origin/main but still in "
        f"docs/superpowers/plans/: {offenders}. Each run's closeout "
        f"(`fr pickup --run <id>`) archives it; or, by hand: {commands}"
    )


def test_reminder_names_each_plan_and_never_archive_all() -> None:
    assert _reminder([]) is None
    text = _reminder(["2026-01-01-a", "2026-01-02-b"])
    assert text is not None
    assert "fr archive docs/superpowers/plans/2026-01-01-a" in text
    assert "fr archive docs/superpowers/plans/2026-01-02-b" in text
    assert "--all" not in text


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_no_merged_but_unarchived_plans() -> None:
    """The reminder. A plan complete ON origin/main that is still sitting in
    the working tree's plans/ has merged and is waiting for its closeout. It
    WARNS rather than fails: see the module docstring.

    Signal = complete-on-origin-main ∩ still-present-in-working-tree-plans/.
    The origin/main arm fires only on plans that genuinely merged complete
    (excludes the finishing PR of a multi-PR plan). The working-tree arm lets
    the PR that archives/removes a stale plan pass (the dir is gone from the
    tree)."""
    offenders = _offenders(REPO_ROOT)
    if offenders is None:
        pytest.skip(
            "no remote-tracking default ref resolvable (shallow checkout? no remote?): "
            f"{merge_evidence(REPO_ROOT, fetch=False).ref_error}"
        )
    text = _reminder(offenders)
    if text is not None:
        warnings.warn(text, UserWarning, stacklevel=1)
