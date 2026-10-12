# ruff: noqa: F811 - pytest fixtures imported from the sibling test modules
"""`fr triage batch drive --once --yes` that would dispatch refuses unless `--single-pass`
(gh#1127, spec 2026-10-11-driver-resilience §A, R1-R6).

The world, clone and runner are `test_triage_batch_drive_cmd`'s.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

import fr.cli  # noqa: F401 - the command modules load in the CLI order
from fr.cli import app
from fr.commands.triage_batch_cmd import loop_command, single_pass_notice
from fr.triage.lease import load_lease
from fr.triage.model import Scope
from typer.testing import CliRunner

from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    REPO,
    DriveCheckout,
    World,
    _drive,
    _pr_open,
    _proposed,
    checkout_fixture,
    runner_fixture,
    sleeps_fixture,
    world_fixture,
)
from tests.unit.test_triage_driver_pass import (  # noqa: F401 - fixtures
    Runners,
    _git,
    _ref,
    _workspace,
    _world,
    clock,
    remote,
    runners,
    visibility,
)

REPO_SCOPE = Scope(kind="repo", target=REPO)
GROUP = Scope.group(["org-a/one", "org-a/two"])


def _args(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "batch_ids": [],
        "scope": REPO_SCOPE,
        "scope_args": ["--repo", REPO],
        "max_inflight": 4,
        "interval": 120,
        "workspace_prefix": "drive",
        "keep_sessions": False,
        "checkout": None,
        "toplevel": Path("/abs/clone"),
    }
    return base | kw


# ------------------------------------------------------------- the pure helper


def test_loop_command_defaults_names_the_scope_and_the_clone_and_acts() -> None:
    assert loop_command(**_args()) == [
        "fr", "triage", "batch", "drive",
        "--repo", REPO,
        "--checkout", f"{REPO}=/abs/clone",
        "--yes",
    ]  # fmt: skip


def test_loop_command_carries_ids_non_defaults_and_absolute_checkouts() -> None:
    argv = loop_command(
        **_args(
            batch_ids=["b1", "b2"],
            scope=GROUP,
            scope_args=["--repo", "org-a/one,org-a/two"],
            max_inflight=2,
            interval=30,
            workspace_prefix="bugfix",
            keep_sessions=True,
            checkout=["org-a/one=/abs/one", "org-a/two=rel/two"],
        )
    )
    assert argv[:6] == ["fr", "triage", "batch", "drive", "b1", "b2"]
    for pair in (["--max-inflight", "2"], ["--interval", "30"], ["--workspace-prefix", "bugfix"]):
        assert any(argv[i : i + 2] == pair for i in range(len(argv))), (pair, argv)
    assert "--keep-sessions" in argv and argv[-1] == "--yes"
    assert "--once" not in argv and "--single-pass" not in argv
    checkouts = [argv[i + 1] for i, a in enumerate(argv) if a == "--checkout"]
    assert checkouts[0] == "org-a/one=/abs/one"
    assert (
        checkouts[1].startswith("org-a/two=/") and Path(checkouts[1].split("=", 1)[1]).is_absolute()
    )


def test_the_notice_names_what_a_single_pass_leaves_undone_then_the_command() -> None:
    argv = loop_command(**_args())
    text = single_pass_notice(argv)
    for word in ("merge", "close", "held", "board"):
        assert word in text.lower(), (word, text)
    assert text.rstrip().endswith(shlex.join(argv))


# ------------------------------------------------------- through the command


def test_once_yes_whose_plan_dispatches_refuses_before_acting(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    flat = " ".join(out.split())
    assert code == 2, out
    command = flat.split("fr triage batch drive")[-1]
    assert "--yes" in command and "--once" not in command and "--single-pass" not in command
    assert runner.dispatched == [] and world.merged == []
    assert not (tmp_path / "board.html").exists()


def test_the_refusal_releases_the_lease_the_pass_took_and_writes_no_board(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runners: Runners,
    clock: list[Any],
    remote: Path,
    visibility: Any,
) -> None:
    _, state = _workspace(tmp_path, "a")
    _world(world, state)
    (state / "scope-durable.yaml").write_text(f"state_repo: {REPO}\n")

    result = CliRunner().invoke(
        app, ["triage", "batch", "drive", "--once", "--yes", "--repo", REPO, "--dir", str(state)]
    )

    assert result.exit_code == 2, result.output
    assert "fr triage batch drive" in " ".join(result.output.split())
    assert load_lease(state) is None, "the lease was released before the refusal"
    assert not runners.dispatched_any() and world.merged == []
    assert not (state / "board.html").exists()
    assert "lease.yaml" not in _git(remote, "ls-tree", "--name-only", _ref(remote))


def _warning_after_the_actions(out: str) -> None:
    lines = out.splitlines()
    warn = next(i for i, x in enumerate(lines) if x.startswith("warning:"))
    actions = [i for i, x in enumerate(lines) if x.startswith("dispatch ")]
    assert actions and max(actions) < warn, out
    assert "fr triage batch drive" in lines[warn] or "fr triage batch drive" in " ".join(
        lines[warn:]
    )


def test_once_yes_with_single_pass_acts_then_warns_with_the_command(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out  # pass_exit: it acted
    assert len(runner.dispatched) == 2
    _warning_after_the_actions(out)


def test_a_planned_dispatch_that_fails_still_warns_under_single_pass(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """R4: the condition is the plan holding a dispatch, not the dispatch starting."""
    _proposed(world, tmp_path)

    def boom(item: Any) -> str | None:
        raise RuntimeError("agent_pane_busy")

    runner.dispatch = boom  # type: ignore[method-assign]
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 1, out  # pass_exit: a dispatch failed
    assert runner.dispatched == []
    _warning_after_the_actions(out)


def test_a_planned_dispatch_that_fails_is_still_refused_without_single_pass(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path)
    runner.dispatch = lambda item: (_ for _ in ()).throw(RuntimeError("agent_pane_busy"))  # type: ignore[method-assign]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 2, out
    assert "agent_pane_busy" not in out and runner.dispatched == []


def test_a_preflight_refusal_under_single_pass_keeps_its_exit_and_warns(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path)
    runner.refusal = "not inside a herdr session"
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 2, out
    assert "not inside a herdr session" in out
    assert "warning:" in out and "fr triage batch drive" in " ".join(out.split())


def test_once_without_yes_prints_the_plan_unchanged(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path)
    code, out = _drive(tmp_path, "--once")
    assert code == 0, out
    assert "re-run with --yes" in out and "fr triage batch drive" not in out.split("re-run")[0]
    assert runner.dispatched == []


def test_once_yes_whose_plan_holds_no_dispatch_acts_without_the_notice(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _pr_open(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert world.merged == [(101, "sha-101", "squash")]
    assert "warning:" not in out


def test_single_pass_without_once_is_refused(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path)
    code, out = _drive(tmp_path, "--yes", "--single-pass")
    assert code == 2, out
    assert "--once" in out and world.passes == []  # type: ignore[attr-defined]
