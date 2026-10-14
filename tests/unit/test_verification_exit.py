"""`fr.verification.exit` — a run's exit: kinds, gates, gated rows, rank
(spec 2026-10-14 exit-gates R1, R5, R6)."""

from __future__ import annotations

from pathlib import Path

from fr.verification.exit import Exit, exit_for_spec

from tests.unit.requirements_support import row, write_matrix

SPEC = "docs/spec.md"


def _repo(
    tmp_path: Path,
    section: str | None,
    rows: list[dict[str, object]],
    remap: str | None = None,
) -> Path:
    (tmp_path / "docs").mkdir(exist_ok=True)
    body = "# Spec\n\n## Requirements\n\nR1. x\n"
    if section is not None:
        body += f"\n## Verification\n\n{section}\n"
    (tmp_path / SPEC).write_text(body)
    write_matrix(tmp_path, rows)
    if remap is not None:
        (tmp_path / ".fr").mkdir(exist_ok=True)
        (tmp_path / ".fr" / "triage.yaml").write_text(remap)
    return tmp_path


def _row(rid: str, verify: str | None = None) -> dict[str, object]:
    return row(SPEC, rid=rid, verify=verify)


def _exit(root: Path, shape_default: str | None = None) -> Exit:
    return exit_for_spec(root, SPEC, shape_default)


def test_the_run_gate_follows_section_then_remap_then_manifest_then_none(tmp_path: Path) -> None:
    # manifest: `live` ships gate tester
    assert _exit(_repo(tmp_path, "strategy: live", [])).run_gate == "tester"
    # a kind with no gate
    assert _exit(_repo(tmp_path, "strategy: candidate", [])).run_gate == "none"
    # remap beats the manifest
    remap = "exit:\n  gates:\n    live: devops\n    candidate: tester\n"
    assert _exit(_repo(tmp_path, "strategy: live", [], remap)).run_gate == "devops"
    assert _exit(_repo(tmp_path, "strategy: candidate", [], remap)).run_gate == "tester"
    # the section's own gate line beats the remap
    assert _exit(_repo(tmp_path, "strategy: live\ngate: owner", [], remap)).run_gate == "owner"


def test_a_row_gate_follows_row_line_run_gate_remap_manifest_none(tmp_path: Path) -> None:
    section = (
        "strategy: candidate\ngate: security\n"
        "gate: r-line=devops\n"
        "- r-live: live — needs the release\n"
        "- r-line: live — also\n"
        "- r-none: none — covered elsewhere\n"
    )
    rows = [_row("r-run"), _row("r-live"), _row("r-line"), _row("r-none")]
    ex = _exit(_repo(tmp_path, section, rows))

    gates = {r.id: ex.row_gates[r.id] for r in ex.rows}
    assert gates["r-line"] == "devops"  # its own line
    assert gates["r-run"] == "security"  # on the run's strategy: the run gate
    assert gates["r-live"] == "tester"  # manifest of live
    assert gates["r-none"] == "none"  # no strategy: no gate
    remap = "exit:\n  gates:\n    live: devops\n"
    ex = _exit(_repo(tmp_path, section, rows, remap))
    assert ex.row_gates["r-live"] == "devops"  # the remap beats the manifest


def test_kinds_include_none_for_a_row_with_no_strategy(tmp_path: Path) -> None:
    section = "strategy: candidate\n- r-live: live — needs the release\n- r-none: none — other\n"
    ex = _exit(_repo(tmp_path, section, [_row("r-a"), _row("r-live"), _row("r-none")]))

    assert ex.kinds == {"candidate", "live", "none"}


def test_a_row_without_a_section_takes_only_its_own_verify(tmp_path: Path) -> None:
    ex = _exit(_repo(tmp_path, None, [_row("r-a"), _row("r-b", verify="live")]))

    assert ex.kinds == {"none", "live"}
    assert ex.gates == {"tester"}


def test_gates_include_the_run_gate_with_no_rows(tmp_path: Path) -> None:
    ex = _exit(_repo(tmp_path, "strategy: live", []))

    assert ex.gates == {"tester"}
    assert ex.gated_rows == ()
    assert ex.is_gated


def test_is_gated_only_for_a_post_merge_gate(tmp_path: Path) -> None:
    ex = _exit(_repo(tmp_path, "strategy: candidate\ngate: owner", [_row("r-a")]))
    assert ex.gates == {"owner"}
    assert not ex.is_gated

    ex = _exit(_repo(tmp_path, "strategy: candidate\ngate: row-x=devops", [_row("row-x")]))
    assert ex.is_gated
    assert [r.id for r in ex.gated_rows] == ["row-x"]


def test_rank_orders_post_merge_over_operator_over_agent_over_none(tmp_path: Path) -> None:
    def rank(section: str) -> int:
        return _exit(_repo(tmp_path, section, [])).rank

    assert rank("strategy: live") > rank("strategy: prerelease")
    assert rank("strategy: client-live") == rank("strategy: prerelease")
    assert rank("strategy: prerelease") > rank("strategy: candidate")
    assert rank("strategy: candidate") > rank("strategy: none")
    assert rank("strategy: none") == _exit(_repo(tmp_path, None, [])).rank


def test_an_unreadable_remap_is_no_remap_and_is_reported(tmp_path: Path) -> None:
    ex = _exit(_repo(tmp_path, "strategy: live", [], remap="exit: [not, a, mapping]"))

    assert ex.run_gate == "tester"
    assert ex.remap_problem is not None and "triage.yaml" in ex.remap_problem
