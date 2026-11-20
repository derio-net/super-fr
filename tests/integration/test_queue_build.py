"""Building combinations into the queue's slots over a real bare remote (spec
2026-11-19-wave-merge-queue R4, R5, R6, §C; Test Plan 1, 2, 7).

`fr.triage.queue_exec.build` puts each entry on top of the one ahead of it, in the
repo's merge method, and pushes entry k's commit to `fr-queue/<scope>/slot-<k>`, leased
on the sha the slot held. No PR branch moves.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.triage.batch_merge import MergeConflictError
from fr.triage.gitseam import LeaseLostError
from fr.triage.model import QueueBuiltEvent
from fr.triage.queue_exec import build, slot_ref

from tests.integration.queue_git import SCOPE, World, git, version_block, world


def _two(tmp_path: Path) -> World:
    w = world(tmp_path)
    w.pr(1, {"b.txt": "bravo\n"}, title="Add bravo")
    w.pr(2, {"c.txt": "charlie\n", "d.txt": "delta\n"}, title="Add charlie", commits=2)
    w.fetch()
    return w


def _build(w: World, method: str, **kw: object) -> list:
    base = w.main()
    return build(
        w.checkout, base, [w.entry(1), w.entry(2)], method, None, scope=SCOPE,
        slots=(1, 2), scratch=w.scratch, **kw,  # type: ignore[arg-type]
    )  # fmt: skip


def _files(w: World, sha: str) -> set[str]:
    return set(git(w.origin, "ls-tree", "-r", "--name-only", sha).split())


def test_squash_builds_one_commit_per_entry_into_slots_and_moves_no_pr_branch(
    tmp_path: Path,
) -> None:
    w = _two(tmp_path)
    base, heads = w.main(), (w.head(1), w.head(2))
    built = _build(w, "squash")
    one, two = built
    assert w.remote(slot_ref(SCOPE, 1)) == one.sha and w.remote(slot_ref(SCOPE, 2)) == two.sha
    assert git(w.origin, "rev-list", "--parents", "-1", one.sha).split()[1:] == [base]
    assert git(w.origin, "rev-list", "--parents", "-1", two.sha).split()[1:] == [one.sha]
    assert git(w.origin, "log", "-1", "--format=%s", one.sha) == "Add bravo (#1)"
    assert git(w.origin, "log", "-1", "--format=%s", two.sha) == "Add charlie (#2)"
    assert _files(w, one.sha) >= {"a.txt", "b.txt"} and "c.txt" not in _files(w, one.sha)
    assert _files(w, two.sha) >= {"a.txt", "b.txt", "c.txt", "d.txt"}  # PR 2's whole change
    assert (w.head(1), w.head(2)) == heads and w.main() == base
    assert (one.parent, two.parent) == (base, one.sha) and one.base == two.base == base


def test_merge_builds_no_ff_merge_commits_with_the_forge_subject(tmp_path: Path) -> None:
    w = _two(tmp_path)
    one, two = _build(w, "merge")
    parents = git(w.origin, "rev-list", "--parents", "-1", two.sha).split()[1:]
    assert parents == [one.sha, w.head(2)]
    assert git(w.origin, "log", "-1", "--format=%s", one.sha) == (
        "Merge pull request #1 from feat/pr-1"
    )


def test_rebase_replays_the_prs_commits(tmp_path: Path) -> None:
    w = _two(tmp_path)
    one, two = _build(w, "rebase")
    replayed = git(w.origin, "log", "--format=%s", f"{one.sha}..{two.sha}").splitlines()
    assert replayed == ["pr 2 part 1", "pr 2 part 0"]
    assert git(w.origin, "rev-list", "--count", "--merges", f"{w.main()}..{two.sha}") == "0"


def test_a_rebuild_of_the_same_inputs_has_the_same_tree_and_a_new_sha(tmp_path: Path) -> None:
    w = _two(tmp_path)
    first = _build(w, "squash")
    again = _build(w, "squash", leases={1: first[0].sha, 2: first[1].sha})
    assert [b.tree for b in again] == [b.tree for b in first]
    assert [b.sha for b in again] != [b.sha for b in first]
    assert all(a.sha != b.sha for a, b in zip(again, first, strict=True))


def test_each_build_is_recorded_before_its_slot_push(tmp_path: Path) -> None:
    w = _two(tmp_path)
    seen: list[tuple[QueueBuiltEvent, str | None]] = []

    def record(event: QueueBuiltEvent) -> None:
        seen.append((event, w.checkout.remote_sha(slot_ref(SCOPE, event.slot))))

    built = _build(w, "squash", record=record)
    assert [(e.slot, e.sha, e.parent, e.head) for e, _ in seen] == [
        (b.slot, b.sha, b.parent, b.entry.head) for b in built
    ]
    assert [pushed for _, pushed in seen] == [None, None]  # recorded first
    assert all(e.base == w.main() and e.patch_id for e, _ in seen)


def test_a_stale_slot_lease_fails_the_push(tmp_path: Path) -> None:
    w = _two(tmp_path)
    _build(w, "squash")
    with pytest.raises(LeaseLostError):
        _build(w, "squash", leases={1: w.main(), 2: None})


def _versioned(tmp_path: Path, b_files: dict[str, str]) -> World:
    w = world(tmp_path)
    w.pr(1, {"b.txt": "bravo\n"}, version="1.0.1")
    w.pr(2, b_files, version="1.0.2")  # conflicts with 1.0.1 in the version line alone
    w.fetch()
    return w


def test_a_version_only_conflict_is_resolved_and_carries_the_slot(tmp_path: Path) -> None:
    w = _versioned(tmp_path, {"c.txt": "charlie\n"})
    one, two = build(
        w.checkout, w.main(), [w.entry(1, bump="patch"), w.entry(2, bump="minor")], "squash",
        version_block(), scope=SCOPE, slots=(1, 2), scratch=w.scratch,
    )  # fmt: skip
    assert 'version = "1.0.1"' in git(w.origin, "show", f"{one.sha}:pyproject.toml")
    assert 'version = "1.1.0"' in git(w.origin, "show", f"{two.sha}:pyproject.toml")
    assert _files(w, two.sha) >= {"b.txt", "c.txt"}


def test_any_other_conflict_raises_with_its_paths(tmp_path: Path) -> None:
    w = world(tmp_path)
    w.pr(1, {"a.txt": "alpha one\n"})
    w.pr(2, {"a.txt": "alpha two\n"})
    w.fetch()
    with pytest.raises(MergeConflictError) as raised:
        _build(w, "squash")
    assert raised.value.paths == ("a.txt",) and raised.value.batch == "b2"
    assert raised.value.head == w.head(2)
    assert w.remote(slot_ref(SCOPE, 1))  # the entry ahead was built


def _merge_pr(w: World, *, evil: bool) -> None:
    """PR 1 whose branch holds a merge commit: a side branch merged into it, with a line
    the merge itself adds when *evil* (content no non-merge commit carries)."""
    seed = w.seed
    git(seed, "fetch", "--quiet", "origin")
    git(seed, "checkout", "--quiet", "-B", "feat/pr-1", "origin/main")
    (seed / "b.txt").write_text("bravo\n")
    git(seed, "add", "--all")
    git(seed, "commit", "--quiet", "-m", "pr 1 part 0")
    git(seed, "checkout", "--quiet", "-B", "side", "origin/main")
    (seed / "s.txt").write_text("side\n")
    git(seed, "add", "--all")
    git(seed, "commit", "--quiet", "-m", "side work")
    git(seed, "checkout", "--quiet", "feat/pr-1")
    git(seed, "merge", "--quiet", "--no-ff", "--no-commit", "side")
    if evil:
        (seed / "s.txt").write_text("side\nresolved by the merge\n")
        git(seed, "add", "--all")
    git(seed, "commit", "--quiet", "-m", "merge side")
    git(seed, "push", "--quiet", "--force", "origin", "feat/pr-1:feat/pr-1")
    git(seed, "checkout", "--quiet", "--detach")
    w.prs[1], w.titles[1] = "feat/pr-1", "Add bravo"
    w.fetch()


def test_rebase_ejects_a_pr_whose_merge_commits_carry_content(tmp_path: Path) -> None:
    """p3-r9: `rebase` replays a branch's non-merge commits only, so what a merge commit
    adds (an evil merge, a conflict resolution) would be dropped silently. The replayed
    tree is compared with a plain merge's, and a difference ejects the entry by name."""
    w = world(tmp_path)
    _merge_pr(w, evil=True)
    with pytest.raises(MergeConflictError) as raised:
        build(w.checkout, w.main(), [w.entry(1)], "rebase", None, scope=SCOPE, slots=(1,),
              scratch=w.scratch)  # fmt: skip
    assert "rebase would drop content from its merge commits" in str(raised.value)
    assert "squash or merge" in str(raised.value)
    assert raised.value.paths == ("s.txt",) and raised.value.batch == "b1"
    assert w.checkout.remote_sha(slot_ref(SCOPE, 1)) is None  # nothing pushed


def test_rebase_of_a_branch_with_a_plain_merge_builds(tmp_path: Path) -> None:
    w = world(tmp_path)
    _merge_pr(w, evil=False)
    (one,) = build(w.checkout, w.main(), [w.entry(1)], "rebase", None, scope=SCOPE,
                   slots=(1,), scratch=w.scratch)  # fmt: skip
    assert _files(w, one.sha) >= {"a.txt", "b.txt", "s.txt"}


def test_a_slot_lease_lost_names_the_slot_and_its_combination(tmp_path: Path) -> None:
    from fr.triage.queue_exec import SlotLostError

    w = _two(tmp_path)
    _build(w, "squash")
    with pytest.raises(SlotLostError) as raised:
        _build(w, "squash", leases={1: w.main(), 2: None})
    assert raised.value.slot == 1 and raised.value.sha
    assert isinstance(raised.value, LeaseLostError)
