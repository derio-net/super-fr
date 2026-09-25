"""`fr-run-idle-guard.sh` — the Claude Code `Stop` hook (spec
`2026-09-20-unit-record-unification-design.md` §4.G; gh#518's artifact half).

It blocks ending a turn on a run that is advanceable with nobody working on it,
and hands back the next command. **Everything else in this file is about it NOT
blocking**, because a guard that blocks wrongly leaves an operator unable to end
a turn — the worst outcome of the whole feature:

- silent in all six legitimate stops (the predicate's, `test_run_idle.py`);
- silent when no run is bound to the session;
- FAILS OPEN on every error: `fr` missing, erroring, refusing, hanging, or
  answering with something that is not a clean parsed "idle";
- acts AT MOST ONCE per cursor position, with Claude Code's own
  `stop_hook_active` and `background_tasks` as independent brakes;
- **always exits 0** — exit 2 is a block on Claude Code, so no failure of this
  script may ever surface as one.

Integration, not unit: the blocking and the six stops run the REAL `fr` from
this checkout, as a subprocess, against a real linked worktree — the hook's
whole job is the seam between a harness payload, a binding file and that CLI.
The fail-open cases use stub `fr`s, because a real one cannot be made to hang.

The payloads are the CAPTURED ones (`tests/fixtures/hooks/`, Claude Code
2.1.278), with only the session id swapped per test. Every test declares its
session and runs under a temp `HOME` and `FR_SESSIONS_DIR`; none reads or writes
the operator's real `~/.cache/fr/sessions/`.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.unit.test_run_cli import (
    _CLI_ONLY_SHAPE,
    _FAILING_SHAPE,
    _GATE_SHAPE,
    _GROUPED_SHAPE,
    _invoke,
    _plan_with_tags,
    _repo,
    _started_grouped_with_plan,
    _write_shape,
)

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="hook scripts require jq")

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "fr-run-idle-guard.sh"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "hooks"
REAL_FR = Path(sys.executable).parent / "fr"
SESSION = "sess-idle-guard"
BASH = shutil.which("bash") or "/bin/bash"
"""Absolute: two tests strip PATH down to prove a missing tool is silence."""

CAPTURES = {
    "claude-code-stop.json": "ed8dc5d7472cd63bbf35a49ff82c3b63f04fcb0a51d3ba0eb5d32aa3b2ac17e0",
    "claude-code-stop-after-block.json": (
        "b9fb043de118d2dae6ba775033241c674a52a951ca362710c448d7c0c7026b9b"
    ),
}


# ---------------------------------------------------------------------------
# The captures are captures.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(CAPTURES))
def test_the_captured_hook_inputs_are_byte_for_byte_what_was_captured(name: str) -> None:
    assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == CAPTURES[name]
    assert CAPTURES[name] in (FIXTURES / "NOTE.md").read_text()


def test_the_capture_carries_the_fields_the_guard_keys_on() -> None:
    """The spec asserted `stop_hook_active` from memory. This is the binary's
    own answer — and `background_tasks`, which the spec did not know about."""
    first = json.loads((FIXTURES / "claude-code-stop.json").read_text())
    after = json.loads((FIXTURES / "claude-code-stop-after-block.json").read_text())
    assert first["hook_event_name"] == after["hook_event_name"] == "Stop"
    assert (first["stop_hook_active"], after["stop_hook_active"]) == (False, True)
    assert first["background_tasks"] == [] and first["session_crons"] == []
    assert first["session_id"] == after["session_id"]


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def _payload(**overrides: object) -> dict:
    payload = json.loads((FIXTURES / "claude-code-stop.json").read_text())
    payload["session_id"] = SESSION
    payload.update(overrides)
    return payload


class Guard:
    """One session, one temp HOME, one sessions dir, one `fr` on PATH."""

    def __init__(self, tmp_path: Path, shipped: Path | None = None) -> None:
        self.home = tmp_path / "home"
        self.sessions = tmp_path / "sessions"
        self.bin = tmp_path / "guardbin"
        for d in (self.home, self.sessions, self.bin):
            d.mkdir(parents=True, exist_ok=True)
        self.shipped = shipped
        self.log = tmp_path / "fr.log"

    def real_fr(self) -> Guard:
        (self.bin / "fr").unlink(missing_ok=True)
        (self.bin / "fr").symlink_to(REAL_FR)
        return self

    def stub_fr(self, body: str) -> Guard:
        stub = self.bin / "fr"
        stub.unlink(missing_ok=True)
        stub.write_text(f'#!/bin/bash\nprintf \'%s|%s\\n\' "$PWD" "$*" >> "$FR_STUB_LOG"\n{body}\n')
        stub.chmod(0o755)
        return self

    def bind(self, worktree: Path | str, session: str = SESSION, **extra: object) -> Path:
        index = self.sessions / f"{session}.json"
        # `harness: "claude"` on purpose — what `fr-session-bind.sh` really
        # writes, where `fr.harness` says "claude-code". The guard keys on
        # `worktree` alone and must not care.
        index.write_text(
            json.dumps(
                {"session_id": session, "harness": "claude", "worktree": str(worktree), **extra}
            )
        )
        return index

    def env(self, **extra: str) -> dict[str, str]:
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("CLAUDE", "FR_", "VK_")) and k != "HOME"
        }
        env.update(
            HOME=str(self.home),
            FR_SESSIONS_DIR=str(self.sessions),
            FR_STUB_LOG=str(self.log),
            FR_HARNESS="claude-code",
            PATH=f"{self.bin}:{os.environ.get('PATH', '')}",
        )
        if self.shipped is not None:
            env["FR_SHIPPED_WORKFLOWS_DIR"] = str(self.shipped)
        env.update(extra)
        return env

    def stop(
        self, payload: dict | str | None = None, **env: str
    ) -> subprocess.CompletedProcess[str]:
        body = payload if isinstance(payload, str) else json.dumps(payload or _payload())
        return subprocess.run(
            [BASH, str(HOOK)],
            input=body,
            capture_output=True,
            text=True,
            env=self.env(**env),
            timeout=120,
        )

    def calls(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []


def _assert_silent(result: subprocess.CompletedProcess[str]) -> None:
    """Silence is BOTH halves: nothing on stdout (no decision) and exit 0
    (exit 2 is itself a block on Claude Code)."""
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert result.stdout.strip() == "", result.stdout


def _assert_blocks(result: subprocess.CompletedProcess[str], next_command: str) -> dict:
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block", decision
    assert next_command in decision["reason"], decision
    return decision


def _start(tmp_path: Path, name: str, shape: str) -> tuple[Path, Path]:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, name, shape)
    started = _invoke(repo, shipped, ["run", "start", name, "--branch", "b", "--run-id", "r1"])
    assert started.exit_code == 0, started.output
    return repo, shipped


def _bound(tmp_path: Path, repo: Path, shipped: Path) -> Guard:
    guard = Guard(tmp_path, shipped).real_fr()
    guard.bind(repo)
    return guard


IDLE_JSON = json.dumps(
    {
        "idle": True,
        "reason": "idle",
        "detail": "x",
        "run": "r1",
        "cursor": "implement",
        "position": "0123456789abcdef",
        "next_command": "fr run advance r1",
        "stalled": [],
    }
)


def _idle_stub(guard: Guard, position: str = "0123456789abcdef") -> Guard:
    body = IDLE_JSON.replace("0123456789abcdef", position)
    return guard.stub_fr(f"printf '%s\\n' '{body}'\nexit 3")


# ---------------------------------------------------------------------------
# It blocks an idle stop, and says what to do.
# ---------------------------------------------------------------------------


def test_an_idle_stop_is_blocked_and_the_reason_names_the_next_command(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)
    guard = _bound(tmp_path, repo, shipped)

    decision = _assert_blocks(guard.stop(), "fr run advance r1")

    # the model has to know WHERE, and how to get out if it means to stop
    assert str(repo) in decision["reason"], decision
    assert "stop again" in decision["reason"], decision


def test_the_gh518_stop_is_blocked(tmp_path: Path) -> None:
    """An executor returned, its unit was resolved, the group is still
    `running`, nothing is held — and the turn is ending on a report."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    plan_rel = _plan_with_tags(repo, [(1, "agentic", ()), (2, "agentic", ())])
    _started_grouped_with_plan(repo, shipped, plan_rel)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    unit = ["--step", "code", "--item", "phase/1"]
    assert _invoke(repo, shipped, ["run", "resolve", "r1", *unit, "--state", "done"]).exit_code == 0

    _assert_blocks(_bound(tmp_path, repo, shipped).stop(), "fr run advance r1")


def test_it_runs_the_predicate_in_the_bound_worktree_and_nowhere_else(tmp_path: Path) -> None:
    """The payload's `cwd` is wherever the session happens to be — an
    orchestrator sits in the BASE clone and reaches the worktree through
    `fr isolation exec`. The binding, not `cwd`, says where the run lives."""
    worktree = tmp_path / "bound-worktree"
    worktree.mkdir()
    guard = _idle_stub(Guard(tmp_path))
    guard.bind(worktree)

    _assert_blocks(guard.stop(_payload(cwd=str(tmp_path))), "fr run advance r1")

    assert guard.calls() == [f"{worktree.resolve()}|run check --idle --format json"]


# ---------------------------------------------------------------------------
# The six legitimate stops — silent, against the real `fr`.
# ---------------------------------------------------------------------------


def test_silent_on_a_pending_operator_gate(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "gated", _GATE_SHAPE)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0

    _assert_silent(_bound(tmp_path, repo, shipped).stop())


def test_silent_on_an_outstanding_manual_phase(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    plan_rel = _plan_with_tags(repo, [(1, "manual", ()), (2, "agentic", (1,))])
    _started_grouped_with_plan(repo, shipped, plan_rel)

    _assert_silent(_bound(tmp_path, repo, shipped).stop())


def test_silent_while_a_dispatched_executor_is_still_working(tmp_path: Path) -> None:
    """`run-idle-guard-allows-waiting` — the case most likely to be got wrong.
    On Claude Code the executor runs in the background and its return arrives
    as a notification; ending the turn meanwhile is what a healthy run does."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped, _plan_with_tags(repo, [(1, "agentic", ())]))
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0  # held

    _assert_silent(_bound(tmp_path, repo, shipped).stop())


def test_silent_on_a_failed_step(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "fails", _FAILING_SHAPE)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 1

    _assert_silent(_bound(tmp_path, repo, shipped).stop())


def test_silent_on_a_finished_run(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0

    _assert_silent(_bound(tmp_path, repo, shipped).stop())


def test_silent_when_the_bound_workspace_has_no_run_at_all(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    _assert_silent(_bound(tmp_path, repo, tmp_path / "shipped").stop())


# ---------------------------------------------------------------------------
# No binding — the guard only reaches session-bound runs (spec §4.I).
# ---------------------------------------------------------------------------


def test_silent_when_no_run_is_bound_to_the_session(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)
    guard = Guard(tmp_path, shipped).real_fr()  # an idle run exists; nothing binds it
    guard.bind(repo, session="somebody-else")

    _assert_silent(guard.stop())


def test_it_never_reads_outside_the_declared_sessions_dir(tmp_path: Path) -> None:
    """With `FR_SESSIONS_DIR` unset it falls back to `$HOME/.cache/fr/sessions`
    — the TEMP home here. Proven by putting the only binding there."""
    guard = _idle_stub(Guard(tmp_path))
    default = guard.home / ".cache" / "fr" / "sessions"
    default.mkdir(parents=True)
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (default / f"{SESSION}.json").write_text(json.dumps({"worktree": str(worktree)}))
    env = guard.env()
    del env["FR_SESSIONS_DIR"]

    result = subprocess.run(
        [BASH, str(HOOK)], input=json.dumps(_payload()), capture_output=True, text=True, env=env
    )

    _assert_blocks(result, "fr run advance r1")
    assert (default / f"{SESSION}.idle-guard").is_file()


# ---------------------------------------------------------------------------
# FAIL OPEN. Every one of these must be silence and exit 0.
# ---------------------------------------------------------------------------


def _bound_stub(tmp_path: Path, body: str) -> Guard:
    worktree = tmp_path / "wt"
    worktree.mkdir(exist_ok=True)
    guard = Guard(tmp_path).stub_fr(body)
    guard.bind(worktree)
    return guard


def test_fails_open_when_fr_is_not_installed(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    guard = Guard(tmp_path)
    guard.bind(worktree)
    tools = tmp_path / "tools"
    tools.mkdir()
    for tool in ("jq", "cat", "sleep", "mktemp", "rm", "mkdir", "dirname", "kill"):
        found = shutil.which(tool)
        if found:
            (tools / tool).symlink_to(found)

    _assert_silent(guard.stop(PATH=str(tools)))


def test_fails_open_when_jq_is_not_installed(tmp_path: Path) -> None:
    guard = _idle_stub(_bound_stub(tmp_path, ""))
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "cat").symlink_to(shutil.which("cat") or "/bin/cat")
    (tools / "fr").symlink_to(guard.bin / "fr")

    _assert_silent(guard.stop(PATH=str(tools)))


@pytest.mark.parametrize(
    ("label", "body"),
    [
        ("fr errors", "echo boom >&2\nexit 1"),
        # exit 2 is what the migration gate's refusal looks like — and what a
        # BLOCK looks like to Claude Code if it ever leaked out of the hook.
        ("the migration gate refuses", "echo 'fr: artifacts ... must be migrated' >&2\nexit 2"),
        ("an old fr without --idle", "echo 'No such option: --idle' >&2\nexit 2"),
        ("idle exit code, no output", "exit 3"),
        ("idle exit code, garbage output", "echo 'not json {'\nexit 3"),
        ("idle exit code, JSON that is not an object", "echo '[1, 2]'\nexit 3"),
        ("idle exit code, JSON saying not idle", "echo '{\"idle\": false}'\nexit 3"),
        ("idle JSON without a next command", 'echo \'{"idle": true, "position": "p"}\'\nexit 3'),
        (
            "idle JSON without a position",
            'echo \'{"idle": true, "next_command": "fr run advance r1"}\'\nexit 3',
        ),
        ("idle JSON but exit 0", f"printf '%s\\n' '{IDLE_JSON}'\nexit 0"),
        # everything present and well-formed EXCEPT the verdict itself
        (
            "exit 3 and a complete answer that says NOT idle",
            "printf '%s\\n' '" + IDLE_JSON.replace('"idle": true', '"idle": false') + "'\nexit 3",
        ),
        (
            "exit 3 and an idle that is the STRING true",
            "printf '%s\\n' '" + IDLE_JSON.replace('"idle": true', '"idle": "true"') + "'\nexit 3",
        ),
        ("killed by a signal", "kill -9 $$"),
    ],
)
def test_fails_open_on_anything_but_a_clean_parsed_idle(
    tmp_path: Path, label: str, body: str
) -> None:
    guard = _bound_stub(tmp_path, body)

    _assert_silent(guard.stop())

    assert guard.calls(), f"{label}: the stub was never reached, so this proved nothing"


def test_fails_open_when_fr_hangs_and_does_not_hang_with_it(tmp_path: Path) -> None:
    # `exec`, so the watchdog's kill lands on the sleeper itself and the test
    # leaves no orphan behind. A hung fr that WOULD have said "idle" is the
    # honest worst case: the answer never arrives, so there is no answer.
    guard = _bound_stub(tmp_path, "exec sleep 30")

    began = time.monotonic()
    result = guard.stop(FR_IDLE_GUARD_TIMEOUT="1")
    elapsed = time.monotonic() - began

    _assert_silent(result)
    assert guard.calls(), "the stub was never reached"
    # 25, not 10: ~1s alone, but >10s under `pytest -n auto` load; still well under the 30s sleep.
    assert elapsed < 25, f"the guard waited {elapsed:.1f}s on a hung fr"


@pytest.mark.parametrize(
    "binding",
    [
        "not json {",
        "[]",
        "{}",
        '{"worktree": ""}',
        '{"worktree": 7}',
        '{"worktree": "/nonexistent/fr-idle-guard-test"}',
    ],
)
def test_fails_open_on_a_binding_it_cannot_use(tmp_path: Path, binding: str) -> None:
    guard = _idle_stub(Guard(tmp_path))
    (guard.sessions / f"{SESSION}.json").write_text(binding)

    _assert_silent(guard.stop())

    assert guard.calls() == []


@pytest.mark.parametrize(
    "stdin",
    ["", "not json {", "[]", "{}", '{"session_id": "../../etc/passwd", "stop_hook_active": false}'],
)
def test_fails_open_on_a_payload_it_cannot_use(tmp_path: Path, stdin: str) -> None:
    guard = _idle_stub(_bound_stub(tmp_path, ""))

    _assert_silent(guard.stop(stdin))

    assert guard.calls() == []


def test_fails_open_when_it_cannot_remember_having_acted(tmp_path: Path) -> None:
    """The loop breaker is what makes blocking safe. If the position cannot be
    WRITTEN, the guard cannot promise to act only once — so it does not act."""
    guard = _idle_stub(_bound_stub(tmp_path, ""))
    (guard.sessions / f"{SESSION}.idle-guard").mkdir()  # a directory where the file goes

    _assert_silent(guard.stop())


# ---------------------------------------------------------------------------
# The loop breaker, and the two brakes Claude Code provides.
# ---------------------------------------------------------------------------


def test_it_acts_at_most_once_per_cursor_position(tmp_path: Path) -> None:
    """`run-idle-guard-acts-once-per-position`: `advance` keeps failing, or the
    model keeps stopping — the second stop at the same position goes through."""
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)
    guard = _bound(tmp_path, repo, shipped)

    _assert_blocks(guard.stop(), "fr run advance r1")
    _assert_silent(guard.stop())
    _assert_silent(guard.stop())


def test_it_acts_again_once_the_cursor_has_moved(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)
    guard = _bound(tmp_path, repo, shipped)
    _assert_blocks(guard.stop(), "fr run advance r1")
    _assert_silent(guard.stop())

    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0  # hello done -> bye

    _assert_blocks(guard.stop(), "fr run advance r1")
    _assert_silent(guard.stop())


def test_the_memory_is_where_fr_will_clean_it_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hook spells the path in bash; `fr isolation detach` deletes it from
    Python (`sessions.idle_guard_path`). Pinned to each other here, so the
    memory cannot quietly outlive the binding it is about."""
    from fr.isolation import sessions

    guard = _idle_stub(_bound_stub(tmp_path, ""))
    monkeypatch.setenv("FR_SESSIONS_DIR", str(guard.sessions))

    _assert_blocks(guard.stop(), "fr run advance r1")

    assert sessions.idle_guard_path(SESSION).read_text() == "0123456789abcdef\n"


def test_one_sessions_memory_is_not_anothers(tmp_path: Path) -> None:
    guard = _idle_stub(_bound_stub(tmp_path, ""))
    guard.bind(tmp_path / "wt", session="sess-two")

    _assert_blocks(guard.stop(), "fr run advance r1")
    _assert_blocks(guard.stop(_payload(session_id="sess-two")), "fr run advance r1")
    _assert_silent(guard.stop())
    _assert_silent(guard.stop(_payload(session_id="sess-two")))


def test_stop_hook_active_is_an_independent_brake(tmp_path: Path) -> None:
    """The CAPTURED second payload. Even with no memory at all and a fresh
    position, a stop that a Stop hook itself caused is let through."""
    guard = _idle_stub(_bound_stub(tmp_path, ""))
    payload = json.loads((FIXTURES / "claude-code-stop-after-block.json").read_text())
    payload["session_id"] = SESSION

    _assert_silent(guard.stop(payload))

    assert guard.calls() == []


def test_a_payload_that_does_not_say_stop_hook_active_is_false_is_let_through(
    tmp_path: Path,
) -> None:
    """Defensive: the guard blocks only on a payload it fully recognises. A
    build that drops or renames the field silences the guard — it never turns
    it into one with a brake missing."""
    guard = _idle_stub(_bound_stub(tmp_path, ""))
    payload = _payload()
    del payload["stop_hook_active"]

    _assert_silent(guard.stop(payload))
    _assert_silent(guard.stop(_payload(stop_hook_active="false")))
    _assert_silent(guard.stop(_payload(hook_event_name="SubagentStop")))
    _assert_silent(guard.stop(_payload(agent_id="a1f1")))

    assert guard.calls() == []


@pytest.mark.parametrize("field", ["background_tasks", "session_crons"])
def test_in_flight_background_work_means_the_session_will_be_woken(
    tmp_path: Path, field: str
) -> None:
    """Claude Code's own account of "paused, not done" (read from the 2.1.278
    schema; the populated shape was NOT captured — see NOTE.md). Agrees with
    fr's `held` from the harness's side, and covers work fr cannot see."""
    guard = _idle_stub(_bound_stub(tmp_path, ""))
    task = {"id": "t1", "type": "subagent", "status": "running", "description": "phase 3"}

    _assert_silent(guard.stop(_payload(**{field: [task]})))

    assert guard.calls() == []


# ---------------------------------------------------------------------------
# The invariant the whole file leans on.
# ---------------------------------------------------------------------------


def test_the_script_can_only_ever_exit_zero() -> None:
    """Exit 2 from a Stop hook IS a block. The script traps EXIT and forces 0,
    and never enables `errexit`, so no failing command can leak one out."""
    text = HOOK.read_text()
    assert "trap 'exit 0' EXIT" in text
    code = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    assert not any(ln.startswith("set -") and "e" in ln.split()[1] for ln in code), code


def test_the_adapter_holds_no_opinion_about_cursors() -> None:
    """§4.G: the predicate is fr's. The hook may know a session, a worktree and
    a position token — never a step state or a unit state."""
    code = "\n".join(ln for ln in HOOK.read_text().splitlines() if not ln.lstrip().startswith("#"))
    for word in ("pending", "running", "blocked", "attempts", "units", "cursor", "gate"):
        assert word not in code, f"the hook re-derives fr's predicate: {word!r}"
