"""`fr archive` CLI — move finished plans (and their specs) to implemented/.

Gate per plan (fr.render.archive_gate): every dispatched phase
`_phase_complete`; every undispatched phase `plan_locally_complete` AND, for an
agentic one, complete on the default branch's remote-tracking ref too (#544 —
one `merge_evidence(fetch=True)` per invocation, not per plan). Manual phases
are judged locally, so the fr-goal close-out still archives. `--force` overrides — single
plan only; `--force --all` is refused because blanket-forcing is how the
2026-06-05 incident happens in reverse.

`--branch <b>` (2026-09-28-closeout-always §B) archives what a MERGED branch
added or modified, kind by kind; anything not ready is a `held:` line, exit 0.
It refuses (exit 2, nothing moved) with no default ref, an unresolvable
branch, or a branch whose changes are not all on the default ref.

Exit codes: 0 archived (or clean no-op for --all); 2 gate failure, dirty
tree, usage, legacy layout; 5 parse error.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import typer
from rich.console import Console
from rich.markup import escape

from fr.archive import (
    ArchiveError,
    GitStatusError,
    MergeEvidence,
    MoveLog,
    SpecSweepResult,
    archive_blockers,
    archive_journal,
    archive_plan_dir,
    archive_run_cursor,
    emitted_plan,
    merge_evidence,
    note_owed_journal,
    outcome_hold,
    paths_dirty,
    recording_moves,
    spec_archive_sweep,
    undoing_staged_moves,
    unticked_manual_phases,
)
from fr.artifacts.paths import KIND_DIRS, artifact_root, kind_dir, space_for
from fr.closeout import BranchArtifact, branch_artifacts, journal_scope_and_slug, owed_artifacts
from fr.commands.common import build_plan_report, require_migrated_layout, resolve_repo_root
from fr.isolation.local import (
    branch_changed_paths,
    branch_changes_present,
    recorded_start,
    resolve_branch_refs,
    subprocess_runner,
)
from fr.isolation.types import IsolationError
from fr.journal.model import JournalScope, archived_journal_path, journal_path
from fr.parser import PlanSchemaError
from fr.repair import plans_referencing_specs, repair_repo
from fr.run.model import archived_run_path, run_path
from fr.usage.file import archived_usage_path

if TYPE_CHECKING:
    from fr.ghclient import GhClient

console = Console()
err_console = Console(stderr=True)

IMPLEMENTED_REL = Path(KIND_DIRS["archive"])


def _make_gh_client() -> GhClient:
    """Factory hook — tests monkeypatch this (same seam as apply_cmd)."""
    from fr.hostclient import client_for

    return client_for(Path.cwd())


@dataclass(frozen=True)
class _Preview:
    """A `--dry-run` in progress (R10, R11): *wrap* turns a forge client into the preview
    forge that records into one ledger; *outside* is quiet or stealth, where the run acts
    on the real checkout, so no follow-up may write anything at all."""

    wrap: Callable[[Any], Any]
    outside: bool


_PREVIEW: _Preview | None = None
"""Set only while `_dry_run` runs the command."""

STAGED_NOTE = "\nmoves staged via git mv — review, commit, and PR them."


def _staged_note() -> None:
    """The real run's closing line; a dry run staged nothing the operator could commit."""
    if _PREVIEW is None:
        typer.echo(STAGED_NOTE)


def _report_sweep(repo_root: Path, sweep: SpecSweepResult) -> bool:
    """Print a sweep result's moves and notes. Returns whether anything moved.

    Repair is a separate concern (#710) — see `_repair_in_passing`, called
    once by each caller of this function.
    """
    for m in sweep.moves:
        typer.echo(f"  archived spec: {m.src} -> {m.dst}")
    for n in sweep.notes:
        typer.echo(f"  note: {n}")
    return bool(sweep.moves)


def _repair_in_passing(repo_root: Path, only_plans: frozenset[str] | None) -> None:
    """Repair refs in passing — the one place `fr archive` calls `repair_repo`.

    Shared by the post-move sweep and `--sweep-only`: the move and the ref
    normalization land in the same operator commit (2026-06-06
    spec-path-repair), and it runs exactly once per invocation (#710) so a
    warning never reaches the operator twice.
    """
    repair = repair_repo(repo_root, write=True, only_plans=only_plans)
    for r in repair.rewrites:
        typer.echo(f"  repaired: {r.file.name} · {r.field}: {r.old} → {r.new}")
    for w in repair.warnings:
        err_console.print(f"[yellow]warning:[/yellow] {w}")


def _branch_refs_or_exit(repo_root: Path, branch: str, remote: str) -> list[str]:
    """Every ref of `branch` that resolves, fetched the way verify-merge does
    (§B.2) — or exit 2 when neither `<remote>/<b>` nor the local `<b>` does,
    or when the remote branch's state is unknown.

    Unknown is verify-merge's `branch_fetched=False`: the fetch failed and
    `ls-remote` did not confirm the branch was deleted. The refs this clone
    holds may then be stale — a post-merge push from another clone would be
    invisible — so the mutating step refuses exactly where verify-merge would
    not verify (review p2 #1)."""
    refs, branch_fetched = resolve_branch_refs(subprocess_runner, repo_root, branch, remote)
    if not refs:
        err_console.print(
            f"branch {branch} resolves neither locally nor as {remote}/{branch} — nothing to diff",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if not branch_fetched:
        err_console.print(
            f"refusing to archive — could not fetch {remote}/{branch}, and {remote} did not "
            f"confirm the branch was deleted, so its remote state is unknown; check it with "
            f"`fr isolation verify-merge --branch {branch}`",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    return refs


@contextmanager
def _refuse_on_isolation_error() -> Iterator[None]:
    """A git diff the branch path cannot compute (no merge-base, a failed
    rev-list) is a refusal, exit 2 — never a traceback, never a move."""
    try:
        yield
    except IsolationError as e:
        err_console.print(f"refusing to archive — {escape(str(e))}", soft_wrap=True)
        raise typer.Exit(2) from e


def _require_landed(repo_root: Path, branch: str, refs: list[str], base_ref: str) -> None:
    """The mutating step's own guard (§B.3): every resolved ref's changes must
    be present on `base_ref`, or exit 2 naming the missing paths."""
    missing: list[str] = []
    start = recorded_start(repo_root, branch)
    for ref in refs:
        with _refuse_on_isolation_error():
            verdict = branch_changes_present(subprocess_runner, repo_root, ref, base_ref, start)
        missing.extend(p for p in verdict.missing if p not in missing)
    if missing:
        err_console.print(
            f"refusing to archive — {branch} has changes not on {base_ref}:", soft_wrap=True
        )
        for path in missing:
            err_console.print(f"  missing: {path}", soft_wrap=True)
        err_console.print(
            f"check it with `fr isolation verify-merge --branch {branch}`", soft_wrap=True
        )
        raise typer.Exit(2)


def _archive_branch(repo_root: Path, branch: str, *, no_spec_sweep: bool) -> None:
    """`fr archive --branch <b>` (2026-09-28-closeout-always §B)."""
    evidence = merge_evidence(repo_root, fetch=True)
    if evidence.ref is None:
        err_console.print(
            f"refusing to archive — no default ref: {evidence.ref_error}", soft_wrap=True
        )
        raise typer.Exit(2)
    base_ref = evidence.ref.ref
    remote = base_ref.split("/", 1)[0]
    refs = _branch_refs_or_exit(repo_root, branch, remote)
    _require_landed(repo_root, branch, refs, base_ref)
    _note_fetch_error(evidence)

    with _refuse_on_isolation_error():
        changed = sorted(
            {
                p
                for ref in refs
                for p in branch_changed_paths(
                    subprocess_runner, repo_root, ref, base_ref, recorded_start(repo_root, branch)
                )
            }
        )
    artifacts = branch_artifacts(repo_root, changed)
    if not artifacts:
        typer.echo(f"nothing to archive for {branch}")
        return

    gh = _make_gh_client()
    moved_plans: list[str] = []
    for a in _of_kind(artifacts, "plan"):
        reason = _archive_branch_plan(repo_root, a.path, gh, evidence)
        if reason is None:
            moved_plans.append(a.path.name)
            _echo_archived(a.path, IMPLEMENTED_REL / "plans" / a.path.name)
        else:
            _echo_held(a.path, reason)

    spec_dsts = _archive_branch_specs(
        repo_root,
        _of_kind(artifacts, "spec"),
        gh,
        no_spec_sweep=no_spec_sweep,
        run_sweep=bool(moved_plans),
    )

    moved_followers = False
    for a in artifacts:
        if a.kind in ("plan", "spec"):
            continue
        outcome = _archive_follower(repo_root, a)
        if isinstance(outcome, Path):
            moved_followers = True
            _echo_archived(a.path, outcome)
        else:
            _echo_held(a.path, outcome)

    if moved_plans or spec_dsts or moved_followers:
        only_plans = frozenset(moved_plans) | plans_referencing_specs(repo_root, spec_dsts)
        _repair_in_passing(repo_root, only_plans)
        _staged_note()


def _record_merged(repo_root: Path, branch: str, placement: str, *, preview: bool = False) -> None:
    """`fr archive --branch <b>` under quiet and stealth (R25): append one `merged: <sha>`
    record to the feature's `merged.yaml`, in ONE commit on the placement's branch, pushed
    (quiet: a plain push of `fr`; stealth: compare-and-swap to the tracking ref), and move
    nothing. The sha is the default ref's commit that merged the branch (R17's clause,
    `fr.placement.merged`, which also reads the forge for a squash or rebase merge): a
    branch that is not merged is refused, saying why, and a record that already agrees is
    not written twice (an unpushed one is pushed). A deleted branch is fine: its merge is
    judged by the heads fr recorded for it (review p5-r3).

    *preview* (`--dry-run`, R10/R11) resolves the merge by reads alone — no placement worktree is
    created — prints the record it would append and the push it would make, and returns before
    anything is appended, committed or pushed."""
    from fr.artifacts.paths import FEATURES_DIR, STEALTH, checked_feature_id
    from fr.placement import merged as merged_status
    from fr.placement.quiet import owner_of
    from fr.settings import SettingsError

    evidence = merge_evidence(repo_root, fetch=True)
    if evidence.ref is None:
        err_console.print(
            f"refusing to archive — no default ref: {evidence.ref_error}", soft_wrap=True
        )
        raise typer.Exit(2)
    # Fetches the branch's remote ref; a branch gone everywhere is no refusal here.
    resolve_branch_refs(subprocess_runner, repo_root, branch, evidence.ref.ref.split("/", 1)[0])
    _note_fetch_error(evidence)
    space = space_for(repo_root, create=not preview)
    try:
        fid = checked_feature_id(branch)
    except SettingsError as e:
        err_console.print(f"refusing to archive: {e}", soft_wrap=True, markup=False)
        raise typer.Exit(2) from e
    froot = space.root / FEATURES_DIR / fid
    if not froot.is_dir():
        typer.echo(f"nothing to archive for {branch}: it has no feature path under {placement}")
        return
    owner = owner_of(space.root, fid)
    if owner is not None and owner != branch:
        err_console.print(
            f"refusing to archive — the feature path {FEATURES_DIR}/{fid} belongs to "
            f"{owner!r}, not {branch!r}",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    forge, why_not = merged_status.forge_for(repo_root)
    if _PREVIEW is not None and isinstance(forge, merged_status.ClientMergedPrs):
        forge = forge.with_client(_PREVIEW.wrap)  # R11: every forge call is previewed
    view = merged_status.merged_features(space, repo_root, forge=forge)
    for notice in view.notices:
        err_console.print(f"note: {escape(notice)}", soft_wrap=True)
    feature = view.get(fid)
    if feature is None:
        reason = view.no_merge(branch)
        if forge is None:
            reason = reason.replace("the forge was not read", f"the forge was {why_not}")
        err_console.print(
            f"refusing to archive — {escape(reason)}. Nothing was written", soft_wrap=True
        )
        raise typer.Exit(2)
    short = feature.sha[:12]
    record = merged_status.merged_file(froot)
    if feature.cached:
        if preview:
            unpushed = placement != STEALTH and _unpushed(space.root, record)
            typer.echo(
                f"would push the record: {branch} merged at {short} is committed on the local "
                f"`fr` branch but not pushed"
                if unpushed
                else f"already recorded: {branch} merged at {short}; nothing to write"
            )
            return
        if placement != STEALTH and _unpushed(space.root, record):
            _push_fr(repo_root, space.root, record)
            typer.echo(f"already recorded: {branch} merged at {short}; pushed the record")
            return
        typer.echo(f"already recorded: {branch} merged at {short}; nothing to write")
        return
    if preview:
        target = (
            "the stealth tracking ref (compare-and-swap)" if placement == STEALTH else "`origin fr`"
        )
        via_pr = f" (PR #{feature.pr})" if feature.pr else ""
        typer.echo(
            f"would record: {branch} merged at {short}{via_pr} "
            f"in {FEATURES_DIR}/{fid}/{merged_status.MERGED_FILE}; nothing moved (R25)\n"
            f"would commit it in one commit and push it to {target}"
        )
        return
    written = [merged_status.append_record(froot, feature.sha, feature.heads, pr=feature.pr)]
    # The verified heads are owned evidence from here on: the merge survives the branch.
    for head in feature.heads:
        added = merged_status.record_head(froot, head)
        if added is not None and added not in written:
            written.append(added)
    via = f" (PR #{feature.pr}, by the forge)" if feature.how == "forge" else ""
    _commit_merged_record(
        repo_root, space, placement, written, f"chore(fr): record {branch} merged at {short}"
    )
    typer.echo(
        f"recorded: {branch} merged at {short}{via} "
        f"({FEATURES_DIR}/{fid}/{merged_status.MERGED_FILE}); nothing moved (R25)"
    )


def _refuse_cannot_tell(repo_root: Path, placement: str) -> None:
    """R10 (review p3-r5): a preview that cannot see what the real run would act on
    refuses by name, exit 2, rather than print "nothing to archive" and exit 0. Checked
    before anything resolves the placement's space, which would create or sync it."""
    from fr.placement.preview import cannot_tell

    why = cannot_tell(repo_root)
    if why is None:
        return
    err_console.print(
        f"dry run cannot tell what `fr archive` would do under {placement}: {why}. "
        "Nothing was written",
        soft_wrap=True,
        markup=False,
    )
    raise typer.Exit(2)


def _unpushed(fr_root: Path, path: Path) -> bool:
    """The local `fr` holds a commit of *path* that `origin/fr` does not (review p5-r7)."""
    from fr.artifacts.paths import SWITCH_REF
    from fr.git import GitUnavailableError, git_answer

    rel = path.resolve().relative_to(fr_root.resolve()).as_posix()
    try:
        done = git_answer(fr_root, "log", "--format=%H", f"{SWITCH_REF}..HEAD", "--", rel)
    except GitUnavailableError:
        return True
    return done.returncode != 0 or bool(done.stdout.strip())


def _push_fr(repo_root: Path, fr_root: Path, record: Path) -> None:
    """Push the local `fr` (under its lock), or exit 2 naming the unpushed record."""
    from fr.git_policy.push import PushRefusedError, atomic_push
    from fr.placement.quiet import QUIET_BRANCH

    try:
        atomic_push(repo_root, fr_root, "origin", QUIET_BRANCH, code=False)
    except PushRefusedError as e:
        err_console.print(
            f"refusing to archive — the record {record} is committed on the local "
            f"`{QUIET_BRANCH}` branch but not pushed, and its push was refused: "
            f"{escape(str(e))}; run `fr push` to retry",
            soft_wrap=True,
        )
        raise typer.Exit(2) from e


def _commit_merged_record(
    repo_root: Path, space: Any, placement: str, written: list[Path], message: str
) -> None:
    """Commit the one record and push it; on any failure put the file back and exit 2
    (a push quiet's `fr` branch refused leaves the commit for `fr push` to retry)."""
    from fr.artifacts.commit import CommitOutcome, StealthPushError, commit_paths
    from fr.artifacts.paths import STEALTH
    from fr.git_policy.push import PushRefusedError, atomic_push
    from fr.placement import stealth
    from fr.placement.quiet import QUIET_BRANCH, fr_worktree_lock, fr_worktree_problem
    from fr.settings import SettingsError

    def refuse(why: str, wt: Path) -> None:
        stealth.restore_files(wt, written)
        err_console.print(f"refusing to archive — {escape(why)}", soft_wrap=True)
        raise typer.Exit(2)

    if placement == STEALTH:
        found = stealth.marker_tracking(repo_root)
        assert found is not None  # space_for resolved a stealth space
        wt = stealth.tracking_root(space)

        def tracking(w: Path, todo: Any, msg: str) -> CommitOutcome:
            return commit_paths(w, todo, msg, tracking_branch=True)

        try:
            outcome = stealth.commit_and_push(
                found[0],
                wt,
                written,
                message,
                tracking,
                target_remote=stealth.origin_url(repo_root),
                target_root=repo_root,
            )
        except StealthPushError as e:  # the worktree is already restored
            err_console.print(f"refusing to archive — {escape(str(e))}", soft_wrap=True)
            raise typer.Exit(2) from e
        except SettingsError as e:
            refuse(str(e), wt)
        else:
            if not outcome.committed:
                refuse(outcome.reason, wt)
        return
    fr_root = space.root
    try:
        with fr_worktree_lock(fr_root):
            problem = fr_worktree_problem(fr_root, dirty=False)
            if problem is not None:
                refuse(problem, fr_root)
            outcome = commit_paths(fr_root, written, message)
    except SettingsError as e:
        refuse(str(e), fr_root)
    if not outcome.committed:
        refuse(outcome.reason, fr_root)
    try:
        atomic_push(repo_root, fr_root, "origin", QUIET_BRANCH, code=False)
    except PushRefusedError as e:
        err_console.print(
            f"recorded on the local `{QUIET_BRANCH}` branch, but its push was refused: "
            f"{escape(str(e))}; run `fr push` to retry",
            soft_wrap=True,
        )
        raise typer.Exit(2) from e


def _note_fetch_error(evidence: MergeEvidence) -> None:
    if evidence.fetch_error:
        err_console.print(
            f"note: {evidence.fetch_error} — judging merge state from the local "
            f"{evidence.ref.ref if evidence.ref else 'remote-tracking refs'}",
            soft_wrap=True,
        )


def _of_kind(artifacts: list[BranchArtifact], kind: str) -> list[BranchArtifact]:
    return [a for a in artifacts if a.kind == kind]


def _echo_archived(src: Path, dst: Path) -> None:
    typer.echo(f"  archived: {src} -> {dst}")


def _echo_held(path: Path, reason: str) -> None:
    typer.echo(f"  held: {path} — {reason}")


def _archive_branch_plan(
    repo_root: Path, plan_rel: Path, gh: GhClient, evidence: MergeEvidence
) -> str | None:
    """The single-plan path (gate, dirty check, move — which carries the
    plan's run, usage and plan journal), with every refusal turned into a
    held reason. `None` means the plan moved."""
    target = repo_root / plan_rel
    try:
        report = build_plan_report(target, gh)
    except PlanSchemaError as e:
        return f"parse error: {e}"
    blockers = archive_blockers(report.plan, report.observed, evidence)
    if blockers:
        _write_manual_owed(repo_root, report.plan, blockers)
        return "; ".join(blockers)
    hold = outcome_hold(repo_root, report.plan, plan_rel)
    if hold:
        return "\n".join(hold)
    try:
        dirty = paths_dirty(repo_root, target)
    except GitStatusError as e:
        return str(e)
    if dirty:
        return "worktree dirty at the plan path — commit or stash first"
    try:
        archive_plan_dir(repo_root, target)
    except ArchiveError as e:
        return str(e)
    return None


def _archive_branch_specs(
    repo_root: Path,
    specs: list[BranchArtifact],
    gh: GhClient,
    *,
    no_spec_sweep: bool,
    run_sweep: bool,
) -> list[Path]:
    """Run `spec_archive_sweep` once (§B.4 spec), print its moves, and hold
    each branch spec it left live. Returns the moved specs' destinations."""
    if no_spec_sweep:
        for a in specs:
            _echo_held(a.path, "spec sweep skipped")
        return []
    if not (specs or run_sweep):
        return []
    sweep = spec_archive_sweep(repo_root, gh)
    for m in sweep.moves:
        _echo_archived(m.src, m.dst)
    for a in specs:
        if (repo_root / a.path).exists():
            prefix = f"{a.path.name}: "
            note = next(
                (n[len(prefix) :] for n in sweep.notes if n.startswith(prefix)),
                "not every Implementation Plans row is archived yet",
            )
            _echo_held(a.path, note)
    return [repo_root / m.dst for m in sweep.moves]


def _archive_follower(repo_root: Path, a: BranchArtifact) -> Path | str:
    """A journal/run/usage artifact's repo-relative destination when it is
    archived — by its owner's move earlier in this run, or here — else the
    reason it is held.

    A follower with uncommitted edits is held, as a dirty plan path is:
    `git mv` would stage the rename with the edit folded in (review p2 #4)."""
    live = repo_root / a.path
    try:
        dirty = live.exists() and paths_dirty(repo_root, live)
    except GitStatusError as e:
        return str(e)
    if dirty:
        return f"worktree dirty at {a.path} — commit or stash first"
    if a.kind == "journal":
        return _archive_branch_journal(repo_root, a)
    run_id = a.path.stem
    dst = (
        archived_run_path(repo_root, run_id)
        if a.kind == "run"
        else archived_usage_path(repo_root, run_id)
    )
    if not (repo_root / a.path).exists():  # its plan's move carried it
        return dst.relative_to(repo_root)
    cursor = run_path(repo_root, run_id)
    if not cursor.exists():
        cursor = archived_run_path(repo_root, run_id)
    plan = emitted_plan(cursor)
    if not plan:
        return "follows no recorded plan"
    if (repo_root / plan).exists():
        return f"follows plan {plan}, still live"
    if not (artifact_root(repo_root) / IMPLEMENTED_REL / "plans" / Path(plan).name).is_dir():
        return f"follows plan {plan}, which is neither live nor archived"
    # The orphan rule (§C): its plan is already archived, so it follows.
    try:
        archive_run_cursor(repo_root, run_id)
    except ArchiveError as e:
        return str(e)
    if (repo_root / a.path).exists():
        return f"plan {plan} is archived, but {dst.relative_to(repo_root)} already exists"
    return dst.relative_to(repo_root)


def _archive_branch_journal(repo_root: Path, a: BranchArtifact) -> Path | str:
    """§B.4: a debug journal on the default ref is done (d2/d3); a plan or
    spec journal follows its owner — moved when the owner moved in this run
    (its move carried the journal) or is already archived, else held."""
    scope = cast("JournalScope", a.owner)
    slug = a.path.stem
    dst = archived_journal_path(repo_root, scope, slug)
    if not (repo_root / a.path).exists():  # its owner's move carried it
        return dst.relative_to(repo_root)
    if scope == "plan":
        owner_archived = (artifact_root(repo_root) / IMPLEMENTED_REL / "plans" / slug).is_dir()
        owner = f"plan {slug}"
    elif scope == "spec":
        owner_archived = any(
            (artifact_root(repo_root) / IMPLEMENTED_REL / "specs" / name).is_file()
            for name in (f"{slug}-design.md", f"{slug}.md")
        )
        owner = f"spec {slug}"
    else:  # debug: on the default ref (§B.3 proved it) means done (d2/d3)
        owner_archived, owner = True, ""
    if not owner_archived:
        return f"follows {owner}, still live or missing"
    try:
        archive_journal(repo_root, scope, slug)
    except ArchiveError as e:  # a held reason, as for a plan (review p2 #3)
        return str(e)
    if journal_path(repo_root, scope, slug).exists():
        return f"destination {dst.relative_to(repo_root)} already exists"
    return dst.relative_to(repo_root)


@dataclass(frozen=True)
class _ArchiveOpts:
    """What the follow-ups need from the invocation."""

    branch: str | None = None
    issues: str | None = None
    no_issues: bool = False
    dry_run: bool = False


def _after_moves(repo_root: Path, log: MoveLog, opts: _ArchiveOpts) -> None:
    """The follow-ups an archive that staged a move owes (spec 2026-10-06 §0).

    The usage refresh is a no-op on an empty log (acceptance rows cite fr artifacts
    logically, so an archive rewrites no row: spec 2026-11-04 R18); the open
    ends step also runs for an explicit `--issues <qids>` with nothing moved
    (R9). Each step runs in its own try: one failure never stops the next, and
    none of them changes the exit code the body chose."""
    steps: list[tuple[str, Callable[[Path, MoveLog, _ArchiveOpts], None]]] = []
    if log:
        steps.append(("usage refresh", _refresh_usage))
    if log or opts.issues is not None:
        steps.append(("open ends", _open_ends_step))
    if log or log.owed_journals:
        steps.append(("owed actions", _owed_step))
    for name, step in steps:
        try:
            step(repo_root, log, opts)
        except Exception as e:  # noqa: BLE001 — a follow-up never fails an archive
            err_console.print(f"note: {name} skipped — {type(e).__name__}: {escape(str(e))}")


USAGE_REFRESH_MAX_AGE_DAYS = 30
"""Claude Code's default transcript retention: past it a session cannot be priced."""


def _edited_in_worktree(repo_root: Path, path: Path) -> bool:
    """True iff `path` differs between the worktree and the index. Staged-only
    changes (a usage file this very invocation just `git mv`d) are not edits."""
    import subprocess

    rc = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--quiet", "--", str(path)],
        capture_output=True,
        check=False,
    ).returncode
    return rc == 1


def _refresh_usage(repo_root: Path, log: MoveLog, opts: _ArchiveOpts) -> None:
    """§A: price earlier closeouts' sessions and stage each refreshed file."""
    import os
    import subprocess

    from fr.usage.backfill import refresh_archived

    if _PREVIEW is not None and _PREVIEW.outside:
        return  # R11: under quiet or stealth a dry run writes nothing anywhere
    report = refresh_archived(
        repo_root,
        os.environ,
        skip=lambda p: _edited_in_worktree(repo_root, p),
        max_age_days=USAGE_REFRESH_MAX_AGE_DAYS,
    )
    for path in report.refreshed:
        subprocess.run(
            ["git", "-C", str(repo_root), "add", "--", str(path.relative_to(repo_root))],
            check=True,
            capture_output=True,
        )
        typer.echo(f"  priced: {path.relative_to(repo_root)}")
    for run_id in report.dirty:
        err_console.print(f"note: usage for {run_id} has uncommitted changes — not refreshed")
    for run_id, why in report.failed:
        err_console.print(f"note: usage for {run_id} not refreshed — {escape(why)}")


def _open_ends_step(repo_root: Path, log: MoveLog, opts: _ArchiveOpts) -> None:
    """§C: list the open ends the moved journals leave behind, and — when the
    flags or the operator say so — file one issue each and defer the finding
    to it. Never raises on a forge error; never changes the exit code."""
    import subprocess

    from fr import archive_followups as af
    from fr.artifacts import trigger
    from fr.run.closeout import services_invalid_text
    from fr.services import ServicesError
    from fr.settings import ForgeQuietError, require_forge

    listed = af.open_ends(repo_root, af.journals_from_log(log.moves))
    if listed:
        typer.echo("  open ends:")
        for end in listed:
            typer.echo(f"    - {end.qid}: {end.title}")
    elif opts.issues is None:
        return
    try:
        require_forge(repo_root, "issues", "labels")  # a filed issue carries its labels
    except ForgeQuietError as exc:
        typer.echo(f"  no tracker configured — left in the journal ({exc})")
        return
    except ServicesError as exc:
        err_console.print(
            f"[yellow]warning:[/yellow] {escape(services_invalid_text(exc))}; "
            "open ends left in the journal"
        )
        return
    if opts.no_issues:
        return
    selection = opts.issues
    if selection is None:
        if opts.dry_run or not listed or not trigger.is_interactive():
            return  # R11: a dry run lists the ends and never prompts
        answer = input("open issues for these? [y/N/select] ").strip().lower()
        if answer in ("y", "yes"):
            selection = "all"
        elif answer == "select":
            selection = input("ids to file (comma list): ").strip()
        else:
            return
    chosen, refused = af.select(listed, selection, repo_root)
    if refused:
        err_console.print(
            f"[yellow]warning:[/yellow] --issues refused, nothing filed — "
            f"{escape('; '.join(refused))}"
        )
        return
    if not chosen:
        return
    for filed in af.file_open_ends(repo_root, chosen, _make_gh_client(), _repo_slug(repo_root)):
        qid = filed.end.qid
        if filed.url is None:
            err_console.print(
                f"[yellow]warning:[/yellow] could not file {qid} — {escape(filed.error or '')}"
            )
            continue
        if _PREVIEW is not None and _PREVIEW.outside:
            # R11: the journal is outside the checkout (quiet, stealth), so a dry run
            # says where the finding would be deferred and writes nothing.
            typer.echo(f"  {'reused' if filed.reused else 'filed'}: {qid} -> {filed.url}")
            typer.echo(f"  would defer {qid} to {filed.url} in its journal")
            continue
        try:
            path = af.write_back(filed)
            subprocess.run(
                ["git", "-C", str(repo_root), "add", "--", str(path)],
                check=True,
                capture_output=True,
            )
        except Exception as e:  # noqa: BLE001 — the issue exists; say the journal is behind
            err_console.print(
                f"[yellow]warning:[/yellow] filed {qid} as {filed.url} but could not defer "
                f"the finding — {escape(str(e))}"
            )
            continue
        typer.echo(f"  {'reused' if filed.reused else 'filed'}: {qid} -> {filed.url}")


def _write_manual_owed(repo_root: Path, plan: Any, blockers: tuple[str, ...]) -> None:
    """R22: a plan held only by unticked `[manual]` phases owes them — one
    `owed` entry each in its plan journal (staged), filed by `_owed_step`."""
    import subprocess

    from fr import archive_followups as af

    phases = unticked_manual_phases(plan, blockers)
    if not phases:
        return
    name = plan.dir.name
    from fr.git import head_on_default_branch

    if head_on_default_branch(repo_root):  # R8: no commit lands here, so nothing is written
        for line in af.manual_owed_preview(repo_root, name, phases):
            typer.echo(f"  would record owed: {line}")
        return
    try:
        path = af.write_manual_owed(repo_root, name, phases)
        if path is not None:
            subprocess.run(
                ["git", "-C", str(repo_root), "add", "--", str(path)],
                check=True,
                capture_output=True,
            )
    except Exception as e:  # noqa: BLE001 — the hold stands; say the journal is behind
        err_console.print(
            f"[yellow]warning:[/yellow] could not record owed manual phase(s) of {name} — "
            f"{escape(str(e))}"
        )
        return
    note_owed_journal("plan", name)


def _owed_step(repo_root: Path, log: MoveLog, opts: _ArchiveOpts) -> None:
    """R21: file every open `owed` entry of the moved (or held-and-owing)
    journals as one `fr:owed` issue — whatever `--issues`/`--no-issues` say —
    and record where it went. Nothing is filed under `forge.issues: off` or `tracking: none`."""
    import subprocess

    from fr import archive_followups as af
    from fr.run.closeout import services_invalid_text
    from fr.services import ServicesError
    from fr.settings import ForgeQuietError, require_forge

    journals = af.journals_from_log(log.moves)
    journals += [j for j in log.owed_journals if j not in journals]
    ends = af.owed_ends(repo_root, journals)
    if not ends:
        return
    typer.echo("  owed actions:")
    for end in ends:
        typer.echo(f"    - {end.key}: {end.title}")
    try:
        require_forge(repo_root, "issues", "labels")  # a filed issue carries its labels
    except ForgeQuietError as exc:
        typer.echo(f"  no tracker configured — owed actions stay in the journal ({exc})")
        return
    except ServicesError as exc:
        err_console.print(
            f"[yellow]warning:[/yellow] {escape(services_invalid_text(exc))}; "
            "owed actions left in the journal"
        )
        return
    repo, why = af.owed_identity(repo_root)
    if repo is None:
        err_console.print(
            f"[yellow]warning:[/yellow] owed actions not filed — {escape(why)}; they stay "
            "in the journal (file each as an fr:owed issue carrying its "
            "`<!-- fr-owed:<key> -->` marker yourself)",
            soft_wrap=True,
        )
        return
    said_unsupported = False
    for filed in af.file_owed_ends(repo_root, ends, _make_gh_client(), repo):
        if filed.unsupported:  # R13: like `ForgeQuietError` above, the entry stays put
            if not said_unsupported:
                typer.echo(f"  {af.UNSUPPORTED_LISTING}")
            said_unsupported = True
            continue
        if filed.ref is None:
            err_console.print(
                f"[yellow]warning:[/yellow] could not file owed {filed.end.key} — "
                f"{escape(filed.error or '')}",
                soft_wrap=True,
            )
            continue
        if _PREVIEW is not None and _PREVIEW.outside:  # R11: nothing is written
            typer.echo(f"  {'reused' if filed.reused else 'filed'}: {filed.end.key} -> {filed.ref}")
            typer.echo(f"  would record {filed.end.key} as {filed.ref} in its journal")
            continue
        try:
            path = af.write_owed_back(filed)
            subprocess.run(
                ["git", "-C", str(repo_root), "add", "--", str(path)],
                check=True,
                capture_output=True,
            )
        except Exception as e:  # noqa: BLE001 — the issue exists; say the journal is behind
            err_console.print(
                f"[yellow]warning:[/yellow] filed {filed.end.key} as {filed.ref} but could "
                f"not record it — {escape(str(e))}"
            )
            continue
        typer.echo(f"  {'reused' if filed.reused else 'filed'}: {filed.end.key} -> {filed.ref}")


def _repo_slug(repo_root: Path) -> str:
    """`org/repo` — the acceptance fragments' `repo:`, else the origin remote."""
    from fr.acceptance.check import resolve_identity
    from fr.acceptance.fold import load_effective

    return "/".join(resolve_identity(load_effective(repo_root), repo_root))


def _in_checkout(repo_root: Path, path: Path) -> Path:
    """*path* relative to the real checkout, when it names something in it: run from the
    scratch's root, it names the same thing there, and the output prints no scratch path."""
    try:
        return path.resolve().relative_to(repo_root)
    except ValueError:
        return path


class _Rewriting:
    """A text stream that writes through to *inner* with every scratch path replaced by
    the real checkout's (review p3-r8): the operator reads paths they can open."""

    def __init__(self, inner: Any, pairs: list[tuple[str, str]]) -> None:
        self._inner = inner
        self._pairs = pairs

    def write(self, text: Any) -> Any:
        if isinstance(text, str):
            for old, new in self._pairs:
                text = text.replace(old, new)
        return self._inner.write(text)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


@contextmanager
def _real_paths_in_output(scratch: Path, real_root: Path) -> Iterator[None]:
    import sys
    import tempfile

    spellings = {str(scratch), str(Path(tempfile.gettempdir()) / scratch.name)}
    pairs = [(old, str(real_root)) for old in sorted(spellings, key=len, reverse=True)]
    saved = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _Rewriting(sys.stdout, pairs), _Rewriting(sys.stderr, pairs)
    try:
        yield
    finally:
        sys.stdout, sys.stderr = saved


@contextmanager
def _rooted_at(scratch: Path) -> Iterator[None]:
    """The command's repo root and cwd are the scratch tree for the block."""
    import os

    saved_cwd = Path.cwd()
    saved_env = os.environ.get("FR_REPO_ROOT")
    os.environ["FR_REPO_ROOT"] = str(scratch)
    os.chdir(scratch)
    try:
        yield
    finally:
        os.chdir(saved_cwd)
        if saved_env is None:
            os.environ.pop("FR_REPO_ROOT", None)
        else:
            os.environ["FR_REPO_ROOT"] = saved_env


def _exit_code_of(run: Callable[..., None], args: tuple[Any, ...], kwargs: dict[str, Any]) -> int:
    try:
        run(*args, **kwargs)
    except typer.Exit as e:
        return e.exit_code
    return 0


def _porcelain(root: Path) -> set[str]:
    import subprocess

    out = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        check=False,
    ).stdout
    return set(out.decode(errors="replace").splitlines())


def _dry_run(run: Callable[..., None], args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    """`fr archive --dry-run` (R10, R11, design §C): the real command, run in-process with
    a forge that records every write instead of making it. For a repo placement it runs
    against a disposable copy of the checkout; under quiet or stealth the record lives
    outside the checkout, so `_record_merged` previews it, the follow-ups write nothing,
    and nothing is copied. The summary, and the refused forge calls, are reported whatever
    way the run ends (review p3-r9)."""
    from fr import archive_preview as ap
    from fr.artifacts.paths import outside_repo
    from fr.git import head_on_default_branch, pinned_head_on_default_branch

    global _PREVIEW  # noqa: PLW0603 — set only while the command runs
    real_root = resolve_repo_root().resolve()
    backend, host = ap.forge_of(real_root)
    ledger = ap.PreviewLedger()

    def wrap(client: Any) -> Any:
        return ap.PreviewForge(client, host=host, backend=backend, ledger=ledger)

    outside = outside_repo(real_root) is not None
    real_factory = _make_gh_client
    staged: list[str] = []
    code = 0
    _PREVIEW = _Preview(wrap=wrap, outside=outside)
    globals()["_make_gh_client"] = lambda: wrap(real_factory())
    try:
        if outside:
            code = _exit_code_of(run, args, kwargs)
        else:
            on_default = head_on_default_branch(real_root)  # p3-r4: the real checkout's answer
            with (
                ap.scratch_checkout(real_root) as scratch,
                pinned_head_on_default_branch(scratch, on_default),
                _real_paths_in_output(scratch, real_root),
            ):
                baseline = _porcelain(scratch)
                plan = kwargs.get("plan_dir")
                if plan is not None:
                    kwargs = {**kwargs, "plan_dir": _in_checkout(real_root, Path(plan))}
                with _rooted_at(scratch):
                    code = _exit_code_of(run, args, kwargs)
                staged = sorted(_porcelain(scratch) - baseline)
    except Exception as e:
        _report_preview(staged, ledger)
        if ledger.refused:
            raise typer.Exit(1) from e
        raise
    else:
        _report_preview(staged, ledger)
    finally:
        globals()["_make_gh_client"] = real_factory
        _PREVIEW = None
    if ledger.refused:
        raise typer.Exit(1)
    if code:
        raise typer.Exit(code)


def _report_preview(staged: list[str], ledger: Any) -> None:
    typer.echo("\ndry run — nothing was written.")
    if staged:
        typer.echo("would stage:")
        for line in staged:
            typer.echo(f"  {line}")
    if ledger.writes:
        typer.echo("would write to the forge:")
        for w in ledger.writes:
            typer.echo(f"  {w}")
    if ledger.refused:
        err_console.print(
            "dry run refused forge call(s) it does not know as a read: "
            + ", ".join(sorted(set(ledger.refused))),
            soft_wrap=True,
            markup=False,
        )


def _with_followups(fn: Callable[..., None]) -> Callable[..., None]:
    """Run `fn` inside one move log, and `_after_moves` in a `finally` — on
    every entry mode and every exit path (spec 2026-10-06 §0)."""

    def run(*args: Any, **kwargs: Any) -> None:
        # A usage error fires before anything moves (R9).
        if kwargs.get("issues") is not None and kwargs.get("no_issues"):
            err_console.print("--issues and --no-issues are mutually exclusive")
            raise typer.Exit(2)
        with recording_moves() as log:
            # R7: a refusal — a non-zero exit, a `SettingsError`, any exception —
            # runs no follow-up: nothing it staged is left to file anything for.
            done: typer.Exit | None = None
            # R7: a single-plan archive that fails anywhere writes nothing.
            single = (
                kwargs.get("plan_dir") is not None
                and not kwargs.get("all_plans")
                and not kwargs.get("sweep_only")
                and kwargs.get("branch") is None
            )
            try:
                if single:
                    try:
                        root0 = resolve_repo_root()
                    except Exception:  # noqa: BLE001 — outside a repo fn refuses by itself
                        fn(*args, **kwargs)
                    else:
                        with undoing_staged_moves(root0):
                            fn(*args, **kwargs)
                else:
                    fn(*args, **kwargs)
            except typer.Exit as e:
                if e.exit_code:
                    raise
                done = e  # an Exit(0) is a normal return that left early
            try:
                root = resolve_repo_root()
            except Exception:  # noqa: BLE001 — outside a repo there is nothing to follow up
                root = None
            if root is not None:
                _after_moves(
                    root,
                    log,
                    _ArchiveOpts(
                        branch=kwargs.get("branch"),
                        issues=kwargs.get("issues"),
                        no_issues=bool(kwargs.get("no_issues")),
                        dry_run=bool(kwargs.get("dry_run")),
                    ),
                )
            if done is not None:
                raise done

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        if kwargs.get("dry_run"):
            _dry_run(run, args, kwargs)
            return
        run(*args, **kwargs)

    return wrapper


@_with_followups
def archive_command(
    plan_dir: Path | None = typer.Argument(None, help="Path to plan folder."),
    all_plans: bool = typer.Option(
        False, "--all", help=f"Archive every finished plan under {KIND_DIRS['plan']}/."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Archive even when the gate reports incomplete phases (single plan only). "
        "It does not lift the Test Plan hold: record a step that does not apply with "
        "`fr closeout outcome --na`.",
    ),
    no_spec_sweep: bool = typer.Option(
        False,
        "--no-spec-sweep",
        help="Archive the plan(s) but skip the spec-archival sweep for this run.",
    ),
    sweep_only: bool = typer.Option(
        False,
        "--sweep-only",
        help="Only re-run the spec-archival sweep (no plan dir, no --all). For specs "
        "stranded live by an earlier run — e.g. a TBD slice removed after the plan "
        "moved, when no plan path can name the work anymore.",
    ),
    branch: str | None = typer.Option(
        None,
        "--branch",
        help="Archive every live artifact this MERGED branch added or modified "
        "(plans with their runs/usage/journals, specs, debug journals); "
        "anything not ready is printed as `held:`, never a failure.",
    ),
    issues: str | None = typer.Option(
        None,
        "--issues",
        help="File one tracker issue per open end the archived journals leave behind: "
        "`all`, or a comma list of qualified ids (<scope>/<slug>/<id>) — which also "
        "works when nothing moved this run. Each filed finding is deferred to its "
        "issue in its journal (staged, never committed).",
    ),
    no_issues: bool = typer.Option(
        False,
        "--no-issues",
        help="List the open ends but file nothing (and do not prompt).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what the run would do and change nothing: the moves, holds, skips, owed "
        "entries and issues, and under quiet or stealth the record and the push. Reads git "
        "and the forge only, never prompts, and exits with the code the real run would.",
    ),
) -> None:
    """Move a finished plan to implemented/plans/ (and its spec when ready).

    Moves are `git mv`; review and commit them (PR per repo workflow).

    Sliced specs: to keep a spec from being swept while a decided-but-unbuilt
    slice is still pending, add a plan row with a `pending` (or `tbd`) File cell
    for that slice. `--no-spec-sweep` is the per-run escape that skips the sweep
    entirely. `--sweep-only` is the inverse: just the sweep, for finishing a
    close-out whose plan moves already landed.
    """
    from fr.artifacts.paths import outside_repo
    from fr.settings import SettingsError

    placement = outside_repo(resolve_repo_root())
    if placement is not None and branch is None:
        raise SettingsError(
            f"`fr archive` without --branch is not available under placement {placement}: "
            "a merged feature is recorded, never moved (R25). Run `fr archive --branch "
            "<branch>`, which appends `merged: <sha>` to its feature path and moves nothing. "
            "Nothing was written"
        )
    if dry_run and placement is not None:
        _refuse_cannot_tell(resolve_repo_root(), placement)
    require_migrated_layout(create=not dry_run)
    if branch is not None:
        for conflicting, name in (
            (plan_dir is not None, "plan_dir"),
            (all_plans, "--all"),
            (sweep_only, "--sweep-only"),
            (force, "--force"),
        ):
            if conflicting:
                err_console.print(f"--branch takes no {name} — it archives what the branch touched")
                raise typer.Exit(2)
        if placement is not None:
            _record_merged(resolve_repo_root(), branch, placement, preview=dry_run)
            return
        _archive_branch(resolve_repo_root(), branch, no_spec_sweep=no_spec_sweep)
        return
    if sweep_only:
        for conflicting, name in (
            (plan_dir is not None, "plan_dir"),
            (all_plans, "--all"),
            (force, "--force"),
            (no_spec_sweep, "--no-spec-sweep"),
        ):
            if conflicting:
                err_console.print(f"--sweep-only takes no {name} — it only re-runs the sweep")
                raise typer.Exit(2)
        repo_root = resolve_repo_root()
        if _report_sweep(repo_root, spec_archive_sweep(repo_root, _make_gh_client())):
            _repair_in_passing(repo_root, None)
            _staged_note()
        else:
            typer.echo("spec sweep: nothing eligible to move.")
        return
    if all_plans and plan_dir is not None:
        err_console.print("--all and plan_dir are mutually exclusive")
        raise typer.Exit(2)
    if not all_plans and plan_dir is None:
        err_console.print("Either provide a plan_dir argument or use --all")
        raise typer.Exit(2)
    if all_plans and force:
        err_console.print(
            "--force with --all is refused: blanket-forcing archives work that "
            "may not be done. Force individual plans explicitly."
        )
        raise typer.Exit(2)

    repo_root = resolve_repo_root()
    gh = _make_gh_client()
    # One merge-evidence read per invocation, never per plan (#544).
    evidence = merge_evidence(repo_root, fetch=True)
    _note_fetch_error(evidence)

    if all_plans:
        plans_root = kind_dir("plan", space_for(repo_root))
        targets = (
            sorted(p for p in plans_root.iterdir() if p.is_dir() and (p / "_meta.yaml").exists())
            if plans_root.is_dir()
            else []
        )
    else:
        assert plan_dir is not None
        targets = [plan_dir]

    archived: list[Path] = []
    skipped: list[str] = []
    for target in targets:
        # Under-repo check FIRST — `git status -- <path>` (the dirty check)
        # and `git mv` both fail opaquely on out-of-repo paths.
        try:
            target.resolve().relative_to(repo_root)
        except ValueError:
            msg = f"{target} is not under this repo root ({repo_root})"
            if not all_plans:
                # soft_wrap: the message carries TWO absolute paths, so rich's
                # default folding splits it — and, on a long tmp root, splits
                # it mid-sentence (review r5-e15). Everything an operator
                # copy-pastes or greps goes out unwrapped.
                err_console.print(f"refusing to archive — {msg}", soft_wrap=True)
                raise typer.Exit(2) from None
            skipped.append(f"{target.name}: skipped — {msg}")
            continue
        try:
            report = build_plan_report(target, gh)
        except PlanSchemaError as e:
            if not all_plans:
                err_console.print(f"parse error: {escape(str(e))}")
                raise typer.Exit(5) from e
            skipped.append(f"{target.name}: parse error: {e}")
            continue

        blockers = archive_blockers(report.plan, report.observed, evidence)
        if blockers and not force:
            if not all_plans:
                # R7: a refusal writes nothing, so it records no owed entry either.
                err_console.print("refusing to archive — plan is not complete or not merged:")
                for b in blockers:
                    err_console.print(f"  {b}", soft_wrap=True)
                err_console.print("(override with --force if you know the work is done)")
                raise typer.Exit(2)
            _write_manual_owed(repo_root, report.plan, blockers)
            skipped.append(f"{target.name}: skipped — {'; '.join(blockers)}")
            continue

        # R19: a spec Test Plan step with no recorded outcome holds the plan in
        # every mode, `--force` included — a skipped step is never dropped.
        hold = outcome_hold(repo_root, report.plan, target.resolve().relative_to(repo_root))
        if hold:
            if not all_plans:
                err_console.print(f"refusing to archive — {hold[0]}:", soft_wrap=True, markup=False)
                for line in hold[1:]:
                    err_console.print(line, soft_wrap=True, markup=False)
                raise typer.Exit(2)
            skipped.append(f"{target.name}: skipped — " + "\n".join(hold))
            continue

        try:
            dirty = paths_dirty(repo_root, target)
            msg = f"{target.name}: worktree dirty at the plan path — commit or stash first"
        except GitStatusError as e:
            dirty, msg = True, f"{target.name}: {e}"
        if dirty:
            if not all_plans:
                err_console.print(f"refusing to archive — {msg}", soft_wrap=True, markup=False)
                raise typer.Exit(2)
            skipped.append(msg.replace(f"{target.name}: ", f"{target.name}: skipped — ", 1))
            continue

        try:
            new_path = archive_plan_dir(repo_root, target.resolve())
        except ArchiveError as e:
            if not all_plans:
                err_console.print(str(e))
                raise typer.Exit(2) from e
            skipped.append(f"{target.name}: {e}")
            continue
        archived.append(new_path)
        typer.echo(f"  archived: {target} -> {new_path.relative_to(repo_root)}")

    # Spec decision once, after all plan moves (order independence in --all).
    # Runs even when nothing archived this run: a spec stranded by a prior
    # run (cross-repo row unresolved then, resolved now) must still get
    # swept — `fr migrate dirs` evaluates specs unconditionally and the two
    # archive paths must agree (review finding, 2026-06-06).
    # Single-plan archive repairs only that plan's own refs (#686); --all is
    # repo-wide by intent. The sweep is repo-wide, though, and may move a
    # spec that belongs to other plans; their refs to it are widened in, so
    # the move and its repair still land together.
    only_plans = None if all_plans else frozenset(p.name for p in archived)
    specs_moved = False
    if (archived or all_plans) and not no_spec_sweep:
        sweep = spec_archive_sweep(repo_root, gh)
        if only_plans is not None:
            only_plans |= plans_referencing_specs(
                repo_root, [repo_root / m.dst for m in sweep.moves]
            )
        specs_moved = _report_sweep(repo_root, sweep)
    elif (archived or all_plans) and no_spec_sweep:
        typer.echo("  (spec sweep skipped)")

    # §C (2026-09-28-closeout-always): owed debug journals, orphan journals
    # and orphan run cursors (+ usage) — after the plan loop and spec sweep
    # above, as today, so an owner archived JUST NOW by this same --all run
    # already counts. Recomputed here rather than reusing an earlier read:
    # the plan/spec moves above changed the working tree `owed_artifacts`
    # reads. Unaffected by --no-spec-sweep — none of these are specs.
    owed_moved = False
    if all_plans:
        for o in owed_artifacts(repo_root, evidence).owed:
            if o.kind in ("debug_journal", "orphan_journal"):
                scope_slug = journal_scope_and_slug(o.path)
                assert scope_slug is not None, o.path
                scope, slug = scope_slug
                journal_scope = cast("JournalScope", scope)
                archive_journal(repo_root, journal_scope, slug)
                _echo_archived(
                    o.path,
                    archived_journal_path(repo_root, journal_scope, slug).relative_to(repo_root),
                )
                owed_moved = True
            elif o.kind == "orphan_run":
                run_id = o.path.stem
                archive_run_cursor(repo_root, run_id)
                _echo_archived(o.path, archived_run_path(repo_root, run_id).relative_to(repo_root))
                owed_moved = True

    # Repair in passing (2026-06-06 spec-path-repair): the move and the
    # ref normalization land in the same operator commit. One pass, whether
    # the sweep or a plan move (or both) triggered it (#710).
    if archived or specs_moved:
        _repair_in_passing(repo_root, only_plans)

    for s in skipped:
        typer.echo(f"  skipped: {s}")
    if archived or specs_moved or owed_moved:
        _staged_note()
    elif all_plans:
        typer.echo("nothing to archive.")
