"""Merged status outside `repo` (spec 2026-11-04-repo-feature-settings R17's quiet and
stealth clause; plan 2026-11-12-placement-resolver phase 5, task 1).

Under quiet and stealth a feature is merged when its code branch's head is reachable
from the product's default ref, ordered by the first-parent commit that introduced it;
`merged:` records are a cache, never the truth. Every repo here is a local sandbox with
a bare origin; nothing reaches a network.
"""

from __future__ import annotations

import itertools
import json
import os
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.acceptance.fold import clear_fold_cache, effective
from fr.artifacts.paths import KIND_DIRS, ArtifactSpace, space_for
from fr.placement import stealth
from fr.placement.merged import MergedPr, append_record, merged_features

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import QUIET, push_fr_branch

REPO = "derio-net/widgets"
ROW = "alpha-spins"
EPOCH = int(time.time()) - 10 * 86400
_CLOCK = itertools.count(1)


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # A clock every commit here ticks (`Product.tick`): merge order and the fr commit a
    # merged feature is frozen at are judged by committer time, never by luck.
    monkeypatch.setenv("GIT_COMMITTER_DATE", f"{EPOCH} +0000")
    monkeypatch.setenv("GIT_AUTHOR_DATE", f"{EPOCH} +0000")
    stealth.reset_caches()
    clear_fold_cache()
    yield home
    stealth.reset_caches()
    clear_fold_cache()


def _row(row_id: str, status: str = "not-implemented") -> dict[str, Any]:
    return {
        "id": row_id,
        "capability": "widgets",
        "acceptance": f"{row_id} holds.",
        "origin": ["spec:2026-01-01-alpha#R1"],
        "status": status,
    }


def _amend(row: str, base: int, status: str) -> dict[str, Any]:
    return {"row": row, "op": "set-status", "base": base, "status": status, "notes": status,
            "why": status}  # fmt: skip


def tick() -> None:
    """Move the committer clock one second on: every later commit is strictly newer."""
    when = f"{EPOCH + next(_CLOCK)} +0000"
    os.environ["GIT_COMMITTER_DATE"] = when
    os.environ["GIT_AUTHOR_DATE"] = when


class FakeForge:
    """`MergedPrs` with no network: branch -> its merged PRs."""

    def __init__(self, prs: dict[str, list[MergedPr]] | None = None, *, fail: bool = False):
        self.prs = prs or {}
        self.fail = fail
        self.asked: list[str] = []

    def merged_prs(self, branch: str) -> list[MergedPr]:
        self.asked.append(branch)
        if self.fail:
            raise RuntimeError("HTTP 401")
        return list(self.prs.get(branch, []))


class Product:
    """A product clone with feature roots below *space*'s root, committed and pushed in
    the placement worktree as fr itself would (OWNER and BASE at the claim, HEADS at each
    pushed head)."""

    def __init__(self, root: Path, space: ArtifactSpace, ops: Path | None = None) -> None:
        self.root = root  # the checkout whose view is read
        self.ops = ops or root  # the checkout git operations run in
        self.space = space
        self.home = git(self.ops, "symbolic-ref", "--short", "HEAD").strip()
        if space.placement == "stealth":
            self.wt, self.fr_push = stealth.tracking_root(space), ("origin", "main")
        else:
            self.wt, self.fr_push = space.root, ("origin", "fr")

    def feature_root(self, name: str) -> Path:
        return self.space.root / "features" / f"feat__{name}"

    def fr_commit(self, name: str, message: str = "chore(fr): state", *, push: bool = True):
        """Commit feature *name*'s root in the placement worktree (and push it)."""
        tick()
        git(self.wt, "add", "-A", "--", str(self.feature_root(name).relative_to(self.wt)))
        git(self.wt, "commit", "-q", "--allow-empty", "-m", message)
        if push:
            git(self.wt, "push", "-q", self.fr_push[0], f"HEAD:{self.fr_push[1]}")

    def write_fragment(
        self,
        name: str,
        rows: Sequence[dict[str, Any]] = (),
        amendments: Sequence[dict[str, Any]] = (),
    ) -> Path:
        frag = self.feature_root(name) / KIND_DIRS["acceptance-fragment"] / f"{name}.yaml"
        frag.parent.mkdir(parents=True, exist_ok=True)
        data = {"schema_version": 1, "feature": name, "repo": REPO, "rows": list(rows),
                "amendments": list(amendments)}  # fmt: skip
        frag.write_text(yaml.safe_dump(data, sort_keys=False))
        return frag

    def feature(
        self,
        name: str,
        *,
        rows: Sequence[dict[str, Any]] = (),
        amendments: Sequence[dict[str, Any]] = (),
        push: bool = True,
        code: bool = True,
        start: str = "main",
    ) -> None:
        """Branch `feat/<name>` from *start* with one code commit (none without *code*),
        claim its feature root, and push both as `fr push` would."""
        git(self.ops, "checkout", "-q", "-b", f"feat/{name}", start)
        base = git(self.ops, "merge-base", "HEAD", "origin/main").strip()
        if code:
            tick()
            (self.ops / f"{name}.txt").write_text(f"{name}\n")
            git(self.ops, "add", "-A")
            git(self.ops, "commit", "-qm", f"feat({name}): code")
        head = git(self.ops, "rev-parse", "HEAD").strip()
        if push:
            git(self.ops, "push", "-q", "origin", f"feat/{name}")
        git(self.ops, "checkout", "-q", self.home)
        froot = self.feature_root(name)
        froot.mkdir(parents=True, exist_ok=True)
        (froot / "OWNER").write_text(f"feat/{name}\n")
        (froot / "BASE").write_text(f"{base}\n")
        if push and self.space.placement == "stealth":  # stealth records it per run
            runs = froot / KIND_DIRS["run"]
            runs.mkdir(parents=True, exist_ok=True)
            (runs / f"claim{stealth.PLACEMENT_SUFFIX}").write_text(
                json.dumps({"product_head": head})
            )
        elif push:  # quiet: `fr push` appends it to HEADS
            (froot / "HEADS").write_text(f"{head}\n")
        if rows or amendments:
            self.write_fragment(name, rows, amendments)
        self.fr_commit(name, f"chore(fr): claim {name}")

    def merge(self, name: str, *, ff: bool = False, squash: bool = False) -> str:
        """Merge `feat/<name>` into main (a merge commit unless *ff* or *squash*), push;
        main's tip."""
        tick()
        git(self.ops, "checkout", "-q", "main")
        if squash:
            git(self.ops, "merge", "-q", "--squash", f"feat/{name}")
            git(self.ops, "commit", "-qm", f"feat({name}): squashed (#7)")
        else:
            git(self.ops, "merge", "-q", "--ff-only" if ff else "--no-ff", "-m",
                f"Merge feat/{name}", f"feat/{name}")  # fmt: skip
        git(self.ops, "push", "-q", "origin", "main")
        git(self.ops, "checkout", "-q", self.home)
        return git(self.ops, "rev-parse", "main").strip()

    def main_commit(self, text: str) -> str:
        tick()
        git(self.ops, "checkout", "-q", "main")
        (self.ops / "main.txt").write_text(text)
        git(self.ops, "add", "-A")
        git(self.ops, "commit", "-qm", "main moves")
        git(self.ops, "push", "-q", "origin", "main")
        git(self.ops, "checkout", "-q", self.home)
        return git(self.ops, "rev-parse", "main").strip()

    def delete_branch(self, name: str) -> None:
        git(self.ops, "branch", "-q", "-D", f"feat/{name}")
        git(self.ops, "push", "-q", "origin", "--delete", f"feat/{name}")

    def view(self, forge: FakeForge | None = None):  # type: ignore[no-untyped-def]
        return merged_features(self.space, self.root, forge=forge)


@pytest.fixture
def quiet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Product:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    git(repo, "checkout", "-q", "-b", "feat/view")
    monkeypatch.chdir(repo)
    space = space_for(repo)
    assert space.placement == "quiet"
    return Product(repo, space)


# --- merged status and order -------------------------------------------------------


def test_a_feature_is_merged_iff_its_head_is_on_the_default_ref(quiet: Product) -> None:
    quiet.feature("a")
    quiet.feature("b")
    sha = quiet.merge("a")
    view = quiet.view()
    assert [f.feature for f in view.features] == ["feat__a"]
    (a,) = view.features
    assert a.sha == sha and a.branch == "feat/a" and not a.cached
    assert "feat__b" in view.unmerged


def test_merged_features_are_ordered_by_the_commit_that_introduced_them(quiet: Product) -> None:
    quiet.feature("a")
    quiet.feature("b")
    quiet.feature("c")
    quiet.merge("b")
    quiet.main_commit("between\n")
    quiet.merge("a")
    quiet.merge("c")
    assert [f.feature for f in quiet.view().features] == ["feat__b", "feat__a", "feat__c"]


def test_a_fast_forward_merge_is_introduced_by_the_head_itself(quiet: Product) -> None:
    quiet.feature("a")
    head = git(quiet.root, "rev-parse", "feat/a").strip()
    quiet.merge("a", ff=True)
    (a,) = quiet.view().features
    assert a.sha == head


def test_a_merged_feature_stays_merged_when_its_branch_moves_on(quiet: Product) -> None:
    """Monotone (review p5-r3): a commit on the branch after its merge, pushed or not,
    never un-merges it; it stays merged at the commit that merged it."""
    quiet.feature("a")
    sha = quiet.merge("a")
    git(quiet.root, "checkout", "-q", "feat/a")
    (quiet.root / "more.txt").write_text("more\n")
    git(quiet.root, "add", "-A")
    git(quiet.root, "commit", "-qm", "more")
    git(quiet.root, "checkout", "-q", quiet.home)
    assert quiet.view().get("feat__a").sha == sha  # type: ignore[union-attr]
    git(quiet.root, "push", "-q", "origin", "feat/a")
    assert quiet.view().get("feat__a").sha == sha  # type: ignore[union-attr]


def test_a_deleted_branch_stays_merged_through_its_recorded_heads(quiet: Product) -> None:
    quiet.feature("a")
    sha = quiet.merge("a")
    quiet.delete_branch("a")
    (a,) = quiet.view().features  # HEADS, as `fr push` recorded it, outlives the refs
    assert a.sha == sha and not a.cached
    head = (quiet.feature_root("a") / "HEADS").read_text().strip()
    append_record(quiet.feature_root("a"), sha, (head,))
    (a,) = quiet.view().features
    assert a.cached and a.sha == sha


def test_a_feature_with_no_head_anywhere_is_not_merged(quiet: Product) -> None:
    quiet.feature("a", push=False)
    git(quiet.root, "branch", "-q", "-D", "feat/a")
    view = quiet.view()
    assert view.features == () and view.unmerged == ("feat__a",)


# --- the cache ---------------------------------------------------------------------


def test_an_agreeing_record_is_a_cache_hit(quiet: Product) -> None:
    quiet.feature("a")
    sha = quiet.merge("a")
    head = git(quiet.root, "rev-parse", "feat/a").strip()
    append_record(quiet.feature_root("a"), sha, (head,))
    view = quiet.view()
    (a,) = view.features
    assert a.cached and a.sha == sha and view.notices == ()


def test_a_record_off_the_default_ref_is_ignored_with_a_notice(quiet: Product) -> None:
    quiet.feature("a")
    sha = quiet.merge("a")
    forged = git(quiet.root, "rev-parse", "feat/a").strip()  # on main, but not first-parent
    append_record(quiet.feature_root("a"), forged, (forged,))
    view = quiet.view()
    (a,) = view.features
    assert not a.cached and a.sha == sha
    assert any("ignored" in n and forged in n for n in view.notices), view.notices


def test_a_record_for_an_unmerged_feature_never_makes_it_merged(quiet: Product) -> None:
    quiet.feature("a")
    tip = quiet.main_commit("x\n")
    append_record(quiet.feature_root("a"), tip, (tip,))  # a forged record naming main
    view = quiet.view()
    assert view.features == () and "feat__a" in view.unmerged
    assert any("never the truth" in n for n in view.notices), view.notices


def test_a_record_naming_a_later_commit_than_the_merge_is_ignored(quiet: Product) -> None:
    quiet.feature("a")
    sha = quiet.merge("a")
    later = quiet.main_commit("later\n")
    append_record(quiet.feature_root("a"), later, ())
    (a,) = quiet.view().features
    assert a.sha == sha and not a.cached


# --- review p5-r1: only the feature's own commits count ------------------------------


def test_a_branch_fresh_from_the_default_ref_is_not_merged(quiet: Product) -> None:
    """Under quiet no product commit happens during brainstorm, spec and plan: a branch
    with nothing past its claimed base is not merged, however reachable its head is."""
    quiet.feature("fresh", code=False)
    assert "feat__fresh" in quiet.view().unmerged
    quiet.main_commit("main moves on\n")  # now behind the default ref, still nothing own
    view = quiet.view()
    assert view.features == () and "feat__fresh" in view.unmerged


def test_a_feature_root_with_no_base_is_merged_only_by_the_forge(quiet: Product) -> None:
    quiet.feature("a")
    (quiet.feature_root("a") / "BASE").unlink()
    sha = quiet.merge("a")
    view = quiet.view()
    assert "feat__a" in view.unmerged
    assert any("records no BASE" in n for n in view.notices), view.notices
    forge = FakeForge({"feat/a": [MergedPr(3, None, sha)]})
    (a,) = quiet.view(forge).features
    assert a.how == "forge" and a.sha == sha and a.pr == 3


# --- review p5-r2: squash and rebase merges, through the forge ---------------------


def test_a_squash_merge_is_found_only_through_the_forge(quiet: Product) -> None:
    quiet.feature("a")
    quiet.feature("b")
    head = git(quiet.root, "rev-parse", "feat/a").strip()
    squashed = quiet.merge("a", squash=True)
    merged_b = quiet.merge("b")
    view = quiet.view()
    assert [f.feature for f in view.features] == ["feat__b"] and "feat__a" in view.unmerged
    assert "squash or rebase merge" in view.no_merge("feat/a")
    assert "not read" in view.no_merge("feat/a")
    forge = FakeForge({"feat/a": [MergedPr(7, head, squashed)]})
    view = quiet.view(forge)
    assert [(f.feature, f.sha) for f in view.features] == [
        ("feat__a", squashed),
        ("feat__b", merged_b),
    ]
    a = view.get("feat__a")
    assert a is not None and a.how == "forge" and a.pr == 7 and a.heads == (head,)
    assert forge.asked == ["feat/a"]  # a git merge never asks the forge


def test_a_forge_merge_commit_off_the_first_parent_line_is_not_a_merge(quiet: Product) -> None:
    quiet.feature("a")
    quiet.merge("a", squash=True)
    side = git(quiet.root, "rev-parse", "feat/a").strip()  # reachable, not first-parent
    view = quiet.view(FakeForge({"feat/a": [MergedPr(7, None, side)]}))
    assert view.features == () and view.forge == "read"


def test_an_earlier_branch_of_the_same_name_is_not_this_feature(quiet: Product) -> None:
    """A PR merged before the feature claimed its root (its merge commit is in BASE)
    belongs to an older branch that bore the name."""
    old = quiet.main_commit("an old feat/a, squashed long ago\n")
    quiet.feature("a")
    view = quiet.view(FakeForge({"feat/a": [MergedPr(1, None, old)]}))
    assert view.features == () and "feat__a" in view.unmerged


def test_an_unreadable_forge_leaves_the_feature_unmerged_and_says_why(quiet: Product) -> None:
    quiet.feature("a")
    quiet.merge("a", squash=True)
    view = quiet.view(FakeForge(fail=True))
    assert "feat__a" in view.unmerged
    assert "unreadable (RuntimeError: HTTP 401)" in view.no_merge("feat/a")


def test_a_forge_merge_record_is_a_cache_on_a_recorded_head(quiet: Product) -> None:
    quiet.feature("a")
    head = git(quiet.root, "rev-parse", "feat/a").strip()
    squashed = quiet.merge("a", squash=True)
    append_record(quiet.feature_root("a"), squashed, (head,), pr=7)
    quiet.delete_branch("a")
    (a,) = quiet.view().features  # no forge: the record's head is one fr recorded
    assert a.how == "record" and a.cached and a.sha == squashed and a.pr == 7
    (quiet.feature_root("a") / "HEADS").write_text("")  # no owned head corroborates it
    view = quiet.view()
    assert view.features == () and any("never the truth" in n for n in view.notices)


# --- review p5-r4: a record is a cache, never a source ----------------------------


def test_a_forged_record_for_a_deleted_branch_is_ignored(quiet: Product) -> None:
    quiet.feature("a")  # never merged
    main = git(quiet.root, "rev-parse", "main").strip()
    quiet.delete_branch("a")
    append_record(quiet.feature_root("a"), main, (main,))
    append_record(quiet.feature_root("a"), main, (main,), pr=9)  # base-equal: refused too
    view = quiet.view()
    assert view.features == () and "feat__a" in view.unmerged
    assert any("never the truth" in n for n in view.notices), view.notices


# --- review p5-r6: the branch's remote is the default ref's ----------------------


def test_the_branchs_remote_head_is_read_from_the_default_refs_remote(quiet: Product) -> None:
    origin = git(quiet.root, "remote", "get-url", "origin").strip()
    git(quiet.root, "remote", "add", "up", origin)
    git(quiet.root, "config", "checkout.defaultRemote", "up")
    quiet.feature("a", push=False)
    git(quiet.root, "push", "-q", "up", "feat/a")
    sha = quiet.merge("a")
    git(quiet.root, "fetch", "-q", "up")
    git(quiet.root, "branch", "-q", "-D", "feat/a")
    (a,) = quiet.view().features  # only refs/remotes/up/feat/a holds its head
    assert a.sha == sha and quiet.view().ref == "refs/remotes/up/main"


def test_the_repo_placement_has_no_feature_roots_to_judge(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    view = merged_features(space_for(repo), repo)
    assert view.features == () and view.unmerged == ()


# --- the fold under quiet ----------------------------------------------------------


def _status(root: Path, row: str = ROW) -> str:
    clear_fold_cache()
    rows = {r.id: r for r in effective(root).matrix.rows}
    return rows[row].status


def test_an_unmerged_features_amendments_apply_in_its_own_view_only(
    quiet: Product, tmp_path: Path
) -> None:
    quiet.feature("a", rows=[_row(ROW)])
    quiet.merge("a")
    quiet.feature("b", amendments=[_amend(ROW, 0, "unwired")])
    assert _status(quiet.root) == "not-implemented"  # feat/view: b's amendment is not merged
    # b's own view adds its pending amendment
    git(quiet.root, "checkout", "-q", "feat/b")
    try:
        assert _status(quiet.root) == "unwired"
    finally:
        git(quiet.root, "checkout", "-q", quiet.home)
    quiet.merge("b")
    assert _status(quiet.root) == "unwired"


@pytest.mark.parametrize(("first", "last", "final"), [("b", "c", "ci"), ("c", "b", "unwired")])
def test_merged_amendments_apply_in_merge_order(
    quiet: Product, first: str, last: str, final: str
) -> None:
    quiet.feature("a", rows=[_row(ROW)])
    quiet.merge("a")
    quiet.feature("b", amendments=[_amend(ROW, 0, "unwired")])
    quiet.feature("c", amendments=[_amend(ROW, 0, "ci")])
    quiet.merge(first)
    quiet.merge(last)
    clear_fold_cache()
    folded = effective(quiet.root)
    assert {r.id: r.status for r in folded.matrix.rows}[ROW] == final
    assert ROW in folded.contested  # the second one was written against base 0


def test_the_fold_reports_an_ignored_record(quiet: Product) -> None:
    quiet.feature("a", rows=[_row(ROW)])
    quiet.merge("a")
    tip = quiet.main_commit("x\n")
    quiet.feature("b", amendments=[_amend(ROW, 0, "ci")])
    append_record(quiet.feature_root("b"), tip, (tip,))
    clear_fold_cache()
    folded = effective(quiet.root)
    assert {r.id: r.status for r in folded.matrix.rows}[ROW] == "not-implemented"
    assert any("never the truth" in n for n in folded.notices)


# --- review p5-r5: a merged feature's fragments are frozen at its merge -------------


def test_a_merged_features_later_amendment_is_pending_on_its_branch(quiet: Product) -> None:
    quiet.feature("a", rows=[_row(ROW)])
    quiet.merge("a")
    quiet.write_fragment("a", [_row(ROW)], [_amend(ROW, 0, "ci")])
    quiet.fr_commit("a", "chore(fr): a amends after its merge")  # pushed, but later
    assert _status(quiet.root) == "not-implemented"  # another view: not merged
    git(quiet.root, "checkout", "-q", "feat/a")
    try:
        folded = effective(quiet.root)
        assert {r.id: r.status for r in folded.matrix.rows}[ROW] == "ci"  # its own: pending
        assert len(folded.pending) == 1
    finally:
        git(quiet.root, "checkout", "-q", quiet.home)


def test_an_unpushed_fr_change_of_a_merged_feature_does_not_count(quiet: Product) -> None:
    quiet.feature("a", rows=[_row(ROW)])
    quiet.write_fragment("a", [_row(ROW)], [_amend(ROW, 0, "ci")])
    quiet.fr_commit("a", "chore(fr): local only", push=False)
    quiet.merge("a")
    assert _status(quiet.root) == "not-implemented"
    quiet.write_fragment("a", [_row(ROW, "ci")])  # and a working-tree edit, uncommitted
    assert _status(quiet.root) == "not-implemented"


def test_an_in_place_edit_of_a_merged_row_is_refused_under_quiet(quiet: Product) -> None:
    from fr.acceptance.amend import branch_refusals

    quiet.feature("a", rows=[_row(ROW)])
    quiet.merge("a")
    git(quiet.root, "checkout", "-q", "feat/a")
    try:
        assert branch_refusals(quiet.root, fetch=False).errors == []
        quiet.write_fragment("a", [_row(ROW, "ci")])  # the merged row, edited in place
        clear_fold_cache()
        folded = effective(quiet.root)
        assert {r.id: r.status for r in folded.matrix.rows}[ROW] == "not-implemented"
        assert any("differs from the merged one" in n for n in folded.notices)
        errors = branch_refusals(quiet.root, fetch=False).errors
        assert any(f"row {ROW} edited in place" in e for e in errors), errors
    finally:
        git(quiet.root, "checkout", "-q", quiet.home)


# --- stealth -----------------------------------------------------------------------


@pytest.fixture
def stealthy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Product:
    from fr.isolation.hostworktree import HostWorktreeTarget

    from tests.unit.stealth_repo import make_tracking

    target = make_repo(tmp_path)
    track = make_tracking(tmp_path)
    state = HostWorktreeTarget(target).up(
        profile=None, branch="feat/view", stealth=stealth.parse_ref(f"{track}@main")
    )
    monkeypatch.chdir(state.worktree)
    space = space_for(state.worktree)
    assert space.placement == "stealth"
    return Product(state.worktree, space, ops=target)


def test_stealth_merged_status_comes_from_the_targets_default_ref(stealthy: Product) -> None:
    stealthy.feature("a", rows=[_row(ROW)])
    stealthy.feature("b", amendments=[_amend(ROW, 0, "ci")])
    stealthy.merge("a")
    assert [f.feature for f in stealthy.view().features] == ["feat__a"]
    assert _status(stealthy.root) == "not-implemented"
    stealthy.merge("b")
    assert _status(stealthy.root) == "ci"


def test_stealth_falls_back_on_the_recorded_product_head(stealthy: Product) -> None:
    stealthy.feature("a")
    sha = stealthy.merge("a")
    head = git(stealthy.root, "rev-parse", "feat/a").strip()
    runs = stealthy.feature_root("a") / KIND_DIRS["run"]
    assert json.loads((runs / f"claim{stealth.PLACEMENT_SUFFIX}").read_text()) == {
        "product_head": head
    }
    stealthy.delete_branch("a")
    (a,) = stealthy.view().features
    assert a.sha == sha and a.heads == (head,)


def test_no_test_wrote_outside_its_sandbox(quiet: Product, tmp_path: Path) -> None:
    assert Path(os.getcwd()).resolve().is_relative_to(tmp_path.resolve())


def test_acceptance_status_names_the_merged_features_and_the_ignored_records(
    quiet: Product,
) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    quiet.feature("a", rows=[_row(ROW)])
    quiet.merge("a")
    quiet.feature("b", amendments=[_amend(ROW, 0, "ci")])
    sha = quiet.merge("b")
    tip = quiet.main_commit("x\n")
    quiet.feature("c")
    append_record(quiet.feature_root("c"), tip, (tip,))
    clear_fold_cache()
    result = CliRunner().invoke(
        app, ["acceptance", "status"], env={**os.environ, "FR_REPO_ROOT": str(quiet.root)}
    )
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "acceptance: ci: 1" in out
    assert "merged: feat__a" in out and f"feat__b at {sha[:12]}" in out
    assert "feat__c" in out and "never the truth" in out


def _fr_ok(root: Path, *argv: str) -> str:
    from fr.cli import app
    from typer.testing import CliRunner

    clear_fold_cache()
    result = CliRunner().invoke(app, list(argv), env={**os.environ, "FR_REPO_ROOT": str(root)})
    assert result.exit_code == 0, result.output
    return result.output


@pytest.mark.parametrize("verb", ["amend", "set-status"])
def test_a_feature_amends_a_row_another_merged_feature_owns(quiet: Product, verb: str) -> None:
    """Under quiet a merged feature's row lives in ITS feature path; another feature's
    branch changes it only by an amendment in its own fragment (R16), validated against
    the fold this branch sees (merged features included)."""
    quiet.feature("a", rows=[_row(ROW)])
    quiet.merge("a")
    argv = (
        ["acceptance", "amend", "--id", ROW, "--op", "set-status", "--why", "w"]
        if verb == "amend"
        else ["acceptance", "set-status", "--id", ROW]
    )
    _fr_ok(quiet.root, *argv, "--status", "unwired", "--notes", "n", "--feature", "2026-01-02-v")
    own = quiet.space.root / "features" / "feat__view" / KIND_DIRS["acceptance-fragment"]
    data = yaml.safe_load((own / "2026-01-02-v.yaml").read_text())
    assert not data.get("rows") and data["amendments"][0]["row"] == ROW
    assert data["amendments"][0]["base"] == 0
    # feature a's fragment is untouched, and this branch's view applies the amendment
    a = quiet.feature_root("a") / KIND_DIRS["acceptance-fragment"] / "a.yaml"
    assert "amendments: []" in a.read_text()
    assert _status(quiet.root) == "unwired"
