"""Merged status outside `repo` (spec 2026-11-04-repo-feature-settings R17's quiet and
stealth clause; plan 2026-11-12-placement-resolver phase 5, task 1).

Under quiet and stealth a feature is merged when its code branch's head is reachable
from the product's default ref, ordered by the first-parent commit that introduced it;
`merged:` records are a cache, never the truth. Every repo here is a local sandbox with
a bare origin; nothing reaches a network.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.acceptance.fold import clear_fold_cache, effective
from fr.artifacts.paths import KIND_DIRS, ArtifactSpace, space_for
from fr.placement import stealth
from fr.placement.merged import append_record, merged_features

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import QUIET, push_fr_branch

REPO = "derio-net/widgets"
ROW = "alpha-spins"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
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


class Product:
    """A product clone with feature roots below *space*'s root."""

    def __init__(self, root: Path, space: ArtifactSpace, ops: Path | None = None) -> None:
        self.root = root  # the checkout whose view is read
        self.ops = ops or root  # the checkout git operations run in
        self.space = space
        self.home = git(self.ops, "symbolic-ref", "--short", "HEAD").strip()

    def feature_root(self, name: str) -> Path:
        return self.space.root / "features" / f"feat__{name}"

    def feature(
        self,
        name: str,
        *,
        rows: Sequence[dict[str, Any]] = (),
        amendments: Sequence[dict[str, Any]] = (),
        push: bool = True,
    ) -> None:
        """Branch `feat/<name>` from main with one code commit, and its feature root."""
        git(self.ops, "checkout", "-q", "-b", f"feat/{name}", "main")
        (self.ops / f"{name}.txt").write_text(f"{name}\n")
        git(self.ops, "add", "-A")
        git(self.ops, "commit", "-qm", f"feat({name}): code")
        if push:
            git(self.ops, "push", "-q", "origin", f"feat/{name}")
        git(self.ops, "checkout", "-q", self.home)
        froot = self.feature_root(name)
        froot.mkdir(parents=True, exist_ok=True)
        (froot / "OWNER").write_text(f"feat/{name}\n")
        if rows or amendments:
            frag = froot / KIND_DIRS["acceptance-fragment"] / f"{name}.yaml"
            frag.parent.mkdir(parents=True, exist_ok=True)
            data = {"schema_version": 1, "feature": name, "repo": REPO, "rows": list(rows),
                    "amendments": list(amendments)}  # fmt: skip
            frag.write_text(yaml.safe_dump(data, sort_keys=False))

    def merge(self, name: str, *, ff: bool = False) -> str:
        """Merge `feat/<name>` into main (a merge commit unless *ff*), push; main's tip."""
        git(self.ops, "checkout", "-q", "main")
        git(self.ops, "merge", "-q", "--ff-only" if ff else "--no-ff", "-m",
            f"Merge feat/{name}", f"feat/{name}")  # fmt: skip
        git(self.ops, "push", "-q", "origin", "main")
        git(self.ops, "checkout", "-q", self.home)
        return git(self.ops, "rev-parse", "main").strip()

    def main_commit(self, text: str) -> str:
        git(self.ops, "checkout", "-q", "main")
        (self.ops / "main.txt").write_text(text)
        git(self.ops, "add", "-A")
        git(self.ops, "commit", "-qm", "main moves")
        git(self.ops, "push", "-q", "origin", "main")
        git(self.ops, "checkout", "-q", self.home)
        return git(self.ops, "rev-parse", "main").strip()

    def view(self):  # type: ignore[no-untyped-def]
        return merged_features(self.space, self.root)


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


def test_unpushed_work_after_a_merge_is_not_merged(quiet: Product) -> None:
    quiet.feature("a")
    quiet.merge("a")
    git(quiet.root, "checkout", "-q", "feat/a")
    (quiet.root / "more.txt").write_text("more\n")
    git(quiet.root, "add", "-A")
    git(quiet.root, "commit", "-qm", "more")
    git(quiet.root, "checkout", "-q", quiet.home)
    assert quiet.view().get("feat__a") is None


def test_a_deleted_branch_stays_merged_through_its_verified_record(quiet: Product) -> None:
    quiet.feature("a")
    sha = quiet.merge("a")
    head = git(quiet.root, "rev-parse", "feat/a").strip()
    append_record(quiet.feature_root("a"), sha, (head,))
    git(quiet.root, "branch", "-q", "-D", "feat/a")
    git(quiet.root, "push", "-q", "origin", "--delete", "feat/a")
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
    runs.mkdir(parents=True)
    (runs / f"r1{stealth.PLACEMENT_SUFFIX}").write_text(json.dumps({"product_head": head}))
    git(stealthy.ops, "branch", "-q", "-D", "feat/a")
    git(stealthy.ops, "push", "-q", "origin", "--delete", "feat/a")
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
