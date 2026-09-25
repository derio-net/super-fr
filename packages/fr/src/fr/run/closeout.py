"""The closeout brief `fr pickup --run` prints for a finished delivery run.

Spec `2026-09-25-fr-goal-closeout-defects-design.md` §3.D.1. Built ONLY from
the `RunState` handed to it and the artifacts it names (spec, plan, both
journals) — never from anything else the delivering session remembers,
because this is read by a brand-new session that inherits none of it.
"""

from __future__ import annotations

from pathlib import Path

from fr.git import GitUnavailableError, git_answer
from fr.journal.model import (
    JournalParseError,
    effective_finding_states,
    parse_journal,
    resolve_journal_read_path,
    spec_journal_slug,
)
from fr.run.model import RunState

__all__ = ["CloseoutNotReadyError", "closeout_brief", "primary_checkout"]

TEST_PLAN_MARKER = "## Test Plan"


class CloseoutNotReadyError(Exception):
    """Raised by `closeout_brief` when `state`'s `deliver` step is not `done`."""


def _first_worktree_list_entry(output: str) -> tuple[Path, bool] | None:
    """`(path, bare)` for the FIRST `worktree` entry of `git worktree list
    --porcelain` output — the main worktree, always listed first — or `None`
    when the output names no worktree at all."""
    path: Path | None = None
    bare = False
    for line in output.splitlines():
        if line.startswith("worktree "):
            if path is not None:
                break  # a second entry has started; the first is complete
            path = Path(line[len("worktree ") :])
        elif path is not None and line == "bare":
            bare = True
        elif path is not None and line == "":
            break
    return None if path is None else (path, bare)


def primary_checkout(repo_root: Path) -> Path:
    """The repo's PRIMARY working tree — the base clone — even when `repo_root`
    is a linked fr workspace. The closeout runs after merge, from the base clone;
    the feature worktree is what it reaps, so naming it would send a fresh session
    into a directory about to vanish (found dogfooding #610's own deliver).

    Resolved via `git worktree list --porcelain`'s first entry (pd-r1): the
    main worktree is always listed first. Falls back to `repo_root` when git
    cannot answer, this is not a git repo, or that first entry is `bare` (no
    checkout to name). For a primary whose `.git` was relocated with
    `--separate-git-dir`, git itself reports that entry's path as the
    relocated git-dir rather than the checkout (a real git limitation,
    verified live against git 2.53.0) — recovered here as the directory
    containing it, when that directory is itself a real checkout."""
    try:
        listed = git_answer(repo_root, "worktree", "list", "--porcelain")
    except GitUnavailableError:
        return repo_root
    if listed.returncode != 0:
        return repo_root
    entry = _first_worktree_list_entry(listed.stdout)
    if entry is None:
        return repo_root
    path, bare = entry
    if bare:
        return repo_root
    if (path / ".git").exists():
        return path
    parent = path.parent
    if (parent / ".git").exists():
        return parent
    return repo_root


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
    # p4-r3: name the checkout — the transient "start a NEW session in
    # <workspace>" line printed by the delivering session is gone by the time
    # a brand-new session reads this brief back, and the run file itself now
    # lives on the default branch (the feature workspace it was written in
    # may already be reaped).
    lines.append(
        f"Run this from {primary_checkout(repo_root)} — the base clone, on the default branch, "
        "after the PR above has merged (the run file lives there; the feature "
        "workspace this run happened in may already be reaped)."
    )
    lines.append("")
    lines.append("Closeout, in order:")
    lines.append(
        f"  fr isolation verify-merge --branch {state.branch}   "
        "# works from the repo root above even once the feature workspace is gone"
    )
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
        # p4-r2: exact commands, not a "# on a housekeeping branch" comment
        # that leaves it to the reader to invent one — a fresh session with
        # no memory of this run could otherwise `fr archive` right here, in
        # the just-merged feature workspace, and commit to a dead branch.
        # Branch naming matches this repo's own housekeeping PRs (`git log
        # --oneline origin/main | grep -i archive`): `chore/archive-<slug>`.
        plan_slug = Path(plan_path).name
        housekeeping_branch = f"chore/archive-{plan_slug}"
        lines.append(
            f"  fr isolation up --branch {housekeeping_branch}   "
            f"# from the base clone above — do NOT run `fr archive` inside "
            f"{state.branch}, that workspace is the just-merged feature branch"
        )
        lines.append(f"  fr archive {plan_path}   # inside the new {housekeeping_branch} workspace")
        lines.append(
            "  git add -A && git commit -m "
            f"'chore: archive {plan_slug}' && git push -u origin {housekeeping_branch}"
        )
    lines.append("  open the housekeeping PR (e.g. `gh pr create --fill`)")
    lines.append(f"  fr isolation down --branch {state.branch}")

    return "\n".join(lines)
