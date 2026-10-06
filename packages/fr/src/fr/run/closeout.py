"""The closeout brief `fr pickup --run` and `fr pickup --branch` print.

Spec `2026-09-25-fr-goal-closeout-defects-design.md` §3.D.1 built the run-mode
brief; `2026-09-28-closeout-always-design.md` §D split it in two:
`branch_closeout_brief` is the ONE builder (branch-mode brief, or run-mode's
core plus its `RunExtras`), and `closeout_brief` keeps the run-mode
done-`deliver` refusal and calls it. Built ONLY from `RunState`/`branch` and
the artifacts they name (spec, plan, both journals) — never from anything
else the delivering session remembers, because this is read by a brand-new
session that inherits none of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
from fr.services import ServicesError, TrackerRequiredError, require_tracker

__all__ = [
    "CloseoutNotReadyError",
    "RunExtras",
    "awaiting_live_lines",
    "branch_closeout_brief",
    "closeout_brief",
    "primary_checkout",
]

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
    """One `fr journal resolve … --state deferred --tracked-by '<#N>'` line per
    finding of `scope`/`slug`'s journal whose EFFECTIVE state (the fold over
    every record naming it) is `out-of-scope` — the same rule `journal
    render` groups its own "Out-of-scope findings" section by.

    Runnable as printed once `<#N>` is filled in (gh#621): `--note` is
    required by `resolve`, and the placeholder sits inside single quotes
    because a bare `#618` starts a shell comment and swallows the value."""
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
        "--state deferred --tracked-by '<#N>' --note 'Filed at closeout as <#N>.'"
        for fid, st in states.items()
        if st == "out-of-scope"
    ]


_NO_TRACKER = "no-tracker"


def services_invalid_text(exc: Exception) -> str:
    """The one wording for an unreadable services declaration — the brief and
    `fr archive`'s open-ends step both print it."""
    return f"the services declaration in .devcontainer/fr-profiles.yaml is invalid ({exc})"


def _tracker_note(repo_root: Path) -> str | None:
    """`_NO_TRACKER` under `tracking: {type: none}`; a warning line when the
    services declaration cannot be read; None otherwise.

    Strict resolution, deliberately: the brief is read-only, but a malformed
    `tracking:` block must not silently read as "has a tracker" and hand the
    reader issue-filing commands. It cannot refuse either — the brief has to
    stay usable after a merge — so it warns loudly and keeps the default lines."""
    try:
        require_tracker(repo_root)
    except TrackerRequiredError:
        return _NO_TRACKER
    except ServicesError as exc:
        return (
            f"{services_invalid_text(exc)}; the issue-filing lines below assume a "
            "tracker — fix it first"
        )
    return None


@dataclass(frozen=True)
class RunExtras:
    """Run-mode-only additions to the branch brief (spec
    2026-09-28-closeout-always §D): the PR/spec/plan lines, the spec's Test
    Plan line, the run's out-of-scope journal-resolve lines, and the run id
    that names the housekeeping branch when no plan was ever emitted."""

    run_id: str
    pr: str | None
    spec_path: str | None
    plan_path: str | None
    has_test_plan: bool
    out_of_scope: list[str]
    awaiting_live: list[str] = field(default_factory=list)


def _housekeeping_branch(branch: str, run_extras: RunExtras | None) -> str:
    """`chore/archive-<plan-slug>` when a plan was named (run mode);
    `chore/closeout-<run-id>` for a run with no plan; `chore/closeout-<branch
    -slug>` (`/` -> `-`) for a plain branch brief with no run at all — the
    naming §D's table leaves unchanged for run mode and introduces for
    branch mode."""
    if run_extras is not None:
        if run_extras.plan_path:
            return f"chore/archive-{Path(run_extras.plan_path).name}"
        return f"chore/closeout-{run_extras.run_id}"
    return f"chore/closeout-{branch.replace('/', '-')}"


def _commit_message(branch: str, plan_path: str | None) -> str:
    """`chore: archive <plan-slug>` with a plan; else `chore: close out <b>`
    — always printed now (§D's table), never the bare `git push` the no-plan
    run-mode case used to fall back to."""
    if plan_path:
        return f"chore: archive {Path(plan_path).name}"
    return f"chore: close out {branch}"


def branch_closeout_brief(
    repo_root: Path, branch: str, *, run_extras: RunExtras | None = None
) -> str:
    """The close-out brief for `branch` (spec 2026-09-28-closeout-always §D).

    `fr pickup --branch <b>` calls this directly with `run_extras=None`.
    `closeout_brief` calls it for a finished run, passing `run_extras` for
    the run-only lines (PR/spec/plan, the Test Plan line, out-of-scope
    findings) — everything else (verify-merge/STOP, `fr status`, the
    housekeeping block, `fr archive --branch <b>`, the commit/push line, the
    housekeeping PR, `fr isolation down`) is common to both modes and always
    printed, because the branch always has at least its own artifacts (or,
    in run mode, its run cursor) to consider.
    """
    lines = [f"branch: {branch}"]
    if run_extras is not None:
        lines.append(f"PR: {run_extras.pr}" if run_extras.pr else "PR: (none recorded)")
        if run_extras.spec_path:
            lines.append(f"spec: {run_extras.spec_path}")
        if run_extras.plan_path:
            lines.append(f"plan: {run_extras.plan_path}")
    lines.append("")
    if run_extras is not None:
        # p4-r3: name the checkout — the transient "start a NEW session in
        # <workspace>" line printed by the delivering session is gone by the
        # time a brand-new session reads this brief back, and the run file
        # itself now lives on the default branch (the feature workspace it
        # was written in may already be reaped).
        lines.append(
            f"Run this from {primary_checkout(repo_root)} — the base clone, on the default "
            "branch, after the PR above has merged (the run file lives there; the feature "
            "workspace this run happened in may already be reaped)."
        )
    else:
        lines.append(
            f"Run this from {primary_checkout(repo_root)} — the base clone, after {branch}'s "
            "PR has merged."
        )
    lines.append("")
    lines.append("Closeout, in order:")
    lines.append(
        f"  fr isolation verify-merge --branch {branch}   "
        "# works from the repo root above even once the feature workspace is gone"
    )
    lines.append("  STOP here if that refuses — the branch is not actually merged yet.")

    if run_extras is not None and run_extras.spec_path and run_extras.has_test_plan:
        lines.append(f"  run the spec's Test Plan: {run_extras.spec_path}")

    if run_extras is not None:
        lines.extend(run_extras.awaiting_live)

    plan_path = run_extras.plan_path if run_extras is not None else None
    out_of_scope = run_extras.out_of_scope if run_extras is not None else []
    if out_of_scope:
        tracker_note = _tracker_note(repo_root)
        if tracker_note == _NO_TRACKER:
            # R6: nowhere to file — the findings stay in the journal and PR body.
            out_of_scope = []
            lines.append(
                "  out-of-scope findings stay recorded in the journal and PR body; "
                "no tracker is configured"
            )
        elif tracker_note:
            # only the issue-filing lines below depend on the declaration
            lines.append(f"  WARNING: {tracker_note}")
    lines.append("  fr status")

    # p4-r2: exact commands, not a "# on a housekeeping branch" comment that
    # leaves it to the reader to invent one — a fresh session with no memory
    # of this run could otherwise `fr archive` right here, in the
    # just-merged feature workspace, and commit to a dead branch.
    housekeeping_branch = _housekeeping_branch(branch, run_extras)
    lines.append(
        f"  fr isolation up --branch {housekeeping_branch}   "
        f"# from the base clone above — do NOT run the steps below inside "
        f"{branch}, that workspace is the just-merged feature branch"
    )
    if out_of_scope:
        # gh#621: inside the housekeeping workspace, never on the default
        # branch — there fr writes the record but commits nothing (§3.C), so
        # it would miss the PR and the journal `fr archive` moves.
        lines.append(
            f"  file an issue for each out-of-scope finding below, then, inside the "
            f"new {housekeeping_branch} workspace (fr commits each record):"
        )
        lines.extend(out_of_scope)
    lines.append(
        f"  fr archive --branch {branch}   # inside the new {housekeeping_branch} workspace"
    )
    lines.append(
        "  git add -A && git commit -m "
        f"'{_commit_message(branch, plan_path)}' && git push -u origin {housekeeping_branch}"
    )
    from fr.hostclient import pr_command  # the forge's own CLI, never `gh` (gh#742)

    lines.append(f"  open the housekeeping PR (e.g. `{pr_command(repo_root, 'fill')}`)")
    lines.append(f"  fr isolation down --branch {branch}")
    # gh#825: the brief brought the housekeeping workspace up, so it takes it
    # down too — after that PR merges, since `down` refuses unlanded work.
    lines.append(
        f"  fr isolation down --branch {housekeeping_branch}   "
        "# once the housekeeping PR has merged"
    )

    return "\n".join(lines)


def awaiting_live_lines(repo_root: Path, state: RunState, pr: str | None) -> list[str]:
    """One label-add command per issue the run's PR `Refs` that a post-merge,
    not-walk-verified row cites (spec 2026-10-06-verification-strategies §F,
    R17): that issue stays open until the walk, so it carries `fr:awaiting-live`
    and triage keeps it out of the ranked backlog. Each repo's add commands follow
    one command creating the label there, which may not exist yet (p4-r4). The PR
    body is read through
    the forge adapter, as `deliver` does (gh#742). Nothing under `tracking:
    none`; an unreadable PR or matrix is said, never read as "nothing owed"."""
    from fr.acceptance.check import resolve_identity
    from fr.acceptance.model import AcceptanceError, load_matrix
    from fr.commands.acceptance_cmd import MATRIX_REL
    from fr.hostclient import FORGE_ERRORS, client_for, issue_command, label_command
    from fr.labels import FR_AWAITING_LIVE
    from fr.record.pr_body import holds_open_for_run, normalize_issue_ref, referenced_refs
    from fr.requirements import load_spec_matrix, run_spec
    from fr.services.resolve import resolve_tracking

    header = "  issues the PR Refs whose post-merge row still awaits its walk:"
    path = repo_root / MATRIX_REL
    if pr is None or not path.is_file() or resolve_tracking(repo_root, lenient=True).type == "none":
        return []
    try:
        matrix = load_matrix(path)
        if not any(row.issues for row in matrix.rows):
            return []
        identity = resolve_identity(matrix, repo_root)
        spec_rel = run_spec(state)
        spec_ref = load_spec_matrix(repo_root, spec_rel)[1] if spec_rel is not None else None
    except AcceptanceError as exc:
        return [f"  WARNING: awaiting-live labels not computed — the matrix is unreadable ({exc})"]
    holds = holds_open_for_run(repo_root, state, matrix, spec_ref)
    waiting = {
        normalize_issue_ref(issue, identity) or issue.lower()
        for row in matrix.rows
        if holds(row)
        for issue in row.issues
    }
    if not waiting:
        return []
    try:
        body = client_for(repo_root).pr_body(pr, cwd=repo_root)
    except FORGE_ERRORS as exc:
        return [
            f"  WARNING: could not read PR {pr} ({exc}), so the awaiting-live labels are not "
            "computed — add fr:awaiting-live by hand to each issue it Refs that a post-merge "
            "row still holds open"
        ]
    refd = sorted(
        {
            ref
            for written in referenced_refs(body)
            if (ref := normalize_issue_ref(written, identity))
        }
        & waiting
    )
    if not refd:
        return []
    # The label may not exist yet on the repo, and adding a missing label fails, so
    # each repo's add lines follow one create line (p4-r4).
    lines = [header]
    for repo in sorted({ref.split("#", 1)[0] for ref in refd}):
        lines.append("    " + label_command(repo_root, FR_AWAITING_LIVE, repo=repo))
        lines.extend(
            "    " + issue_command(repo_root, "issue-label", ref=ref, label=FR_AWAITING_LIVE.name)
            for ref in refd
            if ref.split("#", 1)[0] == repo
        )
    return lines


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

    has_test_plan = False
    if spec_path:
        spec_file = repo_root / spec_path
        try:
            has_test_plan = TEST_PLAN_MARKER in spec_file.read_text()
        except OSError:
            has_test_plan = False

    out_of_scope: list[str] = []
    if spec_path:
        out_of_scope += _out_of_scope_lines(
            repo_root, "spec", spec_journal_slug(Path(spec_path).stem)
        )
    if plan_path:
        out_of_scope += _out_of_scope_lines(repo_root, "plan", Path(plan_path).name)

    run_extras = RunExtras(
        run_id=state.run,
        pr=pr,
        spec_path=spec_path,
        plan_path=plan_path,
        has_test_plan=has_test_plan,
        out_of_scope=out_of_scope,
        awaiting_live=awaiting_live_lines(repo_root, state, pr),
    )
    return branch_closeout_brief(repo_root, state.branch, run_extras=run_extras)
