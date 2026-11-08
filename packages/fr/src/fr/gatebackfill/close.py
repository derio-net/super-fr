"""A gate pass closes the backfill trackers it discharges (spec 2026-11-01-gate-backfill §H, R12),
and `fr gate backfill` closes the tracked-only ones whose key is discharged (spec
2026-11-08-sweep-fixes R10-R15).

`close_gate_trackers` is called by both pass routes (`fr gate pass` and the triage driver) after
`pass_gate`. It lives here, not in `fr.verification.labels`, which re-exports it, so the
`fr.gatebackfill` -> `fr.verification` direction never turns into a cycle. Forge writes go
through the `GhClient` only; a failure is reported in the result, never raised, and never
reverses the pass that already happened.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fr.archive_followups import OWED_ISSUE_FIELDS, is_owned_issue, owned_owed_key
from fr.gatebackfill import trackers
from fr.gatebackfill.model import Manifest, PlanClose
from fr.ghclient import GhClient, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS
from fr.labels import FR_OWED

if TYPE_CHECKING:
    from fr.archive import MergeEvidence
    from fr.gatebackfill.forge import BackfillForge

OPEN_LIMIT = 500
_FAILURES: tuple[type[Exception], ...] = (*FORGE_ERRORS, UnsupportedForgeOperation)
_LIST_FIELDS = f"{OWED_ISSUE_FIELDS},title"  # the tracked-only body restates the item's title
_EVIDENCE_TREES = (Path("docs/acceptance"), Path("docs/superpowers"))


# --- the evidence (R14) ---------------------------------------------------------------------


class EvidenceReader:
    """One checkout's evidence, each source read at most once per pass or run."""

    def __init__(self, root: Path, *, evidence: MergeEvidence | None = None) -> None:
        self.root = root
        self.evidence = evidence

    @cached_property
    def statuses(self) -> dict[str, str]:
        """Row id -> status; empty when the matrix is absent or unreadable."""
        from fr.acceptance.model import AcceptanceError, load_matrix

        try:
            matrix = load_matrix(self.root / "docs/acceptance/matrix.yaml")
        except (AcceptanceError, OSError):
            return {}
        return {r.id: r.status for r in matrix.rows}

    @cached_property
    def fixed_keys(self) -> frozenset[str]:
        """Keys with an `owed` entry whose effective state is `fixed`. Not `journal_owed`'s
        discharged set alone: that is every entry no longer open, a hand-written `refuted` too."""
        from fr.debt.engine import journal_owed
        from fr.journal.model import (
            IMPLEMENTED_JOURNALS_REL,
            JOURNALS_REL,
            JournalParseError,
            effective_finding_states,
            owed_key,
            parse_journal,
        )

        _, discharged, _ = journal_owed(self.root)
        found: set[str] = set()
        for base in (JOURNALS_REL, IMPLEMENTED_JOURNALS_REL):
            for path in sorted((self.root / base).glob("**/*.md")):
                try:
                    entries = parse_journal(path.read_text())
                except (JournalParseError, OSError, UnicodeDecodeError):
                    continue
                states = effective_finding_states(entries)
                for e in entries:
                    key = owed_key(e) if e.kind == "owed" else None
                    if key in discharged and states.get(e.id) == "fixed":
                        found.add(str(key))
        return frozenset(found)

    @cached_property
    def fold(self) -> Any:
        """The debt report with no forge: every source of the fold but issues themselves."""
        from fr.debt.engine import compute

        return compute(self.root, forge=None, now=datetime.now(UTC), evidence=self.evidence)

    def held(self, key: str) -> bool:
        """Whether a source other than an issue holds *key*, or the fold cannot rule that out:
        an unreadable journal or matrix, or for a plan the default ref its phases are read on."""
        report = self.fold
        if report.sources["journals"].why:
            return True
        matrix_read = report.sources["matrix"].state == "read"
        if not matrix_read and (self.root / "docs/acceptance/matrix.yaml").exists():
            return True
        if key.startswith("plan:") and report.sources["git"].state != "read":
            return True
        return any(item.key == key for item in report.owed)


def _plan_evidence(root: Path, name: str, phase: int) -> str | None:
    from fr.gatebackfill import candidates

    manual, ticked, _ = candidates._phase_facts(root, name, phase)
    done, _, total = ticked.partition("/")
    if manual is None or not total.isdigit() or int(total) < 1 or done != total:
        return None
    return f"plan {name} phase {phase} is complete ({ticked} steps ticked or n/a)"


def _spec_evidence(root: Path, slug: str, step: int) -> str | None:
    from fr.gatebackfill.candidates import find_spec
    from fr.journal.model import parse_journal, resolve_journal_read_path
    from fr.ops.holds import fold_step_outcomes

    if find_spec(root, slug) is None:
        return None
    journal = resolve_journal_read_path(root, "spec", slug)
    if not journal.is_file():
        return None
    kind = fold_step_outcomes(parse_journal(journal.read_text())).get(step)
    if kind is None or kind == "owed":
        return None
    return f"the spec journal {slug} records an outcome for Test Plan step {step}"


def _positive_evidence(reader: EvidenceReader, key: str) -> str | None:
    from fr.acceptance.model import DEBT_STATUSES
    from fr.gatebackfill.candidates import split_key

    if key in reader.fixed_keys:
        return f"the journal's owed entry for {key} was resolved fixed"
    kind, name, n = split_key(key)
    if kind == "row":
        status = reader.statuses.get(name)
        if status is None or status in DEBT_STATUSES:
            return None
        return f"row {name} is {status}"
    if kind == "plan" and n is not None:
        return _plan_evidence(reader.root, name, n)
    if kind == "spec" and n is not None:
        return _spec_evidence(reader.root, name, n)
    return None


def discharged_evidence(
    root: Path, key: str, *, reader: EvidenceReader | None = None
) -> str | None:
    """One line naming the evidence that *key* is discharged, else `None` (R14). Only positive
    evidence counts, and only with no source but an issue holding the key in the fold. An `issue:`
    key, a key nothing here can show and anything unreadable are `None`; this never raises."""
    from fr.gatebackfill.candidates import _key_usable

    if key.startswith("issue:") or not _key_usable(key, []):
        return None
    ev = reader if reader is not None else EvidenceReader(root)
    try:
        evidence = _positive_evidence(ev, key)
        return None if evidence is None or ev.held(key) else evidence
    except Exception:  # noqa: BLE001 — unreadable is "not shown", never "discharged" or a crash
        return None


def closes_blocked(root: Path, evidence: MergeEvidence) -> str | None:
    """Why no tracker may close from this checkout (R15), else `None`. The readers use the working
    tree, so HEAD must be the default ref as last fetched and the evidence trees clean: a printed
    discharge can leave its evidence uncommitted, and an older HEAD can show a status that later
    moved back."""
    from subprocess import CalledProcessError

    from fr.archive import paths_dirty
    from fr.gatebackfill.forge import Git

    if evidence.ref is None:
        return f"no default ref resolves ({evidence.ref_error or 'unknown'})"
    git = Git(root)
    head, tip = git.rev("HEAD"), git.rev(evidence.ref.ref)
    if head is None or head != tip:
        return f"HEAD is not {evidence.ref.ref} as last fetched"
    try:
        dirty = paths_dirty(root, *_EVIDENCE_TREES)
    except (CalledProcessError, OSError) as exc:
        return f"git cannot say whether the evidence trees are clean: {exc}"
    if dirty:
        return f"{' or '.join(p.as_posix() for p in _EVIDENCE_TREES)} has uncommitted changes"
    return None


# --- the pass (R10-R12) ---------------------------------------------------------------------


@dataclass
class CloseReport:
    """What a pass did (or, on a dry run, would do) to the PR's backfill trackers."""

    closed: list[int] = field(default_factory=list)  # fr-owned trackers (closed, or would be)
    kept: list[int] = field(default_factory=list)  # `--keep`: now tracked only (or would be)
    adopt_commands: list[str] = field(default_factory=list)  # `gh issue close` for adopted ones
    discharge: list[str] = field(default_factory=list)  # one command per key, §H step 4
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def found(self) -> bool:
        return bool(self.closed or self.kept or self.adopt_commands)

    def summary(self) -> str:
        """One clause for a one-line caller (the driver)."""
        if not self.found and not self.errors:
            return ""
        verb = "would close" if self.dry_run else "closed"
        parts = (
            [f"{verb} trackers {', '.join(f'#{n}' for n in self.closed)}"] if self.closed else []
        )
        if self.kept:
            parts.append(f"kept {', '.join(f'#{n}' for n in self.kept)} (still owed)")
        if self.adopt_commands:
            parts.append(f"{len(self.adopt_commands)} adopted issue(s) to close by hand")
        if self.errors:
            parts.append(f"{len(self.errors)} tracker error(s): {'; '.join(self.errors)}")
        return "; ".join(parts)

    def lines(self) -> list[str]:
        out: list[str] = []
        verb = "would close" if self.dry_run else "closed"
        out += [f"{verb} tracker #{n}" for n in self.closed]
        keep = "would keep" if self.dry_run else "kept"
        out += [f"{keep} #{n} open, tracked only: its key is still owed" for n in self.kept]
        if self.adopt_commands:
            out.append("adopted issues are never closed by fr; close each yourself:")
            out += [f"  {c}" for c in self.adopt_commands]
        if self.discharge:
            out.append("the owed work itself is discharged separately:")
            out += [f"  {line}" for c in self.discharge for line in c.splitlines()]
        out += [f"tracker error: {e}" for e in self.errors]
        return out


@dataclass
class _Pass:
    """One gate pass over the PR's trackers."""

    client: GhClient
    repo: str
    pr: int
    gate: str
    notes: str
    me: str
    report: CloseReport
    root: Path | None
    keep: frozenset[str]
    dry_run: bool
    reader: EvidenceReader | None

    @property
    def said(self) -> str:
        return f"Gate {self.gate} passed on #{self.pr}: {self.notes}"

    def discharge_line(self, key: str) -> str:
        assert self.root is not None
        return trackers.discharge_command(key, repo_root=self.root).replace("\n", "; ")

    def position(self, key: str) -> str:
        """What a closing comment says of *key* (R12): evidence, the command, or nothing."""
        if self.root is None:
            return ""
        evidence = discharged_evidence(self.root, key, reader=self.reader)
        if evidence is not None:
            return f"`{key}` is already discharged: {evidence}"
        return f"`{key}` is still owed, to discharge it: `{self.discharge_line(key)}`"

    def closing_comment(self, keys: list[str]) -> str:
        return "; ".join([self.said, *filter(None, (self.position(k) for k in keys))])

    def discharge(self, key: str) -> None:
        """Print *key*'s discharge command, unless it is already discharged."""
        if self.root is None or discharged_evidence(self.root, key, reader=self.reader):
            return
        line = trackers.discharge_command(key, repo_root=self.root)
        if line not in self.report.discharge:
            self.report.discharge.append(line)


def close_gate_trackers(
    client: GhClient,
    repo: str,
    pr: int,
    gate: str,
    notes: str,
    *,
    root: Path | None = None,
    dry_run: bool = False,
    keep: frozenset[str] = frozenset(),
) -> CloseReport:
    """Close the open `fr:owed` issues fr owns whose gate marker names PR *pr* and *gate*; a key
    in *keep* is converted to the tracked-only form instead (R10)."""
    report = CloseReport(dry_run=dry_run)
    try:
        me = client.viewer_login()
        issues = client.list_issues(repo, "open", OPEN_LIMIT, _LIST_FIELDS, labels=[FR_OWED.name])
    except _FAILURES as exc:
        report.errors.append(f"cannot list the open {FR_OWED.name} issues of {repo}: {exc}")
        return report
    if not me:  # p3-r4: no identity to match, and a ghost's empty author would match it
        report.errors.append(f"the viewer's login on {repo} is empty: closing nothing")
        return report
    reader = EvidenceReader(root) if root is not None else None
    run = _Pass(client, repo, pr, gate, notes, me, report, root, keep, dry_run, reader)
    for issue in issues:
        try:
            _one(run, issue)
        except _FAILURES as exc:
            report.errors.append(f"issue #{issue.get('number')}: {exc}")
    return report


def _one(run: _Pass, issue: dict[str, Any]) -> None:
    number = issue.get("number")
    if not isinstance(number, int) or isinstance(number, bool):
        return
    key = owned_owed_key(issue, run.me)
    if key is not None:
        if trackers.fr_gate_marker(str(issue.get("body") or "")) == (run.gate, run.pr):
            if key in run.keep:
                _keep_owned(run, issue, number, key)
            else:
                _close_owned(run, number, key)
    elif not trackers.is_ours(issue, run.me):  # else fr's own, but not a backfill tracker
        _adopted(run, number)  # a foreign issue: one read, adopt only


def _close_owned(run: _Pass, number: int, key: str) -> None:
    if not run.dry_run:
        run.client.close_issue(run.repo, number, run.closing_comment([key]))
    run.report.closed.append(number)
    run.discharge(key)


def _keep_owned(run: _Pass, issue: dict[str, Any], number: int, key: str) -> None:
    """Comment first, then rewrite: a failure between the two leaves it held, so a retry repeats
    the work and at worst a comment, and never loses the key."""
    if run.root is None:
        run.report.errors.append(f"issue #{number}: --keep {key} needs a checkout; left as it is")
        return
    if not run.dry_run:
        title = str(issue.get("title") or "").removeprefix("Owed: ") or key
        run.client.comment_issue(
            run.repo,
            number,
            f"{run.said}; `{key}` is still owed, so this stays open as its tracker, "
            f"to discharge it: `{run.discharge_line(key)}`",
        )
        run.client.edit_issue_body(
            run.repo,
            number,
            trackers.passed_tracker_body(key, title, run.gate, run.pr, repo_root=run.root),
        )
    run.report.kept.append(number)
    run.discharge(key)


def _adopted(run: _Pass, number: int) -> None:
    comments = run.client.list_issue_comments(run.repo, number)
    here = _adopt_states_for(comments, run.me, run.gate, run.pr)
    to_keep = [k for k, state in here.items() if state == "held" and k in run.keep]
    if to_keep:
        _keep_adopted(run, number, to_keep)
    elif here and "passed" not in here.values():  # a tracked-only comment overrides (R10)
        keys = list(here)
        run.report.adopt_commands.append(close_command(number, run.repo, run.closing_comment(keys)))
        for key in keys:
            run.discharge(key)


def _keep_adopted(run: _Pass, number: int, keys: list[str]) -> None:
    if run.root is None:
        run.report.errors.append(f"issue #{number}: --keep needs a checkout; left as it is")
        return
    for key in keys:
        if not run.dry_run:
            text = trackers.adopt_passed_comment(key, run.gate, run.pr, repo_root=run.root)
            run.client.comment_issue(run.repo, number, text)
        run.discharge(key)
    run.report.kept.append(number)


def _adopt_states_for(
    comments: list[dict[str, Any]], me: str, gate: str, pr: int
) -> dict[str, str]:
    return {
        key: state
        for (key, g, n), state in trackers.adopt_states(comments, me).items()
        if (g, n) == (gate, pr)
    }


def close_command(number: int, repo: str, comment: str) -> str:
    """The `gh issue close` an adopted issue's owner runs: fr never closes it."""
    return f"gh issue close {number} --repo {shlex.quote(repo)} --comment {shlex.quote(comment)}"


def held_keys(client: GhClient, repo: str, pr: int, gate: str) -> set[str]:
    """Every key a tracker of this PR and gate holds, held or already tracked only: what `--keep`
    may name (R11). Raises the forge's error, because the caller refuses before any write."""
    me = client.viewer_login()
    if not me:
        return set()
    found: set[str] = set()
    for issue in client.list_issues(repo, "open", OPEN_LIMIT, _LIST_FIELDS, labels=[FR_OWED.name]):
        key = owned_owed_key(issue, me)
        body = str(issue.get("body") or "")
        if key is not None:
            if (gate, pr) in (trackers.fr_gate_marker(body), trackers.fr_passed_marker(body)):
                found.add(key)
        elif not trackers.is_ours(issue, me):
            comments = client.list_issue_comments(repo, int(issue["number"]))
            found |= set(_adopt_states_for(comments, me, gate, pr))
    return found


# --- the backfill's closes (R13, R15) -------------------------------------------------------


@dataclass
class CloseListing:
    closes: list[PlanClose] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    adopted_refs: set[str] = field(default_factory=set)
    """Foreign issues this account's tracked-only comment made trackers: never candidates."""


def other_holder(issues: list[dict[str, Any]], me: str, key: str, number: object) -> str | None:
    """A ref of an open owed issue fr does not own whose body also carries *key*'s marker: to the
    fold it is another source, so *key* is not held by its own tracker alone (R14)."""
    from fr.debt.engine import OWED_MARKER
    from fr.debt.forge import OWED_LABELS

    for i in issues:
        if i.get("number") == number or owned_owed_key(i, me) is not None:
            continue
        labels = {
            str(lab.get("name", "")) if isinstance(lab, dict) else str(lab)
            for lab in i.get("labels") or []
        }
        m = OWED_MARKER.search(str(i.get("body") or ""))
        if m and m.group(1) == key and labels & set(OWED_LABELS):
            return f"#{i.get('number')}"
    return None


def list_closes(
    root: Path,
    forge: BackfillForge,
    *,
    evidence: MergeEvidence,
    manifest: Manifest | None = None,
) -> CloseListing:
    """The tracker closes a dry run records (R13, R15), built from the open issues and never from
    the candidates: a key resolved in its journal has already left the fold. A key the manifest
    names as a new item is the manifest's claim that it is owed, so it never closes here."""
    out = CloseListing()
    try:
        me = forge.viewer_login()
        issues = forge.open_issues()
    except Exception as exc:  # noqa: BLE001 — a failed read closes nothing, and says so
        out.notes.append(f"trackers to close not read: {type(exc).__name__}: {exc}")
        return out
    if not me:
        return out
    claimed = {m.key for m in (manifest.items if manifest else []) if m.kind is not None}
    owned: list[tuple[str, dict[str, Any]]] = []
    adopted: list[tuple[str, int, dict[str, Any], set[tuple[str, int]]]] = []
    for i in issues:
        ref = str(i.get("ref"))
        key = owned_owed_key(i, me)
        if key is not None:
            if trackers.fr_passed_marker(str(i.get("body") or "")) is not None:
                owned.append((key, i))
            continue
        if FR_OWED.name not in i.get("labels", []) or is_owned_issue(i, me):
            continue
        try:
            comments = forge.issue_comments(int(i["number"]))
        except Exception as exc:  # noqa: BLE001 — one unreadable issue, the rest go on
            out.notes.append(f"{ref}: comments not read: {type(exc).__name__}: {exc}")
            continue
        posted = trackers.adopt_discharged(comments, me)
        for (k, _gate, pr), state in trackers.adopt_states(comments, me).items():
            if state == "passed":
                out.adopted_refs.add(ref)
                adopted.append((k, pr, i, posted))
    if not owned and not adopted:
        return out
    blocked = closes_blocked(root, evidence)
    if blocked is not None:
        out.notes.append(f"no tracker closes: {blocked}")
        return out
    reader = EvidenceReader(root, evidence=evidence)
    for key, i in owned:
        if key in claimed:
            continue
        shown = _shown(root, key, i, issues, me, reader, out)
        if shown is not None:
            ref = str(i.get("ref"))
            out.closes.append(PlanClose(key=key, ref=ref, adopted=False, evidence=shown))
    for key, pr, i, posted in adopted:
        if key in claimed:
            continue
        shown = _shown(root, key, i, issues, me, reader, out)
        if shown is None:
            continue
        ref = str(i.get("ref"))
        if (key, pr) in posted:
            out.notes.append(f"{key}: discharged; close {ref} yourself: {gh_close_for(ref, shown)}")
        else:
            out.closes.append(PlanClose(key=key, ref=ref, adopted=True, evidence=shown))
    return out


def _shown(
    root: Path,
    key: str,
    issue: dict[str, Any],
    issues: list[dict[str, Any]],
    me: str,
    reader: EvidenceReader,
    out: CloseListing,
) -> str | None:
    shown = discharged_evidence(root, key, reader=reader)
    if shown is None:
        return None
    holder = other_holder(issues, me, key, issue.get("number"))
    if holder is not None:
        out.notes.append(f"{key}: discharged, but {holder} also carries its marker: not closing")
        return None
    return shown


def gh_close_for(ref: str, evidence: str) -> str:
    """The printed close command of an adopted issue whose key is discharged (R13)."""
    repo, _, number = ref.partition("#")
    return close_command(int(number), repo, f"Discharged: {evidence}")
