"""What a PR head carries of the combinations the queue built, and whether a commit still
leads to `main`, over a real bare remote (spec 2026-11-24-wave-queue-gaps R2, R4, R5; §F 3).

`Checkout.carried(head, target, built)` is the built shas `head` reaches that `target` does
not; `Checkout.leads(onto, target)` is whether `onto` is an ancestor of `target`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.triage.gitseam import GitError
from fr.triage.queue_exec import build, slot_ref

from tests.integration.queue_git import SCOPE, World, git, world


def _queue(tmp_path: Path) -> tuple[World, str, str]:
    """PRs 1 and 2 built into slots 1 and 2 (squash); PR 3's session merged slot 1."""
    w = world(tmp_path)
    w.pr(1, {"b.txt": "bravo\n"})
    w.pr(2, {"c.txt": "charlie\n"})
    w.pr(3, {"d.txt": "delta\n"})
    w.fetch()
    one, two = build(w.checkout, w.main(), [w.entry(1), w.entry(2)], "squash", None,
                     scope=SCOPE, slots=(1, 2), scratch=w.scratch)  # fmt: skip
    _merge_into(w, 3, one.sha)
    w.fetch()
    return w, one.sha, two.sha


def _merge_into(w: World, number: int, sha: str) -> None:
    branch = w.prs[number]
    git(w.seed, "fetch", "--quiet", "origin", f"{slot_ref(SCOPE, 1)}", f"{branch}")
    git(w.seed, "checkout", "--quiet", "-B", branch, f"origin/{branch}")
    git(w.seed, "merge", "--quiet", "--no-edit", sha)
    git(w.seed, "push", "--quiet", "origin", f"{branch}:{branch}")
    git(w.seed, "checkout", "--quiet", "--detach")


def test_a_head_that_merged_an_ejected_entrys_combination_carries_it(tmp_path: Path) -> None:
    w, one, two = _queue(tmp_path)
    # PR 1 is ejected: nothing stands, the target is `main`, which never held slot 1
    assert w.checkout.carried(w.head(3), w.main(), {one, two}) == (one,)
    assert w.checkout.leads(one, w.main()) is False


def test_a_combination_that_landed_mid_push_is_carried_by_nobody(tmp_path: Path) -> None:
    w, one, two = _queue(tmp_path)
    git(w.origin, "update-ref", "refs/heads/main", one)  # slot 1 landed by push
    w.fetch()
    assert w.checkout.carried(w.head(3), w.main(), {one, two}) == ()
    assert w.checkout.leads(one, w.main()) is True
    assert w.checkout.leads(one, two) is True  # slot 1 leads to slot 2 standing on it


def test_a_combination_rebuilt_fresh_into_mains_history_is_not_carried(tmp_path: Path) -> None:
    w, one, two = _queue(tmp_path)
    # R13: slot 1 rebuilt as a fresh commit with the same tree and parents, which landed
    tree = git(w.clone, "rev-parse", f"{one}^{{tree}}")
    parent = git(w.clone, "rev-parse", f"{one}^")
    fresh = git(w.clone, "commit-tree", tree, "-p", parent, "-m", "Add bravo (#1) fresh")
    git(w.clone, "push", "--quiet", "origin", f"{fresh}:refs/heads/main")
    w.fetch()
    assert fresh != one
    assert w.checkout.carried(w.head(3), w.main(), {one, two, fresh}) == ()


def test_a_head_that_merged_nothing_built_carries_nothing(tmp_path: Path) -> None:
    w, one, two = _queue(tmp_path)
    assert w.checkout.carried(w.head(2), w.main(), {one, two}) == ()


def test_an_unknown_object_raises(tmp_path: Path) -> None:
    w, one, two = _queue(tmp_path)
    ghost = "0" * 39 + "1"
    with pytest.raises(GitError):
        w.checkout.carried(ghost, w.main(), {one})
    with pytest.raises(GitError):
        w.checkout.leads(ghost, w.main())
