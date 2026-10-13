# ruff: noqa: F811 - pytest fixtures imported from the sibling test modules
"""An unreadable state-repo visibility skips a looping drive's pass (gh#1134, spec
2026-10-11-driver-resilience §B, R8-R11).

The world, clone, runner, clock and bare remote are `test_triage_driver_pass`'s. The
visibility client answers from a script, so a read can fail on exactly the push the case
names; every other mode keeps refusing (R9) and a leak still ends the driver (R10).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fr.cli  # noqa: F401 - the command modules load in the CLI's order
import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd, triage_cmd
from fr.gh import GhError
from fr.triage.lease import load_lease
from typer.testing import CliRunner

from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    REPO,
    DriveCheckout,
    World,
    checkout_fixture,
    world_fixture,
)
from tests.unit.test_triage_driver_pass import (  # noqa: F401 - fixtures
    Runners,
    _git,
    _pass,
    _ref,
    _workspace,
    _world,
    clock,
    remote,
    runners,
)

REFS = "example-org/refs"


class Scripted:
    """`repo_visibility`: *script* answers the first calls ("fail" raises), then *default*."""

    def __init__(self, script: list[str], default: str = "private") -> None:
        self.script, self.default = list(script), default
        self.asked: list[str] = []

    def repo_visibility(self, repo: str) -> str:
        self.asked.append(repo)
        answer = self.script.pop(0) if self.script else self.default
        if answer == "fail":
            raise GhError("HTTP 403: API rate limit exceeded")
        return answer


def _use(monkeypatch: pytest.MonkeyPatch, client: Any) -> None:
    monkeypatch.setattr(triage_cmd, "make_visibility_client", lambda: client)


def _leased_state(tmp_path: Path, world: World) -> Path:
    _, state = _workspace(tmp_path, "a")
    _world(world, state)
    (state / "scope-durable.yaml").write_text(f"state_repo: {REPO}\n")
    return state


def _drive_args(state: Path, *args: str) -> list[str]:
    return ["triage", "batch", "drive", *args, "--repo", REPO, "--dir", str(state)]


def _tip_has_b1_dispatch(remote: Path) -> bool:
    ref = _ref(remote)
    return (
        bool(ref)
        and "feat/batch-b1"
        in _git(remote, "show", f"{ref}:judgements.yaml").replace(
            "kind: 'dispatch'", "kind: dispatch"
        )
        and "b1" in _git(remote, "show", f"{ref}:judgements.yaml")
    )


def _loop_two_passes(
    state: Path, monkeypatch: pytest.MonkeyPatch, seen: list[dict[str, Any]], observe: Any
) -> Any:
    """Loop mode; observe() after each pass's nap, Ctrl-C at the second nap."""

    def nap(seconds: float) -> None:
        seen.append(observe())
        if len(seen) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(triage_batch_cmd, "_sleep", nap)
    return CliRunner().invoke(app, _drive_args(state, "--yes"))


def test_a_loop_skips_a_pass_whose_lease_push_cannot_read_the_visibility(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use(monkeypatch, Scripted(["fail"]))
    state = _leased_state(tmp_path, world)
    seen: list[dict[str, Any]] = []

    result = _loop_two_passes(
        state,
        monkeypatch,
        seen,
        lambda: {"merged": list(world.merged), "ref": _ref(remote), "passes": len(world.passes)},  # type: ignore[attr-defined]
    )

    flat = " ".join(result.output.split())
    assert flat.count("pass skipped, retrying every") == 1, result.output
    assert "cannot read the visibility" in flat
    assert seen[0] == {"merged": [], "ref": "", "passes": 0}, "nothing acted, nothing pushed"
    assert seen[1]["merged"] and seen[1]["ref"], "the second pass ran and pushed"


def test_a_loop_pushes_next_pass_the_state_a_skipped_save_left(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # pass 1: only its save_pass cannot read the visibility; pass 2 reads.
    client = Scripted([])
    _use(monkeypatch, client)
    real_save = triage_batch_cmd._Driver.save_pass
    saves: list[int] = []

    def save_pass(self: Any) -> None:
        saves.append(1)
        client.default = "fail" if len(saves) == 1 else "private"
        try:
            real_save(self)
        finally:
            client.default = "private"

    monkeypatch.setattr(triage_batch_cmd._Driver, "save_pass", save_pass)
    state = _leased_state(tmp_path, world)
    seen: list[dict[str, Any]] = []

    result = _loop_two_passes(
        state,
        monkeypatch,
        seen,
        lambda: {"dispatched": runners.dispatched_any(), "tip": _tip_has_b1_dispatch(remote)},
    )

    flat = " ".join(result.output.split())
    assert flat.count("pass skipped, retrying every") == 1, result.output
    assert seen[0] == {"dispatched": True, "tip": False}, "pass 1 acted; its state was not pushed"
    assert seen[1]["tip"] is True, "pass 2 pushed what pass 1 left"


def test_once_yes_with_an_unreadable_visibility_exits_2(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use(monkeypatch, Scripted([], default="fail"))
    state = _leased_state(tmp_path, world)

    result = CliRunner().invoke(app, _drive_args(state, "--once", "--yes"))

    assert result.exit_code == 2, result.output
    assert "cannot read the visibility" in " ".join(result.output.split())
    assert world.passes == [] and not runners.dispatched_any()  # type: ignore[attr-defined]


def test_the_cloud_pass_with_an_unreadable_visibility_exits_2(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use(monkeypatch, Scripted([], default="fail"))
    state = _leased_state(tmp_path, world)

    result = _pass(state, tmp_path / "outbox.json")

    assert result.exit_code == 2, result.output
    assert "cannot read the visibility" in " ".join(result.output.split())
    assert load_lease(state) is None or not runners.dispatched_any()


def test_a_skipped_save_that_installed_a_newer_fr_restarts_instead_of_sleeping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Stub:
        yes = True
        restart_to = "9.9.9"
        read_failures: set[str] = set()

    def one_pass(driver: Any) -> Any:
        raise triage_batch_cmd.ForgeReadError("cannot read the visibility", code=2)

    def sleep(seconds: float) -> None:
        raise AssertionError("slept instead of restarting")

    monkeypatch.setattr(triage_batch_cmd, "one_pass", one_pass)
    monkeypatch.setattr(triage_batch_cmd, "_sleep", sleep)

    assert triage_batch_cmd._host_loop(Stub(), once=False, interval=5) == "9.9.9"  # type: ignore[arg-type]


def test_a_leak_still_ends_a_looping_driver(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Leaky:
        def repo_visibility(self, repo: str) -> str:
            return "public" if repo == REFS else "private"

    _use(monkeypatch, Leaky())
    _, state = _workspace(tmp_path, "a")
    _world(world, state)
    (state / "scope-durable.yaml").write_text(f"state_repo: {REFS}\n")
    (state / "judgements.yaml").write_text(
        (state / "judgements.yaml").read_text(), encoding="utf-8"
    )
    monkeypatch.setattr(
        triage_batch_cmd, "_sleep", lambda s: pytest.fail("a leak must not be retried")
    )

    result = CliRunner().invoke(app, _drive_args(state, "--yes"))

    assert result.exit_code == 2, result.output
    assert "state repo" in " ".join(result.output.split())
    assert "retrying" not in result.output


class MemberFlaky:
    """A public state repo; the member repo's visibility read fails on its first *fails*
    reads (a rate limit), then answers public."""

    def __init__(self, fails: int = 1) -> None:
        self.fails = fails
        self.asked: list[str] = []

    def repo_visibility(self, repo: str) -> str:
        self.asked.append(repo)
        if repo == REFS:
            return "public"
        if self.fails:
            self.fails -= 1
            raise GhError("HTTP 403: API rate limit exceeded")
        return "public"


def test_a_loop_skips_a_pass_whose_member_repo_visibility_cannot_be_read(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """gh#1144: with a public state repo, a failed read of a member repo's visibility is
    unreadable, not a leak: the pass is skipped and the next one reads again."""
    client = MemberFlaky()
    _use(monkeypatch, client)
    _, state = _workspace(tmp_path, "a")
    _world(world, state)
    (state / "scope-durable.yaml").write_text(f"state_repo: {REFS}\n")
    seen: list[dict[str, Any]] = []

    result = _loop_two_passes(
        state,
        monkeypatch,
        seen,
        lambda: {"merged": list(world.merged), "passes": len(world.passes)},  # type: ignore[attr-defined]
    )

    flat = " ".join(result.output.split())
    assert REPO in client.asked, "the member repo was read live"
    assert "which is not public" not in flat, result.output
    assert flat.count("pass skipped, retrying every") == 1, result.output
    assert seen[0] == {"merged": [], "passes": 0}, "nothing acted"
    assert seen[1]["merged"], "the second pass ran"


def test_a_loop_skips_a_pass_whose_judgements_write_cannot_read_the_visibility(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """gh#1145: a VisibilityUnreadable from guard_write mid-pass (the dispatch's write
    check) skips the pass like the lease's and the save's do, rather than ending the
    loop. Today's driver writes add no key, so the guard is forced to answer unreadable."""
    from fr.triage.privacy import VisibilityUnreadable

    _use(monkeypatch, Scripted([]))
    real = triage_batch_cmd.guard_write
    calls: list[int] = []

    def guard_write(*args: Any, **kwargs: Any) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise VisibilityUnreadable("cannot read the visibility of example-org/x")
        real(*args, **kwargs)

    monkeypatch.setattr(triage_batch_cmd, "guard_write", guard_write)
    state = _leased_state(tmp_path, world)
    seen: list[dict[str, Any]] = []

    result = _loop_two_passes(
        state, monkeypatch, seen, lambda: {"dispatched": runners.dispatched_any()}
    )

    flat = " ".join(result.output.split())
    assert calls, "the dispatch's write check ran"
    assert flat.count("pass skipped, retrying every") == 1, result.output
    assert seen[0] == {"dispatched": False}, "nothing launched on the skipped pass"
    assert seen[1] == {"dispatched": True}, "the next pass dispatched"
