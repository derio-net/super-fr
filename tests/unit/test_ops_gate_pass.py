"""`fr gate pass --gate devops --run` (spec 2026-10-22-fr-ops R14): it folds only the
recorded evidence in the checkout, never probing live, and refuses while a plan op is
not DONE/N/A by that evidence or a step whose effective gate is devops has no outcome.
The forge is faked; every probe entry point is booby-trapped."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import gate_cmd
from fr.journal.model import JournalEntry, append_journal_entry, journal_path
from fr.ops.evidence import record_op
from fr.run.model import RunState, StepRecord, save_run_state
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.requirements_support import row, write_matrix

REPO = "derio-net/super-fr"
SPEC = "docs/superpowers/specs/2026-10-22-s-design.md"
PLAN = "docs/superpowers/plans/p"
OPS = """schema_version: 1
ops:
  - id: checked
    summary: has a check
    phase: pre-merge
    check: 'true'
  - id: by-hand
    summary: no check
    phase: post-merge
"""


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "r"
    (root / "docs/superpowers/specs").mkdir(parents=True)
    (root / SPEC).write_text(
        "# S\n\n## Verification\n\nstrategy: none\ngate: developer\n\n## Test Plan\n\n"
        "- [devops] walk the stage\n- [tester] click the page\n"
    )
    write_matrix(root, [row(SPEC, rid="r1")])
    (root / PLAN).mkdir(parents=True)
    (root / PLAN / "ops.yaml").write_text(OPS)
    save_run_state(
        root,
        RunState(
            run="run-1",
            workflow="fr-goal@1",
            branch="feat/x",
            started="2026-10-22T00:00:00+00:00",
            cursor="deliver",
            steps={
                "brainstorm": StepRecord(state="done", emitted={"spec": SPEC}),
                "plan": StepRecord(state="done", emitted={"plan": PLAN}),
            },
        ),
    )
    _git(root, "init", "-q", "-b", "chore/ops-p")
    monkeypatch.chdir(root)
    for target in ("run_probe", "run_probe_full", "run_interactive"):
        monkeypatch.setattr(f"fr.ops.probe.{target}", _no_probe)
    monkeypatch.setattr("fr.ops.engine.run_probe", _no_probe)
    monkeypatch.setattr("fr.ops.engine.ShellRunner.__call__", _no_probe)
    return root


def _no_probe(*a: object, **k: object) -> Any:
    raise AssertionError("fr gate pass ran a probe")


@pytest.fixture
def forge(monkeypatch: pytest.MonkeyPatch) -> Any:
    def install(labels: list[str], head_ref: str = "feat/x") -> FakeGhClient:
        fake = FakeGhClient()
        fake.prs[(REPO, 5)] = {
            "state": "MERGED", "draft": False, "head_ref": head_ref, "base_ref": "main",
            "mergeable": "UNKNOWN", "title": "t", "body": "b", "labels": list(labels),
        }  # fmt: skip
        monkeypatch.setattr(gate_cmd, "client_for_url", lambda url: fake)
        monkeypatch.setattr("fr._hosts.origin_slug", lambda root: None)
        return fake

    return install


def _pass(*args: str) -> Any:
    return CliRunner().invoke(
        app, ["gate", "pass", "--repo", REPO, "--pr", "5", "--notes", "ops done", *args]
    )


def _outcome(root: Path, n: int) -> None:
    slug = "2026-10-22-s"
    entry = JournalEntry(
        kind="discovery",
        scope="spec",
        id=f"test-plan-step-{n}",
        created="2026-10-22T10:00:00+00:00",
        title=f"step {n} ran",
        body="ran it",
    )
    append_journal_entry(journal_path(root, "spec", slug), slug, entry)


def _all_recorded(root: Path) -> None:
    record_op(root, "p", op="checked", result="done", phase="pre-merge")
    record_op(
        root, "p", op="by-hand", result="attested", phase="post-merge", attested_by="operator"
    )
    _outcome(root, 1)


def test_it_refuses_listing_every_open_op_and_unrecorded_devops_step(
    repo: Path, forge: Any
) -> None:
    forge(["gate:devops"])
    res = _pass("--gate", "devops", "--run", "run-1")
    assert res.exit_code == 2, res.output
    assert "checked" in res.output and "by-hand" in res.output
    assert "never checked" in res.output
    assert "step 1" in res.output and "walk the stage" in res.output
    assert "step 2" not in res.output  # a [tester] step is the tester gate's


def test_recorded_open_and_apply_only_evidence_do_not_close_an_op(repo: Path, forge: Any) -> None:
    _all_recorded(repo)
    record_op(repo, "p", op="checked", result="open", phase="pre-merge", reason="key missing")
    record_op(
        repo, "p", op="by-hand", result="open", phase="post-merge",
        reason="applied; no check — attest it",
    )  # fmt: skip
    forge(["gate:devops"])
    res = _pass("--gate", "devops", "--run", "run-1")
    assert res.exit_code == 2 and "key missing" in res.output and "by-hand" in res.output


def test_it_passes_once_everything_is_recorded(repo: Path, forge: Any) -> None:
    _all_recorded(repo)
    fake = forge(["gate:devops"])
    res = _pass("--gate", "devops", "--run", "run-1", "--yes")
    assert res.exit_code == 0, res.output
    assert any(c[0] == "edit_pr_labels" for c in fake.calls)


def test_without_run_it_matches_the_pr_head_ref_to_a_run_branch(repo: Path, forge: Any) -> None:
    forge(["gate:devops"])
    res = _pass("--gate", "devops")
    assert res.exit_code == 2 and "run-1" in res.output


def test_without_run_and_no_matching_branch_it_behaves_as_today(repo: Path, forge: Any) -> None:
    forge(["gate:devops"], head_ref="feat/elsewhere")
    res = _pass("--gate", "devops")
    assert res.exit_code == 0, res.output
    assert "no run" in res.output


def test_an_unknown_run_is_refused(repo: Path, forge: Any) -> None:
    forge(["gate:devops"])
    res = _pass("--gate", "devops", "--run", "nope")
    assert res.exit_code == 2 and "nope" in res.output


def test_the_tester_gate_behaves_as_today(repo: Path, forge: Any) -> None:
    forge(["gate:tester"])
    res = _pass("--gate", "tester", "--run", "run-1")
    assert res.exit_code == 0, res.output


def test_a_legacy_done_op_is_closed_by_its_status(repo: Path, forge: Any) -> None:
    (repo / PLAN / "ops.yaml").unlink()
    (repo / PLAN / "01.yaml").write_text(
        "phase: 1\ntitle: t\ntasks:\n  - id: P1.T1\n    title: t\n    steps:\n"
        "      - id: P1.T1.S1\n        text: |\n          x\n          ```yaml\n"
        "          # manual-operation\n          id: old\n          why_manual: ui\n"
        "          status: done\n          ```\n"
    )
    _outcome(repo, 1)
    forge(["gate:devops"])
    res = _pass("--gate", "devops", "--run", "run-1")
    assert res.exit_code == 0, res.output
