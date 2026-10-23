"""`fr ops` — the CLI surface over the op engine (spec 2026-10-22-fr-ops R3, R17).

`status` reads, never writes; the whole group is gated by the artifact trigger.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fr.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_ops_group_is_registered() -> None:
    result = runner.invoke(app, ["ops", "--help"])
    assert result.exit_code == 0, result.output
    assert "status" in result.output


def test_the_ops_group_is_gated_by_the_artifact_trigger() -> None:
    """R17: the whole group, `status` included, is gated — never exempt."""
    from fr.artifacts import trigger

    assert "ops" not in trigger.READ_ONLY_COMMANDS


# --- fr ops status ---------------------------------------------------------------

PLAN_REL = "docs/superpowers/plans/p"

OPS = """schema_version: 1
ops:
  - id: create-key
    summary: Create the deploy key
    phase: pre-merge
    check: 'true'
    vacuous_if: the key file exists but is empty
  - id: rotate
    summary: Rotate the token
    phase: post-merge
    needs: [create-key]
    check: 'echo "HTTP 404: token missing"; exit 1'
"""


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _repo(tmp_path: Path, ops: str = OPS, branch: str = "feat/x") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, "init", "-q", "-b", branch)
    plan = tmp_path / PLAN_REL
    plan.mkdir(parents=True)
    (plan / "ops.yaml").write_text(ops)
    # Committed: a probe runs only against committed paths (R19), and a plan's
    # ops.yaml is not one of fr's evidence files.
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed")
    _trust_all(tmp_path)
    return tmp_path


def _trust_all(root: Path) -> None:
    """Record the operator's trust in the fixture's op set (R19), as `fr ops trust`
    does once confirmed — so these tests exercise status, not the trust gate
    (`test_ops_trust.py` owns that)."""
    from fr.ops.load import OpsLoadError, load_ops, load_ops_config
    from fr.ops.trust import fingerprint, grant_trust, head_tree, tree_digest

    try:
        ops = load_ops(root / PLAN_REL, root).ops
    except OpsLoadError:
        return  # a test of the carrier refusal; nothing to trust
    tree = head_tree(root)
    fp = fingerprint(ops, load_ops_config(root), root, code_tree=tree_digest(tree))
    grant_trust(root, "p", fp, tree=tree)


def _run_on_branch(root: Path, branch: str = "feat/x") -> None:
    runs = root / "docs/superpowers/runs"
    runs.mkdir(parents=True)
    from fr.artifacts import ARTIFACT_KINDS

    (runs / "r1.yaml").write_text(
        f"schema_version: {ARTIFACT_KINDS['run'].current_version}\n"
        f"run: r1\nworkflow: fr-goal@1\nbranch: {branch}\n"
        "started: '2026-10-22T00:00:00+00:00'\ncursor: implement\n"
        f"steps:\n  plan:\n    state: done\n    emitted: {{plan: {PLAN_REL}}}\n"
    )
    # A branch is only named once it has a commit (an unborn HEAD has none).
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed")


def _status(root: Path, monkeypatch, *args: str):
    monkeypatch.chdir(root)
    return runner.invoke(app, ["ops", "status", *args])


def test_status_reports_each_op_and_exits_1_on_an_open_op(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    result = _status(root, monkeypatch, "--plan", PLAN_REL)
    assert result.exit_code == 1, result.output
    assert "DONE (checked)" in result.stdout and "create-key" in result.stdout
    assert "OPEN" in result.stdout and "HTTP 404: token missing" in result.stdout


def test_status_exits_0_when_everything_is_done(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path, OPS.replace('echo "HTTP 404: token missing"; exit 1', "true"))
    assert _status(root, monkeypatch, "--plan", PLAN_REL).exit_code == 0


def test_status_exits_3_on_an_escalation(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path, OPS + "    escalate: 'true'\n")
    result = _status(root, monkeypatch, "--plan", PLAN_REL)
    assert result.exit_code == 3, result.output
    assert "ESCALATE" in result.stdout


def test_status_defaults_to_the_plan_of_the_run_on_this_branch(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    _run_on_branch(root)
    result = _status(root, monkeypatch)
    assert result.exit_code == 1, result.output
    assert "create-key" in result.stdout


def test_status_refuses_with_no_run_on_this_branch(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    _run_on_branch(root, branch="feat/other")
    result = _status(root, monkeypatch)
    assert result.exit_code == 2
    assert "--plan" in result.output


def test_status_warns_outside_an_ops_profile(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    result = _status(root, monkeypatch, "--plan", PLAN_REL)
    assert "ops profile" in result.stderr


def test_status_json_rows(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    result = _status(root, monkeypatch, "--plan", PLAN_REL, "--json")
    rows = json.loads(result.stdout)
    assert [(r["op"], r["state"], r["how"]) for r in rows] == [
        ("create-key", "DONE", "checked"),
        ("rotate", "OPEN", None),
    ]
    assert rows[1]["reason"] == "HTTP 404: token missing"


def test_status_explain_prints_vacuous_if(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    plain = _status(root, monkeypatch, "--plan", PLAN_REL)
    assert "the key file exists but is empty" not in plain.stdout
    explained = _status(root, monkeypatch, "--plan", PLAN_REL, "--explain")
    assert "the key file exists but is empty" in explained.stdout


def test_status_filters_by_phase_and_by_op_id(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    by_phase = _status(root, monkeypatch, "--plan", PLAN_REL, "--phase", "pre-merge", "--json")
    assert [r["op"] for r in json.loads(by_phase.stdout)] == ["create-key"]
    assert by_phase.exit_code == 0
    one = _status(root, monkeypatch, "--plan", PLAN_REL, "rotate", "--json")
    assert [r["op"] for r in json.loads(one.stdout)] == ["rotate"]


def test_status_refuses_a_needs_cycle_and_a_bad_phase(tmp_path: Path, monkeypatch) -> None:
    root = _repo(
        tmp_path, OPS.replace("phase: pre-merge\n", "phase: pre-merge\n    needs: [rotate]\n")
    )
    result = _status(root, monkeypatch, "--plan", PLAN_REL)
    assert result.exit_code == 2
    assert "cycle" in result.output
    bad = _status(_repo(tmp_path / "b"), monkeypatch, "--plan", PLAN_REL, "--phase", "soon")
    assert bad.exit_code == 2


def test_status_refuses_an_unreadable_carrier(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path, "schema_version: 1\nops:\n  - id: [\n")
    result = _status(root, monkeypatch, "--plan", PLAN_REL)
    assert result.exit_code == 2
    assert "ops.yaml:" in result.output


def test_status_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed")
    _status(root, monkeypatch, "--plan", PLAN_REL)
    porcelain = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True
    ).stdout
    assert porcelain == ""


def test_status_phase_filter_keeps_a_need_on_an_op_of_the_other_phase(
    tmp_path: Path, monkeypatch
) -> None:
    """p1-r2: `rotate` (post-merge) needs `create-key` (pre-merge); filtering to
    post-merge must not read that need as unknown."""
    root = _repo(tmp_path)
    result = _status(root, monkeypatch, "--plan", PLAN_REL, "--phase", "post-merge", "--json")
    assert result.exit_code == 1, result.output
    assert [r["op"] for r in json.loads(result.stdout)] == ["rotate"]
