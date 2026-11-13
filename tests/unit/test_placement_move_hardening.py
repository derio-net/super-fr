"""`fr placement move`, hardened by the phase-7 review (spec 2026-11-04-repo-feature-settings
R27, R24; plan 2026-11-12-placement-resolver, findings p7-r1, r2, r4, r5, r6).

- p7-r1: a source that moves after the copy is copied again before verify or the switch.
- p7-r2: a move killed after a step's commit and before its push completes on re-run.
- p7-r4: verify validates the destination AS LAID OUT, bookkeeping included.
- p7-r5: only fr artifacts are copied; anything else on `fr` refuses, nothing written.
- p7-r6: a quiet-to-stealth move refuses while a quiet feature is unmerged.

Every repo is a local sandbox with a bare origin; nothing reaches a network or a forge.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from fr.acceptance.fold import clear_fold_cache, effective, fold
from fr.placement import move, quiet

from tests.unit.settings_repo import git
from tests.unit.stealth_repo import make_tracking
from tests.unit.test_placement_move import (  # noqa: F401  (_home is an autouse fixture)
    EPOCH,
    FRAG,
    SPEC_A,
    _fragment,
    _home,
    _land,
    _merge,
    _origin,
    _row,
    _run,
    repo_with_artifacts,
)

GAMMA = "2026-01-03-gamma"
GAMMA_FRAG = f"{FRAG}/{GAMMA}.yaml"
REMOVAL = "chore/fr-placement-move-to-quiet"


def _merge_gamma(root: Path) -> None:
    _merge(root, "feat/gamma", {GAMMA_FRAG: _fragment(GAMMA, [_row("gamma-row")], [])})
    git(root, "fetch", "-q", "origin")


def _quiet_rows(root: Path) -> list[str]:
    git(root, "checkout", "-q", "-B", "feat/after", "origin/main")
    clear_fold_cache()
    return sorted(r.id for r in effective(root).matrix.rows)


def _listed(bare: Path, ref: str) -> list[str]:
    return git(bare, "ls-tree", "-r", "--name-only", ref).splitlines()


# --- p7-r1: never switch on a stale copy ----------------------------------------------


def test_a_feature_merged_after_the_copy_is_copied_before_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo_with_artifacts(tmp_path)
    real = move.STEP_FUNCS["verify"]

    def killed(ctx: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setitem(move.STEP_FUNCS, "verify", killed)
    with pytest.raises(KeyboardInterrupt):
        _run(root, "quiet")
    assert json.loads(move.state_path(root).read_text())["done"] == ["copy"]
    monkeypatch.setitem(move.STEP_FUNCS, "verify", real)
    _merge_gamma(root)

    out = "\n".join(_run(root, "quiet"))

    assert "copying again" in out
    origin = _origin(root)
    assert f"features/moved__{GAMMA}/{GAMMA_FRAG}" in _listed(origin, "fr")
    assert GAMMA_FRAG in _listed(origin, "main")
    assert GAMMA_FRAG not in _listed(origin, REMOVAL)  # the removal covers the final copy
    assert "gamma-row" in _quiet_rows(root)


def test_a_feature_merged_between_verify_and_the_switch_is_copied_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo_with_artifacts(tmp_path)
    real = move.STEP_FUNCS["switch"]
    calls = {"n": 0}

    def merges_first(ctx: Any) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            _merge_gamma(root)
        real(ctx)

    monkeypatch.setitem(move.STEP_FUNCS, "switch", merges_first)
    out = "\n".join(_run(root, "quiet"))

    assert "copying again before switch" in out
    origin = _origin(root)
    assert f"features/moved__{GAMMA}/{GAMMA_FRAG}" in _listed(origin, "fr")
    assert GAMMA_FRAG not in _listed(origin, REMOVAL)
    assert "gamma-row" in _quiet_rows(root)


def test_a_source_that_keeps_moving_refuses_and_switches_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo_with_artifacts(tmp_path)
    prints = iter(range(1000))
    monkeypatch.setattr(move.Ctx, "current_print", lambda self: f"moved-{next(prints)}")
    with pytest.raises(move.MoveError, match="Re-run `fr placement move --to quiet`"):
        _run(root, "quiet")
    assert quiet.read_switch(root) is None
    assert json.loads(move.state_path(root).read_text())["done"] == []


# --- p7-r2: killed after a step's commit, before its push -------------------------------


@pytest.mark.parametrize(
    ("branch", "nth"),
    [("fr", 1), ("fr", 2), (REMOVAL, 1)],
    ids=["copy", "switch", "remove"],
)
def test_a_move_killed_between_a_commit_and_its_push_completes_on_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, branch: str, nth: int
) -> None:
    root = repo_with_artifacts(tmp_path)
    real = move._push_branch
    seen: dict[str, int] = {}

    def killed(r: Path, b: str) -> None:
        seen[b] = seen.get(b, 0) + 1
        if b == branch and seen[b] == nth:
            raise KeyboardInterrupt(f"killed before pushing {b}")
        real(r, b)

    monkeypatch.setattr(move, "_push_branch", killed)
    with pytest.raises(KeyboardInterrupt):
        _run(root, "quiet")
    monkeypatch.setattr(move, "_push_branch", real)

    _run(root, "quiet")

    origin = _origin(root)
    assert quiet.read_switch(root) is not None
    switches = git(origin, "log", "--format=%s", "fr", "--", "settings.yaml").splitlines()
    assert len(switches) == 1  # never committed twice
    assert git(origin, "rev-parse", "fr").strip() == git(root, "rev-parse", "fr").strip()
    assert FRAG + f"/{SPEC_A}.yaml" not in _listed(origin, REMOVAL)
    assert not move.state_path(root).exists()


# --- p7-r4: the destination itself is validated -----------------------------------------


def test_verify_refuses_a_destination_whose_synthesised_bookkeeping_is_corrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.placement import merged

    root = repo_with_artifacts(tmp_path)
    monkeypatch.setattr(merged, "record_text", lambda *a, **k: "merged: not-a-list\n")
    with pytest.raises(move.MoveError, match=r"verify refused.*merged\.yaml"):
        _run(root, "quiet")
    assert quiet.read_switch(root) is None
    assert "verify" not in json.loads(move.state_path(root).read_text())["done"]


def test_bookkeeping_problems_reads_each_file_as_its_reader_does() -> None:
    sha = "a" * 40
    good = {
        "OWNER": b"feat/x\n",
        "BASE": f"{sha}\n".encode(),
        "HEADS": f"{sha}\n".encode(),
        "merged.yaml": f"- merged: {sha}\n  head: {sha}\n".encode(),
    }
    assert move.bookkeeping_problems("feat__x", good) == []
    assert move.bookkeeping_problems("feat__y", good)  # OWNER names another feature
    assert move.bookkeeping_problems("feat__x", {**good, "BASE": b"zzz\n"})
    assert move.bookkeeping_problems("feat__x", {**good, "HEADS": b""})
    assert move.bookkeeping_problems("feat__x", {k: v for k, v in good.items() if k != "OWNER"})


# --- p7-r5: only fr artifacts are copied --------------------------------------------------


def _plant_on_fr(root: Path, rel: str, text: str) -> None:
    """Commit *rel* on origin's `fr`, dated before every merge, as someone who can push
    to `fr` could."""
    origin = _origin(root)
    scratch = root.parent / "plant"
    git(root.parent, "clone", "-q", "-b", "fr", str(origin), str(scratch))
    git(scratch, "config", "user.name", "t")
    git(scratch, "config", "user.email", "t@example.invalid")
    (scratch / rel).parent.mkdir(parents=True, exist_ok=True)
    (scratch / rel).write_text(text)
    git(scratch, "add", "-A")
    env = {**os.environ, "GIT_COMMITTER_DATE": f"{EPOCH} +0000"}
    import subprocess

    subprocess.run(["git", "commit", "-qm", "plant"], cwd=scratch, check=True, env=env)
    git(scratch, "push", "-q", "origin", "fr")
    git(root, "fetch", "-q", "origin", quiet.FETCH_REFSPEC)


def test_a_planted_workflow_on_fr_refuses_the_move_to_repo_and_writes_nothing(
    tmp_path: Path,
) -> None:
    root = repo_with_artifacts(tmp_path)
    _run(root, "quiet")
    _land(root, REMOVAL)
    _plant_on_fr(root, f"features/moved__{SPEC_A}/.github/workflows/x.yml", "on: push\n")
    main_before = git(root, "rev-parse", "main").strip()

    with pytest.raises(move.MoveError, match=r"\.github/workflows/x\.yml"):
        _run(root, "repo")

    origin = _origin(root)
    assert not git(origin, "branch", "--list", move.COPY_BRANCH).strip()
    assert not git(root, "branch", "--list", move.COPY_BRANCH).strip()
    assert git(root, "rev-parse", "main").strip() == main_before
    assert not (root / ".github").exists()


def test_foreign_names_what_is_not_an_fr_artifact() -> None:
    assert not move.foreign(f"{FRAG}/x.yaml")
    assert move.foreign(".github/workflows/x.yml")
    assert move.foreign(".gitattributes")
    assert move.foreign("docs/superpowers/specs/.gitattributes")
    assert move.foreign("src/app.py")
    with pytest.raises(move.MoveError, match="not an fr artifact"):
        move.refuse_foreign([f"{FRAG}/x.yaml", ".gitattributes"], "the test")


# --- p7-r6: quiet -> stealth with live branches ------------------------------------------


def test_quiet_to_stealth_refuses_while_a_quiet_feature_is_unmerged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.artifacts.commit import commit_paths
    from fr.artifacts.paths import artifact_root
    from fr.git_policy.push import atomic_push
    from fr.isolation.hostworktree import HostWorktreeTarget

    root = repo_with_artifacts(tmp_path)
    _run(root, "quiet")
    _land(root, REMOVAL)
    ws = HostWorktreeTarget(root).up(profile=None, branch="feat/live").worktree
    path = artifact_root(ws) / FRAG / "2026-02-01-live.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_fragment("2026-02-01-live", [], []))
    assert commit_paths(ws, [path], "chore(fr): row").committed
    atomic_push(ws, quiet.worktree_path(ws), "origin", "feat/live", code=True)
    git(root, "fetch", "-q", "origin")
    bare = make_tracking(tmp_path)
    fr_before = git(_origin(root), "rev-parse", "fr").strip()

    with pytest.raises(move.MoveError, match="feat__live"):
        _run(root, "stealth", tracking=f"{bare}@main")

    assert not move.state_path(root).exists()  # nothing in progress
    assert git(_origin(root), "rev-parse", "fr").strip() == fr_before
    assert quiet.read_switch(root) is not None
    assert "features/" not in git(bare, "ls-tree", "-r", "--name-only", "main")


def test_quiet_to_stealth_moves_once_every_feature_merged(tmp_path: Path) -> None:
    root = repo_with_artifacts(tmp_path)
    before = fold(root, ref="refs/remotes/origin/main", include_pending=False)
    _run(root, "quiet")
    _land(root, REMOVAL)
    bare = make_tracking(tmp_path)
    _run(root, "stealth", tracking=f"{bare}@main")
    assert quiet.read_switch(root) is None
    assert before.matrix.rows


SP = "docs/superpowers/specs"


@pytest.mark.parametrize(
    "rel",
    [
        f"{SP}/.GIT/hooks/post-checkout",
        f"{SP}/.Git/config",
        f"{SP}/git~1/hooks/x",
        f"{SP}/.git./hooks/x",
        f"{SP}/.git /hooks/x",
        f"{SP}/.g‌it/hooks/x",
        f"{SP}/.gi﻿t/hooks/x",
        f"{SP}/.GITATTRIBUTES",
        f"{SP}/.GitModules",
        f"{SP}/gitmod~1",
        ".GIT/hooks/x",
        f"{SP}/.git::$INDEX_ALLOCATION/x",
        f"{SP}/.gitattributes:s",
        f"{SP}/2026-01-01-a:b-design.md",
        f"{SP}/gitign~1",
        f"{SP}/.GitIgnore",
    ],
    ids=[
        "upper",
        "mixed",
        "ntfs-short",
        "trailing-dot",
        "trailing-space",
        "hfs-zwnj",
        "hfs-bom",
        "attributes-upper",
        "modules-mixed",
        "modules-short",
        "top-level",
        "ntfs-index-allocation",
        "ntfs-stream",
        "colon",
        "ignore-short",
        "ignore-mixed",
    ],
)
def test_a_git_like_component_is_refused_in_every_spelling(rel: str) -> None:
    """Review p7-r5 (security follow-up): on a case-insensitive filesystem, or one that
    ignores some codepoints or trailing dots, each of these IS `.git`/`.gitmodules`/
    `.gitattributes`, so the check reads a component the way git's `verify_path` does."""
    assert move.foreign(rel)
    with pytest.raises(move.MoveError) as e:
        move.refuse_foreign([rel], "the test")
    assert rel in str(e.value)


@pytest.mark.parametrize(
    "rel",
    [
        f"{SP}/2026-01-01-gitops-design.md",
        f"{SP}/git-notes.md",
        f"{FRAG}/x.yaml",
        f"{FRAG}/.gitkeep",
    ],
)
def test_an_ordinary_fr_artifact_naming_git_is_kept(rel: str) -> None:
    assert not move.foreign(rel)


def test_the_allowlist_is_case_sensitive() -> None:
    assert move.foreign("Docs/Superpowers/specs/x.md")
    assert move.foreign("DOCS/acceptance/features/x.yaml")
