"""In-place fresh replacement. Pending checkpoints never authorize prompt replay.

The caller owns the scope before entering ownership(); this pane lock remains held
through the caller's batch commit and activation. No tab/branch/transcript deletion.
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from typing import Any

from fr_dispatch.launch import validate_model
from fr_dispatch.protocols import ReplacementInspection, ReplacementRequest, ReplacementResult

from fr_herdr import managed, opencode, restart
from fr_herdr._herdr import HerdrError, _run_herdr, start_agent
from fr_herdr.runner import agent_name, stable_checkout


def observe(d: managed.Descriptor, safe: bool = True, source: bool = False) -> dict[str, Any]:
    """One named foreground session, never stale registration or ambiguous roster."""
    agents = _run_herdr(["agent", "list"]).get("result", {}).get("agents", [])
    found = [a for a in agents if a.get("pane_id") == d.pane or a.get("name") == d.name]
    if len(found) != 1:
        raise managed.ManagedError("missing or ambiguous named agent")
    agent: dict[str, Any] = found[0]
    if (
        agent.get("pane_id") != d.pane
        or agent.get("name") != d.name
        or agent.get("agent") != d.harness
        or (safe and agent.get("agent_status") not in {"idle", "done"})
        or agent.get("agent_status") not in {"idle", "done", "working", "blocked"}
        or (safe and agent.get("interactive_ready") is not True)
    ):
        raise managed.ManagedError("live identity/status/readiness mismatch")
    info = _run_herdr(["pane", "process-info", "--pane", d.pane])
    procs = info.get("result", {}).get("process_info", {}).get("foreground_processes", [])
    if len(procs) != 1:
        raise managed.ManagedError("ambiguous foreground process")
    proc = procs[0]
    argv = proc.get("argv", [])
    cwd_matches = proc.get("cwd") == d.checkout
    if source and not cwd_matches and proc.get("cwd"):
        try:
            cwd_matches = stable_checkout(str(proc["cwd"])) == d.checkout
        except HerdrError:
            pass
    from pathlib import Path

    if (
        not argv
        or Path(str(argv[0])).name != d.harness
        or not proc.get("pid")
        or not cwd_matches
        or argv[1:] != ["--model", d.model]
    ):
        # Claude may have approved launch flags; no positional/resume input is accepted.
        kept = restart.kept_args(argv) if argv and d.harness == "claude" else None
        if (
            not isinstance(kept, list)
            or not proc.get("pid")
            or not cwd_matches
            or Path(str(argv[0])).name != "claude"
            or "--model" not in kept
            or kept[kept.index("--model") + 1 :] != [d.model]
            or any(x in argv for x in ("--resume", "-r", "--continue", "-c", "--session-id"))
        ):
            raise managed.ManagedError("foreground process/model/cwd is unknown or changed")
    if safe:
        screen = str(
            _run_herdr(["pane", "read", d.pane, "--source", "visible", "--ansi"]).get("raw", "")
        )
        if d.harness == "opencode":
            reason = opencode.input_reason(screen)
        else:
            reason = (
                "no-prompt"
                if not restart.has_prompt(screen)
                else "draft"
                if restart.has_draft(screen)
                else "background-work"
                if restart.has_background_work(screen)
                else None
            )
        if reason:
            raise managed.ManagedError(reason)
    return {**agent, "process": proc}


def source_eligible(d: managed.Descriptor) -> dict[str, Any]:
    if d.pane == os.environ.get("HERDR_PANE_ID"):
        raise managed.ManagedError("caller-self session")
    return observe(d, source=True)


def exit_to_shell(d: managed.Descriptor) -> None:
    _run_herdr(["pane", "send-text", d.pane, "exit" if d.harness == "opencode" else "/exit"])
    _run_herdr(["pane", "send-keys", d.pane, "enter"])

    def exited() -> str | None:
        info = _run_herdr(["pane", "process-info", "--pane", d.pane])
        cwd = opencode.shell_cwd(info)
        if cwd:
            return cwd
        screen = str(
            _run_herdr(["pane", "read", d.pane, "--source", "visible", "--ansi"]).get("raw", "")
        )
        if (
            restart._EXIT_DIALOG.search(screen)
            or opencode.input_reason(screen) == "dialog-or-unfocused"
        ):
            raise HerdrError("exit dialog left untouched")
        return None

    cwd = opencode._poll(exited)
    if not cwd:
        raise HerdrError("exit-timeout; interactive shell not confirmed")
    if cwd != d.checkout:
        _run_herdr(["pane", "send-text", d.pane, f"cd {shlex.quote(d.checkout)}"])
        _run_herdr(["pane", "send-keys", d.pane, "enter"])
    if not opencode._poll(
        lambda: (
            True
            if opencode.shell_cwd(_run_herdr(["pane", "process-info", "--pane", d.pane]))
            == d.checkout
            else None
        )
    ):
        raise HerdrError("shell-cwd-timeout")


def launch_target(d: managed.Descriptor) -> None:
    start_agent(
        ["agent", "start", d.name, "--kind", d.harness, "--pane", d.pane, "--", "--model", d.model],
        run=_run_herdr,
        sleep=opencode._sleep,
    )
    observe(d)


def submit(d: managed.Descriptor, brief: str) -> None:
    # NO Enter retry for either harness: stalled submission is uncertain, not permission
    # to answer a dialog or duplicate the reconstruction brief.
    _run_herdr(
        [
            "agent",
            "prompt",
            d.name,
            brief,
            "--wait",
            "--until",
            "working",
            "--until",
            "blocked",
            "--timeout",
            "30000",
        ]
    )


class Operation:
    def __init__(self, request: ReplacementRequest):
        try:
            validate_model(request.harness, request.model)
        except ValueError as exc:
            raise managed.ManagedError(str(exc)) from exc
        if os.environ.get("HERDR_ENV") != "1" or not os.environ.get("HERDR_PANE_ID"):
            raise managed.ManagedError("replacement requires a known caller pane inside herdr")
        if not request.name:
            request = replace(request, name=agent_name(request.item))
        self.request = request
        self.owned = False
        if request.old_harness not in {"claude", "opencode"} or request.harness not in {
            "claude",
            "opencode",
        }:
            raise managed.ManagedError("unsupported replacement harness")
        self.target = managed.Descriptor.model_validate(
            {
                "server": managed.server_identity(),
                "pane": request.pane,
                "name": request.name,
                "item": request.item,
                "role": "batch",
                "branch": request.branch,
                "checkout": stable_checkout(request.checkout),
                "model": request.model,
                "harness": request.harness,
                "attempt": request.attempt,
                "old_harness": request.old_harness,
                "old_model": request.old_model,
                "checkpoint": "prepared",
            }
        )
        self.source = self.target.model_copy(
            update={
                "harness": request.old_harness,
                "model": request.old_model,
                "checkpoint": "active",
            }
        )
        self.before: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return self.target.name

    @contextmanager
    def ownership(self) -> Iterator[None]:
        with managed.pane_lock(self.target.pane):
            self.owned = True
            try:
                yield
            finally:
                self.owned = False

    def _owner(self) -> None:
        if not self.owned:
            raise managed.ManagedError("replacement requires pane owner")

    def inspect(self) -> ReplacementInspection:
        d = managed.load(self.target.pane)
        if d and (d.checkpoint not in {"active", "aborted"}):
            raise managed.ManagedError(f"pending checkpoint {d.checkpoint}; repair owed")
        if d and (d.item, d.name, d.branch, d.checkout) != (
            self.source.item,
            self.source.name,
            self.source.branch,
            self.source.checkout,
        ):
            raise managed.ManagedError("managed source identity mismatch")
        if (
            d
            and d.checkpoint == "active"
            and (d.harness, d.model) != (self.source.harness, self.source.model)
        ):
            raise managed.ManagedError("managed source launch mismatch")
        self.before = source_eligible(self.source)
        return ReplacementInspection(
            self.source.pane,
            self.source.name,
            self.source.harness,
            self.source.model,
            str(self.before["agent_status"]),
        )

    def prepare(self) -> None:
        self._owner()
        if self.before is None:
            self.inspect()
        if source_eligible(self.source) != self.before:
            raise managed.ManagedError("source changed before preparation")
        previous = managed.load(self.target.pane)
        if previous:
            self.target = self.target.model_copy(
                update={
                    "conflict_head": previous.conflict_head,
                    "conflict_brief": previous.conflict_brief,
                }
            )
        self.brief = managed.reconstruct(self.target)
        managed.save(self.target)

    def _checkpoint(self, checkpoint: str) -> None:
        self.target = self.target.model_copy(update={"checkpoint": checkpoint})
        managed.save(self.target)

    def execute(self) -> ReplacementResult:
        self._owner()
        d = self._pending()
        if d.checkpoint != "prepared":
            raise managed.ManagedError("operation already started; repair, never replay")
        try:
            if source_eligible(self.source) != self.before:
                raise managed.ManagedError("source changed immediately before exit")
            exit_to_shell(self.source)
            self._checkpoint("source-exited")
            launch_target(self.target)
            self._checkpoint("target-ready")
            self._checkpoint("submission-started")
            try:
                submit(self.target, self.brief)
            except Exception:
                self._checkpoint("submission-uncertain")
                raise
            self._checkpoint("uptake-confirmed")
            return ReplacementResult(True, "uptake-confirmed", "target")
        except Exception as exc:  # noqa: BLE001 - preserve checkpoint and never restore source
            survivor = "unknown"
            try:
                observe(self.target, safe=False)
                survivor = "target"
            except Exception:  # noqa: BLE001 - diagnostics never authorize another input
                try:
                    observe(self.source, safe=False, source=True)
                    survivor = "source"
                except Exception:  # noqa: BLE001
                    try:
                        if opencode.shell_cwd(
                            _run_herdr(["pane", "process-info", "--pane", d.pane])
                        ):
                            survivor = "shell"
                    except Exception:  # noqa: BLE001
                        pass
            return ReplacementResult(
                False,
                self.target.checkpoint,
                survivor,
                f"{exc}; inspect pane {d.pane}; repair owed; never blindly resubmit",
            )

    def _pending(self) -> managed.Descriptor:
        d = managed.load(self.target.pane)
        if not d or any(
            getattr(d, field) != getattr(self.target, field)
            for field in (
                "attempt",
                "item",
                "name",
                "branch",
                "checkout",
                "harness",
                "model",
                "old_harness",
                "old_model",
            )
        ):
            raise managed.ManagedError("pending descriptor identity mismatch; inspect both stores")
        self.target = d
        return d

    def _restored_source(self) -> managed.Descriptor | None:
        """A completed failure restoration is distinct from a pending target descriptor."""
        d = managed.load(self.source.pane)
        if (
            d
            and d.checkpoint == "active"
            and d.attempt is None
            and all(
                getattr(d, field) == getattr(self.source, field)
                for field in ("item", "name", "branch", "checkout", "harness", "model")
            )
            and d.old_harness is None
            and d.old_model is None
        ):
            return d
        return None

    def reconcile(self) -> ReplacementResult:
        restored = self._restored_source()
        if restored:
            source_eligible(restored)
            return ReplacementResult(False, "active", "source", "original source already restored")
        d = self._pending()
        if d.pane == os.environ.get("HERDR_PANE_ID"):
            raise managed.ManagedError("caller-self session")
        try:
            observe(d)
        except managed.ManagedError:
            try:
                source_eligible(self.source)
                return ReplacementResult(
                    False, d.checkpoint, "source", "original source remains; aborted"
                )
            except managed.ManagedError:
                if opencode.shell_cwd(_run_herdr(["pane", "process-info", "--pane", d.pane])):
                    return ReplacementResult(
                        False, d.checkpoint, "shell", "confirmed shell; aborted"
                    )
                raise managed.ManagedError(
                    "unknown/working/blocked observation; repair refused"
                ) from None
        if d.checkpoint not in {"uptake-confirmed", "batch-committed", "active"}:
            raise managed.ManagedError(
                "no persisted uptake confirmation; inspect/recover target, NEVER replay brief"
            )
        return ReplacementResult(True, d.checkpoint, "target")

    def activate(self, *, success: bool) -> None:
        self._owner()
        if success:
            self._pending()
            if self.target.checkpoint not in {"uptake-confirmed", "batch-committed", "active"}:
                raise managed.ManagedError("activation requires persisted uptake")
            observe(self.target, safe=False)
            self._checkpoint("batch-committed")
            self._checkpoint("active")
        else:
            result = self.reconcile()
            if result.ok:
                raise managed.ManagedError("live reconciliation disagrees with batch failure")
            if self._restored_source() is not None:
                return  # both stores may already be finalized; still rechecked live above
            self._pending()
            if result.survivor == "source":
                restored = self.target.model_copy(
                    update={
                        "harness": self.source.harness,
                        "model": self.source.model,
                        "checkpoint": "active",
                        "attempt": None,
                        "old_harness": None,
                        "old_model": None,
                    }
                )
                managed.save(restored)
            elif self.target.checkpoint != "aborted":
                self._checkpoint("aborted")
