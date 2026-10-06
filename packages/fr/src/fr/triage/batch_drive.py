"""The wave driver's pass, as a pure function (wave-driver spec §B, §C).

`drive_pass(snapshot)` returns the ordered actions one pass of `fr triage batch
drive` takes: merge what is ready, close out what merged, merge an attributed
archive PR, dispatch what may start, report what is blocked or failing, and say
when a finished wave leaves duplicate candidates (`dedupe`).
The command layer (`fr.commands.triage_batch_cmd`) builds the `Snapshot` from
the facts, the forge client, the checkout and the runner, and executes the
actions; this module only decides.

It imports nothing from `fr_dispatch`, runs no git, starts no process and
reads no clock: the time is `Snapshot.now`, so the ten-minute fallback is
testable. `tests/unit/test_triage_batch_drive.py` pins that.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from fr.triage.batch import (
    UNSATISFIABLE,
    BatchStage,
    ForeignPr,
    QueueEntry,
    batch_branch,
    batch_item_id,
)
from fr.triage.model import Batch, CloseoutEvent, Export

DEFAULT_WORKSPACE_PREFIX = "drive"
CLOSEOUT_FALLBACK = timedelta(minutes=10)
"""How long after a merge the close-out starts when no release commit followed it
(a PR with no change fragment releases nothing)."""

DEFAULT_MAX_INFLIGHT = 4

IN_FLIGHT: frozenset[BatchStage] = frozenset({"dispatched", "pr-open"})
LANDED: frozenset[BatchStage] = frozenset({"merged", "partial"})
ARCHIVE_PREFIXES = ("chore/archive-", "chore/closeout-")
EXPORT_PREFIX = "chore/triage-state-wave-"
"""The head of a wave's state-export PR (pages-goal R13). Not in `ARCHIVE_PREFIXES`, so
archive attribution can never claim an export PR."""
RUNS_DIR = "docs/superpowers/runs"
JOURNAL_DIRS = ("docs/superpowers/journals/", "docs/superpowers/implemented/journals/")
RUN_ARTIFACT_DIRS = tuple(
    f"docs/superpowers/{d}/" for d in ("plans", "specs", "journals", "runs", "usage")
)
"""Where a run's live artifacts sit until its close-out archives them under
`docs/superpowers/implemented/` (`fr archive --branch`)."""

ChecksVerdict = Literal["green", "pending", "failing"]
ActionKind = Literal[
    "merge",
    "closeout",
    "adopt",
    "archive",
    "dispatch",
    "blocked",
    "held",
    "warn",
    "foreign",
    "close",
    "dedupe",
    "export",
    "export-merge",
    "export-reconcile",
    "export-closed",
]
EXPORT_KINDS: frozenset[str] = frozenset(
    {"export", "export-merge", "export-reconcile", "export-closed"}
)

ARCHIVED_BY_UNKNOWN_PR = 0
"""`CloseoutEvent.archived` for a close-out found archived on the default branch with
no PR to name: every reader only asks whether `archived` is set (gh#900)."""

_FAILING_BUCKETS = frozenset({"fail", "cancel"})


@dataclass(frozen=True)
class LivePr:
    """A PR as the forge shows it now: a batch PR, or an archive PR candidate."""

    number: int
    state: str  # OPEN | MERGED | CLOSED
    draft: bool
    head: str
    checks: ChecksVerdict = "green"
    failing: tuple[str, ...] = ()
    head_ref: str = ""
    files: tuple[str, ...] = ()
    # From the repo itself, by an allowed author (`fr.triage.batch.distrust`). False
    # unless the command checked it: an archive PR is attributed only when True (gh#936).
    trusted: bool = False
    # The branch the PR merges into, as the forge says now; "" when not read. An export
    # PR is reused or merged only into the default branch (p4-r15).
    base: str = ""


@dataclass(frozen=True)
class Snapshot:
    """Everything one pass decides from. Built fresh each pass, never stored."""

    batches: tuple[Batch, ...]  # every batch of the state file
    stages: Mapping[str, BatchStage]
    queue: tuple[QueueEntry, ...]  # pr-open batches with their collected PR
    live: Mapping[str, LivePr]  # batch id -> its PR as read now
    repos: Mapping[str, str]  # batch id -> OWNER/REPO
    now: datetime
    max_inflight: int = DEFAULT_MAX_INFLIGHT
    merged_at: Mapping[str, datetime] = field(default_factory=dict)
    released: frozenset[str] = frozenset()  # merged batches whose release commit landed
    archives: Mapping[str, tuple[LivePr, ...]] = field(default_factory=dict)  # repo -> PRs
    existing: frozenset[str] = frozenset()  # runner item ids live now
    # What was reported already: a head sha whose CI failed, or a `ForeignPr.key`.
    warned: frozenset[str] = frozenset()
    # The batches this drive acts on (None: all). The in-flight cap and dependency
    # resolution always read every batch: a batch outside the selection still holds
    # a slot, and a dependency outside it is still merged or not (review rg-3).
    selected: frozenset[str] | None = None
    # Landed batches whose merge added run artifacts that are all archived now: closed
    # out already, by hand or by an earlier driver (`is_archived`). A batch merged
    # before the driver existed carries no close-out event, so without this every one
    # of them read as owed (debug 2026-10-03: 50 on this repo).
    archived: frozenset[str] = frozenset()
    # Landed batches with no close-out event whose close-out PR, on the head no other
    # batch can produce (`housekeeping_branch` with no run), is open or merged: a
    # close-out started by hand (gh#912).
    adopted: Mapping[str, LivePr] = field(default_factory=dict)
    # batch id -> the open PRs on its branch that are not its own (gh#936).
    foreign: Mapping[str, tuple[ForeignPr, ...]] = field(default_factory=dict)
    # Close finished batches' sessions (off under `--keep-sessions` and without `--yes`),
    # and the batch and close-out item ids of batches that a closing runner holds live.
    close_sessions: bool = False
    sessions: frozenset[str] = frozenset()
    # Triage-dedupe R10. The waves that were unfinished on this process's previous pass
    # (None on its first), the candidate-group count, and the scope-qualified check
    # command: the count and the command arrive here so this module imports no dedupe.
    unfinished_waves: frozenset[str] | None = None  # wave keys, as `finished`
    duplicate_groups: int = 0
    dedupe_command: str = ""
    # Per-wave state export (pages-goal R13, §I). `export_path`: repo -> the export
    # directory `<path>/<scope>` in the repo, for a single-repo scope only; `exports`:
    # what the state file records; `export_prs`: (repo, wave) -> the live PR of a recorded, unmerged
    # export, or the open PR on the wave's export head when none is recorded;
    # `finished`: `finished_waves(batches, stages)`, computed once; `export_refused`:
    # the repos of a group or org scope that opt in, which never export.
    export_path: Mapping[str, str] = field(default_factory=dict)
    exports: tuple[Export, ...] = ()
    export_prs: Mapping[tuple[str, str], LivePr] = field(default_factory=dict)
    finished: frozenset[str] = frozenset()
    export_refused: frozenset[str] = frozenset()
    # repo -> the open PRs from the repo itself on any `chore/triage-state-wave-<N>`
    # head that no live export entry records: a pass that died between opening and
    # recording (p4-r3), or a reopened PR recorded closed. Cross-repo PRs never appear
    # here (p4-r7). The export reuses one; it never adopts its content (p4-r12).
    export_orphans: Mapping[str, tuple[LivePr, ...]] = field(default_factory=dict)
    # repo -> its default branch: the only base an export PR (p4-r15) or an archive PR
    # (gh#1004) may have; "" or absent when the clone could not say, which matches none
    default_branch: Mapping[str, str] = field(default_factory=dict)
    # Landed batches with no close-out event whose evidence (archived? released?) the
    # clone could not give: plan mode only, where a failed read is reported rather
    # than fatal. Unknown is not "not archived", so no close-out is planned (gh#991).
    unverified: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    batch: str
    detail: str
    pr: int | None = None
    head: str = ""
    recorded: bool = False  # closeout: the runner holds the tab; record the event only
    post_merge: bool = False  # closeout: run the repo's post_merge first
    train: str = ""  # merge: the repo whose train this candidate belongs to
    archived: int | None = None  # adopt: the close-out event's `archived`
    items: tuple[str, ...] = ()  # close: the item ids whose sessions to close
    # export*, and a warn about one: the wave key (`batch` is then the repo); the
    # highest wave the export PR covers, which names its branch
    wave: str | None = None
    covers: tuple[str, ...] = ()  # export: every wave the PR records


@dataclass(frozen=True)
class Summary:
    """The pass's closing line, projected past its own actions."""

    in_flight: int
    merged: int
    pending: int
    closing: int
    blocked: int = 0
    queued: int = 0  # merge-train members not attempted this pass (the head excluded)

    @property
    def idle(self) -> bool:
        """Nothing pending, in flight or closing: nothing the driver can still move."""
        return self.in_flight == 0 and self.pending == 0 and self.closing == 0

    @property
    def done(self) -> bool:
        """Idle and nothing blocked: every driven batch is finished."""
        return self.idle and self.blocked == 0

    @property
    def waiting_on_operator(self) -> bool:
        """Idle, but a blocked batch remains: only the operator can move it (R7)."""
        return self.idle and self.blocked > 0


def settle(summary: Summary, *, unlanded: int = 0, held: int = 0, queued: int = 0) -> Summary:
    """The pass's summary once its actions ran: *unlanded* planned merges did not
    land (held, updated, refused), so they are still in flight and not closing, and
    *held* planned dispatches did not start, so they are still pending (review rg-1)."""
    return replace(
        summary,
        in_flight=summary.in_flight + unlanded - held,
        merged=summary.merged - unlanded,
        closing=summary.closing - unlanded,
        pending=summary.pending + held,
        queued=summary.queued + queued,
    )


@dataclass(frozen=True)
class Train:
    """One repo's merge train for a pass (drive-merge-train spec §A)."""

    repo: str
    head: str | None  # the first candidate, or the waiting head; None: all stepped over
    candidates: tuple[str, ...]  # batches with a merge action, in order
    queued: tuple[str, ...]  # the member that stopped the walk (not the head), then the rest
    stepped: tuple[str, ...]  # batches stepped over (failing)
    numbers: Mapping[str, int]  # batch id -> PR number, for train_line


@dataclass(frozen=True)
class Pass:
    actions: tuple[Action, ...]
    summary: Summary
    trains: tuple[Train, ...] = ()


# ------------------------------------------------------------------ checks (R4)


def checks_verdict(
    required: Sequence[Mapping[str, Any]], all_checks: Mapping[str, int], *, ci_none: bool
) -> tuple[ChecksVerdict, tuple[str, ...]]:
    """R4: the required checks when the branch has any, else all checks; a repo
    whose services say `ci none` is green on non-draft alone.

    *required* is `GhClient.pr_required_checks`; *all_checks* is the collected
    `PullRequest.checks` counts (`pass`, `fail`, `pending`). `SKIPPED` and
    `NEUTRAL` read as passed. No check reported at all is `pending`, never green: a
    head the driver just pushed, or a PR just readied, has no check registered yet
    (review rg-4); only a `ci none` repo merges without one.
    """
    if ci_none:
        return "green", ()
    if required:
        failing = tuple(
            sorted(str(c.get("name")) for c in required if c.get("bucket") in _FAILING_BUCKETS)
        )
        if failing:
            return "failing", failing
        pending = tuple(
            sorted(str(c.get("name")) for c in required if c.get("bucket") == "pending")
        )
        return ("pending", pending) if pending else ("green", ())
    if all_checks.get("fail", 0):
        return "failing", (f"{all_checks['fail']} failing check(s)",)
    if all_checks.get("pending", 0):
        return "pending", (f"{all_checks['pending']} pending check(s)",)
    if not all_checks.get("pass", 0):
        return "pending", ("no check reported yet",)
    return "green", ()


def closeout_due(*, released: bool, merged_at: datetime | None, now: datetime) -> bool:
    """§B step 2: the release commit that follows the merge is on the base branch,
    or ten minutes passed since the merge with none. An unknown merge time is not
    yet due (review rg-9): the caller supplies when it first saw the merge."""
    if released:
        return True
    return merged_at is not None and now - merged_at >= CLOSEOUT_FALLBACK


# ---------------------------------------------------------- close-out (§C)


def closeout_item_id(repo: str, batch_id: str) -> str:
    """`<OWNER>/<REPO>/run/closeout-<batch-id>`: unit `run`, one per batch.

    Spelled here like `batch_item_id`: `fr.triage` never imports `fr_dispatch`.
    """
    return f"{repo}/run/closeout-{batch_id}"


def wave_group(prefix: str, wave: int | None) -> str:
    """The runner group (a herdr workspace) a wave's sessions open in."""
    if not prefix.strip():
        raise ValueError("the workspace prefix must not be blank")
    return f"{prefix}-wave-{wave}" if wave is not None else f"{prefix}-no-wave"


def find_run(cursors: Iterable[object], branch: str) -> tuple[str, str | None] | None:
    """The run id (and plan slug, if one was emitted) of the cursor whose `branch` is
    *branch*, from the parsed `docs/superpowers/runs/*.yaml` documents; None when no
    cursor names it (a debug batch, or a run that left none)."""
    for doc in cursors:
        if not isinstance(doc, Mapping) or doc.get("branch") != branch:
            continue
        run = doc.get("run")
        if not isinstance(run, str) or not run:
            continue
        plan: str | None = None
        steps = doc.get("steps")
        for record in steps.values() if isinstance(steps, Mapping) else ():
            emitted = record.get("emitted") if isinstance(record, Mapping) else None
            if isinstance(emitted, Mapping) and isinstance(emitted.get("plan"), str):
                plan = PurePosixPath(emitted["plan"]).name
        return run, plan
    return None


def housekeeping_branch(branch: str, run: str | None, plan: str | None) -> str:
    """The branch the close-out pushes its archive PR from — the naming of
    `fr.run.closeout` (`chore/archive-<plan>`, `chore/closeout-<run>`,
    `chore/closeout-<branch with / as ->`)."""
    if run is not None:
        return f"chore/archive-{plan}" if plan else f"chore/closeout-{run}"
    return f"chore/closeout-{branch.replace('/', '-')}"


def closeout_brief(batch: Batch, *, run: str | None, checkout: Path) -> str:
    """The close-out work item's brief: the `fr pickup` instruction for the batch."""
    branch = batch_branch(batch)
    pickup = f"fr pickup --run {run}" if run else f"fr pickup --branch {branch}"
    return (
        f"Close out batch {batch.id} ({batch.title}): its PR on {branch} has merged.\n"
        f"In {checkout}, run `{pickup}` and follow the brief it prints, in order."
    )


def attributed(pr: LivePr, batch: Batch, event: CloseoutEvent) -> bool:
    """Whether archive PR *pr* belongs to *batch*'s close-out (§B step 3).

    Its head alone attributes it only when the head is `chore/closeout-<batch branch
    with / as ->`, a name no other batch can produce. Any other `chore/archive-*` or
    `chore/closeout-*` head (`chore/archive-<plan>`, `chore/closeout-<run-id>`) must
    also change the batch's run file or its plan journal (review rg-12). Neither
    attributes a PR that is not `trusted`: a fork or a foreign author can choose
    both the head name and the files (gh#936)."""
    if not pr.trusted:
        return False
    branch = batch_branch(batch)
    if pr.head_ref == f"chore/closeout-{branch.replace('/', '-')}":
        return True
    if not pr.head_ref.startswith(ARCHIVE_PREFIXES):
        return False
    archive = event.archive or ""
    plan = archive.removeprefix("chore/archive-") if archive.startswith("chore/archive-") else ""
    for f in pr.files:
        if event.run and (f == f"{RUNS_DIR}/{event.run}.yaml" or f.endswith(f"/{event.run}.yaml")):
            return True
        if plan and f.startswith(JOURNAL_DIRS) and PurePosixPath(f).stem == plan:
            return True
    return False


def is_archived(added: Iterable[str], live: Callable[[str], bool]) -> bool:
    """Whether a merged batch's close-out has already happened: its merge commit
    *added* at least one run artifact (`RUN_ARTIFACT_DIRS`), and none of those is
    *live* on the default branch any more. No added artifact is no evidence, so
    the close-out stays owed."""
    mine = [p for p in added if p.startswith(RUN_ARTIFACT_DIRS)]
    return bool(mine) and not any(live(p) for p in mine)


def default_selection(batches: Iterable[Batch]) -> frozenset[str]:
    """The batch ids a drive acts on when none is named: every batch with a wave, else
    all. The one rule `fr triage batch drive` and the board's hints both read."""
    every = list(batches)
    waved = [b for b in every if b.wave is not None]
    return frozenset(b.id for b in (waved or every))


def closeout_event(batch: Batch) -> CloseoutEvent | None:
    """The batch's close-out event, if it has one."""
    for e in reversed(batch.events):
        if isinstance(e, CloseoutEvent):
            return e
    return None


def finished_waves(batches: Iterable[Batch], stages: Mapping[str, str]) -> frozenset[str]:
    """The wave keys (`str(batch.wave)`) whose every batch is terminal: derived stage
    `cancelled` or `abandoned`, or a close-out event whose `archived` is set. *stages* maps
    batch id to its derived stage. A batch with no wave never makes one, and a wave with a
    batch that is not terminal (a merged one still owed its archive, say) is not finished.
    The board, the history page and the driver all read this one predicate."""
    wave_ok: dict[str, bool] = {}
    for b in batches:
        if b.wave is None:
            continue
        event = closeout_event(b)
        terminal = stages.get(b.id) in {"cancelled", "abandoned"} or (
            event is not None and event.archived is not None
        )
        key = str(b.wave)
        wave_ok[key] = wave_ok.get(key, True) and terminal
    return frozenset(k for k, ok in wave_ok.items() if ok)


def export_branch(wave: str) -> str:
    """The head a wave's state-export PR is pushed to; the driver owns it."""
    return f"{EXPORT_PREFIX}{wave}"


def _wave_order(wave: str) -> tuple[int, int | str]:
    return (0, int(wave)) if wave.lstrip("-").isdigit() else (1, wave)


ExportCount = Literal["closing", "blocked"] | None


def _outside(root: str, files: Sequence[str]) -> str:
    """Why *files* do not all lie under the export directory *root*, or "". An unknown
    file list is never "all inside": an export PR always changes something."""
    if not files:
        return "its changed files are unknown"
    prefix = root.rstrip("/") + "/"
    stray = [f for f in files if not f.startswith(prefix)]
    return f"it changes {', '.join(stray[:3])}, outside {prefix}" if stray else ""


@dataclass(frozen=True)
class ExportTarget:
    """What step 3b decides about for one repo (§I, R13): the repo's newest unmerged
    export PR and the waves recorded with it, or, with none, every finished wave of the
    repo that has no export entry at all. `wave`, the highest, names the branch."""

    repo: str
    wave: str
    covers: tuple[str, ...]
    recorded: Export | None  # the newest unmerged entry with a PR; None: not exported
    orphan: LivePr | None = None  # unrecorded: the open PR to reuse, on wave `wave`'s head


def export_wave_of(head_ref: str) -> str | None:
    """The wave key a `chore/triage-state-wave-<N>` head names, or None."""
    wave = head_ref.removeprefix(EXPORT_PREFIX) if head_ref.startswith(EXPORT_PREFIX) else ""
    return wave if wave.isdigit() else None


def export_target(
    repo: str,
    batches: Iterable[Batch],
    repos: Mapping[str, str],
    finished: frozenset[str],
    exports: Iterable[Export],
    orphans: Sequence[LivePr] = (),
) -> ExportTarget | None:
    """One export PR per repo covers every unexported finished wave. While one is
    unmerged, it is the target and a wave that finished since waits for a later pass,
    so no second PR is opened. With none recorded, an unrecorded open PR on any wave's
    export head (*orphans*, highest wave first) is reused: the export pushes onto its
    branch and covers every owed wave (p4-r3, p4-r13). None: nothing is owed."""
    mine = [e for e in exports if e.repo == repo and not e.closed]  # closed: owed again
    unmerged = [e for e in mine if e.pr is not None and not e.merged]
    if unmerged:
        newest = unmerged[-1]
        covers = sorted({e.wave for e in unmerged if e.pr == newest.pr}, key=_wave_order)
        return ExportTarget(repo, covers[-1], tuple(covers), newest)
    entered = {e.wave for e in mine}
    waves = {str(b.wave) for b in batches if b.wave is not None and repos.get(b.id) == repo}
    owed = sorted((waves & finished) - entered, key=_wave_order)
    if not owed:
        return None
    named = [(w, o) for o in orphans if (w := export_wave_of(o.head_ref)) is not None]
    if named:
        wave, orphan = max(named, key=lambda pair: _wave_order(pair[0]))
        return ExportTarget(repo, wave, tuple(owed), None, orphan)
    return ExportTarget(repo, owed[-1], tuple(owed), None)


def _wrong_base(live: LivePr, default: str) -> str:
    """Why *live* is not based on the default branch, or "" (p4-r15). An unknown base
    is never the default."""
    if default and live.base == default:
        return ""
    return f"is based on {live.base or 'an unknown branch'}, not {default or 'the default branch'}"


def _export_row(
    repo: str, wave: str, done: Export | None, live: LivePr | None, root: str, default: str = ""
) -> tuple[Action | None, ExportCount]:
    """One row of §I's table: the action for *repo*'s finished *wave*, given its
    recorded export (*done*), the live PR and the export directory *root*
    (`<path>/<scope>`), and how the summary counts it. The driver auto-merges this
    PR unreviewed, so it adopts or merges one only when every file it changes is under
    *root*, and merges only at the head it recorded (p4-sec-unpinned-merge)."""
    head = export_branch(wave)
    if done is not None and (done.merged or done.pr is None):
        return None, None  # merged, or the export changed nothing
    if done is None:
        if live is None or live.state != "OPEN":
            return Action("export", repo, f"to {root} on {head}", wave=wave), "closing"
        why = "" if live.trusted else "is not trusted (not from this repo by an allowed author)"
        why = why or _wrong_base(live, default)
        if why:
            return Action("warn", repo, f"PR #{live.number} on {head} {why}; it is never "
                          "reused or merged", pr=live.number, wave=wave), "blocked"  # fmt: skip
        # Reused, never adopted (p4-r12): the export pushes the driver's own commit onto
        # this PR's branch, and the merge pins to that commit. Nothing of the PR's is kept.
        reuse = f"to {root} on {head}, reusing open PR #{live.number}"
        return Action("export", repo, reuse, pr=live.number, wave=wave), "closing"
    if live is None:
        return None, "closing"  # not read this pass: still owed
    if live.state == "MERGED":  # merged by hand, or a pass died before recording (p4-r1)
        merged = f"export PR #{live.number} was merged outside the driver; recording it"
        return Action("export-reconcile", repo, merged, pr=live.number, wave=wave), "closing"
    if live.state != "OPEN":  # closed unmerged: recorded once, its waves owed again (p4-r6)
        return Action("export-closed", repo, f"export PR #{live.number} was closed without "
                      "a merge; its waves are owed again and re-exported next pass",
                      pr=live.number, wave=wave), "closing"  # fmt: skip
    why = ""
    if not live.trusted:
        why = "is not trusted (not from this repo by an allowed author)"
    elif live.head != done.head or not done.head:
        why = (f"head is {live.head[:12] or 'unknown'}, not the recorded "
               f"{(done.head or 'none')[:12]}: a commit the driver did not push")  # fmt: skip
    elif outside := _outside(root, live.files):
        why = outside
    elif wrong := _wrong_base(live, default):
        why = wrong
    elif live.draft:
        why = "is a draft"
    elif live.checks == "failing":
        why = f"has failing checks: {', '.join(live.failing) or 'unknown'}"
    if why:
        return Action("warn", repo, f"export PR #{live.number} {why}; the operator must act",
                      pr=live.number, wave=wave), "blocked"  # fmt: skip
    if live.checks != "green":
        return None, "closing"  # checks pending: wait
    pinned = done.head or ""  # set: a head that differs was refused above
    # Pinned to the RECORDED head, never the live one (they are equal here).
    return Action("export-merge", repo, f"PR #{live.number} at {pinned[:12]}",
                  pr=live.number, head=pinned, wave=wave), "closing"  # fmt: skip


def _export_actions(snap: Snapshot) -> tuple[list[Action], int, int]:
    """§I step 3b: a group or org scope that opts in is warned once; then, for each
    opted-in repo, `_export_row` on its `export_target`: one PR per repo, never one per
    wave. Returns the actions and how many owed export PRs are closing (acting or
    waiting) and blocked (warned)."""
    actions = [
        Action("warn", repo, f"export is per repo scope; run drive with --repo {repo}")
        for repo in sorted(snap.export_refused)
    ]
    counts = {"closing": 0, "blocked": 0}
    for repo in sorted(snap.export_path):
        target = export_target(
            repo, snap.batches, snap.repos, snap.finished, snap.exports,
            snap.export_orphans.get(repo, ()),
        )  # fmt: skip
        if target is None:
            continue
        live = (
            target.orphan if target.recorded is None else snap.export_prs.get((repo, target.wave))
        )
        action, count = _export_row(
            repo, target.wave, target.recorded, live, snap.export_path[repo],
            snap.default_branch.get(repo, ""),
        )  # fmt: skip
        if action is not None:
            if action.kind == "export":
                action = replace(action, covers=target.covers)
                if len(target.covers) > 1:
                    action = replace(action, detail=f"{action.detail} (covers waves "
                                     f"{', '.join(target.covers)})")  # fmt: skip
            actions.append(action)
        if count is not None:
            counts[count] += 1
        if action is not None and action.kind == "export" and target.orphan is not None:
            actions.extend(_stale_orphans(repo, snap, target.orphan))
    return actions, counts["closing"], counts["blocked"]


def _stale_orphans(repo: str, snap: Snapshot, reused: LivePr) -> list[Action]:
    """p4-r16: every other unrecorded export PR, named once per drive as stale. They
    block nothing: the reused PR carries the state."""
    out = []
    for o in sorted(snap.export_orphans.get(repo, ()), key=lambda o: o.number):
        key = f"stale-export\0{repo}\0{o.number}"
        if o.number == reused.number or key in snap.warned:
            continue
        out.append(Action("warn", repo, f"export PR #{o.number} on {o.head_ref} is stale: "
                          f"PR #{reused.number} carries the export; it is safe to close",
                          pr=o.number, head=key))  # fmt: skip
    return out


def is_finished(batch: Batch, stage: BatchStage, archives: Sequence[LivePr]) -> bool:
    """Whether *batch* is finished: landed, with a close-out event whose `archived`
    is set (the driver merged its archive PR), or an attributed archive PR in
    `archives` that is MERGED. One reading for the archive step and the close step."""
    event = closeout_event(batch)
    if event is None or stage not in LANDED:
        return False
    if event.archived is not None:
        return True
    return any(p.state == "MERGED" and attributed(p, batch, event) for p in archives)


def unfinished_waves(snap: Snapshot) -> frozenset[str]:
    """The wave keys (`str(batch.wave)`) of the state file that `snap.finished` does not
    hold: what the next pass compares against (triage-dedupe R10). `finished` is
    `finished_waves`, the one predicate the board, the history page and the driver read."""
    return frozenset(str(b.wave) for b in snap.batches if b.wave is not None) - snap.finished


# ------------------------------------------------------------------ the pass


def _dispatch_key(batch: Batch) -> tuple[int, int, int, int, str]:
    """Wave, then merge order (an explicit `order`), then id; unset sorts last."""
    wave, order = batch.wave, batch.order
    return (wave is None, wave or 0, order is None, order or 0, batch.id)


def _walk_train(
    repo: str, entries: Sequence[QueueEntry], snap: Snapshot
) -> tuple[Train | None, list[Action]]:
    """§A: walk one repo's *entries* (already in train order). A green member becomes
    a merge candidate and the walk goes on; a failing one is stepped over, wherever it
    sits; a moved head or a pending one stops it, and every other member after the
    stop is queued."""
    merges: list[Action] = []
    candidates: list[str] = []
    stepped: list[str] = []
    numbers: dict[str, int] = {}
    waiting: str | None = None
    queued: list[str] = []
    members = 0
    for entry in entries:
        bid = entry.batch.id
        pr = snap.live.get(bid)
        if pr is None or pr.state != "OPEN" or pr.draft:
            continue  # not a member
        members += 1
        numbers[bid] = pr.number
        if pr.checks == "failing":  # wherever it sits: reported now, not when it leads
            stepped.append(bid)
            if pr.head not in snap.warned:
                merges.append(
                    Action("warn", bid, f"PR #{pr.number} CI failing at {pr.head[:12]}: "
                           f"{', '.join(pr.failing)}", pr=pr.number, head=pr.head)
                )  # fmt: skip
            continue
        if waiting is not None or queued:
            queued.append(bid)
            continue
        if pr.head != entry.pr.head_oid or pr.checks == "pending":
            if candidates:
                queued.append(bid)
            else:
                waiting = bid
            continue
        candidates.append(bid)
        merges.append(
            Action("merge", bid, f"PR #{pr.number} at {pr.head[:12]}", pr=pr.number,
                   head=pr.head, train=repo)
        )  # fmt: skip
    if not members:
        return None, merges
    head = candidates[0] if candidates else waiting
    return Train(repo, head, tuple(candidates), tuple(queued), tuple(stepped), numbers), merges


def drive_pass(snap: Snapshot) -> Pass:
    """One pass: report foreign PRs, merge, close out, archive, dispatch, close sessions,
    then report duplicate candidates of newly finished waves — in that order, so a slot a
    merge frees is used in the same pass."""
    actions: list[Action] = []
    stages = dict(snap.stages)
    merging: set[str] = set()
    chosen = tuple(b for b in snap.batches if snap.selected is None or b.id in snap.selected)

    # 0. Report a PR on a batch branch that is not the batch's, once (gh#936). It
    # never reaches the queue, so it is never merged.
    for batch in chosen:
        for found in snap.foreign.get(batch.id, ()):
            if found.key not in snap.warned:
                actions.append(
                    Action("foreign", batch.id,
                           f"PR #{found.pr.number} on {found.pr.head_ref} is not this batch's: "
                           f"{found.reason}; it is never merged", pr=found.pr.number,
                           head=found.key)
                )  # fmt: skip

    # 1. Merge: one train per repo, walked in the stable dispatch order.
    by_repo: dict[str, list[QueueEntry]] = {}
    for entry in sorted(snap.queue, key=lambda e: _dispatch_key(e.batch)):
        bid = entry.batch.id
        if snap.selected is not None and bid not in snap.selected:
            continue
        by_repo.setdefault(snap.repos.get(bid, ""), []).append(entry)
    trains: list[Train] = []
    for repo in sorted(by_repo):
        train, merges = _walk_train(repo, by_repo[repo], snap)
        actions.extend(merges)
        merging.update(a.batch for a in merges if a.kind == "merge")
        if train is not None:
            trains.append(train)

    # 2. Close out. Recording a close-out that has already finished starts nothing and
    # writes nothing to the forge, so it reads every landed batch, selected or not
    # (gh#990); starting one, or recording one under way, follows the selection.
    closing = 0
    for batch in snap.batches:
        if stages.get(batch.id) not in LANDED or batch.id in merging:
            continue
        if closeout_event(batch) is not None:
            continue
        driven_now = snap.selected is None or batch.id in snap.selected
        if batch.id in snap.unverified:
            closing += driven_now
            continue
        # A close-out the driver did not start is recorded once, as an event: every
        # later pass, the board and `batch list` read it (gh#899, gh#900, gh#912).
        if batch.id in snap.archived:
            actions.append(Action("adopt", batch.id, "archived on the default branch already",
                                  archived=ARCHIVED_BY_UNKNOWN_PR))  # fmt: skip
            continue
        hand = snap.adopted.get(batch.id)
        if hand is not None and hand.state == "MERGED":
            actions.append(Action("adopt", batch.id, f"close-out PR #{hand.number} merged",
                                  pr=hand.number, archived=hand.number))  # fmt: skip
            continue
        if not driven_now:
            continue
        closing += 1
        if hand is not None:
            actions.append(Action("adopt", batch.id,
                                  f"close-out PR #{hand.number} ({hand.head_ref}) is open",
                                  pr=hand.number))  # fmt: skip
            continue
        due = closeout_due(
            released=batch.id in snap.released,
            merged_at=snap.merged_at.get(batch.id),
            now=snap.now,
        )
        if not due:
            continue
        item = closeout_item_id(snap.repos.get(batch.id, ""), batch.id)
        owed = not any(e.kind == "post_merge" for e in batch.events)
        if item in snap.existing:
            actions.append(Action("closeout", batch.id, f"record the live {item}", recorded=True))
        else:
            actions.append(Action("closeout", batch.id, f"start {item}", post_merge=owed))

    # 3. Archive.
    archives_blocked = 0
    for batch in chosen:
        event = closeout_event(batch)
        if event is None or stages.get(batch.id) not in LANDED:
            continue
        archives = snap.archives.get(snap.repos.get(batch.id, ""), ())
        mine = [p for p in archives if attributed(p, batch, event)]
        if is_finished(batch, stages[batch.id], archives):
            landed = next((p for p in mine if p.state == "MERGED"), None)
            if event.archived is None and landed is not None:
                # Merged, but not by this driver: recorded once, so `batch list` and
                # every later pass read it from the event (gh#882).
                actions.append(Action("adopt", batch.id, f"archive PR #{landed.number} merged",
                                      pr=landed.number, archived=landed.number))  # fmt: skip
            continue
        ready = [p for p in mine if p.state == "OPEN" and not p.draft and p.checks == "green"]
        default = snap.default_branch.get(snap.repos.get(batch.id, ""), "")
        good = next((p for p in ready if not _wrong_base(p, default)), None)
        if good is None and ready:
            # Merged only into the default branch, as the export (gh#1004, p4-r15): only
            # the operator can retarget it, so the batch is blocked, reported once.
            archives_blocked += 1
            wrong = ready[0]
            if wrong.head not in snap.warned:
                actions.append(
                    Action("warn", batch.id, f"archive PR #{wrong.number} ({wrong.head_ref}) "
                           f"{_wrong_base(wrong, default)}; it is never merged",
                           pr=wrong.number, head=wrong.head)
                )  # fmt: skip
            continue
        closing += 1
        if good is not None:
            actions.append(
                Action("archive", batch.id, f"PR #{good.number} ({good.head_ref})",
                       pr=good.number, head=good.head)
            )  # fmt: skip

    # 3b. Export each finished wave's state (pages-goal R13).
    exporting, exports_closing, exports_blocked = _export_actions(snap)
    actions.extend(exporting)
    closing += exports_closing

    # 4. Dispatch.
    # The cap counts every batch in flight, selected or not (review rg-3); the
    # summary's own figure is the selection's, which is what this drive waits on.
    occupants = {
        b.id for b in snap.batches if stages.get(b.id) in IN_FLIGHT and b.id not in merging
    }
    driven = {b.id for b in chosen}
    in_flight = sum(1 for b in driven if stages.get(b) in IN_FLIGHT) - len(merging)
    for bid in merging:
        stages[bid] = "merged"
    by_id = {b.id: b for b in snap.batches}
    pending, blocked = 0, exports_blocked + archives_blocked
    for batch in sorted(chosen, key=_dispatch_key):
        if stages.get(batch.id) != "proposed":
            continue
        dead = [
            f"{d} is {stages.get(d, 'unknown')}"
            for d in batch.after
            if d not in by_id or stages.get(d) in UNSATISFIABLE
        ]
        if dead:
            blocked += 1
            actions.append(Action("blocked", batch.id, f"waits on {'; '.join(dead)}"))
            continue
        if any(stages.get(d) != "merged" for d in batch.after):
            pending += 1
            continue
        if len(occupants) >= snap.max_inflight:
            # The summary counts only the selection, so a cap held by batches
            # outside it would otherwise read as idle (gh#913).
            pending += 1
            actions.append(Action("held", batch.id, f"the in-flight cap ({snap.max_inflight}) "
                                  f"is full: {', '.join(sorted(occupants))}"))  # fmt: skip
            continue
        occupants.add(batch.id)
        in_flight += 1
        actions.append(
            Action("dispatch", batch.id, f"wave {batch.wave if batch.wave is not None else '-'}")
        )

    # 5. Close the sessions of finished batches. Never work remaining (R10): the
    # summary does not see it.
    if snap.close_sessions:
        for batch in chosen:
            repo = snap.repos.get(batch.id, "")
            if not is_finished(
                batch, stages.get(batch.id, "proposed"), snap.archives.get(repo, ())
            ):
                continue
            live = tuple(
                i for i in (batch_item_id(repo, batch.id), closeout_item_id(repo, batch.id))
                if i in snap.sessions
            )  # fmt: skip
            if live:
                actions.append(Action("close", batch.id, f"sessions {', '.join(live)}", items=live))

    # 6. Report duplicate candidates once per wave observed going unfinished -> finished
    # (R10). Never inferred from a planned action: an archive merge may still fail.
    if snap.duplicate_groups > 0:
        n = snap.duplicate_groups
        groups = f"{n} duplicate candidate {'group' if n == 1 else 'groups'}"
        for wave in sorted(snap.finished & (snap.unfinished_waves or frozenset()), key=int):
            actions.append(
                Action("dedupe", "", f"{groups} after wave {wave} finished; run "
                       f"`{snap.dedupe_command}` to judge them")
            )  # fmt: skip

    merged = sum(1 for b in driven if stages.get(b) in LANDED)
    closing += len(merging)
    return Pass(
        actions=tuple(actions),
        summary=Summary(
            in_flight=in_flight,
            merged=merged,
            pending=pending,
            closing=closing,
            blocked=blocked,
            queued=sum(len(t.queued) for t in trains),
        ),
        trains=tuple(trains),
    )


# --------------------------------------------------------------- lines (R13)


def action_line(action: Action, outcome: str | None = None) -> str:
    """The one line an action prints, in plan mode (*outcome* None) and when acted:
    the same words in `--once` and loop mode."""
    if action.kind == "dedupe":  # names no batch
        return f"dedupe: {outcome or action.detail}"
    if action.wave is not None:
        return f"{action.kind} wave {action.wave} {action.batch}: {outcome or action.detail}"
    return f"{action.kind} {action.batch}: {outcome or action.detail}"


def summary_line(summary: Summary) -> str:
    line = (
        f"in flight {summary.in_flight}, merged {summary.merged}, "
        f"pending {summary.pending}, closing {summary.closing}"
    )
    if summary.queued:
        line += f", queued {summary.queued}"
    return line + (f", blocked {summary.blocked}" if summary.blocked else "")


def train_line(train: Train) -> str:
    """R6: `train <repo>: head a (PR #12) · then b (#13) · queued c (#14) · stepped over d`."""

    def ref(bid: str) -> str:
        return f"{bid} (#{train.numbers[bid]})" if bid in train.numbers else bid

    head = train.head
    parts = []
    if head is None:
        parts.append("no head")
    else:
        parts.append(f"head {head} (PR #{train.numbers[head]})" if head in train.numbers
                     else f"head {head}")  # fmt: skip
    then = train.candidates[1:]
    if then:
        parts.append("then " + ", ".join(ref(b) for b in then))
    if train.queued:
        parts.append("queued " + ", ".join(ref(b) for b in train.queued))
    if train.stepped:
        parts.append("stepped over " + ", ".join(ref(b) for b in train.stepped))
    return f"train {train.repo}: " + " · ".join(parts)
