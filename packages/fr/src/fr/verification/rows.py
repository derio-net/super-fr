"""A run's rows and their strategies — the one place a consumer gets a row's
effective strategy from (spec 2026-10-06-verification-strategies §B).

The PR body, visual evidence, self-review and the walk recorder all ask the
same question about a matrix row: given its spec's `## Verification` section
and the shape's default, what is its strategy, and is that post-merge? This
module binds the inputs once (`SpecVerification`) and answers through
`fr.verification.effective` — nobody compares a `verify` string themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr.verification.effective import effective_strategy, is_post_merge
from fr.verification.spec_section import Section, parse_section

if TYPE_CHECKING:
    from fr.acceptance.model import Row
    from fr.run.model import RunState

__all__ = [
    "SpecVerification",
    "run_verification",
    "shape_default",
    "spec_section_at",
    "spec_verification",
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


@dataclass(frozen=True)
class SpecVerification:
    """One spec's verification inputs, bound: its section (or `None`), the
    shape's default strategy, and the repo strategies resolve against."""

    repo_root: Path
    section: Section | None = None
    shape_default: str | None = None

    def strategy(self, row: Row) -> str | None:
        return effective_strategy(row.verify, row.id, self.section, self.shape_default)

    def is_post_merge(self, row: Row) -> bool:
        """Raises `StrategyError` when the row's strategy does not resolve."""
        return is_post_merge(self.strategy(row), self.repo_root)

    def reason(self, row: Row) -> str | None:
        """The section's one-line reason for `row`, when it gives one."""
        line = self.section.rows.get(row.id) if self.section is not None else None
        return line.reason if line is not None else None


def spec_verification(
    repo_root: Path, spec_rel: str | None, shape_default: str | None = None
) -> SpecVerification:
    """`SpecVerification` for the spec at `spec_rel` (`SectionError` when its
    section is malformed)."""
    return SpecVerification(repo_root, spec_section_at(repo_root, spec_rel), shape_default)


def shape_default(repo_root: Path, state: RunState) -> str | None:
    """The run's workflow shape's default strategy, or `None` when the shape
    does not resolve or declares none."""
    from fr.workflow.model import WorkflowError
    from fr.workflow.resolve import resolve_workflow

    try:
        return resolve_workflow(state.workflow.partition("@")[0], repo_root).verification
    except (WorkflowError, OSError):
        return None


def run_verification(repo_root: Path, state: RunState) -> tuple[str | None, SpecVerification]:
    """`(spec_rel, SpecVerification)` for a run: the spec it emitted and that
    spec's section bound to the shape's default (`SectionError` when the
    section is malformed). `spec_rel` is `None` when the run emitted no spec."""
    from fr.requirements import run_spec

    spec_rel = run_spec(state)
    return spec_rel, spec_verification(repo_root, spec_rel, shape_default(repo_root, state))
