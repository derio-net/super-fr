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


def test_frank_runbook_shape_is_read_without_refusal(tmp_path: Path) -> None:
    """p1-r3: the real runbook shape — `operations:` mapping, extra keys, mapping
    commands, free-text statuses (R2)."""
    root = _repo(tmp_path, "runbook-frank")
    opset = load_ops(root / PLAN, root, runbook=True)
    legacy = {lo.op.id: lo.legacy for lo in opset.ops}
    assert legacy == {
        "rotate-dns": "done",
        "old-backup": "n/a",
        "lb-health": "n/a",
        "cert": None,
        "later": None,
        "freeform": None,
    }
    rotate = opset.get("rotate-dns")
    assert rotate is not None and rotate.op.commands is not None
    assert "192.0.2.10" in rotate.op.commands[1]
    assert rotate.line == 5
    kept = " ".join(opset.warnings)
    for key in ("done_note", "decommissioned", "note", "notes"):
        assert key in kept
    assert "rotate-dns" in kept and "prose" in kept


def test_self_review_tolerates_frank_keys_in_step_blocks(tmp_path: Path, monkeypatch) -> None:
    """A plan whose step blocks carry frank's extra keys reviews without an error
    from the op loader (it still owes the fr ops floor)."""
    from fr.parser import parse as parse_plan
    from fr.plan_ops import self_review

    from tests.unit.test_ops_artifacts import _plan

    plan_dir = _plan(tmp_path, monkeypatch)
    phase = plan_dir / "01.yaml"
    phase.write_text(
        phase.read_text().replace(
            "text: |-\n      s\n",
            "text: |-\n      ```yaml\n      # manual-operation\n      id: x\n"
            "      why_manual: needs a click\n      note: kept as prose\n"
            "      commands:\n        - {host: 192.0.2.10, run: ls}\n"
            "      status: done 2026-07-27 by hand\n      ```\n",
        )
    )
    errors = [i.message for i in self_review(parse_plan(plan_dir)) if i.severity == "error"]
    assert not [e for e in errors if "do not load" in e], errors


# --- the `none:` acknowledgement (spec 2026-11-01-ops-gate-probes R4) ------------------


def _plan_with(tmp_path: Path, ops_yaml: str | None) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    plan = root / PLAN
    plan.mkdir(parents=True)
    if ops_yaml is not None:
        (plan / "ops.yaml").write_text(ops_yaml)
    return root, plan


def test_ops_none_reads_the_reason(tmp_path: Path) -> None:
    from fr.ops.load import ops_none

    _, plan = _plan_with(tmp_path, "schema_version: 2\nnone: physical steps only\n")
    assert ops_none(plan) == "physical steps only"


def test_ops_none_is_none_without_the_key_or_the_file(tmp_path: Path) -> None:
    from fr.ops.load import ops_none

    _, plan = _plan_with(tmp_path, "schema_version: 2\nops: []\n")
    assert ops_none(plan) is None
    (plan / "ops.yaml").unlink()
    assert ops_none(plan) is None
    assert ops_none(tmp_path / "missing") is None


def test_ops_none_beside_step_blocks_is_refused_by_name(tmp_path: Path) -> None:
    from fr.ops.load import ops_none

    root = _repo(tmp_path, "step-blocks")
    (root / PLAN / "ops.yaml").write_text("schema_version: 2\nnone: nothing\n")
    with pytest.raises(OpsLoadError, match="none"):
        ops_none(root / PLAN)
    with pytest.raises(OpsLoadError, match="none"):
        load_ops(root / PLAN, root)


def test_a_none_file_loads_no_ops_and_never_counts_as_ops(tmp_path: Path) -> None:
    from fr.ops.load import plan_has_ops

    root, plan = _plan_with(tmp_path, "schema_version: 2\nnone: nothing to run\n")
    assert load_ops(plan, root).ops == ()
    assert plan_has_ops(root, plan) is False


def test_none_beside_ops_is_refused_by_the_loader(tmp_path: Path) -> None:
    root, plan = _plan_with(
        tmp_path,
        "schema_version: 2\nnone: x\nops:\n  - {id: a, summary: s, phase: pre-merge}\n",
    )
    with pytest.raises(OpsLoadError, match="none"):
        load_ops(plan, root)
