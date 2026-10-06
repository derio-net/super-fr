"""`fr triage batch drive` survives a disruption (batch drive-restart-forge).

- gh#883: a restart never starts a second close-out, even when the first one's tab
  has already ended: the close-out is recorded before its tab starts.
- gh#921: a degraded forge or clone skips a pass, never ends the loop: a repo collect
  skipped is left out of the pass, a git fetch, an archive merge or an update push that
  fails is reported once and retried, and a git call that stalls times out.
- gh#998: a `.fr/triage.yaml` key added by one of the driver's own merges is ignored
  with a warning, and a `post_merge` that installs a newer `fr` restarts the driver
  on it.

The world, clone and runner are `test_triage_batch_drive_cmd`'s.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.commands import triage_batch_cmd
from fr.gh import GhError
from fr.triage import gitseam
from fr.triage.collect import read_config, read_config_lenient
from fr.triage.errors import TriageError
from fr.triage.gitseam import GitError
from fr.triage.model import Skipped, TriageConfig, load_judgements

from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 — fixtures
    REPO,
    DriveCheckout,
    World,
    _batch,
    _dispatch_event,
    _drive,
    _drive_named,
    _events,
    _lines,
    _merged,
    _naps_until,
    _pr_open,
    _proposed,
    _sandbox,
    _state,
    _StopError,
    checkout_fixture,
    runner_fixture,
    sleeps_fixture,
    world_fixture,
)

CLOSEOUT_ITEM = f"{REPO}/run/closeout-b1"


# ------------------------------------------------- gh#883: one close-out, ever


class _KilledError(BaseException):
    """The driver process dying: no `except Exception` sees it."""


def test_the_closeout_is_recorded_before_its_tab_starts(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _merged(world, tmp_path)
    checkout.released = True
    seen: list[list[str]] = []
    real = runner.dispatch

    def _dispatch(item: Any) -> str | None:
        seen.append(_events(tmp_path, "b1"))
        return real(item)

    runner.dispatch = _dispatch  # type: ignore[method-assign]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert seen == [["dispatch", "closeout"]]
    assert _events(tmp_path, "b1") == ["dispatch", "closeout"]
    closeout = load_judgements(tmp_path / "judgements.yaml").batches[0].events[-1]
    assert closeout.handle == "w2:p1K"  # type: ignore[union-attr]  # the runner's, once known


def test_a_restart_after_the_closeout_tab_ended_starts_no_second_closeout(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """gh#883: the driver dies right after the tab started; the tab runs and ends
    before the restart, and its archive PR is not visible yet. Liveness cannot see it,
    so only what was written before the tab started stops a second one."""
    _merged(world, tmp_path)
    checkout.released = True
    real = runner.dispatch

    def _dispatch_then_die(item: Any) -> str | None:
        real(item)
        raise _KilledError

    runner.dispatch = _dispatch_then_die  # type: ignore[method-assign]
    with pytest.raises(_KilledError):
        _drive(tmp_path, "--once", "--yes")
    runner.dispatch = real  # type: ignore[method-assign]
    assert runner.live == set()  # the tab has ended

    _drive(tmp_path, "--once", "--yes")

    assert len(runner.dispatched) == 1


def test_a_closeout_the_runner_fails_to_start_is_not_left_recorded(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _merged(world, tmp_path)
    checkout.released = True
    runner.fail = RuntimeError("no such workspace")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 1, out
    assert "no such workspace" in out
    assert _events(tmp_path, "b1") == ["dispatch"]
    runner.fail = None
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert len(runner.dispatched) == 1


# ------------------------------------------ gh#921 (1): a repo collect skipped


def _skipping(world: World, monkeypatch: pytest.MonkeyPatch, reason: str) -> None:
    real = world.facts
    monkeypatch.setattr(
        world,
        "facts",
        lambda: real().model_copy(update={"skipped": [Skipped(repo=REPO, reason=reason)]}),
    )


def test_the_batches_of_a_repo_collect_skipped_are_left_out_of_the_pass(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """Its PRs and config were not read, so its stages are guesses: a proposed batch
    there would be dispatched on default config, a merged one read as dispatched."""
    _proposed(world, tmp_path, 1)
    _skipping(world, monkeypatch, "HTTP 502: bad gateway")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert runner.dispatched == []
    assert code == 3, out  # work remains: it is not done, only unread
    assert "HTTP 502: bad gateway" in out
    assert "left out" in out


def test_a_skipped_repo_is_reported_once_and_driven_again_when_it_is_read(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _proposed(world, tmp_path, 1)
    real = world.facts
    passes: list[int] = []

    def _facts() -> Any:
        passes.append(1)
        if len(passes) <= 2:
            return real().model_copy(update={"skipped": [Skipped(repo=REPO, reason="HTTP 502")]})
        return real()

    monkeypatch.setattr(world, "facts", _facts)
    _naps_until(monkeypatch, 3)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert result.output.count("HTTP 502") == 1
    assert len(runner.dispatched) == 1


# ------------------------------------- gh#921 (2): a git read skips the pass


def test_a_failed_fetch_does_not_end_the_loop(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """`_archived` / `_released` fetch to read origin; a fetch that fails during a
    forge outage skips the pass like a forge read, and the close-out starts later."""
    _merged(world, tmp_path)
    checkout.released = True
    fetches: list[int] = []

    def _fetch() -> None:
        fetches.append(1)
        if len(fetches) == 1:
            raise GitError("`git fetch` failed: Could not resolve host: github.com")

    monkeypatch.setattr(checkout, "fetch", _fetch)
    _naps_until(monkeypatch, 2)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert result.output.count("Could not resolve host") == 1
    assert len(runner.dispatched) == 1


def test_a_failed_fetch_for_a_merge_does_not_end_the_loop(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _pr_open(world, tmp_path)
    fetches: list[int] = []

    def _fetch() -> None:
        fetches.append(1)
        if len(fetches) == 2:  # `_ci_none` reads first and holds on its own; the merge's fails
            raise GitError("`git fetch` failed: Connection reset by peer")

    monkeypatch.setattr(checkout, "fetch", _fetch)
    _naps_until(monkeypatch, 2)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert result.output.count("Connection reset by peer") == 1
    assert world.merged == [(101, "sha-101", "squash")]


def test_once_still_exits_non_zero_on_a_failed_fetch(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _merged(world, tmp_path)
    checkout.released = True

    def _fetch() -> None:
        raise GitError("`git fetch` failed: Could not resolve host: github.com")

    monkeypatch.setattr(checkout, "fetch", _fetch)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code != 0, out
    assert "Could not resolve host" in out
    assert runner.dispatched == []


def test_a_git_call_that_stalls_times_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """gh#921: a stalled fetch blocked the loop the way gh#909's `gh` call did."""
    seen: list[Any] = []

    def _run(argv: list[str], **kw: Any) -> Any:
        seen.append(kw.get("timeout"))
        raise subprocess.TimeoutExpired(argv, kw.get("timeout") or 0)

    monkeypatch.setattr(gitseam.subprocess, "run", _run)
    with pytest.raises(GitError, match="timed out after"):
        gitseam.git(["fetch", "origin"], tmp_path)
    with pytest.raises(GitError, match="timed out after"):
        gitseam.git_ok(["merge-base", "--is-ancestor", "a", "b"], tmp_path)
    assert seen == [gitseam.GIT_TIMEOUT_SECONDS] * 2


def test_post_merge_is_not_bounded_by_the_git_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`post_merge` is the repo's own install, which may take long: never cut short."""
    seen: list[Any] = []

    def _run(argv: list[str], **kw: Any) -> Any:
        seen.append(kw.get("timeout"))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(gitseam.subprocess, "run", _run)
    gitseam.Checkout(tmp_path).run_command(["./scripts/install.sh"])
    assert seen == [None]


# ---------------------------------------- gh#921 (3): a write that fails


def _closing(world: World, tmp_path: Path) -> None:
    closeout = (
        "      - {kind: closeout, at: 2026-10-02T11:59:00Z, runner: fake, handle: h, "
        "run: r1, archive: chore/archive-p1}\n"
    )
    _merged(world, tmp_path, events=closeout)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + closeout))


def test_a_refused_archive_merge_does_not_end_the_loop_and_is_reported_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """As a refused batch-PR merge (rg-4): reported once, merged on a later pass."""
    _closing(world, tmp_path)
    real = world.pr_merge
    tries: list[int] = []

    def _merge(repo: str, number: int, **kw: Any) -> None:
        tries.append(number)
        if len(tries) <= 2:
            raise GhError("HTTP 502: Bad Gateway", returncode=1)
        real(repo, number, **kw)

    monkeypatch.setattr(world, "pr_merge", _merge)
    _naps_until(monkeypatch, 3)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert result.output.count("Bad Gateway") == 1
    assert [m[0] for m in world.merged] == [201]


def test_once_exits_1_on_a_refused_archive_merge(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _closing(world, tmp_path)
    world.refuse_merge = "HTTP 502: Bad Gateway"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 1, out
    assert _lines(out, "archive")[0].startswith("archive b1: stopped:")


def test_a_rejected_update_push_steps_over_the_pr_and_does_not_end_the_loop(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """gh#921 (comment): `! [remote rejected] HEAD -> <branch> (failed)` on a PR's
    update push ended the driver with exit 2; it is a failed write of that PR only."""
    _pr_open(world, tmp_path)
    checkout.behind.add("sha-101")
    from tests.unit.test_triage_batch_drive_cmd import _Worktree

    real = _Worktree.push
    pushes: list[str] = []

    def _push(self: Any, branch: str) -> None:
        pushes.append(branch)
        if len(pushes) == 1:
            raise GitError(f"`git push` failed: ! [remote rejected] HEAD -> {branch} (failed)")
        real(self, branch)

    monkeypatch.setattr(_Worktree, "push", _push)
    _naps_until(monkeypatch, 3)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert result.output.count("remote rejected") == 1
    assert world.merged == [(101, "sha-updated", "squash")]


def test_once_exits_1_on_a_rejected_update_push(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _pr_open(world, tmp_path)
    checkout.behind.add("sha-101")
    from tests.unit.test_triage_batch_drive_cmd import _Worktree

    def _push(self: Any, branch: str) -> None:
        raise GitError("`git push` failed: ! [remote rejected]")

    monkeypatch.setattr(_Worktree, "push", _push)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 1, out
    assert _lines(out, "merge")[0].startswith("merge b1: stopped:")


# -------------------------------------- gh#998: a config key from main


FUTURE = {"post_merge": ["./scripts/install.sh"], "future_block": {"path": "docs/x"}}


def test_a_config_key_this_fr_does_not_know_does_not_stop_a_merge(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """gh#998, as seen live: a merged batch added a key to main's `.fr/triage.yaml`,
    and the older running driver's next merge refused `extra_forbidden` and exited."""
    world.config = {"post_merge": ["./scripts/install.sh"]}  # what this fr collected
    _pr_open(world, tmp_path)
    monkeypatch.setattr(
        checkout, "show",
        lambda ref, file: yaml.safe_dump(FUTURE) if file == ".fr/triage.yaml" else None,
    )  # fmt: skip
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert world.merged == [(101, "sha-101", "squash")]


def test_a_config_key_this_fr_does_not_know_does_not_stop_a_closeout(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    world.config = {"post_merge": ["./scripts/install.sh"]}
    _merged(world, tmp_path)
    checkout.released = True
    monkeypatch.setattr(
        checkout, "show",
        lambda ref, file: yaml.safe_dump(FUTURE) if file == ".fr/triage.yaml" else None,
    )  # fmt: skip
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert len(runner.dispatched) == 1


def test_a_config_key_this_fr_does_not_know_does_not_stop_a_dispatch(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    world.config = {"post_merge": ["./scripts/install.sh"]}
    _proposed(world, tmp_path, 1)
    monkeypatch.setattr(
        checkout, "show",
        lambda ref, file: yaml.safe_dump(FUTURE) if file == ".fr/triage.yaml" else None,
    )  # fmt: skip
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert len(runner.dispatched) == 1


def test_the_drive_collects_its_config_leniently_and_says_what_it_ignored(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    from fr.triage.collect import CollectStats

    _proposed(world, tmp_path, 1)
    seen: list[dict[str, Any]] = []

    def _collect_into(scope: Any, target: Path, **kw: Any) -> Any:
        seen.append(kw)
        import json

        (target / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
        return None, target / "facts.json", CollectStats(ignored={REPO: ("future_block",)})

    monkeypatch.setattr(triage_batch_cmd, "recollect", _REAL_RECOLLECT)
    monkeypatch.setattr(triage_batch_cmd, "collect_into", _collect_into)
    _naps_until(monkeypatch, 3)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert all(kw.get("lenient") is True for kw in seen) and len(seen) == 3
    assert result.output.count("future_block") == 1  # warned once, not every pass


_REAL_RECOLLECT = triage_batch_cmd.recollect


def test_a_config_that_is_invalid_otherwise_skips_the_pass_not_the_loop(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """A broken known key on main is the repo owner's to fix; the driver waits for it."""
    from fr.triage.collect import CollectStats

    _proposed(world, tmp_path, 1)
    calls: list[int] = []

    def _collect_into(scope: Any, target: Path, **kw: Any) -> Any:
        calls.append(1)
        if len(calls) == 1:
            raise TriageError(f"{REPO}: .fr/triage.yaml is not valid triage config: bad")
        import json

        (target / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
        return None, target / "facts.json", CollectStats()

    monkeypatch.setattr(triage_batch_cmd, "recollect", _REAL_RECOLLECT)
    monkeypatch.setattr(triage_batch_cmd, "collect_into", _collect_into)
    _naps_until(monkeypatch, 2)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert len(runner.dispatched) == 1


class _Forge:
    def __init__(self, body: str) -> None:
        self.body = body

    def read_file_at_ref(self, *, repo: str, path: str, ref: str) -> str:
        return self.body


def test_read_config_is_strict_by_default_so_a_typo_run_by_hand_still_fails() -> None:
    forge = _Forge(yaml.safe_dump({"post_merg": ["x"]}))
    with pytest.raises(TriageError, match="extra_forbidden|Extra inputs"):
        read_config(forge, REPO)  # type: ignore[arg-type]


def test_read_config_lenient_drops_unknown_top_level_keys_and_names_them() -> None:
    forge = _Forge(yaml.safe_dump(FUTURE))
    config, ignored = read_config_lenient(forge, REPO)  # type: ignore[arg-type]
    assert config == TriageConfig(post_merge=["./scripts/install.sh"])
    assert ignored == ("future_block",)


def test_read_config_lenient_still_refuses_a_bad_known_key() -> None:
    forge = _Forge(yaml.safe_dump({"stale_dispatch_days": -1}))
    with pytest.raises(TriageError):
        read_config_lenient(forge, REPO)  # type: ignore[arg-type]


# -------------------------------- gh#998: re-exec on the fr post_merge installed


@pytest.fixture
def execs(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    out: list[list[str]] = []

    def _exec(argv: list[str]) -> None:
        out.append(argv)
        raise _StopError

    monkeypatch.setattr(triage_batch_cmd, "_exec", _exec)
    return out


def test_a_post_merge_that_installs_a_newer_fr_restarts_the_driver_on_it(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch, execs: list[list[str]], sleeps: list[float],
) -> None:  # fmt: skip
    world.config = {"post_merge": ["./scripts/install.sh"]}
    _merged(world, tmp_path)
    checkout.released = True
    monkeypatch.setattr(triage_batch_cmd, "_installed_version", lambda: "99.0.0")
    lock = tmp_path / "drive.lock"
    held: list[bool] = []
    real_exec = triage_batch_cmd._exec

    def _exec(argv: list[str]) -> None:
        held.append(lock.exists())
        real_exec(argv)

    monkeypatch.setattr(triage_batch_cmd, "_exec", _exec)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert len(runner.dispatched) == 1  # the pass that ran post_merge finished first
    (argv,) = execs
    assert argv[:3] == [triage_batch_cmd.sys.executable, "-m", "fr"]
    assert argv[3:] == triage_batch_cmd.sys.argv[1:]  # the same command, same arguments
    assert held == [False]  # the lock is released for the new process to take
    assert "99.0.0" in result.output


def test_no_restart_when_post_merge_installed_the_same_fr(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch, execs: list[list[str]],
) -> None:  # fmt: skip
    from fr import __version__

    world.config = {"post_merge": ["./scripts/install.sh"]}
    _merged(world, tmp_path)
    checkout.released = True
    monkeypatch.setattr(triage_batch_cmd, "_installed_version", lambda: __version__)
    _naps_until(monkeypatch, 1)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert execs == []


def test_once_never_restarts(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch, execs: list[list[str]],
) -> None:  # fmt: skip
    world.config = {"post_merge": ["./scripts/install.sh"]}
    _merged(world, tmp_path)
    checkout.released = True
    monkeypatch.setattr(triage_batch_cmd, "_installed_version", lambda: "99.0.0")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert execs == []


def test_a_restart_that_cannot_exec_says_why_and_how_to_resume(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch, sleeps: list[float],
) -> None:  # fmt: skip
    """review: the interpreter can vanish mid-reinstall; a traceback is no answer."""
    world.config = {"post_merge": ["./scripts/install.sh"]}
    _merged(world, tmp_path)
    checkout.released = True
    monkeypatch.setattr(triage_batch_cmd, "_installed_version", lambda: "99.0.0")

    def _execv(path: str, argv: list[str]) -> None:
        raise FileNotFoundError(2, "No such file or directory", path)

    monkeypatch.setattr(triage_batch_cmd.os, "execv", _execv)
    result = _drive_named(tmp_path, "--yes")
    assert result.exit_code == 1, result.output
    assert "could not restart" in result.output
    assert "fr triage batch drive" in result.output
    assert not (tmp_path / "drive.lock").exists()
