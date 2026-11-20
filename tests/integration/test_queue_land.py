"""Landing the longest green prefix over a real bare remote and a fake forge (spec
2026-11-19-wave-merge-queue R9, R10, R11, R22, R34, R35, §D; Test Plan 1-4, 14, 25).

`land_push` is ONE `git push --atomic`, leased on the base and on each head the
combination was built from; `land_merge` merges each PR through the forge at its
pinned head and then compares `main`'s tree with the tested one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fr.ghclient import UnsupportedBatchOps
from fr.triage.model import QueueLandEvent
from fr.triage.queue_exec import (
    Built,
    build,
    forge_refusal,
    land_merge,
    land_push,
    landings_of,
    read_back,
)

from tests.integration.queue_git import SCOPE, FakeForge, World, forge, git, world

AT = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def _two(tmp_path: Path, method: str) -> tuple[World, list[Built]]:
    w = world(tmp_path)
    w.pr(1, {"b.txt": "bravo\n"}, title="Add bravo")
    w.pr(2, {"c.txt": "charlie\n"}, title="Add charlie")
    w.fetch()
    built = build(w.checkout, w.main(), [w.entry(1), w.entry(2)], method, None,  # type: ignore[arg-type]
                  scope=SCOPE, slots=(1, 2), scratch=w.scratch)  # fmt: skip
    return w, built


def _land(w: World, built: list[Built], method: str, **kw: object):  # type: ignore[no-untyped-def]
    return land_push(w.checkout, default="main", base=built[0].base,
                     landings=landings_of(built), method=method, **kw)  # type: ignore[arg-type]  # fmt: skip


@pytest.mark.parametrize("method", ["squash", "rebase"])
def test_one_atomic_push_moves_main_to_the_tip_and_each_head_to_its_commit(
    tmp_path: Path, method: str
) -> None:
    w, built = _two(tmp_path, method)
    recorded: list[QueueLandEvent] = []
    result = _land(w, built, method, record=recorded.append, now=lambda: AT)
    assert result.outcome == "landed" and result.main == built[-1].sha
    assert w.main() == built[-1].sha  # exactly the tested commit (R9)
    assert (w.head(1), w.head(2)) == (built[0].sha, built[1].sha)
    assert [e.main for e in recorded] == [built[-1].sha]
    assert [e.entries[0].batch for e in recorded] == ["b1"] and len(recorded[0].entries) == 2


def test_under_merge_the_heads_are_pushed_unchanged(tmp_path: Path) -> None:
    w, built = _two(tmp_path, "merge")
    heads = (w.head(1), w.head(2))
    assert _land(w, built, "merge").outcome == "landed"
    assert w.main() == built[-1].sha and (w.head(1), w.head(2)) == heads
    forge_ = FakeForge(w, tmp_path)
    assert [forge_.pr_view("r", n)["state"] for n in (1, 2)] == ["MERGED", "MERGED"]


@pytest.mark.parametrize("method", ["squash", "merge"])
def test_a_session_push_since_the_build_fails_the_whole_push(tmp_path: Path, method: str) -> None:
    w, built = _two(tmp_path, method)
    main = w.main()
    moved = w.push_to(2, {"c.txt": "charlie, edited\n"})
    result = _land(w, built, method)
    assert result.outcome == "lease"
    assert w.main() == main and w.head(2) == moved and w.head(1) == built[0].entry.head


def test_a_server_without_atomic_push_holds_the_queue(tmp_path: Path) -> None:
    w, built = _two(tmp_path, "squash")
    git(w.origin, "config", "receive.advertiseAtomic", "false")
    main = w.main()
    result = _land(w, built, "squash")
    assert result.outcome == "held" and "--atomic" in result.detail and "R22" in result.detail
    assert w.main() == main


def test_a_push_refused_by_protection_names_both_remedies_and_land_merge(tmp_path: Path) -> None:
    w, built = _two(tmp_path, "squash")
    hook = w.origin / "hooks" / "pre-receive"
    hook.write_text('#!/bin/sh\necho "error: GH013: Repository rule violations found" >&2\n'
                    "exit 1\n")  # fmt: skip
    hook.chmod(0o755)
    result = _land(w, built, "squash")
    assert result.outcome == "held"
    assert "GH013" in result.detail and "queue.land: merge" in result.detail
    assert "bypass" in result.detail and "require a pull request" in result.detail
    assert "never" in result.detail  # the operator's own credential is never a bypass actor


def test_land_merge_merges_each_pr_at_its_pinned_head_in_order(tmp_path: Path) -> None:
    w, built = _two(tmp_path, "squash")
    f = forge(w, tmp_path)
    recorded: list[QueueLandEvent] = []
    result = land_merge(
        f,
        w.checkout,
        "r",
        default="main",
        tip=built[-1].sha,
        landings=landings_of(built),
        method="squash",
        record=recorded.append,
    )
    assert [(n, h) for n, h, _ in f.merges] == [(1, built[0].entry.head), (2, built[1].entry.head)]
    assert result.outcome == "landed" and result.main == w.main()
    assert git(w.origin, "rev-parse", "main^{tree}") == built[-1].tree
    assert [e.main for e in recorded] == [w.main()]


def test_land_merge_stops_on_a_tree_mismatch(tmp_path: Path) -> None:
    w, built = _two(tmp_path, "squash")
    f = forge(w, tmp_path)
    f.main_after_merge = "drift.txt"
    result = land_merge(
        f,
        w.checkout,
        "r",
        default="main",
        tip=built[-1].sha,
        landings=landings_of(built),
        method="squash",
    )
    assert result.outcome == "stopped" and "tree" in result.detail
    assert len(f.merges) == 2  # the merges done are not undone, and none is retried


def test_land_merge_stops_on_a_refusal_and_lands_nothing_after_it(tmp_path: Path) -> None:
    w, built = _two(tmp_path, "squash")
    f = forge(w, tmp_path)
    f.refuse[1] = "Pull request is not up to date with its base"
    result = land_merge(
        f,
        w.checkout,
        "r",
        default="main",
        tip=built[-1].sha,
        landings=landings_of(built),
        method="squash",
    )
    assert result.outcome == "stopped" and "not up to date" in result.detail
    assert f.merges == []


def test_read_back_names_a_landed_pr_the_forge_still_shows_open(tmp_path: Path) -> None:
    w, built = _two(tmp_path, "merge")
    _land(w, built, "merge")
    f = forge(w, tmp_path)
    f.sticky.add(2)
    assert read_back(f, "r", [1, 2]) == (2,)


def test_a_glab_or_tea_client_is_held_naming_the_parity_issue() -> None:
    class Glab(UnsupportedBatchOps):
        backend = "glab"

    reason = forge_refusal(Glab())
    assert reason is not None and "gh#611" in reason and "glab" in reason
    assert forge_refusal(object()) is None


def test_a_tip_not_built_on_the_base_is_held_and_main_never_rewritten(tmp_path: Path) -> None:
    """p3-r7: a leased push moves a ref by any amount; the landing pushes only a tip that
    fast-forwards the queue's base (its chain's bottom built on it, the base its
    ancestor). Built on the old main, after a foreign move it is held, main untouched."""
    w, built = _two(tmp_path, "squash")
    moved = w.move_main({"f.txt": "foreign\n"})
    w.fetch()
    result = land_push(w.checkout, default="main", base=moved, landings=landings_of(built),
                       method="squash")  # fmt: skip
    assert result.outcome == "held" and "fast-forward" in result.detail
    assert w.main() == moved and w.head(1) == built[0].entry.head


def test_a_chain_whose_bottom_was_built_on_another_commit_is_held(tmp_path: Path) -> None:
    from dataclasses import replace

    w, built = _two(tmp_path, "squash")
    main = w.main()
    landings = landings_of(built)
    landings[0] = replace(landings[0], parent="f" * 40)
    result = land_push(w.checkout, default="main", base=main, landings=landings,
                       method="squash")  # fmt: skip
    assert result.outcome == "held" and w.main() == main
