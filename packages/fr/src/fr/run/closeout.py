"""The closeout brief `fr pickup --run` prints for a finished delivery run.

Spec `2026-09-25-fr-goal-closeout-defects-design.md` §3.D.1. Built ONLY from
the `RunState` handed to it and the artifacts it names (spec, plan, both
journals) — never from anything else the delivering session remembers,
because this is read by a brand-new session that inherits none of it.
"""

from __future__ import annotations

from pathlib import Path

from fr.journal.model import (
    JournalParseError,
    effective_finding_states,
    parse_journal,
    resolve_journal_read_path,
    spec_journal_slug,
)
from fr.run.model import RunState

__all__ = ["CloseoutNotReadyError", "closeout_brief"]

TEST_PLAN_MARKER = "## Test Plan"


class CloseoutNotReadyError(Exception):
    """Raised by `closeout_brief` when `state`'s `deliver` step is not `done`."""


def _emitted(state: RunState, name: str) -> str | None:
    """The value a step recorded under `name`, wherever the shape's steps put
    it — mirrors `run_cmd._emitted_plan`, generalised to any artifact name."""
    for record in state.steps.values():
        if record.emitted and name in record.emitted:
            return record.emitted[name]
    return None


def _out_of_scope_lines(repo_root: Path, scope: str, slug: str) -> list[str]:
    """One `fr journal resolve … --state deferred --tracked-by <#N>` line per
    finding of `scope`/`slug`'s journal whose EFFECTIVE state (the fold over
    every record naming it) is `out-of-scope` — the same rule `journal
    render` groups its own "Out-of-scope findings" section by."""
    path = resolve_journal_read_path(repo_root, scope, slug)  # type: ignore[arg-type]
    if not path.exists():
        return []
    try:
        entries = parse_journal(path.read_text())
    except JournalParseError:
        return []
    states = effective_finding_states(entries)
    return [
        f"  fr journal resolve --scope {scope} --slug {slug} --id {fid} "
        "--state deferred --tracked-by <#N>"
        for fid, st in states.items()
        if st == "out-of-scope"
    ]


def closeout_brief(repo_root: Path, state: RunState) -> str:
    """A self-contained closeout brief for a run whose `deliver` step is done.

    Raises `CloseoutNotReadyError` otherwise, naming the cursor the run is
    actually on — `fr pickup --run` maps that to exit 2.
    """
    deliver = state.steps.get("deliver")
    if deliver is None or deliver.state != "done":
        raise CloseoutNotReadyError(
            f"run {state.run!r} is not ready for closeout — its cursor is "
            f"{state.cursor!r}, not a done `deliver`"
        )

    pr = _emitted(state, "pr")
    spec_path = _emitted(state, "spec")
    plan_path = _emitted(state, "plan")

    lines = [f"branch: {state.branch}"]
    lines.append(f"PR: {pr}" if pr else "PR: (none recorded)")
    if spec_path:
        lines.append(f"spec: {spec_path}")
    if plan_path:
        lines.append(f"plan: {plan_path}")
    lines.append("")
    lines.append("Closeout, in order:")
    lines.append(f"  fr isolation verify-merge --branch {state.branch}")
    lines.append("  STOP here if that refuses — the branch is not actually merged yet.")

    if spec_path:
        spec_file = repo_root / spec_path
        try:
            has_test_plan = TEST_PLAN_MARKER in spec_file.read_text()
        except OSError:
            has_test_plan = False
        if has_test_plan:
            lines.append(f"  run the spec's Test Plan: {spec_path}")

    out_of_scope: list[str] = []
    if spec_path:
        out_of_scope += _out_of_scope_lines(
            repo_root, "spec", spec_journal_slug(Path(spec_path).stem)
        )
    if plan_path:
        out_of_scope += _out_of_scope_lines(repo_root, "plan", Path(plan_path).name)
    if out_of_scope:
        lines.append("  file an issue for each out-of-scope finding below, then:")
        lines.extend(out_of_scope)

    lines.append("  fr status")
    if plan_path:
        lines.append(f"  fr archive {plan_path}   # on a housekeeping branch")
    lines.append("  open the housekeeping PR")
    lines.append(f"  fr isolation down --branch {state.branch}")

    return "\n".join(lines)
