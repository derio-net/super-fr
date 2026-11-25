"""What a PR head carries of the combinations the queue built, and whether a commit still
leads to `main`, over a real bare remote (spec 2026-11-24-wave-queue-gaps R2, R4, R5; §F 3).

`Checkout.carried(head, target, built)` is the built shas `head` reaches that `target` does
not; `Checkout.leads(onto, target)` is whether `onto` is an ancestor of `target`.
"""

from __future__ import annotations

import subprocess
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


# ------------------------------------------------- the carry brief, run (review p1-r1, p1-r3)


def _run_brief_steps(w: World, tmp_path: Path, brief: str) -> tuple[Path, list[str]]:
    """Run the carry brief's steps 2-4 as a session would, in a fresh clone of PR 3."""
    import re

    work = tmp_path / "session"
    git(tmp_path, "clone", "--quiet", str(w.origin), str(work))
    git(work, "config", "user.email", "s@example.com")
    git(work, "config", "user.name", "session")
    git(work, "checkout", "--quiet", w.prs[3])
    steps = {ln[:2]: re.findall(r"`([^`]+)`", ln) for ln in brief.splitlines() if ln[:2] in
             ("2.", "3.")}  # fmt: skip
    fetch, rev_list = steps["2."][:2]
    git(work, *fetch.split()[1:])
    listed = git(work, *rev_list.split()[1:]).split()
    git(work, *steps["3."][0].split()[1:])
    for sha in listed:
        git(work, "cherry-pick", sha)
    return work, listed


@pytest.mark.parametrize("slotted", [True, False])
def test_the_carry_brief_drops_the_dead_slot_commit(tmp_path: Path, slotted: bool) -> None:
    from fr.triage.model import Batch
    from fr.triage.queue_handback import carry_brief

    w = world(tmp_path)
    w.pr(1, {"b.txt": "bravo\n"})
    w.pr(3, {"d.txt": "delta\n"})
    w.fetch()
    reset = w.head(3)
    (one,) = build(w.checkout, w.main(), [w.entry(1)], "squash", None, scope=SCOPE,
                   slots=(1,), scratch=w.scratch)  # fmt: skip
    _merge_into(w, 3, one.sha)
    w.push_to(3, {"d.txt": "delta, edited after the merge\n"})
    batch = Batch.model_validate({"id": "b3", "title": "change 3", "ids": ["super-fr#3"]})
    onto_ref = slot_ref(SCOPE, 1).removeprefix("refs/heads/") if slotted else "origin/main"
    brief = carry_brief(batch, pr=3, head=w.head(3), reset=reset, carried=(one.sha,),
                        onto=one.sha if slotted else w.main(), onto_ref=onto_ref,
                        branch=w.prs[3])  # fmt: skip

    work, listed = _run_brief_steps(w, tmp_path, brief)

    assert one.sha not in listed and len(listed) == 1
    gone = subprocess.run(["git", "merge-base", "--is-ancestor", one.sha, "HEAD"], cwd=work)
    assert gone.returncode == 1
    assert (work / "d.txt").read_text() == "delta, edited after the merge\n"
    assert not (work / "b.txt").exists()
