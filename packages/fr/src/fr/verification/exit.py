"""A run's exit — spec 2026-10-14 exit-gates R1, §A.

The exit is two things: its **kinds** (the effective strategies of the run and
of every row citing its spec, `none` where no strategy applies) and its
**gates** (the run-level gate plus each such row's effective gate). One
function computes it; labels, `deliver`, the driver, the board and release all
read this and none re-derives it. The ORDER in which a gate is decided lives in
`SpecVerification.run_gate` / `.gate`, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr.gates import POST_MERGE_GATES
from fr.verification.model import RESERVED, StrategyError
from fr.verification.resolve import resolve_strategy
from fr.verification.rows import SpecVerification, run_verification, spec_verification

if TYPE_CHECKING:
    from fr.acceptance.model import Row
    from fr.run.model import RunState

__all__ = ["Exit", "exit_for_spec", "kind_rank", "run_exit"]


def kind_rank(kind: str, repo_root: Path | None) -> int:
    """How long a kind makes the exit wait: post-merge (3) > pre-merge
    operator-driven (2) > pre-merge agent-driven (1) > `none` or unresolvable (0)."""
    if kind == RESERVED:
        return 0
    try:
        manifest = resolve_strategy(kind, repo_root)
    except StrategyError:
        return 0
    if manifest.when == "post-merge":
        return 3
    return 2 if manifest.driver == "operator" else 1


@dataclass(frozen=True)
class Exit:
    kinds: frozenset[str]
    run_gate: str
    gates: frozenset[str]
    gated_rows: tuple[Row, ...]
    rank: int
    rows: tuple[Row, ...]
    row_gates: dict[str, str]
    row_kinds: dict[str, str]
    run_kind: str
    remap_problem: str | None = None

    @property
    def is_gated(self) -> bool:
        """R6: gated iff the gates hold a post-merge gate."""
        return bool(self.gates & POST_MERGE_GATES)


def _build(verification: SpecVerification, rows: list[Row]) -> Exit:
    def kind(strategy: str | None) -> str:
        return strategy if strategy is not None else RESERVED

    run_gate = verification.run_gate()
    row_gates = {r.id: verification.gate(r) for r in rows}
    run_kind = kind(verification.run_strategy())
    row_kinds = {r.id: kind(verification.strategy(r)) for r in rows}
    kinds = {run_kind, *row_kinds.values()}
    gates = {g for g in (run_gate, *row_gates.values()) if g != "none"}
    return Exit(
        kinds=frozenset(kinds),
        run_gate=run_gate,
        gates=frozenset(gates),
        gated_rows=tuple(r for r in rows if row_gates[r.id] in POST_MERGE_GATES),
        rank=max(kind_rank(k, verification.repo_root) for k in kinds),
        rows=tuple(rows),
        row_gates=row_gates,
        row_kinds=row_kinds,
        run_kind=run_kind,
        remap_problem=verification.remap_problem,
    )


def exit_for_spec(repo_root: Path, spec_rel: str, shape_default: str | None = None) -> Exit:
    """The exit of the spec at `spec_rel` (`SectionError` / `AcceptanceError`
    when its section or the matrix is unreadable)."""
    from fr.requirements import load_spec_matrix, rows_citing

    verification = spec_verification(repo_root, spec_rel, shape_default)
    matrix, spec_ref = load_spec_matrix(repo_root, spec_rel)
    return _build(verification, rows_citing(matrix, spec_ref))


def run_exit(repo_root: Path, state: RunState) -> Exit:
    """The exit of a run: its spec's section bound to the shape's default, and
    the rows citing that spec. A run with no spec has the empty exit."""
    from fr.requirements import load_spec_matrix, rows_citing

    spec_rel, verification = run_verification(repo_root, state)
    if spec_rel is None:
        return _build(verification, [])
    matrix, spec_ref = load_spec_matrix(repo_root, spec_rel)
    return _build(verification, rows_citing(matrix, spec_ref))
