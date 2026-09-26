"""The record template is the interface (spec 2026-09-25-lean-cost-aware-process
§5.C.3, §7 item 12): `fr pickup` and the dispatch brief carry a pre-filled
record, and an in-progress record survives the session that started it."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from fr.record.model import parse_record

from tests.unit.record_support import (
    LAST_BRIEF,
    PLAN_REL,
    RUN,
    commit_all,
    fr,
    implement_record,
    started_run,
    write_record,
)


def _pickup(root: Path, env: dict[str, str] | None = None):
    from fr.cli import app
    from typer.testing import CliRunner

    return CliRunner().invoke(
        app,
        ["pickup", str(root / PLAN_REL), "--phase", "1"],
        env={**os.environ, "VK_REPO_ROOT": str(root), **(env or {})},
    )


def test_the_dispatch_brief_carries_a_prefilled_record(tmp_path: Path) -> None:
    started_run(tmp_path)
    record = LAST_BRIEF["record"]
    assert record["path"].endswith(f"{RUN}.records/implement-phase__phase-1.yaml")
    parsed = parse_record(record["template"])
    assert (parsed.run, parsed.step, parsed.item) == (RUN, "implement-phase", "phase/1")
    text = record["template"]
    keys = {k for k in yaml.safe_load(text)}
    assert {"ticks", "refactor", "journal", "resolves", "evidence"} <= keys
    assert "acceptance" not in keys
    assert "P1.T1.S1, P1.T1.S2, P1.T2.S1" in text
    assert "P1.T1" in text.split("owed by tasks with no refactor step:")[1].splitlines()[0]
    assert record["in_progress"] is None


def test_pickup_carries_the_template_for_the_runs_unit(tmp_path: Path) -> None:
    root = started_run(tmp_path)

    out = _pickup(root)

    assert out.exit_code == 0, out.output
    assert "## Step record" in out.stdout
    assert f"run: {RUN}" in out.stdout and "item: phase/1" in out.stdout
    assert "--record docs/superpowers/runs/r1.records/implement-phase__phase-1.yaml" in out.stdout


_SHIPPED_MANIFEST = (
    Path(__file__).resolve().parents[2] / "plugins" / "super-fr" / "workflows" / "fr-goal.yaml"
)


def _all_manifest_steps():
    from fr.workflow.model import parse_manifest

    manifest = parse_manifest(_SHIPPED_MANIFEST.read_text())
    pairs = []
    for step in manifest.steps:
        pairs.append((step, None))
        for member in step.steps:
            pairs.append((member, step))
    return pairs


def test_a_template_for_every_shipped_step_parses_under_the_live_schema_version() -> None:
    """Spec §3.B, Test Plan item 5: bumping `RECORD_SCHEMA_VERSION` must not
    make a freshly rendered template fail its own parse."""
    from fr.record.model import RECORD_SCHEMA_VERSION, allowed_sections, parse_record
    from fr.record.template import render_template

    for step, group in _all_manifest_steps():
        emits = tuple(step.emits) or (tuple(group.emits) if group is not None else ())
        allowed = allowed_sections(step, group)
        text = render_template(
            run="r1",
            step=step.id,
            item=None,
            allowed=allowed,
            tick_ids=[],
            refactor_tasks=[],
            evidence=list(step.evidence),
            emitted=[n for n in ("spec", "plan", "pr") if n in emits],
            resolve=f"fr run resolve r1 --step {step.id}",
            gated=step.gate == "operator",
        )
        record = parse_record(text)
        assert record.schema_version == RECORD_SCHEMA_VERSION, step.id


def test_a_gated_steps_template_carries_a_commented_questions_hint() -> None:
    """§3.B: `render_template` puts a commented `questions:` hint on any
    gated step's template — `brainstorm` is the one shipped example."""
    from fr.record.model import allowed_sections
    from fr.record.template import render_template

    gated = [step for step, _ in _all_manifest_steps() if step.gate == "operator"]
    assert gated, "no gated step in the shipped manifest — fixture is stale"
    for step in gated:
        text = render_template(
            run="r1",
            step=step.id,
            item=None,
            allowed=allowed_sections(step),
            tick_ids=[],
            refactor_tasks=[],
            evidence=list(step.evidence),
            emitted=[],
            resolve=f"fr run resolve r1 --step {step.id}",
            gated=True,
        )
        assert "questions:" in text
        lines = [line for line in text.splitlines() if "questions:" in line]
        assert any(line.strip().startswith("#") for line in lines)


def test_a_stale_session_resumes_an_in_progress_record(tmp_path: Path) -> None:
    root = started_run(tmp_path)
    # Session A: one tick and one decision, committed with its work, then gone.
    partial = implement_record(
        ticks=["P1.T1.S1"], refactor=None, resolves=None,
        journal=[{"kind": "decision", "id": "d-a", "title": "session A's call"}],
    )  # fmt: skip
    path = write_record(root, partial)
    commit_all(root, "session A: partial work")

    # Session B: a fresh process with another session's identity.
    b = {"CLAUDE_CODE_SESSION_ID": "session-b", "FR_SESSION_ID": "session-b"}
    out = _pickup(root, b)
    assert out.exit_code == 0, out.output
    assert "record in progress: 1 ticks, 1 decisions" in out.stdout
    assert path.relative_to(root).as_posix() in out.stdout

    data = yaml.safe_load(path.read_text())
    data["ticks"] += ["P1.T1.S2", "P1.T2.S1"]
    data["refactor"] = {"P1.T1": "none: one function"}
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    rel = path.relative_to(root).as_posix()
    resolve = ["run", "resolve", RUN, "--step", "implement-phase", "--item", "phase/1"]
    done = fr(root, [*resolve, "--record", str(root / rel)])

    assert done.exit_code == 0, done.output
    assert "3 ticked" in done.stdout and "1 decision" in done.stdout
    assert not path.exists()
