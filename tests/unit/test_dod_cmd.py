"""`fr run dod <run-id> [--json]` (spec 2026-11-27-ops-gate-truth R18): prints the run's
Definition of Done, changes nothing, exits 0 when discharged, 1 when an item is owed and 2
when the run or its inputs cannot be read."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fr.cli import app
from fr.run.model import save_run_state
from typer.testing import CliRunner

from tests.unit.test_run_dod import MANUAL, PLAN, _repo, _state

runner = CliRunner()


def _invoke(repo: Path, argv: list[str]):  # noqa: ANN202
    return runner.invoke(app, argv, env={**os.environ, "FR_REPO_ROOT": str(repo)})


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _no_gate_run(tmp_path: Path) -> Path:
    """A run with no post-merge gate and only a ticked manual phase: discharged."""
    root = _repo(tmp_path)
    (root / PLAN / "ops.yaml").unlink()
    (root / PLAN / "02.yaml").write_text(MANUAL.format(n=2, tick="x"))
    spec = next((root / "docs/superpowers/specs").glob("*.md"))
    spec.write_text("# G\n\n## Verification\n\nstrategy: none\ngate: developer\n")
    save_run_state(root, _state())
    return root


def test_an_owed_run_prints_each_group_and_exits_1(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    save_run_state(root, _state())
    before = _snapshot(root)
    result = _invoke(root, ["run", "dod", "run-1"])
    assert result.exit_code == 1, result.output
    for name in ("gate:devops", "gate:tester", "manual phases", "owed"):
        assert name in result.output
    assert "[owed] phase 2 [manual]" in result.output
    assert _snapshot(root) == before, "fr run dod changes no file"


def test_a_discharged_run_exits_0(tmp_path: Path) -> None:
    root = _no_gate_run(tmp_path)
    result = _invoke(root, ["run", "dod", "run-1"])
    assert result.exit_code == 0, result.output
    assert "Definition of Done — discharged" in result.output


def test_json_emits_the_groups(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    save_run_state(root, _state())
    result = _invoke(root, ["run", "dod", "run-1", "--json"])
    assert result.exit_code == 1, result.output
    data = json.loads(result.output)
    assert data["run"] == "run-1" and data["discharged"] is False
    names = [g["name"] for g in data["groups"]]
    assert names == ["gate:devops", "gate:tester", "manual phases", "owed"]
    manual = next(g for g in data["groups"] if g["name"] == "manual phases")
    assert manual["items"][0] == {"what": "phase 2 [manual]", "discharged": False,
                                  "why": "not ticked — Walk it live 2"}  # fmt: skip


def test_an_unknown_run_exits_2(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    result = _invoke(root, ["run", "dod", "nope"])
    assert result.exit_code == 2, result.output


def test_an_unreadable_input_exits_2(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    save_run_state(root, _state())
    (root / PLAN / "ops.yaml").write_text("ops: [\n")
    result = _invoke(root, ["run", "dod", "run-1"])
    assert result.exit_code == 2, result.output
    assert "cannot be read" in result.output
