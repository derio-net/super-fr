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
    "remap_key_problems",
    "row_verification_issues",
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
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValidationError) as e:
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


def unrunnable_strategies(
    repo_root: Path, section: Section | None, rows: Sequence[Row]
) -> list[str]:
    """One message per distinct strategy the spec names EXPLICITLY — the
    section's `strategy:`, a per-row line, or a `verify:` of one of `rows` —
    that resolves and whose install program the repo cannot run (spec
    2026-10-12 §B, R5). Never consults the shape default (R4 drops that) and
    needs no plan; an unresolvable name is another check's to report."""
    sources: dict[str, list[tuple[str, str]]] = {}

    def add(name: str | None, kind: str, where: str) -> None:
        if name and name != RESERVED and (kind, where) not in sources.setdefault(name, []):
            sources[name].append((kind, where))

    if section is not None:
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


def section_grammar_issues(section: Section | None, rows: Sequence[Row]) -> list[str]:
    """Section lines that read differently across fr versions or name nothing
    (exit-gates review p1-r1, p1-r3): a `gate: <row>=` / `- <row>:` line naming
    a row no matrix row citing the spec has, and a section of `gate:` lines
    alone (it exists for this fr, not for a released one)."""
    if section is None:
        return []
    out: list[str] = []
    known = sorted(r.id for r in rows)
    named = [*section.row_gates, *(rid for rid in section.rows if rid not in section.row_gates)]
    for rid in named:
        if rid not in known:
            where = "`gate: {0}=`" if rid in section.row_gates else "`- {0}:`"
            out.append(
                f"the section's {where.format(rid)} line names row `{rid}`, which no matrix "
                "row citing the spec has (it would be silently ignored); rows citing the "
                f"spec: {', '.join(known) or 'none'}"
            )
    if (
        (section.gate is not None or section.row_gates)
        and section.strategy is None
        and not section.rows
    ):
        out.append(
            "the section has `gate:` lines but no `strategy:` line and no row line, so a "
            "released fr does not read it as a section at all — add `strategy: <name|none>` "
            "(or `- <row-id>: <strategy|none> — <reason>` lines) so every fr reads it the same way"
        )
    return out


def remap_key_problems(remap: Mapping[str, str], repo_root: Path) -> list[str]:
    """One message per `.fr/triage.yaml` `exit.gates` key that can never match:
    `none`, or a name that resolves to no strategy (exit-gates review p1-r7)."""
    out: list[str] = []
    for key in remap:
        if key == RESERVED:
            out.append(f"`exit.gates` key `{key}` is ignored: `none` has no gate to remap")
            continue
        try:
            resolve_strategy(key, repo_root)
        except StrategyError:
            out.append(f"`exit.gates` key `{key}` names no strategy, so it is ignored")
    return out


def row_verification_issues(
    repo_root: Path,
    section: Section | None,
    rows: Sequence[Row],
    shape_default: str | None,
) -> list[str]:
    """Every per-row verification problem of the rows citing a spec (spec
    2026-10-14 exit-gates R24, gh#1155), with or without a `## Verification`
    section — without one, only a row's own `verify:` counts:

    - the strategy does not resolve;
    - the repo cannot run its install;
    - an agent-driven pre-merge row has no `scenario:`;
    - a post-merge or `none` row has no reason.

    Both `fr plan self-review` (errors) and the brainstorm warning (advisory)
    call it; neither re-derives a check."""
    verification = SpecVerification(repo_root, section, shape_default)
    out = section_grammar_issues(section, rows)
    out += unrunnable_strategies(repo_root, section, rows)

    def reason_fix(row_id: str, name: str, why: str) -> str:
        if section is not None:
            return f"add `- {row_id}: {name} — <{why}>`"
        return (
            f"add a `## Verification` section with `- {row_id}: {name} — <{why}>` "
            "(every other row citing the spec then takes the section's `strategy:`, "
            "or the shape default when it has no `strategy:` line)"
        )

    for row in rows:
        name = verification.strategy(row)
        if name is None:
            continue
        if name == RESERVED:
            if not verification.reason(row):
                out.append(
                    f"row `{row.id}` is `none` with no reason — "
                    + reason_fix(row.id, "none", "what verifies it instead")
                )
            continue
        try:
            manifest = resolve_strategy(name, repo_root)
        except StrategyError as e:
            out.append(f"row `{row.id}`: {e}")
            continue
        if manifest.when == "post-merge" and not verification.reason(row):
            out.append(
                f"row `{row.id}` is post-merge (`{name}`) with no reason — "
                + reason_fix(row.id, name, "why no pre-merge strategy applies")
            )
        if manifest.when == "pre-merge" and manifest.driver == "agent" and not row.scenario:
            out.append(
                f"row `{row.id}` is walked by an agent before merge (`{name}`) but names "
                "no `scenario` — set one with `fr acceptance set-status "
                f"--id {row.id} ... --scenario <path>`"
            )
    return out
