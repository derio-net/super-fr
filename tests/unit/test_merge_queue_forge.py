"""`GhClient.pr_enqueue` and `pr_queue_state` (spec 2026-10-11-merge-train-safety §D, R13):
`gh pr merge --auto` on RealGhClient, GraphQL for the queue state; REST cannot enqueue and
reads only `auto_merge`; a forge without the concepts raises / reads (None, False).
The GraphQL answer is the documented `pullRequest` shape, built inline (no live capture:
the repo has no merge queue)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fr import gh as _gh
from fr.ghclient import GhClient, QueueState, UnsupportedBatchOps, UnsupportedForgeOperation
from fr.real_ghclient import RealGhClient
from fr.real_ghrestclient import RealGhRestClient

REPO = "example-org/example-repo"
SHA = "a" * 40


def test_enqueue_argv_is_auto_merge_pinned_to_the_head(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(_gh, "_run_gh", lambda args: seen.append(args) or "")
    RealGhClient().pr_enqueue(REPO, 12, head_sha=SHA, method="squash")
    assert seen == [
        ["pr", "merge", "12", "--repo", REPO, "--auto", "--match-head-commit", SHA, "--squash"]
    ]


def test_enqueue_refuses_an_unknown_method() -> None:
    with pytest.raises(ValueError, match="merge method"):
        RealGhClient().pr_enqueue(REPO, 12, head_sha=SHA, method="fast")


def test_rest_cannot_enqueue() -> None:
    with pytest.raises(UnsupportedForgeOperation, match="pr_enqueue"):
        RealGhRestClient().pr_enqueue(REPO, 12, head_sha=SHA, method="squash")


def test_an_unsupported_forge_cannot_enqueue_and_reads_no_queue() -> None:
    ops = UnsupportedBatchOps()
    with pytest.raises(UnsupportedForgeOperation, match="pr_enqueue"):
        ops.pr_enqueue(REPO, 12, head_sha=SHA, method="squash")
    assert ops.pr_queue_state(REPO, 12) == QueueState(None, False)


def _graphql(in_queue: bool, auto: bool, state: str = "OPEN", merged: bool = False) -> str:
    pr = {"state": state, "merged": merged, "isInMergeQueue": in_queue,
          "autoMergeRequest": {"enabledAt": "t"} if auto else None}  # fmt: skip
    return json.dumps({"data": {"repository": {"pullRequest": pr}}})


@pytest.mark.parametrize(("in_queue", "auto"), [(True, True), (False, True), (False, False)])
def test_queue_state_reads_graphql(
    monkeypatch: pytest.MonkeyPatch, in_queue: bool, auto: bool
) -> None:
    seen: list[list[str]] = []

    def run(args: list[str]) -> str:
        seen.append(args)
        return _graphql(in_queue, auto)

    monkeypatch.setattr(_gh, "_run_gh", run)
    assert RealGhClient().pr_queue_state(REPO, 12) == QueueState(in_queue, auto)
    assert seen[0][:2] == ["api", "graphql"]
    assert "isInMergeQueue" in " ".join(seen[0]) and "autoMergeRequest" in " ".join(seen[0])


class _Rest:
    def __init__(self, auto_merge: Any) -> None:
        self.auto_merge, self.routes = auto_merge, []

    def __call__(self, args: list[str]) -> str:
        self.routes.append(args[-1])
        return json.dumps({"number": 12, "auto_merge": self.auto_merge})


def test_rest_queue_state_is_auto_merge_with_unknown_queue_membership() -> None:
    fake = _Rest({"enabled_by": {}})
    assert RealGhRestClient(run=fake).pr_queue_state(REPO, 12) == QueueState(None, True)
    assert fake.routes == [f"repos/{REPO}/pulls/12"]
    assert RealGhRestClient(run=_Rest(None)).pr_queue_state(REPO, 12) == QueueState(None, False)


def test_the_verbs_are_on_the_protocol() -> None:
    assert "pr_enqueue" in GhClient.__dict__ and "pr_queue_state" in GhClient.__dict__


def test_a_merged_or_closed_pr_reads_as_not_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """p3-r6: the query asks for state and merged, so a PR merged after the view is never
    read as ejected."""
    seen: list[list[str]] = []
    answers = iter([_graphql(False, False, "MERGED", True), _graphql(False, False, "CLOSED")])

    def run(args: list[str]) -> str:
        seen.append(args)
        return next(answers)

    monkeypatch.setattr(_gh, "_run_gh", run)
    assert RealGhClient().pr_queue_state(REPO, 12) == QueueState(False, False, open=False)
    assert RealGhClient().pr_queue_state(REPO, 12).open is False
    assert "state merged" in " ".join(seen[0])


def test_rest_queue_state_reads_merged_and_closed() -> None:
    class Pull:
        def __init__(self, **pull: Any) -> None:
            self.pull = pull

        def __call__(self, args: list[str]) -> str:
            return json.dumps(self.pull)

    assert RealGhRestClient(run=Pull(state="open", merged=False)).pr_queue_state(REPO, 1).open
    assert not RealGhRestClient(run=Pull(state="closed", merged=True)).pr_queue_state(REPO, 1).open


def test_dequeue_argv_and_unsupported_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(_gh, "_run_gh", lambda args: seen.append(args) or "")
    RealGhClient().pr_dequeue(REPO, 12)
    assert seen == [["pr", "merge", "12", "--repo", REPO, "--disable-auto"]]
    with pytest.raises(UnsupportedForgeOperation, match="pr_dequeue"):
        RealGhRestClient().pr_dequeue(REPO, 12)
    with pytest.raises(UnsupportedForgeOperation, match="pr_dequeue"):
        UnsupportedBatchOps().pr_dequeue(REPO, 12)
    assert "pr_dequeue" in GhClient.__dict__
