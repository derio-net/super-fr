"""`fr workflow check` semantic validation — spec §4.A/§4.F, Phase 6.

`check_workflow(manifest)` is pure and takes an already-PARSED
`WorkflowManifest` — a manifest with a structurally invalid schema (unknown
`schema:` version, unknown top-level/step key) can never reach it, because
`fr.workflow.model.parse_manifest` already refuses to construct one (see
`test_workflow_model.py`). What `check_workflow` catches is everything only
meaningful once a valid step graph exists: duplicate step ids, dangling
`needs`, cycles, capability names outside the closed set, and a `for_each`
that contradicts its manifest's `unit`.

The CLI (`fr workflow check <name>`) is the single place BOTH failure
classes — parse-time `WorkflowError` and semantic `check_workflow` errors,
including "unknown schema" — surface uniformly as an exit-1 report; that
half is exercised at the bottom of this file via the `fr.cli` app directly
(no MCP/subprocess — `resolve_workflow`'s `shipped_root` and
`resolve_repo_root`'s `$VK_REPO_ROOT` override are both test-friendly).
"""

from __future__ import annotations

from pathlib import Path

from fr.workflow.check import check_workflow
from fr.workflow.model import parse_manifest
from typer.testing import CliRunner

runner_cli = CliRunner()


def _manifest(text: str):
    return parse_manifest(text)


def test_clean_manifest_has_no_errors() -> None:
    manifest = _manifest(
        "workflow: x\nschema: 1\nunit: run\nrequires: [git]\n"
        "steps:\n"
        "  - id: a\n    kind: cli\n    run: echo hi\n    emits: [spec]\n"
        "  - id: b\n    kind: cli\n    run: echo bye\n    needs: [spec]\n"
    )
    assert check_workflow(manifest) == []


def test_duplicate_step_ids_reported() -> None:
    manifest = _manifest(
        "workflow: x\nschema: 1\nunit: run\n"
        "steps:\n"
        "  - id: a\n    kind: cli\n    run: echo 1\n"
        "  - id: a\n    kind: cli\n    run: echo 2\n"
    )
    errors = check_workflow(manifest)
    assert any("duplicate" in e and "'a'" in e for e in errors)


def test_needs_an_artifact_no_earlier_step_emits() -> None:
    manifest = _manifest(
        "workflow: x\nschema: 1\nunit: run\n"
        "steps:\n"
        "  - id: a\n    kind: cli\n    run: echo hi\n    needs: [ghost]\n"
    )
    errors = check_workflow(manifest)
    assert any("ghost" in e and "'a'" in e for e in errors)


def test_needs_an_artifact_only_a_later_step_emits_is_dangling() -> None:
    manifest = _manifest(
        "workflow: x\nschema: 1\nunit: run\n"
        "steps:\n"
        "  - id: a\n    kind: cli\n    run: echo hi\n    needs: [late]\n"
        "  - id: b\n    kind: cli\n    run: echo bye\n    emits: [late]\n"
    )
    errors = check_workflow(manifest)
    assert any("late" in e for e in errors)


def test_cycle_in_needs_emits_is_reported() -> None:
    manifest = _manifest(
        "workflow: x\nschema: 1\nunit: run\n"
        "steps:\n"
        "  - id: a\n    kind: cli\n    run: echo a\n    needs: [y]\n    emits: [x]\n"
        "  - id: b\n    kind: cli\n    run: echo b\n    needs: [x]\n    emits: [y]\n"
    )
    errors = check_workflow(manifest)
    assert any("cycle" in e.lower() for e in errors)


def test_unknown_capability_in_requires_reported() -> None:
    manifest = _manifest(
        "workflow: x\nschema: 1\nunit: run\nrequires: [git, telepathy]\nsteps: []\n"
    )
    errors = check_workflow(manifest)
    assert any("telepathy" in e for e in errors)


def test_known_capabilities_produce_no_error() -> None:
    manifest = _manifest(
        "workflow: x\nschema: 1\nunit: run\n"
        "requires: [git, tests, scm, browser, network, devcontainer]\nsteps: []\n"
    )
    assert check_workflow(manifest) == []


def test_for_each_phase_is_legal_in_a_run_unit_shape() -> None:
    manifest = _manifest(
        "workflow: x\nschema: 1\nunit: run\n"
        "steps:\n  - id: a\n    kind: agent\n    agent: x\n    for_each: phase\n"
    )
    assert check_workflow(manifest) == []


def test_for_each_phase_is_an_error_in_a_phase_unit_shape() -> None:
    manifest = _manifest(
        "workflow: x\nschema: 1\nunit: phase\n"
        "steps:\n  - id: a\n    kind: agent\n    agent: x\n    for_each: phase\n"
    )
    errors = check_workflow(manifest)
    assert any("for_each" in e and "'a'" in e for e in errors)


def test_multiple_problems_all_reported_together() -> None:
    manifest = _manifest(
        "workflow: x\nschema: 1\nunit: run\nrequires: [nonsense]\n"
        "steps:\n"
        "  - id: a\n    kind: cli\n    run: echo hi\n"
        "  - id: a\n    kind: cli\n    run: echo bye\n    needs: [ghost]\n"
    )
    errors = check_workflow(manifest)
    assert len(errors) >= 3


# ── CLI: `fr workflow check` — one report for parse-time AND semantic errors ──


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "superpowers" / "workflows").mkdir(parents=True)
    return tmp_path


def _invoke(monkeypatch: object, repo: Path, shipped: Path, argv: list[str]):
    import os

    from fr.cli import app

    env = {**os.environ, "VK_REPO_ROOT": str(repo), "FR_SHIPPED_WORKFLOWS_DIR": str(shipped)}
    return runner_cli.invoke(app, argv, env=env)


def test_cli_exits_zero_on_a_clean_shape(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    (shipped / "ok.yaml").write_text(
        "workflow: ok\nschema: 1\nunit: run\nsteps:\n  - id: a\n    kind: cli\n    run: echo hi\n"
    )
    result = _invoke(None, repo, shipped, ["workflow", "check", "ok"])
    assert result.exit_code == 0, result.output


def test_cli_exits_one_on_a_semantic_error(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    (shipped / "bad.yaml").write_text(
        "workflow: bad\nschema: 1\nunit: run\n"
        "steps:\n  - id: a\n    kind: cli\n    run: echo hi\n    needs: [ghost]\n"
    )
    result = _invoke(None, repo, shipped, ["workflow", "check", "bad"])
    assert result.exit_code == 1


def test_cli_exits_one_on_an_unsupported_schema_version(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    (shipped / "future.yaml").write_text("workflow: future\nschema: 2\nunit: run\nsteps: []\n")
    result = _invoke(None, repo, shipped, ["workflow", "check", "future"])
    assert result.exit_code == 1
    assert "schema" in result.output.lower()


def test_cli_all_validates_every_discoverable_shape(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    (shipped / "ok.yaml").write_text(
        "workflow: ok\nschema: 1\nunit: run\nsteps:\n  - id: a\n    kind: cli\n    run: echo hi\n"
    )
    (shipped / "bad.yaml").write_text(
        "workflow: bad\nschema: 1\nunit: run\n"
        "steps:\n  - id: a\n    kind: cli\n    run: echo hi\n    needs: [ghost]\n"
    )
    result = _invoke(None, repo, shipped, ["workflow", "check", "--all"])
    assert result.exit_code == 1
    assert "ok" in result.output
    assert "bad" in result.output


# --- r2-f2: a `kind: cli` step with no `run:` is not expressible ------------


def test_a_cli_step_with_no_run_command_is_an_error() -> None:
    """`Step.run` is optional (agent steps have none), so "cli implies run"
    can only be a semantic check. Unchecked it produced a green run that
    executed nothing: `advance` rendered `""` and `subprocess.run("",
    shell=True)` exits 0."""
    manifest = _manifest(
        "workflow: x\nschema: 1\nunit: run\nsteps:\n  - id: silent\n    kind: cli\n"
    )
    errors = check_workflow(manifest)
    assert len(errors) == 1
    assert "silent" in errors[0]
    assert "run:" in errors[0]


def test_a_cli_step_whose_run_is_only_whitespace_is_an_error() -> None:
    manifest = _manifest(
        'workflow: x\nschema: 1\nunit: run\nsteps:\n  - id: blank\n    kind: cli\n    run: "   "\n'
    )
    assert [e for e in check_workflow(manifest) if "blank" in e]


def test_an_agent_step_with_no_run_command_is_fine() -> None:
    """The check must not leak onto the kind that legitimately has no `run:`."""
    manifest = _manifest(
        "workflow: x\nschema: 1\nunit: run\nsteps:\n  - id: think\n    kind: agent\n"
    )
    assert check_workflow(manifest) == []
