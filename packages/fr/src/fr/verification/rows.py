"""A run's rows and their strategies — the one place a consumer gets a row's
effective strategy from (spec 2026-10-06-verification-strategies §B).

The PR body, visual evidence, self-review and the walk recorder all ask the
same question about a matrix row: given its spec's `## Verification` section
and the shape's default, what is its strategy, and is that post-merge? This
module binds the inputs once (`SpecVerification`) and answers through
`fr.verification.effective` — nobody compares a `verify` string themselves.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fr.verification.effective import effective_strategy, install_problem, is_post_merge
from fr.verification.model import RESERVED, StrategyError
from fr.verification.resolve import resolve_strategy
from fr.verification.spec_section import Section, parse_section

if TYPE_CHECKING:
    from fr.acceptance.model import Row
    from fr.run.model import RunState

__all__ = [
    "SpecVerification",
    "load_remap",
    "run_verification",
    "shape_default",
    "spec_section_at",
    "spec_verification",
    "unrunnable_strategies",
]


def spec_section_at(repo_root: Path, spec_rel: str | None) -> Section | None:
    """The `## Verification` section of the spec at `spec_rel`, or `None` when
    there is no spec, no such file, or no section. A spec archived since the
    run started is found at its archive twin. A malformed section raises
    `SectionError` — the caller decides what an unreadable section means."""
    from fr.acceptance.model import archive_twin

    if not spec_rel:
        return None
    for rel in (spec_rel, archive_twin(spec_rel)):
        if rel and (repo_root / rel).is_file():
            return parse_section((repo_root / rel).read_text())
    return None


def load_remap(repo_root: Path) -> tuple[dict[str, str], str | None]:
    """The repo's gate remap (`.fr/triage.yaml`'s `exit: {gates: {...}}`, spec
    2026-10-14 R4) and why it could not be read, if it could not. Lenient: an
    unreadable or invalid file is no remap, reported by the caller."""
    import yaml
    from pydantic import ValidationError

    from fr.triage.model import parse_triage_config

    path = repo_root / ".fr" / "triage.yaml"
    if not path.is_file():
        return {}, None
    try:
        config, _ = parse_triage_config(yaml.safe_load(path.read_text()) or {})
    except (OSError, yaml.YAMLError, ValidationError) as e:
        return {}, f"{path.relative_to(repo_root)} is not valid triage config: {e}"
    return (dict(config.exit.gates) if config.exit else {}), None


@dataclass(frozen=True)
class SpecVerification:
    """One spec's verification inputs, bound: its section (or `None`), the
    shape's default strategy, the repo's gate remap, and the repo strategies
    resolve against."""

    repo_root: Path
    section: Section | None = None
    shape_default: str | None = None
    remap: Mapping[str, str] = field(default_factory=dict)
    remap_problem: str | None = None

    def strategy(self, row: Row) -> str | None:
        return effective_strategy(row.verify, row.id, self.section, self.shape_default)

    def is_post_merge(self, row: Row) -> bool:
        """Raises `StrategyError` when the row's strategy does not resolve."""
        return is_post_merge(self.strategy(row), self.repo_root)

    def run_strategy(self) -> str | None:
        """The run's own strategy: the section's `strategy:` line, else the
        shape's default; `None` without a section (the world before strategies)."""
        return effective_strategy(None, "", self.section, self.shape_default)

    def _kind_gate(self, strategy: str | None) -> str:
        """The gate of a strategy kind: the repo's remap, else the manifest's
        `gate:`, else `none`. An unresolvable strategy is another check's to
        report, so it has no gate here."""
        if strategy is None or strategy == RESERVED:
            return "none"
        if strategy in self.remap:
            return self.remap[strategy]
        try:
            return resolve_strategy(strategy, self.repo_root).gate
        except StrategyError:
            return "none"

    def run_gate(self) -> str:
        """The run-level gate (R1), first match wins: the section's `gate:`
        line, the remap of the run strategy's kind, its manifest `gate:`, `none`."""
        if self.section is not None and self.section.gate is not None:
            return self.section.gate
        return self._kind_gate(self.run_strategy())

    def gate(self, row: Row) -> str:
        """A row's effective gate (R5), first match wins: its `gate: <row>=`
        line, the run-level gate (a row on the run's own strategy), the remap
        of its kind, the manifest's `gate:`, `none`."""
        if self.section is not None and row.id in self.section.row_gates:
            return self.section.row_gates[row.id]
        strategy = self.strategy(row)
        if strategy is not None and strategy != RESERVED and strategy == self.run_strategy():
            return self.run_gate()
        return self._kind_gate(strategy)

    def reason(self, row: Row) -> str | None:
        """The section's one-line reason for `row`, when it gives one."""
        line = self.section.rows.get(row.id) if self.section is not None else None
        return line.reason if line is not None else None


def spec_verification(
    repo_root: Path, spec_rel: str | None, shape_default: str | None = None
) -> SpecVerification:
    """`SpecVerification` for the spec at `spec_rel` (`SectionError` when its
    section is malformed)."""
    remap, problem = load_remap(repo_root)
    return SpecVerification(
        repo_root, spec_section_at(repo_root, spec_rel), shape_default, remap, problem
    )


def raw_shape_default(repo_root: Path, state: RunState) -> str | None:
    """The run's workflow shape's declared default strategy, BEFORE the
    `effective_shape_default` filter (`None` when it declares none)."""
    from fr.workflow.model import WorkflowError
    from fr.workflow.resolve import resolve_workflow

    try:
        return resolve_workflow(state.workflow.partition("@")[0], repo_root).verification
    except (WorkflowError, OSError):
        return None


def shape_default(repo_root: Path, state: RunState) -> str | None:
    """The run's workflow shape's default strategy, or `None` when the shape
    does not resolve or declares none, or when the repo cannot run it
    (`effective_shape_default`)."""
    from fr.verification.effective import effective_shape_default

    return effective_shape_default(raw_shape_default(repo_root, state), repo_root)


def run_verification(repo_root: Path, state: RunState) -> tuple[str | None, SpecVerification]:
    """`(spec_rel, SpecVerification)` for a run: the spec it emitted and that
    spec's section bound to the shape's default (`SectionError` when the
    section is malformed). `spec_rel` is `None` when the run emitted no spec."""
    from fr.requirements import run_spec

    spec_rel = run_spec(state)
    return spec_rel, spec_verification(repo_root, spec_rel, shape_default(repo_root, state))


def unrunnable_strategies(repo_root: Path, section: Section, rows: Sequence[Row]) -> list[str]:
    """One message per distinct strategy the spec names EXPLICITLY — the
    section's `strategy:`, a per-row line, or a `verify:` of one of `rows` —
    that resolves and whose install program the repo cannot run (spec
    2026-10-12 §B, R5). Never consults the shape default (R4 drops that) and
    needs no plan; an unresolvable name is another check's to report."""
    sources: dict[str, list[tuple[str, str]]] = {}

    def add(name: str | None, kind: str, where: str) -> None:
        if name and name != RESERVED and (kind, where) not in sources.setdefault(name, []):
            sources[name].append((kind, where))

    add(section.strategy, "section", "the section's `strategy:` line")
    for rid, line in section.rows.items():
        add(line.strategy, "line", f"the `- {rid}:` line")
    for r in rows:
        add(r.verify, "verify", f"row `{r.id}`'s own `verify:`")
    out: list[str] = []
    for name, named_by in sources.items():
        try:
            problem = install_problem(resolve_strategy(name, repo_root), repo_root)
        except StrategyError:
            continue
        if problem is None:
            continue
        where = "; ".join(w for _, w in named_by)
        fixes: list[str] = []
        if any(k == "section" for k, _ in named_by):
            fixes.append("`strategy: none`")
        if any(k in ("section", "line") for k, _ in named_by):
            fixes.append("a per-row `- <row-id>: none — <reason>` line")
        verify_rows = [w for k, w in named_by if k == "verify"]
        if verify_rows:
            fixes.append(
                "for the row(s) naming it in `verify:`, which outranks the spec's lines, "
                "`fr acceptance set-status --id <row> --status <status> --notes <why> "
                "--verify none`"
            )
        out.append(
            f"{problem} (named by {where}). Either say it does not need it — "
            f"{', or '.join(fixes)} — or add the executable"
        )
    return out
