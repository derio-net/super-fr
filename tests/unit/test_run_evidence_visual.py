"""The `visual` derived evidence (spec 2026-09-28-ui-visual-evidence §C, Test
Plan 3–5).

Part 1 drives the pure checks (`fr.run.visual.owed_rows` / `check_visual`,
checks 1–3); part 2 drives the real `fr run resolve --record` path, with a
Claude Code session tree built from captured records (checks 4–5, the witness
transcript per step, unobserved, refusals).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
from pathlib import Path

import pytest
from fr.acceptance.model import Matrix, Row, Visual
from fr.record.model import VisualEvidence, VisualShot
from fr.run.visual import check_visual, owed_rows

OPENED = _dt.datetime(2026, 9, 28, 10, 0, 0, tzinfo=_dt.UTC)


def _row(rid: str = "ui-row", *, post_merge: bool = False, visual: bool = True) -> Row:
    return Row(
        id=rid,
        capability="c",
        acceptance="a",
        origin=("super-fr:docs/superpowers/specs/s.md#R1",),
        status="ci",
        verify="post-merge" if post_merge else None,
        visual=Visual(states=("accepted",), interactions=("20 cap",)) if visual else None,
    )


def _shot(where: Path, name: str, data: bytes = b"\x89PNG bytes", *, age: float = 0) -> Path:
    path = where / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if age:
        stamp = OPENED.timestamp() - age
        os.utime(path, (stamp, stamp))
    else:
        stamp = OPENED.timestamp() + 5
        os.utime(path, (stamp, stamp))
    return path


def _entry(row: str, *shots: tuple[Path | str, tuple[str, ...]], script: str | None = None):
    return VisualEvidence(
        row=row,
        script=script,
        shots=tuple(VisualShot(path=str(p), shows=shows) for p, shows in shots),
    )


def _check(tmp_path: Path, rows, entries, *, fresh: bool = False, ignored: bool = True):
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    return check_visual(
        rows,
        entries,
        opened=OPENED,
        fresh_required=fresh,
        repo_root=repo,
        records_dir=repo / "docs/superpowers/runs/r1.records",
        is_ignored=lambda _p: ignored,
    )


def _outside(tmp_path: Path) -> Path:
    return tmp_path / "scratch"


# --- owed rows ---------------------------------------------------------------


def test_owed_rows_are_the_phase_rows_with_visual_and_no_post_merge() -> None:
    matrix = Matrix(
        rows=(_row("a"), _row("b", post_merge=True), _row("c", visual=False), _row("d"))
    )

    assert [r.id for r in owed_rows(matrix, phase_rows=("a", "b", "c"))] == ["a"]


def test_owed_rows_at_deliver_are_the_rows_citing_the_spec() -> None:
    other = _row("x").model_copy(update={"origin": ("super-fr:docs/other.md",)})
    matrix = Matrix(rows=(_row("a"), other, _row("b", post_merge=True)))

    rows = owed_rows(matrix, spec_ref="super-fr:docs/superpowers/specs/s.md")

    assert [r.id for r in rows] == ["a"]


def test_no_owed_row_is_none(tmp_path: Path) -> None:
    result = _check(tmp_path, [], [])

    assert result.problems == ()
    assert result.witness() == "none"


# --- check 1: an entry per row -------------------------------------------------


def test_a_missing_row_entry_is_refused(tmp_path: Path) -> None:
    result = _check(tmp_path, [_row()], [])

    assert any("ui-row" in p and "no `visual` entry" in p for p in result.problems)


# --- check 2: coverage ---------------------------------------------------------


def test_an_uncovered_name_is_refused(tmp_path: Path) -> None:
    shot = _shot(_outside(tmp_path), "a.png")
    result = _check(tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted",)))])

    assert any("'20 cap'" in p and "no shot shows" in p for p in result.problems)


def test_an_unknown_name_in_shows_is_refused(tmp_path: Path) -> None:
    shot = _shot(_outside(tmp_path), "a.png")
    result = _check(
        tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap", "acceptd")))]
    )

    assert any("'acceptd'" in p and "declares no such" in p for p in result.problems)


# --- check 3: the files --------------------------------------------------------


def test_a_missing_shot_is_refused(tmp_path: Path) -> None:
    missing = _outside(tmp_path) / "gone.png"
    result = _check(tmp_path, [_row()], [_entry("ui-row", (missing, ("accepted", "20 cap")))])

    assert any("missing or empty" in p for p in result.problems)


def test_a_zero_byte_shot_is_refused(tmp_path: Path) -> None:
    empty = _shot(_outside(tmp_path), "e.png", b"")
    result = _check(tmp_path, [_row()], [_entry("ui-row", (empty, ("accepted", "20 cap")))])

    assert any("missing or empty" in p for p in result.problems)


def test_a_shot_in_the_records_dir_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shot = _shot(repo / "docs/superpowers/runs/r1.records", "s.png")
    result = _check(tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap")))])

    assert any("records dir" in p for p in result.problems)


def test_a_repo_shot_that_is_not_ignored_is_refused(tmp_path: Path) -> None:
    shot = _shot(tmp_path / "repo" / "shots", "s.png")
    result = _check(
        tmp_path,
        [_row()],
        [_entry("ui-row", ("shots/s.png", ("accepted", "20 cap")))],
        ignored=False,
    )

    assert shot.exists()
    assert any("git-ignored" in p for p in result.problems)


def test_a_repo_shot_that_is_ignored_passes(tmp_path: Path) -> None:
    _shot(tmp_path / "repo" / "shots", "s.png")
    result = _check(tmp_path, [_row()], [_entry("ui-row", ("shots/s.png", ("accepted", "20 cap")))])

    assert result.problems == ()


def test_a_non_image_suffix_is_refused(tmp_path: Path) -> None:
    shot = _shot(_outside(tmp_path), "s.txt")
    result = _check(tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap")))])

    assert any("image suffix" in p for p in result.problems)


def test_a_stale_shot_is_refused_when_freshness_is_required(tmp_path: Path) -> None:
    shot = _shot(_outside(tmp_path), "s.png", age=60)
    result = _check(
        tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap")))], fresh=True
    )

    assert any("predates this unit" in p for p in result.problems)


def test_a_stale_shot_is_accepted_when_freshness_is_not_required(tmp_path: Path) -> None:
    shot = _shot(_outside(tmp_path), "s.png", age=60)
    result = _check(tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap")))])

    assert result.problems == ()


def test_one_second_of_slack_on_freshness(tmp_path: Path) -> None:
    shot = _shot(_outside(tmp_path), "s.png", age=0.5)
    result = _check(
        tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap")))], fresh=True
    )

    assert result.problems == ()


# --- the witness ---------------------------------------------------------------


def test_the_witness_hashes_the_shot_bytes_in_path_order(tmp_path: Path) -> None:
    b = _shot(_outside(tmp_path), "b.png", b"BBB")
    a = _shot(_outside(tmp_path), "a.png", b"AAA")
    second = _row("ui-2")
    result = _check(
        tmp_path,
        [_row(), second],
        [
            _entry("ui-row", (b, ("20 cap",)), (a, ("accepted",))),
            _entry("ui-2", (a, ("accepted", "20 cap"))),
        ],
    )

    assert result.problems == ()
    digest = hashlib.sha256(b"AAABBB").hexdigest()[:12]
    single = hashlib.sha256(b"AAA").hexdigest()[:12]
    assert result.witness() == f"ui-row:2:{digest},ui-2:1:{single}"
    assert result.witness(unobserved=True) == (
        f"ui-row:2:{digest}:unobserved,ui-2:1:{single}:unobserved"
    )


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".jpeg", ".webp", ".gif", ".PNG"])
def test_every_image_suffix_is_accepted(tmp_path: Path, suffix: str) -> None:
    shot = _shot(_outside(tmp_path), f"s{suffix}")
    result = _check(tmp_path, [_row()], [_entry("ui-row", (shot, ("accepted", "20 cap")))])

    assert result.problems == ()


# =============================================================================
# Part 2 — through `fr run resolve` (checks 4–5, the witness transcript, the
# refusals). Transcripts are COPIES of captured records (transcript_sessions).
# =============================================================================

EXEC_ID = "a0exec0000000001"
REV_ID = "a0rev00000000002"
SPEC_REL = "docs/superpowers/specs/2026-09-28-widget-design.md"

_VISUAL_SHAPE = """
workflow: visual
schema: 1
unit: run
steps:
  - id: plan
    kind: agent
    emits: [plan, spec]
  - id: implement
    kind: agent
    needs: [plan]
    for_each: phase
    emits: [journal:plan]
    steps:
      - id: code
        kind: agent
        agent: super-fr:fr-phase-executor
        needs: [plan]
        emits: [journal:plan]
        evidence: [visual]
      - id: peer-review
        kind: agent
        needs: [journal:plan]
        emits: [journal:plan]
        evidence: [review, reviewer, visual]
  - id: deliver
    kind: agent
    needs: [journal:plan]
    evidence: [visual]
"""


def _visual_row(*, phase_linked: bool = True) -> dict[str, object]:
    from tests.unit.requirements_support import row

    out = row(SPEC_REL, rid="ui-row", status="ci")
    out["visual"] = {"states": ["accepted"], "interactions": ["20 cap"]}
    return out


def _setup(tmp_path: Path, *, link_row: bool = True) -> tuple[Path, Path]:
    """Run `r1` of the `visual` shape: plan (and spec) recorded, `phase/1/code`
    not yet opened. The plan's phase 1 links `ui-row` when `link_row`."""
    import shutil
    import subprocess

    from tests.unit.requirements_support import write_matrix
    from tests.unit.skeleton_override import write_skeleton_override
    from tests.unit.test_run_cli import _FIXTURE_PLAN, _invoke, _repo, _write_shape
    from tests.unit.test_run_evidence import PLAN_SLUG, _journal

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "visual", _VISUAL_SHAPE)
    plan_dir = repo / "docs" / "superpowers" / "plans" / PLAN_SLUG
    shutil.copytree(_FIXTURE_PLAN, plan_dir)
    write_skeleton_override(repo)
    if link_row:
        phase = plan_dir / "01.yaml"
        lines = phase.read_text().split("\n")
        lines.insert(lines.index("  tag: agentic") + 1, "  acceptance:\n    - ui-row")
        phase.write_text("\n".join(lines))
    (repo / SPEC_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / SPEC_REL).write_text("# Widget\n")
    write_matrix(repo, [_visual_row()])
    _journal(repo)
    (repo / ".gitignore").write_text("shots/\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "setup", "--no-verify"],
        check=True,
        capture_output=True,
    )
    out = _invoke(repo, shipped, ["run", "start", "visual", "--branch", "b", "--run-id", "r1"])
    assert out.exit_code == 0, out.output
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    out = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "plan", "--state", "done",
         "--emitted", f"plan=docs/superpowers/plans/{PLAN_SLUG}",
         "--emitted", f"spec={SPEC_REL}"],
    )  # fmt: skip
    assert out.exit_code == 0, out.output
    return repo, shipped


def _run(repo: Path, shipped: Path, argv: list[str], root: Path | None = None):
    from tests.unit.test_run_cli import _invoke, _invoke_measurable

    if root is None:
        return _invoke(repo, shipped, argv)
    return _invoke_measurable(repo, shipped, argv, root, "s-v")


def _advance(repo: Path, shipped: Path, key: str) -> str:
    """Open the next unit; return when it opened (the cursor's `dispatched`)."""
    from fr.run import units
    from fr.run.model import load_run_state

    out = _run(repo, shipped, ["run", "advance", "r1"])
    assert out.exit_code == 0, out.output
    attempt = units.last_attempt(load_run_state(repo, "r1"), key)
    assert attempt is not None
    return attempt.dispatched


def _stamp(at: str, seconds: int = 1) -> str:
    """A transcript stamp `seconds` after (negative: before) a cursor stamp."""
    from fr.run.telemetry import parse_timestamp

    parsed = parse_timestamp(at)
    assert parsed is not None
    moved = parsed + _dt.timedelta(seconds=seconds)
    return moved.strftime("%Y-%m-%dT%H:%M:%S") + ".500Z"


def _read(timestamp: str, path: Path, n: int, *, tool: str = "Read") -> dict[str, object]:
    from tests.unit.transcript_sessions import bash_rows

    call, _ = bash_rows(timestamp, tool_use_id=f"toolu_read{n}")
    block = call["message"]["content"][0]
    block["name"] = tool
    block["input"] = {"file_path": str(path)}
    return call


def _bash(timestamp: str, command: str, n: int) -> dict[str, object]:
    from tests.unit.transcript_sessions import bash_rows

    call, _ = bash_rows(timestamp, tool_use_id=f"toolu_bash{n}")
    call["message"]["content"][0]["input"] = {"command": command}
    return call


def _dispatch(timestamp: str, tool_use_id: str) -> dict[str, object]:
    from tests.unit.transcript_sessions import AGENT_TOOL_USE_LINE, ORCHESTRATOR, copy_of, records

    row = copy_of(records(ORCHESTRATOR)[AGENT_TOOL_USE_LINE])
    row["timestamp"] = timestamp
    row["uuid"] = f"uuid-{tool_use_id}"
    row["message"]["content"][0]["id"] = tool_use_id
    return row


def _session(
    root: Path,
    *,
    orchestrator: list[dict[str, object]] = (),  # type: ignore[assignment]
    agents: dict[str, tuple[str, str, str, list[dict[str, object]]]] | None = None,
) -> None:
    """`s-v`: the captured orchestrator prelude plus `orchestrator` rows, and for
    each `agent_id: (dispatched_at, tool_use_id, agent_type, rows)` its Agent
    tool_use in the orchestrator stream and its own transcript."""
    import json

    from tests.unit.transcript_sessions import (
        ORCHESTRATOR,
        SUBAGENT,
        SUBAGENT_META,
        copy_of,
        records,
        write_agent,
        write_session,
    )

    agents = agents or {}
    rows = [*records(ORCHESTRATOR)]
    rows += [_dispatch(at, tid) for at, tid, _t, _r in agents.values()]
    rows += list(orchestrator)
    session = write_session(root, session_id="s-v", rows=rows)
    for agent_id, (at, tid, agent_type, extra) in agents.items():
        sub = copy_of(records(SUBAGENT))
        for r in sub:
            r["timestamp"] = at
        meta = json.loads(SUBAGENT_META.read_text())
        meta["agentType"] = agent_type
        write_agent(session, agent_id, tool_use_id=tid, rows=[*sub, *extra], meta=meta)


def _record(repo: Path, step: str, item: str | None, **body: object) -> Path:
    import yaml
    from fr.record.model import RECORD_SCHEMA_VERSION, record_path

    path = record_path(repo, "r1", step, item)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "run": "r1",
        "step": step,
        **({"item": item} if item else {}),
        "outcome": "done",
        **body,
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def _resolve(repo: Path, shipped: Path, step: str, item: str | None, record: Path, root=None):
    argv = ["run", "resolve", "r1", "--step", step]
    if item:
        argv += ["--item", item]
    # About the evidence gate alone: the test advances itself (`--record`
    # advances by default, spec 2026-09-29-fr-goal-light-path §B).
    return _run(repo, shipped, [*argv, "--record", str(record), "--no-advance"], root)


def _fresh_shot(tmp_path: Path, name: str = "all.png", data: bytes = b"\x89PNG one") -> Path:
    path = tmp_path / "scratch" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _visual(shot: Path, script: str | None = None) -> list[dict[str, object]]:
    entry: dict[str, object] = {
        "row": "ui-row",
        "shots": [{"path": str(shot), "shows": ["accepted", "20 cap"]}],
    }
    if script is not None:
        entry["script"] = script
    return [entry]


def _unit_evidence(repo: Path, step: str, key: str) -> dict[str, str]:
    from fr.run import units
    from fr.run.model import load_run_state

    return units.evidence_of(load_run_state(repo, "r1").steps[step], key)


def _witness(data: bytes) -> str:
    return f"ui-row:1:{hashlib.sha256(data).hexdigest()[:12]}"


def _squash(text: str) -> str:
    return " ".join(text.split())


# --- no owed row: the path every existing run takes -------------------------------


def test_a_step_declaring_visual_with_no_visual_row_records_none(tmp_path: Path) -> None:
    repo, shipped = _setup(tmp_path, link_row=False)
    _advance(repo, shipped, "phase/1/code")

    out = _run(
        repo, shipped, ["run", "resolve", "r1", "--step", "code", "--item", "phase/1",
                        "--state", "done"],
    )  # fmt: skip

    assert out.exit_code == 0, out.output
    assert _unit_evidence(repo, "implement", "phase/1/code")["visual"] == "none"


# --- implement-phase: the holder's transcript --------------------------------------


def test_dispatched_implement_phase_reads_in_the_holders_transcript_pass(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    _session(
        root,
        agents={
            EXEC_ID: (
                _stamp(opened),
                "toolu_exec",
                "super-fr:fr-phase-executor",
                [_read(_stamp(opened, 2), shot, 1)],
            )
        },
    )
    record = _record(repo, "code", "phase/1", evidence={"agent": EXEC_ID}, visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 0, out.output
    assert _unit_evidence(repo, "implement", "phase/1/code")["visual"] == _witness(
        shot.read_bytes()
    )


def test_dispatched_implement_phase_reads_only_in_the_orchestrator_are_refused(
    tmp_path: Path,
) -> None:
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    _session(
        root,
        orchestrator=[_read(_stamp(opened, 3), shot, 1)],
        agents={EXEC_ID: (_stamp(opened), "toolu_exec", "super-fr:fr-phase-executor", [])},
    )
    record = _record(repo, "code", "phase/1", evidence={"agent": EXEC_ID}, visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    assert "was not opened" in _squash(out.output)
    assert "visual" not in _unit_evidence(repo, "implement", "phase/1/code")


def test_inline_implement_phase_reads_in_the_orchestrator_pass(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    _session(root, orchestrator=[_read(_stamp(opened, 2), shot, 1, tool="read_file")])
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 0, out.output
    assert _unit_evidence(repo, "implement", "phase/1/code")["visual"] == _witness(
        shot.read_bytes()
    )


def test_a_read_before_the_unit_opened_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    _session(root, orchestrator=[_read(_stamp(opened, -30), shot, 1)])
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    assert "was not opened" in _squash(out.output)


def test_a_stale_shot_at_implement_phase_is_accepted(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    os.utime(shot, (0, 0))
    _session(root, orchestrator=[_read(_stamp(opened, 2), shot, 1)])
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 0, out.output


# --- check 5: the capture script ---------------------------------------------------


def test_a_named_script_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    _session(root, orchestrator=[_read(_stamp(opened, 2), shot, 1)])
    record = _record(repo, "code", "phase/1", visual=_visual(shot, script="shots.cjs"))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    assert "does not exist" in _squash(out.output)


def test_a_named_script_no_shell_call_named_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    (repo / "shots.cjs").write_text("// capture\n")
    _session(root, orchestrator=[_read(_stamp(opened, 2), shot, 1)])
    record = _record(repo, "code", "phase/1", visual=_visual(shot, script="shots.cjs"))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    assert "executed the capture script" in _squash(out.output)


def test_a_named_script_that_was_run_passes(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    (repo / "shots.cjs").write_text("// capture\n")
    _session(
        root,
        orchestrator=[
            _bash(_stamp(opened, 1), f"cd {repo} && node shots.cjs", 1),
            _read(_stamp(opened, 2), shot, 1),
        ],
    )
    record = _record(repo, "code", "phase/1", visual=_visual(shot, script="shots.cjs"))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 0, out.output


# --- unobserved ----------------------------------------------------------------------


def test_an_unreadable_transcript_records_unobserved_and_warns(tmp_path: Path) -> None:
    repo, shipped = _setup(tmp_path)
    _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record)

    assert out.exit_code == 0, out.output
    evidence = _unit_evidence(repo, "implement", "phase/1/code")
    assert evidence["visual"] == _witness(shot.read_bytes()) + ":unobserved"
    assert "visual" in evidence["unobserved"]
    assert "could not verify" in _squash(out.stderr)


def test_checks_1_to_3_still_apply_when_unobserved(tmp_path: Path) -> None:
    repo, shipped = _setup(tmp_path)
    _advance(repo, shipped, "phase/1/code")
    record = _record(repo, "code", "phase/1", visual=_visual(tmp_path / "nope.png"))

    out = _resolve(repo, shipped, "code", "phase/1", record)

    assert out.exit_code == 2, out.output
    assert "missing or empty" in _squash(out.output)


# --- refusals of the flag form -------------------------------------------------------


def test_evidence_visual_is_refused_as_derived(tmp_path: Path) -> None:
    repo, shipped = _setup(tmp_path)
    _advance(repo, shipped, "phase/1/code")

    out = _run(
        repo, shipped, ["run", "resolve", "r1", "--step", "code", "--item", "phase/1",
                        "--state", "done", "--evidence", "visual=x"],
    )  # fmt: skip

    assert out.exit_code == 2, out.output
    assert "not yours to pass" in _squash(out.output)


def test_a_flag_form_resolve_owing_visual_rows_points_at_record(tmp_path: Path) -> None:
    repo, shipped = _setup(tmp_path)
    _advance(repo, shipped, "phase/1/code")

    out = _run(
        repo, shipped, ["run", "resolve", "r1", "--step", "code", "--item", "phase/1",
                        "--state", "done"],
    )  # fmt: skip

    assert out.exit_code == 2, out.output
    assert "--record" in _squash(out.output)
    assert "ui-row" in _squash(out.output)


# --- review-phase: the reviewer's own transcript -------------------------------------


def _to_review(tmp_path: Path, root: Path) -> tuple[Path, Path, str, str]:
    """`phase/1/code` done by EXEC_ID (unobserved), `phase/1/peer-review` open.
    Returns (repo, shipped, code opened, review opened)."""
    repo, shipped = _setup(tmp_path)
    code_opened = _advance(repo, shipped, "phase/1/code")
    old = _fresh_shot(tmp_path, "exec.png", b"\x89PNG exec")
    record = _record(repo, "code", "phase/1", evidence={"agent": EXEC_ID}, visual=_visual(old))
    out = _resolve(repo, shipped, "code", "phase/1", record)
    assert out.exit_code == 0, out.output
    review_opened = _advance(repo, shipped, "phase/1/peer-review")
    return repo, shipped, code_opened, review_opened


def _review_record(repo: Path, shot: Path) -> Path:
    return _record(
        repo,
        "peer-review",
        "phase/1",
        evidence={"review": "rev-p1", "reviewer": REV_ID},
        visual=_visual(shot),
    )


def test_review_reads_only_in_the_executors_transcript_are_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, code_opened, opened = _to_review(tmp_path, root)
    shot = _fresh_shot(tmp_path, "rev.png", b"\x89PNG rev")
    _session(
        root,
        agents={
            EXEC_ID: (_stamp(code_opened), "toolu_exec", "super-fr:fr-phase-executor",
                      [_read(_stamp(opened, 2), shot, 1)]),
            REV_ID: (_stamp(opened), "toolu_rev", "general-purpose", []),
        },
    )  # fmt: skip

    out = _resolve(repo, shipped, "peer-review", "phase/1", _review_record(repo, shot), root)

    assert out.exit_code == 2, out.output
    assert "was not opened" in _squash(out.output)


def test_review_reads_in_the_reviewers_transcript_pass(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, code_opened, opened = _to_review(tmp_path, root)
    shot = _fresh_shot(tmp_path, "rev.png", b"\x89PNG rev")
    _session(
        root,
        agents={
            EXEC_ID: (_stamp(code_opened), "toolu_exec", "super-fr:fr-phase-executor", []),
            REV_ID: (_stamp(opened), "toolu_rev", "general-purpose",
                     [_read(_stamp(opened, 2), shot, 1)]),
        },
    )  # fmt: skip

    out = _resolve(repo, shipped, "peer-review", "phase/1", _review_record(repo, shot), root)

    assert out.exit_code == 0, out.output
    evidence = _unit_evidence(repo, "implement", "phase/1/peer-review")
    assert evidence["visual"] == _witness(shot.read_bytes())


def test_a_stale_shot_at_review_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, code_opened, opened = _to_review(tmp_path, root)
    shot = _fresh_shot(tmp_path, "rev.png", b"\x89PNG rev")
    os.utime(shot, (0, 0))
    _session(
        root,
        agents={
            REV_ID: (_stamp(opened), "toolu_rev", "general-purpose",
                     [_read(_stamp(opened, 2), shot, 1)]),
        },
    )  # fmt: skip

    out = _resolve(repo, shipped, "peer-review", "phase/1", _review_record(repo, shot), root)

    assert out.exit_code == 2, out.output
    assert "predates this unit" in _squash(out.output)


# --- deliver: the orchestrator's own stream ------------------------------------------


def _to_deliver(tmp_path: Path) -> tuple[Path, Path, str]:
    repo, shipped = _setup(tmp_path)
    _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path, "exec.png", b"\x89PNG exec")
    out = _resolve(repo, shipped, "code", "phase/1", _record(repo, "code", "phase/1",
                   visual=_visual(shot)))  # fmt: skip
    assert out.exit_code == 0, out.output
    _advance(repo, shipped, "phase/1/peer-review")
    os.utime(shot)  # the review's own capture: fresh however long the steps above took
    out = _resolve(repo, shipped, "peer-review", "phase/1", _review_record(repo, shot))
    assert out.exit_code == 0, out.output
    return repo, shipped, _advance(repo, shipped, "step/deliver")


def test_deliver_orchestrator_reads_of_fresh_shots_pass(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _to_deliver(tmp_path)
    shot = _fresh_shot(tmp_path, "deliver.png", b"\x89PNG deliver")
    _session(root, orchestrator=[_read(_stamp(opened, 2), shot, 1)])

    out = _resolve(repo, shipped, "deliver", None, _record(repo, "deliver", None,
                   visual=_visual(shot)), root)  # fmt: skip

    assert out.exit_code == 0, out.output
    evidence = _unit_evidence(repo, "deliver", "step/deliver")
    assert evidence["visual"] == _witness(shot.read_bytes())


def test_deliver_stale_shots_are_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _to_deliver(tmp_path)
    shot = _fresh_shot(tmp_path, "deliver.png", b"\x89PNG deliver")
    os.utime(shot, (0, 0))
    _session(root, orchestrator=[_read(_stamp(opened, 2), shot, 1)])

    out = _resolve(repo, shipped, "deliver", None, _record(repo, "deliver", None,
                   visual=_visual(shot)), root)  # fmt: skip

    assert out.exit_code == 2, out.output
    assert "predates this unit" in _squash(out.output)


# --- review findings p2-r1 … p2-r9 ---------------------------------------------------


def test_a_record_naming_an_agent_this_session_never_dispatched_is_refused(
    tmp_path: Path,
) -> None:
    """p2-r1: a readable session and a bogus holder id is a refusal — never
    `unobserved`, which would let any made-up id skip checks 4–5."""
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    _session(root, orchestrator=[_read(_stamp(opened, 2), shot, 1)])
    record = _record(repo, "code", "phase/1", evidence={"agent": "bogus-id"}, visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    assert "names no subagent this session dispatched" in _squash(out.output)
    assert "'bogus-id'" in _squash(out.output)
    assert "visual" not in _unit_evidence(repo, "implement", "phase/1/code")


def test_a_read_before_the_shots_last_write_is_refused(tmp_path: Path) -> None:
    """p2-r2: the read at T looked at bytes the write at T+5 replaced."""
    from fr.run.telemetry import parse_timestamp

    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    read_at = _stamp(opened, 2)
    stamp = parse_timestamp(read_at)
    assert stamp is not None
    written = stamp.timestamp() + 5
    os.utime(shot, (written, written))
    _session(root, orchestrator=[_read(read_at, shot, 1)])
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    assert "was not opened" in _squash(out.output)
    assert "last written" in _squash(out.output)


def test_an_ignored_shot_inside_the_repo_passes_through_git(tmp_path: Path) -> None:
    """p2-r3: the real `git check-ignore`, against the fixture's `shots/`."""
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = repo / "shots" / "a.png"
    shot.parent.mkdir()
    shot.write_bytes(b"\x89PNG in repo")
    _session(root, orchestrator=[_read(_stamp(opened, 2), shot, 1)])
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 0, out.output


def test_a_shot_inside_the_repo_that_git_does_not_ignore_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = repo / "other" / "a.png"
    shot.parent.mkdir()
    shot.write_bytes(b"\x89PNG in repo")
    _session(root, orchestrator=[_read(_stamp(opened, 2), shot, 1)])
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    assert "not git-ignored" in _squash(out.output)


def test_git_ignored_does_not_cover_a_tracked_file_in_an_ignored_dir(tmp_path: Path) -> None:
    """p2-r3: `git add -f` tracks a file under an ignored directory — it would be
    committed with the next `git commit -a`, so it is not ignored."""
    import subprocess

    from fr.run.visual import git_ignored

    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-C", str(repo)]
    subprocess.run([*git, "init", "-q"], check=True)
    (repo / ".gitignore").write_text("shots/\n")
    tracked = _shot(repo / "shots", "tracked.png")
    loose = _shot(repo / "shots", "loose.png")
    subprocess.run([*git, "add", "-f", ".gitignore", "shots/tracked.png"], check=True)
    subprocess.run(
        [*git, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "x"],
        check=True,
    )

    ignored = git_ignored(repo)
    assert ignored(loose.resolve()) is True
    assert ignored(tracked.resolve()) is False
    result = check_visual(
        [_row()],
        [_entry("ui-row", (tracked, ("accepted", "20 cap")))],
        opened=OPENED,
        fresh_required=False,
        repo_root=repo,
        records_dir=repo / "docs/superpowers/runs/r1.records",
        is_ignored=ignored,
    )
    assert any("not git-ignored" in p for p in result.problems)


def test_a_dispatched_but_unclaimed_implement_phase_is_refused(tmp_path: Path) -> None:
    """p2-r4: the session shows two executor dispatches, nobody claimed either
    (so no ONE child is the holder, spec 2026-10-02-opencode-observe-2 R5) —
    the orchestrator's own reads must not stand in for the executor's."""
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    _session(
        root,
        orchestrator=[_read(_stamp(opened, 3), shot, 1)],
        agents={
            EXEC_ID: (_stamp(opened), "toolu_exec", "super-fr:fr-phase-executor", []),
            "a0exec0000000009": (
                _stamp(opened, 1),
                "toolu_exec9",
                "super-fr:fr-phase-executor",
                [],
            ),
        },
    )
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    text = _squash(out.output)
    assert "no holder was claimed" in text
    assert "fr run claim r1 --step code --item phase/1 --agent <id>" in text


def test_the_one_observed_executor_is_the_holder_its_reads_are_checked(tmp_path: Path) -> None:
    """R5: one unclaimed executor dispatch becomes the holder, so the witness
    reads ITS session — the orchestrator's read of the shot does not count."""
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    _session(
        root,
        orchestrator=[_read(_stamp(opened, 3), shot, 1)],
        agents={EXEC_ID: (_stamp(opened), "toolu_exec", "super-fr:fr-phase-executor", [])},
    )
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    text = _squash(out.output)
    assert f"holder {EXEC_ID} observed" in text
    assert "no holder was claimed" not in text


def test_an_unclaimed_unit_owing_visual_resolves_through_its_one_child(tmp_path: Path) -> None:
    """R5 runs BEFORE the visual derive: the one executor child read the shot,
    nobody claimed the unit, and the fill names it before the witness's
    "unclaimed" refusal could fire."""
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    _session(
        root,
        agents={
            EXEC_ID: (
                _stamp(opened),
                "toolu_exec",
                "super-fr:fr-phase-executor",
                [_read(_stamp(opened, 2), shot, 1)],
            )
        },
    )
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 0, out.output
    assert _unit_evidence(repo, "implement", "phase/1/code")["visual"] == _witness(
        shot.read_bytes()
    )


def test_an_inline_refusal_names_the_orchestrator(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    _session(root, orchestrator=[])
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    assert "transcript of the orchestrator (the unit ran inline" in _squash(out.output)
    assert opened


def test_a_holder_refusal_names_the_executor(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    _session(
        root,
        orchestrator=[_read(_stamp(opened, 3), shot, 1)],
        agents={EXEC_ID: (_stamp(opened), "toolu_exec", "super-fr:fr-phase-executor", [])},
    )
    record = _record(repo, "code", "phase/1", evidence={"agent": EXEC_ID}, visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    assert f"transcript of the executor {EXEC_ID}" in _squash(out.output)


def test_a_review_refusal_names_the_reviewer(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, code_opened, opened = _to_review(tmp_path, root)
    shot = _fresh_shot(tmp_path, "rev.png", b"\x89PNG rev")
    _session(root, agents={REV_ID: (_stamp(opened), "toolu_rev", "general-purpose", [])})

    out = _resolve(repo, shipped, "peer-review", "phase/1", _review_record(repo, shot), root)

    assert out.exit_code == 2, out.output
    assert f"transcript of the reviewer {REV_ID}" in _squash(out.output)
    assert code_opened


def test_the_unobserved_warning_gives_a_visual_reason(tmp_path: Path) -> None:
    """p2-r5: not the `questions` wording borrowed from the question gate."""
    from tests.unit.test_run_cli import _invoke_as_harness

    repo, shipped = _setup(tmp_path)
    _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _invoke_as_harness(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--record", str(record)],
        {"FR_HARNESS": "hermes"},
    )

    assert out.exit_code == 0, out.output
    text = _squash(out.stderr)
    assert "could not verify that the screenshots were opened" in text
    assert "questions" not in text
    assert "fr cannot yet read file opens from hermes's transcripts" in text


def test_a_sidechain_read_in_the_session_file_does_not_count_inline(tmp_path: Path) -> None:
    """p2-r6: a sidechain record in the orchestrator's file is a subagent's."""
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    read = _read(_stamp(opened, 2), shot, 1)
    read["isSidechain"] = True
    _session(root, orchestrator=[read])
    record = _record(repo, "code", "phase/1", visual=_visual(shot))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    assert "was not opened" in _squash(out.output)


def test_a_command_that_only_names_the_script_is_refused(tmp_path: Path) -> None:
    """p2-r7: `cat shots.cjs` names the script and does not run it."""
    root = tmp_path / "projects"
    repo, shipped = _setup(tmp_path)
    opened = _advance(repo, shipped, "phase/1/code")
    shot = _fresh_shot(tmp_path)
    (repo / "shots.cjs").write_text("// capture\n")
    _session(
        root,
        orchestrator=[
            _bash(_stamp(opened, 1), f"cat {repo}/shots.cjs", 1),
            _read(_stamp(opened, 2), shot, 1),
        ],
    )
    record = _record(repo, "code", "phase/1", visual=_visual(shot, script="shots.cjs"))

    out = _resolve(repo, shipped, "code", "phase/1", record, root)

    assert out.exit_code == 2, out.output
    assert "executed the capture script" in _squash(out.output)


def test_a_row_named_by_two_entries_is_refused(tmp_path: Path) -> None:
    """p2-r9: two entries for one row — which one is the evidence?"""
    shot = _shot(_outside(tmp_path), "a.png")
    result = _check(
        tmp_path,
        [_row()],
        [
            _entry("ui-row", (shot, ("accepted", "20 cap"))),
            _entry("ui-row", (shot, ("accepted",))),
        ],
    )

    assert any("ui-row" in p and "more than one `visual` entry" in p for p in result.problems)


# --- OpenCode: the witness reads OpenCode's own parts (spec 2026-10-02 §G, R12) ---


def _opencode_visual(
    tmp_path: Path, *, role: str, reviewer: str | None = None, holder: str | None = None,
    orchestrator_reads: bool = True, reviewer_reads: bool = True, script_runs: bool = True,
    with_script: bool = True,
):  # fmt: skip
    """`derive_visual` over a copy of the OpenCode run-tree fixture whose read
    and shell parts name THIS test's shot and capture script. Returns what the
    witness derives (or raises `VisualRefusedError`)."""
    import json
    import sqlite3
    from contextlib import closing

    from fr.run.telemetry import parse_timestamp
    from fr.run.visual import derive_visual

    from tests.unit.opencode_fixture import opencode_env, shifted

    shot = tmp_path / "scratch" / "a.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    shot.write_bytes(b"\x89PNG one")
    script = tmp_path / "scratch" / "shots.cjs"
    script.write_text("// capture\n")
    written = _dt.datetime.fromtimestamp(shot.stat().st_mtime, tz=_dt.UTC)
    since = (written - _dt.timedelta(seconds=30)).isoformat()
    opened = parse_timestamp(since)
    assert opened is not None
    db = shifted(tmp_path, opened)
    with closing(sqlite3.connect(db)) as con:
        for part_id, session, raw in con.execute(
            "SELECT id, session_id, data FROM part"
        ).fetchall():
            data = json.loads(raw)
            tool_input = data.get("state", {}).get("input", {})
            if data.get("tool") == "read" and str(tool_input.get("filePath", "")).endswith("a.png"):
                keep = orchestrator_reads if session == "ses_run" else reviewer_reads
                if keep:
                    tool_input["filePath"] = str(shot)
                else:
                    con.execute("DELETE FROM part WHERE id = ?", (part_id,))
                    continue
            elif data.get("tool") == "bash" and session == "ses_run":
                if tool_input.get("command") == "node shots.cjs":
                    if script_runs:
                        tool_input["command"] = f"node {script}"
                    else:
                        con.execute("DELETE FROM part WHERE id = ?", (part_id,))
                        continue
            else:
                continue
            con.execute("UPDATE part SET data = ? WHERE id = ?", (json.dumps(data), part_id))
        con.commit()
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    return derive_visual(
        [_row()],
        [
            _entry(
                "ui-row",
                (shot, ("accepted", "20 cap")),
                script=str(script) if with_script else None,
            )
        ],
        role=role,  # type: ignore[arg-type]
        since=since,
        holder=holder,
        reviewer=reviewer,
        repo_root=repo,
        records_dir=repo / "docs/superpowers/runs/r1.records",
        env={k: v for k, v in opencode_env(db).items() if v is not None},
    )


def test_a_png_read_only_in_the_orchestrators_session_does_not_satisfy_the_reviewer(
    tmp_path: Path,
) -> None:
    from fr.run.visual import VisualRefusedError

    with pytest.raises(VisualRefusedError) as refused:
        _opencode_visual(
            tmp_path, role="reviewer", reviewer="ses_gen1", reviewer_reads=False, with_script=False
        )

    assert "was not opened in the transcript of the reviewer ses_gen1" in " ".join(
        refused.value.lines
    )


def test_the_same_read_in_the_reviewers_child_satisfies_it(tmp_path: Path) -> None:
    derived = _opencode_visual(
        tmp_path, role="reviewer", reviewer="ses_gen1", orchestrator_reads=False, with_script=False
    )  # fmt: skip

    assert derived.unobserved is False


def test_a_capture_script_run_in_the_run_session_satisfies_an_inline_unit(tmp_path: Path) -> None:
    derived = _opencode_visual(tmp_path, role="orchestrator")

    assert derived.unobserved is False


def test_a_capture_script_nobody_ran_is_refused_inline(tmp_path: Path) -> None:
    from fr.run.visual import VisualRefusedError

    with pytest.raises(VisualRefusedError) as refused:
        _opencode_visual(tmp_path, role="orchestrator", script_runs=False)

    assert "executed the capture script" in " ".join(refused.value.lines)


def test_the_unobservable_reason_no_longer_names_opencode() -> None:
    from fr.run.visual import _unobservable

    assert "cannot yet read" not in _unobservable({"FR_HARNESS": "opencode"})
    assert "hermes's transcripts" in _unobservable({"FR_HARNESS": "hermes"})
