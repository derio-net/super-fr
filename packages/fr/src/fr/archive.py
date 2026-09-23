"""`fr archive` library — gate check, git mv, spec-archival sweep.

The lifecycle step the 2026-06-05 postmortem found missing: completed
plans move to `docs/superpowers/implemented/plans/`, and a spec whose
rows are all implemented follows to `implemented/specs/`. Moves are
`git mv` (rename history survives); committing is the operator's job.

The gate is `vk.render.archive_gate` — shared with the apply/status
nudge so the three surfaces can't disagree. The spec decision is
`vk.migrate._spec_fully_implemented` — shared with `fr migrate dirs`.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr.git import (
    GIT_TIMEOUT_SECONDS,
    GitRefusal,
    GitUnavailableError,
    git_answer,
    remote_default_ref,
    remote_name,
)
from fr.journal.model import archived_journal_path, journal_path, spec_journal_slug
from fr.migrate import DirsMove, MigrationError, _spec_fully_implemented
from fr.run.legacy import RunStateV4, parse_run_state_v4
from fr.run.model import (
    RUNS_REL,
    RunState,
    RunStateError,
    archived_run_path,
    parse_run_state,
    run_path,
)

if TYPE_CHECKING:
    from fr.ghclient import GhClient
    from fr.parser import Plan

__all__ = [
    "FETCH_TIMEOUT_SECONDS",
    "ArchiveError",
    "DefaultRef",
    "MergeEvidence",
    "SpecSweepResult",
    "archive_plan_dir",
    "completed_unarchived_plans",
    "find_run_for_plan",
    "merge_evidence",
    "paths_dirty",
    "spec_archive_sweep",
]

PLANS_REL = Path("docs/superpowers/plans")


def completed_unarchived_plans(repo_root: Path) -> list[str]:
    """Plan-dir names under ``docs/superpowers/plans/`` that are fully locally
    complete (#334).

    A plan counts iff it has at least one phase and *every* phase satisfies
    ``render.plan_locally_complete`` (``completion.at`` set, or all steps
    ticked). Deliberately offline (no gh observation, no ref).

    Local completeness is NOT "merged", and this is not the archive gate's
    answer: a plan can be complete in the working tree without ever having
    reached the default branch, and the mover must refuse that (#526/#544).
    "Merged" has one definition, ``merge_evidence``, whose ``complete_on_ref``
    applies this same per-phase predicate to the default ref's copy of the
    plans — the tripwire's signal. Malformed plan dirs are skipped, not
    flagged — a parse failure is a different problem and must not wedge the
    check red.
    """
    return [
        name
        for name, plan in _parsed_plans(repo_root / PLANS_REL)
        if plan is not None and _fully_complete(plan)
    ]


def _parsed_plans(plans_dir: Path) -> Iterator[tuple[str, Plan | None]]:
    """Every plan dir (one with a ``_meta.yaml``) under ``plans_dir``, sorted,
    with its parse — ``None`` when the current parser rejects it."""
    from fr.parser import PlanSchemaError, parse

    if not plans_dir.is_dir():
        return
    for plan_dir in sorted(plans_dir.iterdir()):
        if not (plan_dir / "_meta.yaml").exists():
            continue
        try:
            yield plan_dir.name, parse(plan_dir)
        except PlanSchemaError:
            yield plan_dir.name, None


def _complete_phases(plan: Plan) -> frozenset[int]:
    """Phase numbers ``render.plan_locally_complete`` accepts."""
    from fr.render import plan_locally_complete

    return frozenset(p.phase.number for p in plan.phases if plan_locally_complete(p))


def _fully_complete(plan: Plan) -> bool:
    """At least one phase, and every phase locally complete."""
    return bool(plan.phases) and len(_complete_phases(plan)) == len(plan.phases)


# --- merge evidence: the one definition of "merged" (spec 2026-09-23 §3.A) ---

FETCH_TIMEOUT_SECONDS = 30
"""Cap on `_fetch`: a hanging fetch must not stall `fr status` (spec §4)."""


@dataclass(frozen=True)
class DefaultRef:
    ref: str
    """e.g. ``origin/main``: a remote-tracking ref, never a local branch."""
    sha: str
    """Short SHA read, so a stale ref is visible in output."""


@dataclass(frozen=True)
class MergeEvidence:
    """What the default branch's remote-tracking ref says has landed.

    ``ref is None`` means "unknown" — never "merged" — and ``ref_error`` says
    why. A failed fetch is not fatal: ``fetch_error`` is set and every set
    below is read from the stale local ref.
    """

    ref: DefaultRef | None
    ref_error: str | None
    fetched: bool
    """A fetch was attempted and succeeded."""
    fetch_error: str | None
    """A fetch was attempted and failed (offline, auth, timeout)."""
    landed_phases: Mapping[str, frozenset[int]]
    """Plan name → phase numbers locally complete on the ref."""
    agentic_landed: frozenset[str]
    """Plans on the ref whose every agentic phase is in ``landed_phases``.

    Manual phases are excluded: fr-goal ships its trailing ``[manual]`` phase
    unticked and the operator ticks it after merge, so requiring it on the ref
    would make every fr-goal plan unarchivable. A plan with no agentic phase is
    landed once its dir exists on the ref. Judged from the REF's copy of the
    plan: a phase that exists only in the working tree is not in it, so a
    caller judging a local phase must consult ``landed_phases``.
    """
    complete_on_ref: frozenset[str]
    """Plans with EVERY phase (manual included) complete on the ref."""
    unparsed_on_ref: tuple[str, ...]
    """Ref-side plan dirs the current fr could not parse — reported, never
    silently treated as unmerged."""


def _fetch(repo_root: Path, remote: str) -> None:
    """``git fetch`` the default remote, prompt-free and time-boxed.

    A module-level seam (the ``_make_gh_client`` pattern) so tests never touch
    a network. Raises ``CalledProcessError``/``TimeoutExpired``/``OSError`` on
    failure; ``merge_evidence`` records that and falls back to the local ref.
    A fetch moves only remote-tracking refs, so read-only callers stay so.
    """
    subprocess.run(
        ["git", "-C", str(repo_root), "fetch", "--quiet", "--no-tags", remote],
        check=True,
        capture_output=True,
        text=True,
        timeout=FETCH_TIMEOUT_SECONDS,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def _describe_fetch_failure(e: Exception) -> str:
    if isinstance(e, subprocess.TimeoutExpired):
        return f"git fetch timed out after {e.timeout:g}s"
    if isinstance(e, subprocess.CalledProcessError):
        detail = e.stderr.strip() if isinstance(e.stderr, str) else ""
        return f"git fetch failed (exit {e.returncode})" + (f": {detail}" if detail else "")
    return f"git fetch could not run: {e}"


def _unknown(reason: str, *, fetched: bool, fetch_error: str | None) -> MergeEvidence:
    """Evidence for an unresolvable ref: "unknown", with nothing merged."""
    return MergeEvidence(
        ref=None,
        ref_error=reason,
        fetched=fetched,
        fetch_error=fetch_error,
        landed_phases={},
        agentic_landed=frozenset(),
        complete_on_ref=frozenset(),
        unparsed_on_ref=(),
    )


def merge_evidence(repo_root: Path, *, fetch: bool) -> MergeEvidence:
    """The single definition of "merged": plans as they exist on the default
    branch's remote-tracking ref (spec 2026-09-23 §3.A).

    With ``fetch=True`` the default remote is fetched first through ``_fetch``;
    a failure degrades to the local ref with ``fetch_error`` set. The ref's
    ``docs/superpowers/plans`` tree is materialised with ``git archive`` and
    parsed per phase — the evidence is plan CONTENT on the ref, not commit
    ancestry, so a squash merge counts.
    """
    fetched = False
    fetch_error: str | None = None
    try:
        remote = remote_name(repo_root)
        if isinstance(remote, GitRefusal):
            return _unknown(remote.reason, fetched=False, fetch_error=None)
        if remote is None:
            return _unknown(
                "no git remote, so nothing can be shown to have merged",
                fetched=False,
                fetch_error=None,
            )
        if fetch:
            try:
                _fetch(repo_root, remote)
                fetched = True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
                fetch_error = _describe_fetch_failure(e)
        ref = remote_default_ref(repo_root)
        if isinstance(ref, GitRefusal):
            return _unknown(ref.reason, fetched=fetched, fetch_error=fetch_error)
        if ref is None:
            return _unknown(
                f"no remote-tracking default branch for {remote} "
                f"(no {remote}/HEAD and no {remote}/main|master|trunk|develop)",
                fetched=fetched,
                fetch_error=fetch_error,
            )
        sha = git_answer(repo_root, "rev-parse", "--short", ref).stdout.strip()
        landed, agentic, complete, unparsed = _plans_on_ref(repo_root, ref)
    except GitUnavailableError as e:
        return _unknown(str(e), fetched=fetched, fetch_error=fetch_error)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        return _unknown(
            f"could not read the plans on {ref}: {e}", fetched=fetched, fetch_error=fetch_error
        )
    return MergeEvidence(
        ref=DefaultRef(ref=ref, sha=sha),
        ref_error=None,
        fetched=fetched,
        fetch_error=fetch_error,
        landed_phases=landed,
        agentic_landed=agentic,
        complete_on_ref=complete,
        unparsed_on_ref=unparsed,
    )


_PlanSets = tuple[dict[str, frozenset[int]], frozenset[str], frozenset[str], tuple[str, ...]]


def _plans_on_ref(repo_root: Path, ref: str) -> _PlanSets:
    """Materialise ``ref``'s plans tree in a temp dir and judge it per phase.

    Returns ``(landed_phases, agentic_landed, complete_on_ref,
    unparsed_on_ref)``; all empty when the ref has no plans tree.
    """
    listed = git_answer(repo_root, "ls-tree", "-d", ref, "--", str(PLANS_REL))
    if listed.returncode != 0 or not listed.stdout.strip():
        return {}, frozenset(), frozenset(), ()

    landed: dict[str, frozenset[int]] = {}
    agentic: set[str] = set()
    complete: set[str] = set()
    unparsed: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        archived = subprocess.run(
            ["git", "-C", str(repo_root), "archive", ref, "--", str(PLANS_REL)],
            capture_output=True,
            check=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        subprocess.run(
            ["tar", "-x", "-C", td],
            input=archived.stdout,
            capture_output=True,
            check=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        for name, plan in _parsed_plans(Path(td) / PLANS_REL):
            if plan is None:
                unparsed.append(name)
                continue
            done = _complete_phases(plan)
            landed[name] = done
            if all(p.phase.number in done for p in plan.phases if p.phase.tag == "agentic"):
                agentic.add(name)
            if _fully_complete(plan):
                complete.add(name)
    return landed, frozenset(agentic), frozenset(complete), tuple(unparsed)


class ArchiveError(Exception):
    pass


@dataclass(frozen=True)
class SpecSweepResult:
    moves: tuple[DirsMove, ...]
    notes: tuple[str, ...]


def paths_dirty(repo_root: Path, *paths: Path) -> bool:
    """True iff `git status --porcelain` reports changes under any path."""
    out = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain", "--", *map(str, paths)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return bool(out.strip())


def _git_mv(repo_root: Path, src_rel: Path, dst_rel: Path) -> None:
    (repo_root / dst_rel).parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "mv", str(src_rel), str(dst_rel)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise ArchiveError(
            f"git mv {src_rel} -> {dst_rel} failed: {(e.stderr or '').strip()}"
        ) from e


def archive_plan_dir(repo_root: Path, plan_dir: Path) -> Path:
    """`git mv` an active plan dir to implemented/plans/. Returns the new path.

    Caller has already run the archive gate and the dirty check.
    """
    try:
        src_rel = plan_dir.resolve().relative_to(repo_root)
    except ValueError as e:
        # `fr archive /path/in/another/repo` (or wrong cwd): a clean
        # refusal, not a traceback (review finding, 2026-06-06).
        raise ArchiveError(
            f"plan dir {plan_dir} is not under this repo root ({repo_root}); "
            f"run fr archive from the repo that owns the plan"
        ) from e
    dst_rel = Path("docs/superpowers/implemented/plans") / plan_dir.name
    if (repo_root / dst_rel).exists():
        # A prior botched archive (copied to implemented/ but never removed
        # from plans/) leaves a duplicate; `git mv` would nest src INTO the
        # existing dir (implemented/plans/X/X), corrupting the tree. Refuse
        # with a clear next step instead. (#334)
        raise ArchiveError(
            f"destination already exists: {dst_rel} — this plan appears already "
            f"archived. Remove the stale plans/ copy ({src_rel}) instead "
            f"(e.g. `git rm -r {src_rel}`)."
        )
    _git_mv(repo_root, src_rel, dst_rel)
    _archive_journal(repo_root, "plan", plan_dir.name)
    _archive_run(repo_root, src_rel)
    return repo_root / dst_rel


def find_run_for_plan(repo_root: Path, plan_rel: Path) -> str | None:
    """The id of the run whose recorded `emitted.plan` points at `plan_rel`,
    or `None` if no run file references it (a plan not born from `fr run
    start` — the common case today, and a correct no-op).

    Matches by DATA — the `plan` step's `emitted` artifact every run file
    already carries (spec §4.B) — never by a name/slug convention. A run id
    is `<date>-<flattened-branch>` (`fr.commands.run_cmd.derive_run_id`)
    and a plan slug is authored independently by whatever agent step
    creates it; the two share no naming relationship in real use (Phase 7
    review finding: a name-keyed lookup silently never matched). A
    malformed run file is skipped, not fatal to archival — a parse failure
    there is a different problem.

    Public (it was `_find_run_for_plan` until the 2026-08-30 §3.E adoption
    work) because `fr.run.adopt` asks the same question from the other end —
    "does this plan already have a run?" — and a second implementation of
    the match would be a second chance to key it on a name.
    """
    runs_dir = repo_root / RUNS_REL
    if not runs_dir.is_dir():
        return None
    target = str(plan_rel).rstrip("/")
    for run_file in sorted(runs_dir.glob("*.yaml")):
        state = _read_any_version(run_file.read_text())
        if state is None:
            continue
        for record in state.steps.values():
            if record.emitted and record.emitted.get("plan", "").rstrip("/") == target:
                return state.run
    return None


def _read_any_version(text: str) -> RunState | RunStateV4 | None:
    """`text` as a run cursor of ANY version, or `None` if it is not one.

    A cursor fr has not migrated yet is still a cursor. The live model is the
    current shape only (`run` 5 removed `items`/`dispatch`/`accounting`), so
    reading with it alone made every stale cursor look like NO cursor — and
    `fr migrate artifacts` then offered to adopt plans that already had one.
    For a cursor the 4 -> 5 rewrite refuses, which stays v4 indefinitely,
    `--adopt` would have written a second cursor for the same plan.

    `emitted.plan` and `run` are the same facts in every version, so the match
    falls back to the frozen reader (`fr.run.legacy`). Not a migration, and
    nothing is written: this only answers "whose cursor is this?".
    """
    try:
        return parse_run_state(text)
    except RunStateError:
        pass
    try:
        return parse_run_state_v4(text)
    except RunStateError:
        return None


def _archive_run(repo_root: Path, plan_rel: Path) -> None:
    """Move the run-state file that created `plan_rel` (if any) to
    implemented/runs/, alongside its plan. A no-op when no run file
    references this plan, or when the destination already holds one (a
    re-run) — same shape as `_archive_journal`.
    """
    run_id = find_run_for_plan(repo_root, plan_rel)
    if run_id is None:
        return
    src = run_path(repo_root, run_id)
    if not src.exists():
        return
    dst = archived_run_path(repo_root, run_id)
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    _git_mv(repo_root, src.relative_to(repo_root), dst.relative_to(repo_root))


def _archive_journal(repo_root: Path, scope: str, slug: str) -> None:
    """Move a scoped journal to implemented/journals/<scope-dir>/.

    A no-op when no journal exists (back-compat with pre-journal plans/specs)
    or when the destination already holds one (a re-run). Path resolution is
    delegated to `fr.journal.model` so the layout has one source of truth
    (2026-07-22 fr-goal-subagent-execution spec §A).
    """
    src = journal_path(repo_root, scope, slug)  # type: ignore[arg-type]
    if not src.exists():
        return
    dst = archived_journal_path(repo_root, scope, slug)  # type: ignore[arg-type]
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    _git_mv(repo_root, src.relative_to(repo_root), dst.relative_to(repo_root))


def spec_archive_sweep(repo_root: Path, gh: GhClient | None) -> SpecSweepResult:
    """Move every spec whose rows are all implemented to implemented/specs/.

    Runs after plan moves (single archive or end of an `--all` sweep), so a
    spec whose last plans archived in the same run qualifies. Cross-repo
    rows resolve via the gh contents API when `gh` is given; unresolved
    rows leave the spec in place with a note — never a silent pass.

    A spec delivered in slices holds itself: a plan row whose File cell is a
    `pending`/`tbd` placeholder marks a decided-but-unbuilt slice and keeps
    the spec in place (a note is emitted) until that slice's plan is built and
    archived (#351).
    """
    moves: list[DirsMove] = []
    notes: list[str] = []
    specs_dir = repo_root / "docs" / "superpowers" / "specs"
    if not specs_dir.is_dir():
        return SpecSweepResult(moves=(), notes=())
    for spec_path in sorted(specs_dir.glob("*.md")):
        implemented, note = _spec_fully_implemented(spec_path, repo_root, gh)
        if implemented:
            src_rel = spec_path.relative_to(repo_root)
            dst_rel = Path("docs/superpowers/implemented/specs") / spec_path.name
            try:
                _git_mv(repo_root, src_rel, dst_rel)
            except ArchiveError as e:
                notes.append(str(e))
                continue
            # A spec journal is keyed by the bare feature slug, not the spec's
            # `<slug>-design` filename stem; strip the suffix so the move
            # resolves the real file and follows the spec into
            # implemented/journals/specs/ (2026-07-22 spec §A; #417).
            _archive_journal(repo_root, "spec", spec_journal_slug(spec_path.stem))
            moves.append(DirsMove(src=src_rel, dst=dst_rel, kind="spec"))
        elif note and "no Implementation Plans rows" not in note:
            notes.append(f"{spec_path.name}: {note}")
    return SpecSweepResult(moves=tuple(moves), notes=tuple(notes))


# Re-exported for callers that catch both error families with one except.
_ = MigrationError
