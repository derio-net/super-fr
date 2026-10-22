"""The op carriers (spec 2026-10-22-fr-ops R2, §B): `ops.yaml`, `# manual-operation`
blocks in step text, and the repo runbook, read only for an explicit selection."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fr.ops.load import OpsLoadError, load_ops, load_ops_config

FIXTURES = Path(__file__).parent / "fixtures" / "ops"
PLAN = Path("docs/superpowers/plans/p")


def _repo(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    shutil.copytree(FIXTURES / name, root)
    return root


def _ids(opset: object) -> list[str]:
    return [lo.op.id for lo in opset.ops]  # type: ignore[attr-defined]


def test_ops_yaml_only(tmp_path: Path) -> None:
    root = _repo(tmp_path, "yaml-only")
    opset = load_ops(root / PLAN, root)
    assert _ids(opset) == ["create-key", "rotate"]
    first = opset.ops[0]
    assert first.source == root / PLAN / "ops.yaml"
    assert first.line == 3
    assert not first.legacy_done and not first.runbook
    assert opset.warnings == ()


def test_step_text_blocks_are_dedented_and_read_through_the_legacy_model(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path, "step-blocks")
    opset = load_ops(root / PLAN, root)
    assert _ids(opset) == ["from-step", "second"]
    from_step, second = opset.ops
    assert from_step.op.summary == "needs an admin click"
    assert from_step.op.phase == "post-merge"
    assert from_step.op.commands == ("open the admin page",)
    assert from_step.source == root / PLAN / "01.yaml"
    # The block's `# manual-operation` line: file line 15.
    assert from_step.line == 15
    assert second.op.phase == "pre-merge"
    assert second.legacy_done


def test_a_mid_sentence_fence_does_not_swallow_the_next_block(tmp_path: Path) -> None:
    """The first step's prose names "```yaml" mid-line; a naive toggle on any
    fence-looking text would open a fence there and read the real block as its
    closer, losing `from-step`."""
    root = _repo(tmp_path, "step-blocks")
    assert "from-step" in _ids(load_ops(root / PLAN, root))


def test_the_same_id_in_both_carriers_is_an_error_naming_both(tmp_path: Path) -> None:
    root = _repo(tmp_path, "step-blocks")
    (root / PLAN / "ops.yaml").write_text(
        "schema_version: 1\nops:\n  - id: second\n    summary: s\n    phase: pre-merge\n"
    )
    with pytest.raises(OpsLoadError) as exc:
        load_ops(root / PLAN, root)
    msg = str(exc.value)
    assert "second" in msg
    assert "ops.yaml:3" in msg and "01.yaml:" in msg


def test_malformed_yaml_names_file_and_line(tmp_path: Path) -> None:
    root = _repo(tmp_path, "yaml-only")
    (root / PLAN / "ops.yaml").write_text("schema_version: 1\nops:\n  - id: [unclosed\n")
    with pytest.raises(OpsLoadError, match=r"ops\.yaml:\d+"):
        load_ops(root / PLAN, root)


def test_malformed_step_block_names_file_and_line(tmp_path: Path) -> None:
    root = _repo(tmp_path, "step-blocks")
    phase = root / PLAN / "01.yaml"
    phase.write_text(phase.read_text().replace("layer: ci", "layer: [ci"))
    with pytest.raises(OpsLoadError, match=r"01\.yaml:\d+"):
        load_ops(root / PLAN, root)


def test_an_unknown_key_names_the_key_file_and_line(tmp_path: Path) -> None:
    root = _repo(tmp_path, "yaml-only")
    path = root / PLAN / "ops.yaml"
    path.write_text(path.read_text().replace("    check: test", "    chekc: test"))
    with pytest.raises(OpsLoadError) as exc:
        load_ops(root / PLAN, root)
    assert "chekc" in str(exc.value)
    assert "ops.yaml:6" in str(exc.value)


def test_runbook_ops_are_absent_by_default_except_what_needs_pulls_in(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path, "runbook")
    opset = load_ops(root / PLAN, root)
    # `deploy` needs `rb-backup`, so it comes in; `rb-dns` does not.
    assert _ids(opset) == ["deploy", "shared", "rb-backup"]
    rb = opset.get("rb-backup")
    assert rb is not None and rb.runbook
    assert rb.source == root / "ops/manual-operations.yaml"


def test_runbook_true_selects_every_runbook_op(tmp_path: Path) -> None:
    root = _repo(tmp_path, "runbook")
    opset = load_ops(root / PLAN, root, runbook=True)
    assert _ids(opset) == ["deploy", "shared", "rb-backup", "rb-dns"]


def test_a_plan_op_shadows_a_runbook_op_with_a_warning(tmp_path: Path) -> None:
    root = _repo(tmp_path, "runbook")
    opset = load_ops(root / PLAN, root, runbook=True)
    shared = opset.get("shared")
    assert shared is not None and shared.op.summary == "The plan's version"
    assert any("shared" in w and "shadows" in w for w in opset.warnings)


def test_the_runbook_is_not_read_for_a_default_selection_that_needs_nothing(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path, "runbook")
    (root / "ops/manual-operations.yaml").write_text("- id: [broken\n")
    (root / PLAN / "ops.yaml").write_text(
        "schema_version: 1\nops:\n  - id: alone\n    summary: s\n    phase: pre-merge\n"
    )
    assert _ids(load_ops(root / PLAN, root)) == ["alone"]


def test_ids_select_named_ops_including_runbook_ones(tmp_path: Path) -> None:
    root = _repo(tmp_path, "runbook")
    assert _ids(load_ops(root / PLAN, root, ids=("rb-dns",))) == ["rb-dns"]
    with pytest.raises(OpsLoadError, match="nope"):
        load_ops(root / PLAN, root, ids=("nope",))


def test_no_carrier_is_an_empty_set(tmp_path: Path) -> None:
    plan = tmp_path / PLAN
    plan.mkdir(parents=True)
    assert load_ops(plan, tmp_path).ops == ()


def test_ops_config_reads_runbook_and_identities(tmp_path: Path) -> None:
    root = _repo(tmp_path, "runbook")
    config = load_ops_config(root)
    assert config.runbook == "ops/manual-operations.yaml"
    assert config.identities["admin"].env["TOKEN"].from_ == "echo admin-token"
    assert load_ops_config(tmp_path).identities == {}
