"""The wave's state-export step of the drive pass (wave-driver spec §I, step 3b), split out
of `batch_drive` (spec 2026-11-27-triage-leaves-split R2), which re-exports every name here.

Pure: no git, no forge, no clock. It reads the pass's `Snapshot` only for its annotations.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from fr.triage.batch_drive_types import CONFLICTING, Action, Admitted, LivePr, _wrong_base
from fr.triage.model import Batch, Export

if TYPE_CHECKING:  # `fr.triage.batch_drive` imports this module
    from fr.triage.batch_drive import Snapshot

EXPORT_PREFIX = "chore/triage-state-"  # + `<scope id>-wave-<N>` (gh#1101)
"""The head of a wave's state-export PR (pages-goal R13). Not in `ARCHIVE_PREFIXES`, so
archive attribution can never claim an export PR."""


def export_branch(wave: str, scope: str) -> str:
    """The head a wave's state-export PR is pushed to; the driver of scope id *scope*
    owns it. The scope id keeps two scopes of one repo (another host's driver) off each
    other's export PRs (gh#1101)."""
    return f"{EXPORT_PREFIX}{scope}-wave-{wave}"


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


def export_wave_of(head_ref: str, scope: str) -> str | None:
    """The wave key a `chore/triage-state-<scope>-wave-<N>` head of scope id *scope*
    names, or None: another scope's export head is never this scope's."""
    prefix = f"{EXPORT_PREFIX}{scope}-wave-"
    wave = head_ref.removeprefix(prefix) if head_ref.startswith(prefix) else ""
    return wave if wave.isdigit() else None


def export_target(
    repo: str,
    batches: Iterable[Batch],
    repos: Mapping[str, str],
    finished: frozenset[str],
    exports: Iterable[Export],
    orphans: Sequence[LivePr] = (),
    *,
    scope: str,
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
    named = [(w, o) for o in orphans if (w := export_wave_of(o.head_ref, scope)) is not None]
    if named:
        wave, orphan = max(named, key=lambda pair: _wave_order(pair[0]))
        return ExportTarget(repo, wave, tuple(owed), None, orphan)
    return ExportTarget(repo, owed[-1], tuple(owed), None)


def _export_row(
    repo: str,
    wave: str,
    done: Export | None,
    live: LivePr | None,
    root: str,
    default: str = "",
    *,
    scope: str,
) -> tuple[Action | Admitted | None, ExportCount]:
    """One row of §I's table: the action for *repo*'s finished *wave*, given its
    recorded export (*done*), the live PR and the export directory *root*
    (`<path>/<scope>`), and how the summary counts it. The driver auto-merges this
    PR unreviewed, so it adopts or merges one only when every file it changes is under
    *root*, and merges only at the head it recorded (p4-sec-unpinned-merge)."""
    head = export_branch(wave, scope)
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
    elif live.mergeable == CONFLICTING:
        # No session owns it: straight to the operator, with a recorded stop (R12).
        return Action("export-conflict", repo, f"export PR #{live.number} conflicts with "
                      "the default branch; the operator must act", pr=live.number,
                      head=live.head, wave=wave), "blocked"  # fmt: skip
    elif live.draft:
        why = "is a draft"
    elif live.checks == "failing":
        why = f"has failing checks: {', '.join(live.failing) or 'unknown'}"
    if why:
        return Action("warn", repo, f"export PR #{live.number} {why}; the operator must act",
                      pr=live.number, wave=wave), "blocked"  # fmt: skip
    if live.checks != "green":
        return None, "closing"  # checks pending: wait
    # Admitted at the RECORDED head, never a later one: they are equal here, and the queue
    # builds exactly this head (p4-sec-unpinned-merge, R32).
    return Admitted("export", repo, live, wave=None, at=done.at), "closing"


def _export_actions(snap: Snapshot) -> tuple[list[Action], list[Admitted], int, int]:
    """§I step 3b: a group or org scope that opts in is warned once; then, for each
    opted-in repo, `_export_row` on its `export_target`: one PR per repo, never one per
    wave. Returns the actions, the export PRs admitted to a queue (R32), and how many owed
    export PRs are closing (acting or waiting) and blocked (warned)."""
    actions = [
        Action("warn", repo, f"export is per repo scope; run drive with --repo {repo}")
        for repo in sorted(snap.export_refused)
    ]
    counts = {"closing": 0, "blocked": 0}
    admitted: list[Admitted] = []
    for repo in sorted(snap.export_path):
        target = export_target(
            repo, snap.batches, snap.repos, snap.finished, snap.exports,
            snap.export_orphans.get(repo, ()), scope=snap.scope_id,
        )  # fmt: skip
        if target is None:
            continue
        live = (
            target.orphan if target.recorded is None else snap.export_prs.get((repo, target.wave))
        )
        action, count = _export_row(
            repo, target.wave, target.recorded, live, snap.export_path[repo],
            snap.default_branch.get(repo, ""), scope=snap.scope_id,
        )  # fmt: skip
        if isinstance(action, Admitted):
            admitted.append(action)
        elif action is not None:
            if action.kind == "export":
                action = replace(action, covers=target.covers)
                if len(target.covers) > 1:
                    action = replace(action, detail=f"{action.detail} (covers waves "
                                     f"{', '.join(target.covers)})")  # fmt: skip
            actions.append(action)
        if count is not None:
            counts[count] += 1
        if isinstance(action, Action) and action.kind == "export" and target.orphan is not None:
            actions.extend(_stale_orphans(repo, snap, target.orphan))
    return actions, admitted, counts["closing"], counts["blocked"]


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
