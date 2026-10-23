"""`## Manual operations` in the PR body (spec 2026-10-22-fr-ops R13, §H): rendered by
`deliver` from the plan's ops and the RECORDED evidence, never a live probe, and never a
reason to refuse."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.ops.evidence import record_op
from fr.record.pr_body import REQUIRED_SECTIONS, render_pr_body
from fr.run.model import RunState, StepRecord, load_run_state

from tests.unit.record_support import PLAN_REL, RUN, commit_all
from tests.unit.test_deliver_pr_body import _at_deliver, _body, _deliver

OPS = """schema_version: 1
ops:
  - id: create-key
    summary: create the deploy key
    phase: pre-merge
    check: 'true'
    apply: 'true'
  - id: click-ui
    summary: enable the toggle
    phase: post-merge
  - id: signed
    summary: a signed proof
    phase: post-merge
    check: proof
"""


@pytest.fixture(autouse=True)
def _no_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: object, **k: object) -> object:
        raise AssertionError("the PR body ran a probe")

    for target in ("run_probe", "run_probe_full", "run_interactive"):
        monkeypatch.setattr(f"fr.ops.probe.{target}", boom)
    monkeypatch.setattr("fr.ops.engine.run_probe", boom)


def _state(plan: str = "docs/superpowers/plans/p") -> RunState:
    return RunState(
        run="run-1",
        workflow="fr-goal@1",
        branch="feat/x",
        started="2026-10-22T00:00:00+00:00",
        cursor="deliver",
        steps={"plan": StepRecord(state="done", emitted={"plan": plan})},
    )


def _section(body: str) -> str:
    return body.split("## Manual operations\n\n")[1].split("\n\n## ")[0]


def test_the_section_sits_right_after_post_merge_owed() -> None:
    i = REQUIRED_SECTIONS.index("## Post-merge verification owed")
    assert REQUIRED_SECTIONS[i + 1] == "## Manual operations"


def test_a_plan_without_ops_renders_none(tmp_path: Path) -> None:
    (tmp_path / "docs/superpowers/plans/p").mkdir(parents=True)
    body = render_pr_body(tmp_path, _state())
    assert _section(body) == "None."
    assert body.index("## Post-merge verification owed") < body.index("## Manual operations")
    assert body.index("## Manual operations") < body.index("## Proportionality")


def test_a_run_with_no_plan_renders_none(tmp_path: Path) -> None:
    state = _state()
    state = state.model_copy(update={"steps": {}})
    assert _section(render_pr_body(tmp_path, state)) == "None."


def test_each_op_shows_its_phase_last_recorded_state_and_command(tmp_path: Path) -> None:
    plan = tmp_path / "docs/superpowers/plans/p"
    plan.mkdir(parents=True)
    (plan / "ops.yaml").write_text(OPS)
    record_op(tmp_path, "p", op="create-key", result="done", phase="pre-merge")
    record_op(
        tmp_path, "p", op="click-ui", result="open", phase="post-merge",
        reason="applied; no check — attest it",
    )  # fmt: skip
    section = _section(render_pr_body(tmp_path, _state()))
    lines = section.splitlines()
    key = next(ln for ln in lines if "create-key" in ln)
    assert "pre-merge" in key and "DONE (checked)" in key and "fr ops apply create-key" in key
    ui = next(ln for ln in lines if "click-ui" in ln)
    assert "post-merge" in ui and "applied; no check" in ui and "fr ops attest click-ui" in ui
    assert "DONE" not in ui
    signed = next(ln for ln in lines if "`signed`" in ln)
    assert "never checked" in signed
    assert "DevOps stage" in section and "fr ops gate --run run-1" in section


def test_an_unreadable_ops_yaml_says_so_and_does_not_crash(tmp_path: Path) -> None:
    plan = tmp_path / "docs/superpowers/plans/p"
    plan.mkdir(parents=True)
    (plan / "ops.yaml").write_text("schema_version: 1\nops: [ {id: \n")
    assert _section(render_pr_body(tmp_path, _state())).startswith("Not available:")


def test_deliver_never_refuses_on_open_ops(tmp_path: Path, monkeypatch) -> None:
    import fr.gh

    root = _at_deliver(tmp_path)
    (root / PLAN_REL / "ops.yaml").write_text(OPS)
    record_op(root, Path(PLAN_REL).name, op="create-key", result="open", phase="pre-merge")
    commit_all(root, "ops, one open")
    served: dict[str, str] = {"body": "none yet"}
    monkeypatch.setattr(fr.gh, "view_pr_body", lambda ref, *, cwd=None: served["body"])
    _deliver(root)  # renders the body; refused only because the live body lacks it
    rendered = _body(root).read_text()
    assert "create-key" in _section(rendered) and "open" in _section(rendered)
    served["body"] = rendered
    rec, out = _deliver(root)
    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"


def test_p3_r5_an_unreadable_ops_yaml_names_a_repo_relative_path(tmp_path: Path) -> None:
    plan = tmp_path / "docs/superpowers/plans/p"
    plan.mkdir(parents=True)
    (plan / "ops.yaml").write_text("schema_version: 1\nops: [ {id: \n")
    section = _section(render_pr_body(tmp_path, _state()))
    assert "docs/superpowers/plans/p/ops.yaml" in section
    assert str(tmp_path) not in section
    for prefix in ("/Users/", "/home/", "/var/folders/", "/private/", "/tmp/"):
        assert prefix not in section, section
