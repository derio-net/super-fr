"""The queue's git failures, told apart (lens fix round, l-errors-*): a remote's refusal, a
failed connection and a push that landed before its connection died are three things, over
a real bare remote."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.triage import gitseam
from fr.triage.gitseam import GitError, PushRefusedError, TransientPushError
from fr.triage.queue_exec import build, land_push, landings_of

from tests.integration.queue_git import SCOPE, World, git, world


def _two(tmp_path: Path) -> tuple[World, list]:  # type: ignore[type-arg]
    w = world(tmp_path)
    w.pr(1, {"b.txt": "bravo\n"}, title="Add bravo")
    w.fetch()
    built = build(w.checkout, w.main(), [w.entry(1)], "squash", None,  # type: ignore[arg-type]
                  scope=SCOPE, slots=(1,), scratch=w.scratch)  # fmt: skip
    return w, built


def _drop_the_connection(monkeypatch: pytest.MonkeyPatch, *, after_landing: bool) -> None:
    real = gitseam.git

    def flaky(args: list[str], cwd: Path) -> str:
        if args[:1] == ["push"]:
            if after_landing:
                real(args, cwd)
            raise GitError("fatal: the remote end hung up unexpectedly")
        return real(args, cwd)

    monkeypatch.setattr(gitseam, "git", flaky)


def test_a_push_the_remote_rejected_is_a_refusal_and_holds(tmp_path: Path) -> None:
    w, built = _two(tmp_path)
    hook = w.origin / "hooks" / "pre-receive"
    hook.write_text('#!/bin/sh\necho "denied by policy" >&2\nexit 1\n')
    hook.chmod(0o755)
    with pytest.raises(PushRefusedError):
        w.checkout.push_leased([(built[0].sha, "refs/heads/main")],
                               {"refs/heads/main": built[0].base}, atomic=True)  # fmt: skip
    result = land_push(w.checkout, default="main", base=built[0].base,
                       landings=landings_of(built), method="squash")  # fmt: skip
    assert result.outcome == "held"


def test_a_push_that_landed_before_the_connection_died_is_a_landing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w, built = _two(tmp_path)
    _drop_the_connection(monkeypatch, after_landing=True)
    recorded: list = []  # type: ignore[type-arg]
    result = land_push(w.checkout, default="main", base=built[0].base,
                       landings=landings_of(built), method="squash",
                       record=recorded.append)  # fmt: skip
    assert result.outcome == "landed" and w.main() == built[0].sha and len(recorded) == 1


def test_a_failed_connection_that_landed_nothing_is_transient_not_a_halt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w, built = _two(tmp_path)
    main = w.main()
    _drop_the_connection(monkeypatch, after_landing=False)
    with pytest.raises(TransientPushError):
        w.checkout.push_leased([(built[0].sha, "refs/heads/main")],
                               {"refs/heads/main": built[0].base}, atomic=True)  # fmt: skip
    result = land_push(w.checkout, default="main", base=built[0].base,
                       landings=landings_of(built), method="squash")  # fmt: skip
    assert result.outcome == "transient" and "hung up" in result.detail and w.main() == main


# ------------------------------------------------------------------ the lease on main (l-tests-r2)


def test_main_moving_after_the_base_was_read_fails_the_lease_and_the_next_pass_rebuilds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A release commit lands on `main` between the pass reading its base and the landing
    push: the push fails with `lease`, nothing lands, and the next pass rebuilds on the new
    `main` and lands."""
    from fr.triage.model import QueueHaltEvent, QueueLandEvent

    from tests.integration.test_queue_resume import _driver

    d = _driver(tmp_path)
    d.one_pass()  # open
    d.one_pass()  # build both
    real = gitseam.Checkout.push_leased
    moved: list[str] = []

    def push(self: gitseam.Checkout, refspecs, leases, *, atomic: bool):  # type: ignore[no-untyped-def]
        if atomic and not moved:  # the landing push: a release commit gets there first
            moved.append(d.w.move_main({"release.txt": "release: v1.0.1\n"}))
        return real(self, refspecs, leases, atomic=atomic)

    monkeypatch.setattr(gitseam.Checkout, "push_leased", push)
    lines = d.one_pass()
    assert any("a lease failed" in line for line in lines)
    assert d.events(QueueLandEvent) == [] and d.w.main() == moved[0]
    assert not d.events(QueueHaltEvent)
    for _ in range(5):
        d.one_pass()
    lands = d.events(QueueLandEvent)
    assert len(lands) == 1 and [e.batch for e in lands[0].entries] == ["b1", "b2"]
    parent = d.w.remote("refs/heads/main")
    assert moved[0] in git(d.w.origin, "rev-list", parent).split()


# ------------------------------------------------------------------ the hold (l-errors-r2)


def test_a_hold_write_that_fails_in_transport_is_a_warning_not_a_halt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage.model import QueueHaltEvent

    from tests.integration.test_queue_resume import _driver

    d = _driver(tmp_path)
    real = gitseam.git

    def flaky(args: list[str], cwd: Path) -> str:
        if args[:1] == ["push"] and any("fr-hold" in a for a in args):
            raise GitError("fatal: unable to access: Could not resolve host")
        return real(args, cwd)

    monkeypatch.setattr(gitseam, "git", flaky)
    lines = d.one_pass()
    assert any("warning: the hold was not written" in line for line in lines)
    assert d.events(QueueHaltEvent) == []


def test_a_hold_write_the_remote_rejects_is_still_a_halt(tmp_path: Path) -> None:
    from fr.triage.model import QueueHaltEvent

    from tests.integration.test_queue_resume import _driver

    d = _driver(tmp_path)
    hook = d.w.origin / "hooks" / "pre-receive"
    hook.write_text('#!/bin/sh\nwhile read old new ref; do case "$ref" in *fr-hold*) exit 1;; '
                    "esac; done\n")  # fmt: skip
    hook.chmod(0o755)
    d.one_pass()
    assert [e.state for e in d.events(QueueHaltEvent)] == ["held"]
