"""The effective-matrix fold (spec 2026-11-04-repo-feature-settings R17, §3.D).

Every case builds a real repo with a bare origin: merge order is git's first-parent
history of the default ref, so it can only be tested against git.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.acceptance.fold import FoldError, FoldHistoryError, clear_fold_cache, fold, git_runner

REPO = "derio-net/widgets"
OWNER = "2026-01-01-alpha"
ROW = "alpha-spins"


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
        env={
            **{k: v for k, v in os.environ.items() if not k.startswith("GIT_DIR")},
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )
    return done.stdout


def _row(row_id: str, *, capability: str = "widgets", status: str = "ci") -> dict[str, Any]:
    return {
        "id": row_id,
        "capability": capability,
        "acceptance": f"{row_id} holds.",
        "origin": [f"spec:{OWNER}#R1"],
        "status": status,
    }


def _amend(row: str, base: int, status: str, why: str = "moved") -> dict[str, Any]:
    return {
        "row": row,
        "op": "set-status",
        "base": base,
        "status": status,
        "notes": why,
        "why": why,
    }


class Repo:
    """A working clone of a bare origin; `main` is the default branch."""

    def __init__(self, tmp: Path, *, remote: bool = True) -> None:
        self.root = tmp / "work"
        self.root.mkdir()
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "commit", "-q", "--allow-empty", "-m", "init")
        self.remote = remote
        if remote:
            self.origin = tmp / "origin.git"
            _git(tmp, "init", "-q", "--bare", "-b", "main", str(self.origin))
            _git(self.root, "remote", "add", "origin", str(self.origin))
            self.push()

    def push(self, branch: str = "main") -> None:
        _git(self.root, "push", "-q", "origin", branch)
        _git(self.root, "fetch", "-q", "origin")

    def write(
        self,
        feature: str,
        *,
        rows: Sequence[dict[str, Any]] = (),
        amendments: Sequence[dict[str, Any]] = (),
    ) -> None:
        path = self.root / "docs/acceptance/features" / f"{feature}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": 1,
            "feature": feature,
            "repo": REPO,
            "rows": list(rows),
            "amendments": list(amendments),
        }
        path.write_text(yaml.safe_dump(data, sort_keys=False))

    def commit(self, message: str) -> None:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", message)

    def checkout(self, branch: str, *, new: bool = False) -> None:
        _git(self.root, "checkout", "-q", *(["-b"] if new else []), branch)

    def merge_feature(self, branch: str) -> None:
        """Merge *branch* into main with --no-ff, push main, return to main."""
        self.checkout("main")
        _git(self.root, "merge", "-q", "--no-ff", branch, "-m", f"merge {branch}")
        if self.remote:
            self.push()

    def feature(
        self,
        feature: str,
        *,
        rows: Sequence[dict[str, Any]] = (),
        amendments: Sequence[dict[str, Any]] = (),
        merge: bool = True,
    ) -> None:
        """Branch from main, write *feature*'s fragment, commit, and (by default) merge it."""
        self.checkout("main")
        self.checkout(f"feat/{feature}", new=True)
        self.write(feature, rows=rows, amendments=amendments)
        self.commit(f"feat: {feature}")
        if merge:
            self.merge_feature(f"feat/{feature}")


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    clear_fold_cache()


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    r = Repo(tmp_path)
    r.feature(OWNER, rows=[_row(ROW)])
    return r


def _status(effective: Any, row_id: str = ROW) -> str:
    return next(r.status for r in effective.matrix.rows if r.id == row_id)


def test_merged_features_yield_the_union_of_their_rows(repo: Repo) -> None:
    repo.feature("2026-01-02-beta", rows=[_row("beta-hums", capability="audio")])
    eff = fold(repo.root)
    assert [r.id for r in eff.matrix.rows] == ["beta-hums", ROW], "capability, then fragment"
    assert (eff.matrix.org, eff.matrix.repo) == ("derio-net", "widgets")
    assert eff.owners == {ROW: OWNER, "beta-hums": "2026-01-02-beta"}
    assert eff.revisions == {ROW: 0, "beta-hums": 0}
    assert eff.pending == ()


def test_another_features_amendment_applies_and_counts_a_revision(repo: Repo) -> None:
    repo.feature("2026-01-02-beta", amendments=[_amend(ROW, 0, "unwired")])
    eff = fold(repo.root)
    assert _status(eff) == "unwired"
    assert eff.revisions[ROW] == 1
    assert eff.contested == frozenset()
    assert eff.owners[ROW] == OWNER, "an amendment never moves ownership"


def test_amendments_apply_in_merge_order_not_name_order(repo: Repo) -> None:
    # z merges first, b second: name order would apply b's base-1 amendment first.
    repo.feature("2026-01-03-zulu", amendments=[_amend(ROW, 0, "unwired")])
    repo.feature("2026-01-02-bravo", amendments=[_amend(ROW, 1, "walk-owed")])
    eff = fold(repo.root)
    assert _status(eff) == "walk-owed"
    assert eff.revisions[ROW] == 2
    assert eff.contested == frozenset()


def test_ties_inside_one_commit_break_by_base_then_feature_slug_then_index(repo: Repo) -> None:
    # Plan journal `fold-ties-break-by-base` (supersedes the slug-first tie, pr1408-r6).
    repo.checkout("feat/both", new=True)
    repo.write("2026-01-03-charlie", amendments=[_amend(ROW, 0, "manual")])
    repo.write("2026-01-02-bravo", amendments=[_amend(ROW, 0, "unwired"), _amend(ROW, 1, "ci")])
    repo.commit("feat: both")
    repo.merge_feature("feat/both")
    eff = fold(repo.root)
    # bravo[0] (base 0 ok), charlie[0] (base 0, stale at 1), bravo[1] (base 1, stale at 2)
    assert _status(eff) == "ci"
    assert eff.revisions[ROW] == 3
    assert eff.contested == frozenset({ROW})


def _two_fragment_branch(repo: Repo) -> None:
    """One branch amends ROW through fragment zz (base 0), then through aa (base 1)."""
    repo.checkout("feat/two", new=True)
    repo.write("2026-01-09-zz", amendments=[_amend(ROW, 0, "unwired", why="first")])
    repo.commit("feat: zz")
    repo.write("2026-01-08-aa", amendments=[_amend(ROW, 1, "walk-owed", why="second")])
    repo.commit("feat: aa")


def test_a_branchs_own_sequence_across_two_fragments_is_not_stale(repo: Repo) -> None:
    # pr1408-r6: pending amendments order the way the merged fold will.
    _two_fragment_branch(repo)
    eff = fold(repo.root)
    assert eff.stale_pending == ()
    assert eff.contested == frozenset()
    assert _status(eff) == "walk-owed"
    assert [a.why for a in eff.pending] == ["first", "second"]


def test_the_same_sequence_merged_by_merge_commit_folds_clean(repo: Repo) -> None:
    _two_fragment_branch(repo)
    repo.merge_feature("feat/two")
    eff = fold(repo.root)
    assert eff.contested == frozenset()
    assert _status(eff) == "walk-owed"
    assert eff.revisions[ROW] == 2


def test_the_same_sequence_merged_by_squash_folds_clean(repo: Repo) -> None:
    _two_fragment_branch(repo)
    repo.checkout("main")
    _git(repo.root, "merge", "-q", "--squash", "feat/two")
    repo.commit("feat: two (squashed)")
    repo.push()
    eff = fold(repo.root)
    assert eff.contested == frozenset()
    assert _status(eff) == "walk-owed"


def test_amendments_added_to_an_existing_fragment_take_their_own_merge_position(
    repo: Repo,
) -> None:
    repo.feature("2026-01-02-bravo", amendments=[_amend(ROW, 0, "unwired")])
    repo.feature("2026-01-03-charlie", amendments=[_amend(ROW, 1, "manual")])
    # A later plan of bravo appends to bravo's fragment: it merges after charlie.
    repo.checkout("main")
    repo.checkout("feat/bravo-2", new=True)
    repo.write("2026-01-02-bravo", amendments=[_amend(ROW, 0, "unwired"), _amend(ROW, 2, "ci")])
    repo.commit("feat: bravo plan 2")
    repo.merge_feature("feat/bravo-2")
    eff = fold(repo.root)
    assert _status(eff) == "ci"
    assert eff.revisions[ROW] == 3
    assert eff.contested == frozenset()


def test_an_amendment_inserted_above_a_merged_one_takes_its_own_merge_position(
    repo: Repo,
) -> None:
    # pr1408-r8: the merged order is found by value, not by list position (the
    # insert is refused before merge, so this shape needs a check bypass).
    first = _amend(ROW, 0, "unwired", why="first")
    repo.feature("2026-01-02-bravo", amendments=[first])
    repo.feature("2026-01-03-charlie", amendments=[_amend(ROW, 1, "manual")])
    repo.checkout("feat/bravo-2", new=True)
    repo.write("2026-01-02-bravo", amendments=[_amend(ROW, 2, "ci", why="third"), first])
    repo.commit("feat: bravo plan 2, inserted above")
    repo.merge_feature("feat/bravo-2")
    eff = fold(repo.root)
    assert _status(eff) == "ci"
    assert eff.contested == frozenset()


def test_a_branchs_own_entries_apply_after_every_merged_one(repo: Repo) -> None:
    # The branch is cut before zulu merges and never rebased.
    repo.checkout("feat/mine", new=True)
    repo.feature("2026-01-03-zulu", amendments=[_amend(ROW, 0, "unwired")])
    repo.checkout("feat/mine")
    repo.write(
        "2026-01-04-mine",
        rows=[_row("mine-new")],
        amendments=[_amend(ROW, 1, "walk-owed", why="mine")],
    )
    repo.commit("feat: mine")
    eff = fold(repo.root)
    assert _status(eff) == "walk-owed"
    assert eff.revisions[ROW] == 2
    assert eff.contested == frozenset()
    assert [a.why for a in eff.pending] == ["mine"]
    assert eff.owners["mine-new"] == "2026-01-04-mine"
    assert fold(repo.root, include_pending=False).revisions == {ROW: 1}


def test_an_unmerged_branch_contributes_nothing_to_another_branch(repo: Repo) -> None:
    repo.feature("2026-01-05-abandoned", amendments=[_amend(ROW, 0, "failing")], merge=False)
    repo.feature("2026-01-06-later", rows=[_row("later-row")])
    for branch in ("main", "feat/2026-01-06-later"):
        repo.checkout(branch)
        eff = fold(repo.root)
        assert _status(eff) == "ci", branch
        assert eff.revisions[ROW] == 0
        assert eff.pending == ()


def test_a_stale_base_marks_the_row_contested_until_a_current_one_clears_it(repo: Repo) -> None:
    repo.feature("2026-01-02-bravo", amendments=[_amend(ROW, 0, "unwired")])
    repo.feature("2026-01-03-charlie", amendments=[_amend(ROW, 0, "manual")])
    eff = fold(repo.root)
    assert _status(eff) == "manual", "a stale amendment still applies"
    assert eff.contested == frozenset({ROW})
    assert eff.revisions[ROW] == 2
    repo.feature("2026-01-04-delta", amendments=[_amend(ROW, 2, "ci")])
    eff = fold(repo.root)
    assert eff.contested == frozenset()
    assert eff.revisions[ROW] == 3


def test_a_row_defined_twice_names_both_files(repo: Repo) -> None:
    repo.feature("2026-01-02-bravo", rows=[_row(ROW)])
    with pytest.raises(FoldError) as e:
        fold(repo.root)
    assert f"{OWNER}.yaml" in str(e.value) and "2026-01-02-bravo.yaml" in str(e.value)


def test_a_pending_amendment_naming_an_unknown_row_is_an_error(repo: Repo) -> None:
    repo.feature("2026-01-02-bravo", amendments=[_amend("no-such-row", 0, "ci")], merge=False)
    with pytest.raises(FoldError, match="no-such-row"):
        fold(repo.root)


def test_a_merged_amendment_naming_an_unknown_row_is_a_notice_not_an_error(repo: Repo) -> None:
    # A merged entry is immutable: raising would break every default-ref reader
    # with no legal fix (review p1-r1).
    repo.feature("2026-01-02-bravo", amendments=[_amend("no-such-row", 0, "ci")])
    eff = fold(repo.root)
    assert [r.id for r in eff.matrix.rows] == [ROW]
    assert any("no-such-row" in n and "not applied" in n for n in eff.notices), eff.notices


def test_a_merged_amendment_to_a_row_retired_meanwhile_marks_it_contested(repo: Repo) -> None:
    # R17 "merged anyway": two features branched at revision 0; one retires the row,
    # the other's set-status merges after it.
    retire = {"row": ROW, "op": "retire", "base": 0, "notes": "superseded", "why": "gone"}
    repo.feature("2026-01-02-bravo", amendments=[retire])
    repo.feature("2026-01-03-charlie", amendments=[_amend(ROW, 0, "unwired")])
    eff = fold(repo.root)
    assert [r.id for r in eff.retired] == [ROW]
    assert eff.retired[0].status == "ci", "the late amendment is not applied"
    assert eff.contested == frozenset({ROW})
    assert eff.revisions[ROW] == 2
    assert any("retired row" in n for n in eff.notices), eff.notices


def test_a_stale_pending_amendment_to_a_retired_row_is_stale_not_an_error(repo: Repo) -> None:
    # pr1408-r1: a retired row keeps R17's base rule (plan journal
    # `fold-retired-rows-keep-the-base-rule`): a stale pending one is refused by
    # check/deliver as stale, never a FoldError that breaks every reader.
    retire = {"row": ROW, "op": "retire", "base": 0, "notes": "superseded", "why": "gone"}
    repo.feature("2026-01-02-bravo", amendments=[retire])
    repo.feature("2026-01-03-charlie", amendments=[_amend(ROW, 0, "unwired")], merge=False)
    eff = fold(repo.root)
    assert [(s.row, s.base, s.revision) for s in eff.stale_pending] == [(ROW, 0, 1)]
    assert [r.id for r in eff.retired] == [ROW]


def test_a_contested_retired_row_is_cleared_by_a_correctly_based_amendment(repo: Repo) -> None:
    # pr1408-r1: retired, then a stale set-status merged anyway (contested, revision 2).
    retire = {"row": ROW, "op": "retire", "base": 0, "notes": "superseded", "why": "gone"}
    repo.feature("2026-01-02-bravo", amendments=[retire])
    repo.feature("2026-01-03-charlie", amendments=[_amend(ROW, 0, "unwired")])
    assert fold(repo.root).contested == frozenset({ROW})
    repo.feature(
        "2026-01-04-delta",
        amendments=[{"row": ROW, "op": "retire", "base": 2, "notes": "gone", "why": "settle"}],
        merge=False,
    )
    eff = fold(repo.root)
    assert eff.stale_pending == ()
    assert eff.contested == frozenset(), "a correctly based amendment clears it"
    assert [r.id for r in eff.retired] == [ROW], "and the row stays retired"
    assert eff.revisions[ROW] == 3
    repo.merge_feature("feat/2026-01-04-delta")
    assert fold(repo.root).contested == frozenset()


def test_a_stale_retire_that_merged_anyway_leaves_the_row_contested(repo: Repo) -> None:
    # pr1408-r2: both branched at revision 0; the set-status merges first, then the retire.
    repo.feature("2026-01-02-bravo", amendments=[_amend(ROW, 0, "unwired")])
    retire = {"row": ROW, "op": "retire", "base": 0, "notes": "superseded", "why": "gone"}
    repo.feature("2026-01-03-charlie", amendments=[retire])
    eff = fold(repo.root)
    assert [r.id for r in eff.retired] == [ROW]
    assert eff.contested == frozenset({ROW}), "a stale retire is visible, as debt"


def test_retire_removes_the_row_and_keeps_it_listed(repo: Repo) -> None:
    retire = {"row": ROW, "op": "retire", "base": 0, "notes": "superseded", "why": "gone"}
    repo.feature("2026-01-02-bravo", amendments=[retire])
    eff = fold(repo.root)
    assert ROW not in {r.id for r in eff.matrix.rows}
    assert [r.id for r in eff.retired] == [ROW]
    assert eff.retired[0].notes == "superseded"


def test_every_op_applies(repo: Repo) -> None:
    unit = "widgets:tests/unit/test_w.py#test_spin"
    repo.feature(
        "2026-01-02-bravo",
        amendments=[
            {"row": ROW, "op": "reword", "base": 0, "why": "w", "acceptance": "New words."},
            {"row": ROW, "op": "add-level", "base": 1, "why": "w", "level": "unit", "ref": unit},
            {
                "row": ROW,
                "op": "set-status",
                "base": 2,
                "why": "w",
                "status": "unwired",
                "notes": "n",
                "issues": ["derio-net/widgets#3"],
            },
            {"row": ROW, "op": "drop-level", "base": 3, "why": "w", "level": "unit", "ref": unit},
        ],
    )
    (row,) = fold(repo.root).matrix.rows
    assert row.acceptance == "New words."
    assert row.levels["unit"] == ()
    assert (row.status, row.notes, row.issues) == ("unwired", "n", ("derio-net/widgets#3",))


def test_with_no_remote_heads_history_is_the_merged_history(tmp_path: Path) -> None:
    r = Repo(tmp_path, remote=False)
    r.feature(OWNER, rows=[_row(ROW)])
    r.feature("2026-01-02-bravo", amendments=[_amend(ROW, 0, "unwired")])
    eff = fold(r.root)
    assert _status(eff) == "unwired" and eff.revisions[ROW] == 1
    assert eff.pending == ()
    assert any("HEAD" in n for n in eff.notices), eff.notices


def test_a_shallow_clone_with_amendments_is_refused(repo: Repo, tmp_path: Path) -> None:
    repo.feature("2026-01-02-bravo", amendments=[_amend(ROW, 0, "unwired")])
    shallow = tmp_path / "shallow"
    _git(tmp_path, "clone", "-q", "--depth", "1", f"file://{repo.origin}", str(shallow))
    with pytest.raises(FoldHistoryError, match="fetch-depth: 0"):
        fold(shallow)


def test_a_shallow_clone_without_amendments_folds_its_rows(repo: Repo, tmp_path: Path) -> None:
    shallow = tmp_path / "shallow"
    _git(tmp_path, "clone", "-q", "--depth", "1", f"file://{repo.origin}", str(shallow))
    assert [r.id for r in fold(shallow).matrix.rows] == [ROW]


def test_the_no_default_ref_notice_is_not_served_from_the_cache_to_an_explicit_ref(
    tmp_path: Path,
) -> None:
    # Review p1-r2: same sha, different resolution; the notice must follow the call.
    r = Repo(tmp_path, remote=False)
    r.feature(OWNER, rows=[_row(ROW)])
    assert any("HEAD" in n for n in fold(r.root).notices)
    assert fold(r.root, ref="HEAD").notices == ()
    assert any("HEAD" in n for n in fold(r.root).notices)


def test_an_explicit_ref_folds_that_history(repo: Repo) -> None:
    repo.feature("2026-01-02-bravo", amendments=[_amend(ROW, 0, "unwired")], merge=False)
    eff = fold(repo.root, ref="feat/2026-01-02-bravo", include_pending=False)
    assert _status(eff) == "unwired"


def test_the_fold_is_memoised_and_returns_independent_copies(repo: Repo) -> None:
    calls: list[tuple[str, ...]] = []
    inner = git_runner(repo.root)

    def counting(args: Sequence[str], stdin: bytes | None = None) -> Any:
        calls.append(tuple(args))
        return inner(args, stdin)

    a = fold(repo.root, runner=counting)
    first = len(calls)
    b = fold(repo.root, runner=counting)
    assert a == b and a is not b
    assert len(calls) - first <= 1, "a repeat fold only re-reads the ref's commit"
    a.revisions[ROW] = 99
    assert b.revisions[ROW] == 0


def test_the_git_call_count_does_not_grow_with_history(tmp_path: Path) -> None:
    r = Repo(tmp_path)
    r.checkout("feat/many", new=True)
    r.write(OWNER, rows=[_row(ROW)])
    for i in range(120):
        r.write(f"2026-02-01-f{i:03d}", rows=[_row(f"row-{i:03d}")])
        if i % 10 == 9:
            r.commit(f"feat: batch {i}")
    r.merge_feature("feat/many")
    for i in range(20):
        r.checkout("main")
        r.checkout(f"feat/amend-{i}", new=True)
        r.write(
            f"2026-02-01-f{i:03d}",
            rows=[_row(f"row-{i:03d}")],
            amendments=[_amend(ROW, i, "unwired" if i % 2 else "ci")],
        )
        r.commit(f"feat: amend {i}")
        _git(r.root, "checkout", "-q", "main")
        _git(r.root, "merge", "-q", "--no-ff", f"feat/amend-{i}", "-m", f"merge {i}")
    r.push()
    calls: list[tuple[str, ...]] = []
    inner = git_runner(r.root)

    def counting(args: Sequence[str], stdin: bytes | None = None) -> Any:
        calls.append(tuple(args))
        return inner(args, stdin)

    eff = fold(r.root, runner=counting)
    assert eff.revisions[ROW] == 20 and eff.contested == frozenset()
    assert len(eff.matrix.rows) == 121
    # O(fragments-with-amendments + 1) is the ceiling; batched reads keep it constant.
    assert len(calls) <= 21, calls
    assert len(calls) <= 8, calls
