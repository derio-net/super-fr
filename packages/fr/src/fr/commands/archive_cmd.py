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
        typer.echo("\nmoves staged via git mv — review, commit, and PR them.")


def _record_merged(repo_root: Path, branch: str, placement: str) -> None:
    """`fr archive --branch <b>` under quiet and stealth (R25): append one `merged: <sha>`
    record to the feature's `merged.yaml`, in ONE commit on the placement's branch, pushed
    (quiet: a plain push of `fr`; stealth: compare-and-swap to the tracking ref), and move
    nothing. The sha is the default ref's commit that merged the branch (R17's clause):
    a branch that is not merged is refused, and a record that already agrees is not
    written twice."""
    from fr.artifacts.paths import FEATURES_DIR, feature_id
    from fr.placement import merged as merged_status
    from fr.placement.quiet import owner_of

    evidence = merge_evidence(repo_root, fetch=True)
    if evidence.ref is None:
        err_console.print(
            f"refusing to archive — no default ref: {evidence.ref_error}", soft_wrap=True
        )
        raise typer.Exit(2)
    _branch_refs_or_exit(repo_root, branch, evidence.ref.ref.split("/", 1)[0])
    _note_fetch_error(evidence)
    space = space_for(repo_root)
    fid = feature_id(branch)
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
    view = merged_status.merged_features(space, repo_root)
    for notice in view.notices:
        err_console.print(f"note: {escape(notice)}", soft_wrap=True)
    feature = view.get(fid)
    if feature is None:
        err_console.print(
            f"refusing to archive — {branch} is not merged into {view.ref or 'the default ref'}:"
            " its head is not reachable from it (R17). Nothing was written",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    short = feature.sha[:12]
    if feature.cached:
        typer.echo(f"already recorded: {branch} merged at {short}; nothing to write")
        return
    path = merged_status.append_record(froot, feature.sha, feature.heads)
    _commit_merged_record(
        repo_root, space, placement, path, f"chore(fr): record {branch} merged at {short}"
    )
    typer.echo(
        f"recorded: {branch} merged at {short} "
        f"({FEATURES_DIR}/{fid}/{merged_status.MERGED_FILE}); nothing moved (R25)"
    )


def _commit_merged_record(
    repo_root: Path, space: Any, placement: str, path: Path, message: str
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
        stealth.restore_files(wt, [path])
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
                [path],
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
            outcome = commit_paths(fr_root, [path], message)
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
    if paths_dirty(repo_root, target):
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
    if live.exists() and paths_dirty(repo_root, live):
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
        if not listed or not trigger.is_interactive():
            return
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
    for filed in af.file_owed_ends(repo_root, ends, _make_gh_client(), repo):
        if filed.ref is None:
            err_console.print(
                f"[yellow]warning:[/yellow] could not file owed {filed.end.key} — "
                f"{escape(filed.error or '')}"
            )
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


def _with_followups(fn: Callable[..., None]) -> Callable[..., None]:
    """Run `fn` inside one move log, and `_after_moves` in a `finally` — on
    every entry mode and every exit path (spec 2026-10-06 §0)."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        # A usage error fires before anything moves (R9).
        if kwargs.get("issues") is not None and kwargs.get("no_issues"):
            err_console.print("--issues and --no-issues are mutually exclusive")
            raise typer.Exit(2)
        with recording_moves() as log:
            try:
                fn(*args, **kwargs)
            finally:
                try:
                    root = resolve_repo_root()
                except Exception:  # noqa: BLE001 — outside a repo there is nothing to follow up
                    pass
                else:
                    _after_moves(
                        root,
                        log,
                        _ArchiveOpts(
                            branch=kwargs.get("branch"),
                            issues=kwargs.get("issues"),
                            no_issues=bool(kwargs.get("no_issues")),
                        ),
                    )

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
    require_migrated_layout()
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
            _record_merged(resolve_repo_root(), branch, placement)
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
            typer.echo("\nmoves staged via git mv — review, commit, and PR them.")
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
            _write_manual_owed(repo_root, report.plan, blockers)
            if not all_plans:
                err_console.print("refusing to archive — plan is not complete or not merged:")
                for b in blockers:
                    err_console.print(f"  {b}", soft_wrap=True)
                err_console.print("(override with --force if you know the work is done)")
                raise typer.Exit(2)
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

        if paths_dirty(repo_root, target):
            msg = f"{target.name}: worktree dirty at the plan path — commit or stash first"
            if not all_plans:
                err_console.print(f"refusing to archive — {msg}")
                raise typer.Exit(2)
            skipped.append(f"{target.name}: skipped — dirty worktree")
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
        typer.echo("\nmoves staged via git mv — review, commit, and PR them.")
    elif all_plans:
        typer.echo("nothing to archive.")
