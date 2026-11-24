"""The DevOps barrier through `fr triage batch drive` itself (spec
2026-11-19-wave-merge-queue R26, §J).

Over the same real bare origin as `test_queue_drive_cmd.py`. A `gate:devops` PR is no entry
until the DevOps stage's `fr-queue:release` label is settled into a `queue_release` at the
patch-id it has; it then lands as the last entry of its push; the wave does not drain until
the stage's `fr-queue:postmerge-done` label is settled into a `queue_postmerge_done`.
"""

from __future__ import annotations

from pathlib import Path

from fr.triage.model import (
    QueueLandEvent,
    QueuePostmergeDoneEvent,
    QueueReleaseEvent,
    load_judgements,
)

from tests.integration.test_queue_drive_cmd import (  # noqa: F401 - fixtures
    Origin,
    QueueWorld,
    _closed_out_by_hand,
    _drive,
    _passes,
    queue_fixture,
    runner_fixture,
    world_fixture,
)


def _mark(origin: Origin, qw: QueueWorld, number: int, branch: str) -> None:
    """What stage 2 writes: the marker comment naming the head and patch-id it verified."""
    from fr.triage.approval import release_marker
    from fr.triage.gitseam import Checkout

    from tests.integration.test_queue_drive_cmd import _git

    _git(origin.clone, "fetch", "--quiet", "origin")
    head = origin.sha(f"refs/heads/{branch}")
    pid = Checkout(origin.clone).patch_id(head, "origin/main")
    qw.comments[number] = [{"association": "OWNER", "id": 1, "body": release_marker(head, pid)}]


def _events(tmp_path: Path, kind: type) -> list:
    return [e for q in load_judgements(tmp_path / "judgements.yaml").queues
            for e in q.events if isinstance(e, kind)]  # fmt: skip


def _landed(tmp_path: Path) -> list[list[str | None]]:
    return [[e.batch for e in land.entries] for land in _events(tmp_path, QueueLandEvent)]


def test_a_released_devops_pr_lands_last_and_the_wave_drains_after_its_post_merge_ops(
    tmp_path: Path, queue: tuple[Origin, QueueWorld, Path]
) -> None:
    origin, qw, _ = queue
    _closed_out_by_hand(tmp_path)  # R15: nothing else keeps the wave open
    qw.prs[101]["labels"] = ["approved-fr", "gate:devops"]
    _passes(tmp_path, 5)
    # b1 is held by the DevOps gate and no release is settled: only b2 was queued and landed
    assert _landed(tmp_path) == [["b2"]] and _events(tmp_path, QueueReleaseEvent) == []

    qw.prs[101]["labels"] = ["approved-fr", "gate:devops", "fr-queue:release"]
    _passes(tmp_path, 1)
    assert _events(tmp_path, QueueReleaseEvent) == [], "a label with no stage 2 marker is none"
    _mark(origin, qw, 101, "feat/batch-b1")
    _passes(tmp_path, 3)
    (release,) = _events(tmp_path, QueueReleaseEvent)
    assert release.entry.batch == "b1" and release.patch_id and release.head
    assert _landed(tmp_path) == [["b2"], ["b1"]], "the release makes b1 an entry; it lands"
    drained = [e for q in load_judgements(tmp_path / "judgements.yaml").queues
               for e in q.events if e.kind == "queue_drain"]  # fmt: skip
    assert drained == [], "the wave does not drain until the post-merge ops are done"

    qw.prs[101]["labels"] = ["approved-fr", "gate:devops", "fr-queue:release",
                             "fr-queue:postmerge-done"]  # fmt: skip
    _passes(tmp_path, 2)
    assert _events(tmp_path, QueuePostmergeDoneEvent) == [], "the label alone lifts nothing"
    from fr.triage.approval import postmerge_marker

    qw.comments[101] = [*qw.comments[101], {"association": "OWNER", "id": 2,
                                            "body": postmerge_marker("a" * 40)}]  # fmt: skip
    _passes(tmp_path, 3)
    (done,) = _events(tmp_path, QueuePostmergeDoneEvent)
    assert done.entry.batch == "b1"
    drained = [e for q in load_judgements(tmp_path / "judgements.yaml").queues
               for e in q.events if e.kind == "queue_drain"]  # fmt: skip
    assert len(drained) == 1


def test_a_diff_that_changes_after_the_release_voids_it_and_removes_the_label(
    tmp_path: Path, queue: tuple[Origin, QueueWorld, Path]
) -> None:
    origin, qw, _ = queue
    qw.prs[101]["labels"] = ["approved-fr", "gate:devops", "fr-queue:release"]
    # b2 goes first; stop before b1 builds by never letting it be ready: release, then change
    # the diff on its branch before the next pass settles anything further
    _mark(origin, qw, 101, "feat/batch-b1")
    _passes(tmp_path, 1)  # settles the release at the current diff
    (release,) = _events(tmp_path, QueueReleaseEvent)
    origin.branch("feat/batch-b1", {"b1.txt": "changed after the release\n"})
    qw.sync()
    _passes(tmp_path, 1)
    assert "fr-queue:release" not in qw.prs[101]["labels"], "the stale release is removed"
    voids = [e for e in _events(tmp_path, QueueReleaseEvent) if e.voided]
    assert len(voids) == 1 and voids[0].head != release.head
