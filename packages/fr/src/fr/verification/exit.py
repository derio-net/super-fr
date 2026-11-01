"""A run's exit — spec 2026-10-14 exit-gates R1, §A.

The exit is two things: its **kinds** (the effective strategies of the run and
of every row citing its spec, `none` where no strategy applies) and its
**gates** (the run-level gate plus each such row's effective gate). One
function computes it; labels, `deliver`, the driver, the board and release all
read this and none re-derives it. The ORDER in which a gate is decided lives in
`SpecVerification.run_gate` / `.gate`, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
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

IMPLEMENTED_PLANS_REL = Path("docs/superpowers/implemented/plans")


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
    ops_promoted: bool = False
    """`devops` was added because the run's plan carries ops (spec 2026-10-22-fr-ops R13)."""

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


def exit_for_spec(
    repo_root: Path, spec_rel: str, shape_default: str | None = None, *, repo: str | None = None
) -> Exit:
    """The exit of the spec at `spec_rel` (`SectionError` / `AcceptanceError`
    when its section or the matrix is unreadable). *repo* names the repository when
    `repo_root` is not a checkout (a tree materialised from a ref, spec
    2026-11-01-ops-gate-probes R5); the matrix's own `repo:` key still wins."""
    from fr.requirements import load_spec_matrix, rows_citing

    verification = spec_verification(repo_root, spec_rel, shape_default)
    if repo is None:
        matrix, spec_ref = load_spec_matrix(repo_root, spec_rel)
    else:
        from fr.acceptance.model import Matrix, load_matrix
        from fr.commands.acceptance_cmd import MATRIX_REL

        path = repo_root / MATRIX_REL
        matrix = load_matrix(path) if path.exists() else Matrix()
        spec_ref = f"{matrix.repo or repo}:{spec_rel}"
    return _build(verification, rows_citing(matrix, spec_ref))


def run_plan_dir(repo_root: Path, state: RunState) -> Path | None:
    """The plan dir the run emitted, live or archived; `None` when it emitted none or
    the plan is in neither place."""
    plan_rel = next(
        (r.emitted["plan"] for r in state.steps.values() if r.emitted and "plan" in r.emitted),
        None,
    )
    if not plan_rel:
        return None
    live = repo_root / plan_rel
    if live.is_dir():
        return live
    archived = repo_root / IMPLEMENTED_PLANS_REL / Path(plan_rel).name
    return archived if archived.is_dir() else None


def _promote(exit_: Exit, repo_root: Path, state: RunState) -> Exit:
    """R13: `devops` beside the declared gates whenever the run's plan has any op."""
    from fr.ops.load import plan_has_ops

    plan_dir = run_plan_dir(repo_root, state)
    if plan_dir is None or not plan_has_ops(repo_root, plan_dir):
        return exit_
    return replace(exit_, gates=exit_.gates | {"devops"}, ops_promoted=True)


def run_exit(repo_root: Path, state: RunState) -> Exit:
    """The exit of a run: its spec's section bound to the shape's default, and
    the rows citing that spec, plus `devops` when its plan has ops (R13). A run
    with no spec has the empty exit, still promoted when its plan has ops."""
    from fr.requirements import load_spec_matrix, rows_citing

    spec_rel, verification = run_verification(repo_root, state)
    if spec_rel is None:
        return _promote(_build(verification, []), repo_root, state)
    matrix, spec_ref = load_spec_matrix(repo_root, spec_rel)
    return _promote(_build(verification, rows_citing(matrix, spec_ref)), repo_root, state)
