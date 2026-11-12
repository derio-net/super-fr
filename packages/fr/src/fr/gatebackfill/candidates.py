"""What a repo owes and under which gate (spec 2026-11-01-gate-backfill §B, §D).

`collect_candidates` takes `fr debt`'s fold of the whole repo (`debt.engine.compute(...).owed`)
plus the operator manifest, and decorates each item with its gate (`gate_for`), its default
decision, the age and ticked counts of a phase, and the open issues that merely look like its
tracker. Nothing here writes; the forge is a read-only port.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from fr.archive_followups import owned_owed_key
from fr.gatebackfill.forge import OPEN_ISSUE_LIMIT, BackfillForge, Git
from fr.gatebackfill.model import BackfillError, Manifest, ManifestItem, PlanEntry, PlanFile, PrHit
from fr.gatebackfill.trackers import fr_gate_marker, fr_passed_marker, is_ours
from fr.triage.debt import has_marker

if TYPE_CHECKING:
    from fr.archive import MergeEvidence

PLANS_REL = Path("docs/superpowers/plans")
IMPLEMENTED_PLANS_REL = Path("docs/superpowers/implemented/plans")
SPECS_REL = Path("docs/superpowers/specs")
IMPLEMENTED_SPECS_REL = Path("docs/superpowers/implemented/specs")
MANIFEST_HINT = "in a manifest entry for this key (--from), not in the plan file"
"""Where an operator's delivering PR goes: `--yes` re-resolves a plan file's `pr:` (R15)."""


class Candidate(BaseModel):
    """One owed item, with everything the later stages need to resolve and apply it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    source: str
    title: str
    how: str = ""
    ref: str = ""
    gate: str | None = None
    walk_only: bool = False
    decision: str = "owed"
    why: str = ""
    age_days: int | None = None
    ticked: str = ""
    tracker_ref: str | None = None
    tracker_candidates: tuple[str, ...] = ()
    plans: tuple[str, ...] = ()
    """Plan directory names the delivering PR is looked for through."""
    spec_rel: str | None = None
    issue_number: int | None = None
    manifest_pr: int | None = None
    row_id: str | None = None

    def to_entry(
        self,
        pr: PrHit | None = None,
        *,
        ambiguous: tuple[int, ...] = (),
        why: str = "",
    ) -> PlanEntry:
        """The plan-file entry for this candidate, with the delivering PR found for it. An
        ambiguity, a planning PR or no gate each default the decision to `review`."""
        decision, reasons = self.decision, [self.why] if self.why else []
        if why:
            reasons.append(why)
        if pr is not None and pr.planning:
            decision = "review"
            reasons.append(f"planning PR; set the delivering one as pr: {MANIFEST_HINT}")
        if ambiguous:
            numbers = ", ".join(f"#{n}" for n in ambiguous)
            decision = "review"
            reasons.append(f"several merged PRs: {numbers}; pick one as pr: {MANIFEST_HINT}")
        return PlanEntry(
            key=self.key,
            title=self.title,
            gate=self.gate,
            pr=pr,
            ambiguous=list(ambiguous),
            tracker={"ref": self.tracker_ref, "candidates": list(self.tracker_candidates)},  # type: ignore[arg-type]
            age_days=self.age_days,
            ticked=self.ticked,
            walk_only=self.walk_only,
            why="; ".join(r for r in reasons if r),
            decision=decision,
            default_decision=decision,
            computed_gate=self.gate,
            issue=self.issue_number,
        )


def split_key(key: str) -> tuple[str, str, int | None]:
    """`(kind, name, n)` of an owed key: `plan:<name>#p<n>`, `spec:<slug>#step<n>`, `row:<id>`
    or `issue:<owner/repo>#<n>` (name `owner/repo`, n the issue number)."""
    kind, _, rest = key.partition(":")
    if kind == "row":
        return kind, rest, None
    name, _, tail = rest.rpartition("#")
    digits = re.sub(r"^(?:step|p)", "", tail)
    return kind, name, int(digits) if digits.isdigit() else None


def gate_for(
    key: str,
    *,
    manifest: ManifestItem | None = None,
    manual_phase: bool | None = None,
    spec_run_gate: str | None = None,
) -> str | None:
    """The post-merge gate of one candidate, or `None` (spec §D's table). Pure: the phase's
    tag and the spec's run gate are read by the caller."""
    kind, _, _ = split_key(key)
    if manifest is not None:
        if manifest.gate is not None:
            return manifest.gate
        return {"op": "devops", "walk": "tester", "closed-issue": "tester"}.get(manifest.kind or "")
    if kind == "row":
        return "tester"
    if kind == "plan":
        return "devops" if manual_phase else None
    if kind == "spec":
        if spec_run_gate is None:
            return None
        return "devops" if spec_run_gate == "devops" else "tester"
    return None


# --- repo reads -----------------------------------------------------------------------------


def find_spec(root: Path, slug: str) -> str | None:
    """The repo-relative path of the spec whose journal slug is *slug*, live then archived."""
    from fr.archive import spec_slug_of

    for rel in (SPECS_REL, IMPLEMENTED_SPECS_REL):
        d = root / rel
        if d.is_dir():
            for p in sorted(d.glob("*.md")):
                if spec_slug_of(p) == slug:
                    return (rel / p.name).as_posix()
    return None


def spec_plans(root: Path, spec_rel: str) -> tuple[str, ...]:
    """Plan directories the spec's `## Implementation Plans` table names, that this repo holds."""
    try:
        text = (root / spec_rel).read_text()
    except OSError:
        return ()
    m = re.search(r"^## Implementation Plans\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if m is None:
        return ()
    found: list[str] = []
    for line in m.group(1).splitlines():
        for cell in line.split("|"):
            name = cell.strip().strip("`")
            if re.fullmatch(r"[\w.-]+", name) and name not in found:
                if (root / PLANS_REL / name).is_dir() or (
                    root / IMPLEMENTED_PLANS_REL / name
                ).is_dir():
                    found.append(name)
    return tuple(found)


def row_spec(root: Path, origins: tuple[str, ...]) -> str | None:
    """The spec file a row's `origin` refs name, when this repo holds it (live or archived)."""
    from fr.acceptance.logical import origin_spec_path

    for origin in origins:
        path = origin_spec_path(origin, root)
        if path is None:
            continue
        for cand in (Path(path), IMPLEMENTED_SPECS_REL / Path(path).name):
            if (root / cand).is_file():
                return cand.as_posix()
    return None


def _plan_dir(root: Path, name: str) -> tuple[Path | None, bool]:
    live = root / PLANS_REL / name
    if live.is_dir():
        return live, False
    archived = root / IMPLEMENTED_PLANS_REL / name
    return (archived, True) if archived.is_dir() else (None, False)


def _phase_facts(root: Path, name: str, phase: int) -> tuple[bool | None, str, bool]:
    """`(manual?, "k/n" ticked, archived)` of one phase; manual is `None` when unreadable."""
    from fr.parser import PlanSchemaError, parse

    d, archived = _plan_dir(root, name)
    if d is None:
        return None, "", False
    try:
        plan = parse(d, enforce_fr_version=False)
    except PlanSchemaError:
        return None, "", archived
    for doc in plan.phases:
        if doc.phase.number == phase:
            steps = doc.state.steps.values()
            done = sum(1 for s in steps if s.state in ("x", "-"))
            return doc.phase.tag == "manual", f"{done}/{len(steps)}", archived
    return None, "", archived


def _age_days(git: Git, ref: str | None, root: Path, name: str, now: datetime) -> int | None:
    if ref is None:
        return None
    d, archived = _plan_dir(root, name)
    rel = (IMPLEMENTED_PLANS_REL if archived else PLANS_REL) / name
    iso = git.last_commit(ref, rel.as_posix())
    if iso is None:
        return None
    try:
        return (now - datetime.fromisoformat(iso)).days
    except ValueError:
        return None


def _as_issue(i: dict[str, Any]) -> dict[str, object]:
    return {k: i.get(k) for k in ("number", "body", "author", "labels")}


def _lookalikes(
    c: Candidate,
    issues: list[dict[str, Any]],
    manifest: ManifestItem | None,
    owned: frozenset[str] = frozenset(),
) -> list[str]:
    """Open issues that read like this item's tracker but that fr did not write: suggestions."""
    kind, name, n = split_key(c.key)
    found = []
    for i in issues:
        ref = str(i.get("ref"))
        if ref == c.ref or ref == c.tracker_ref or ref in owned:
            continue
        if manifest is not None and manifest.issue is not None:
            if str(i.get("number")) == str(manifest.issue):  # the manifest names it: always a hit
                found.append(ref)
                continue
        if has_marker(str(i.get("body") or "")):
            continue  # R7: a debt digest is never a tracker look-alike, whoever wrote it
        text = f"{i.get('title', '')}\n{i.get('body', '')}"
        hit = False
        if kind == "plan" and name in text and n is not None:
            hit = re.search(rf"(?i)\bphase {n}\b|\bp{n}\b", text) is not None
        elif kind == "row":
            hit = re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w.-])", text) is not None
        if hit:
            found.append(ref)
    return found


def _key_usable(key: str, notes: list[str]) -> bool:
    """Whether *key* may be used at all: a key from an issue marker is text anyone wrote, and
    its name reaches the filesystem (`_plan_dir`) and argv, so only the canonical shape, with
    no dot-only name, passes."""
    from fr.journal.model import OWED_KEY_RE

    name = key.partition(":")[2].rpartition("#")[0] or key.partition(":")[2]
    if OWED_KEY_RE.match(key) and name.strip(".") != "":
        return True
    notes.append(f"{key}: owed key dropped (not a valid owed key)")
    return False


# --- the collection -------------------------------------------------------------------------


def collect_candidates(
    repo_root: Path,
    *,
    forge: BackfillForge | None,
    now: datetime,
    manifest: Manifest | None = None,
    previous: PlanFile | None = None,
    stale_days: int | None = None,
    evidence: MergeEvidence | None = None,
) -> tuple[list[Candidate], list[str]]:
    """`(candidates, notes)` for the whole repo, sorted by key. *notes* are degradations that
    stay out of the candidates (an unreadable issue list, a dropped tracker)."""
    from fr.acceptance.fold import load_effective
    from fr.acceptance.model import AcceptanceError
    from fr.archive import merge_evidence
    from fr.debt.engine import compute
    from fr.verification.exit import exit_for_spec
    from fr.verification.spec_section import SectionError

    notes: list[str] = []
    ev = evidence if evidence is not None else merge_evidence(repo_root, fetch=False)
    ref = ev.ref.ref if ev.ref else None
    report = compute(repo_root, forge=forge, now=now, stale_days=stale_days, evidence=ev)
    days = report.stale_days
    git = Git(repo_root)
    try:
        matrix = load_effective(repo_root)
        origins = {r.id: tuple(r.origin) for r in matrix.rows}
    except (AcceptanceError, OSError):
        origins = {}
    issues: list[dict[str, Any]] = []
    if forge is not None:
        try:
            issues = forge.open_issues()
            if len(issues) >= OPEN_ISSUE_LIMIT:
                notes.append(
                    f"{len(issues)} open issues read, the cap: trackers and look-alikes past it "
                    "are not seen"
                )
        except Exception as exc:  # noqa: BLE001 — a failed read degrades look-alikes only
            notes.append(f"open issues not read: {type(exc).__name__}: {exc}")
    me = ""
    if forge is not None:
        try:
            me = forge.viewer_login()
        except Exception as exc:  # noqa: BLE001 — no identity: no issue is trusted as ours
            notes.append(f"viewer login not read: {type(exc).__name__}: {exc}")
    owned_trackers = {
        k: str(i.get("ref")) for i in issues if (k := owned_owed_key(_as_issue(i), me))
    }
    ours = {str(i.get("ref")) for i in issues if is_ours(i, me)}
    adopted = {r for e in (previous.entries if previous else []) if (r := e.adopt_ref)}
    by_ref = {str(i.get("ref")): i for i in issues}
    man = {m.key: m for m in (manifest.items if manifest else [])}
    fold_source = {o.key: o.source for o in report.owed}

    def _taken_back(key: str) -> bool:
        """A manifest NEW item may take a key back only when the fold holds it through fr's own
        tracker alone (source `issue`); a row, plan or journal that also has a tracker keeps it
        (p2-r3)."""
        item = man.get(key)
        held_by_tracker = fold_source.get(key) == "issue" and key in owned_trackers
        return item is not None and item.kind is not None and held_by_tracker

    for key, entry in man.items():
        _check_manifest_item(entry, held=key in fold_source, taken_back=_taken_back(key))

    # a key held only by fr's own tracker (filed by an earlier `--yes`) is the manifest's again:
    # the manifest supplies its gate and PR, so a second `--yes` over it stays idempotent (R7)
    sources: list[tuple[str, str, str, str, str]] = [
        (o.key, o.source, o.title, o.how, o.ref) for o in report.owed if not _taken_back(o.key)
    ]
    sources += [(m.key, "manifest", m.title, "", "") for m in man.values() if m.kind is not None]
    sources = [src for src in sources if _key_usable(src[0], notes)]
    out: list[Candidate] = []
    for key, source, title, how, iref in sources:
        item = man.get(key)
        # the manifest item when it is a new one; an override only sets pr, gate and walk_only
        new = item if item is not None and item.kind is not None else None
        kind, name, n = split_key(key)
        fields: dict[str, Any] = {
            "key": key, "source": source, "title": title, "how": how, "ref": iref,
            "tracker_ref": owned_trackers.get(key),
            "manifest_pr": item.pr if item else None,
        }  # fmt: skip
        why: list[str] = []
        decision = "owed"
        manual: bool | None = None
        run_gate: str | None = None
        walk_only = kind == "row"
        if kind == "row":
            fields["row_id"] = name
            fields["spec_rel"] = row_spec(repo_root, origins.get(name, ()))
        elif kind == "plan" and n is not None:
            manual, ticked, archived = _phase_facts(repo_root, name, n)
            fields["plans"] = (name,)
            fields["ticked"] = ticked
            fields["age_days"] = _age_days(git, ref, repo_root, name, now)
            if manual is False:
                why.append("unfinished agentic phase")
            elif manual is True and fields["age_days"] is not None and fields["age_days"] > days:
                why.append(f"stale: plan idle {fields['age_days']}d (> {days}d), ticked {ticked}")
        elif kind == "spec":
            spec_rel = find_spec(repo_root, name)
            fields["spec_rel"] = spec_rel
            if spec_rel is not None:
                try:
                    run_gate = exit_for_spec(repo_root, spec_rel).run_gate
                except (SectionError, AcceptanceError, OSError) as exc:
                    why.append(f"spec exit unreadable: {exc}")
            else:
                why.append("spec file not found in this checkout")
        elif kind == "issue":
            fields["issue_number"] = n
            if item is not None and item.issue is not None:
                fields["issue_number"] = item.issue
        if item is not None and item.issue is not None:
            fields["issue_number"] = item.issue
        if fields.get("spec_rel") and not fields.get("plans"):
            fields["plans"] = spec_plans(repo_root, fields["spec_rel"])
        if item is not None and item.walk_only is not None:
            walk_only = item.walk_only
        elif new is not None:
            walk_only = new.kind in ("walk", "closed-issue")
        gate = gate_for(key, manifest=new, manual_phase=manual, spec_run_gate=run_gate)
        if new is None and item is not None and item.gate is not None:
            gate = item.gate
        if gate is None and not why:
            why.append("no gate: set gate: in the plan file")
        if why:
            decision = "review"
        cand = Candidate(
            **fields, gate=gate, walk_only=walk_only, decision=decision, why="; ".join(why)
        )
        out.append(cand)

    out = _settle_trackers(
        out, issues, by_ref, man, adopted, ours, notes, frozenset(owned_trackers.values())
    )
    return sorted(out, key=lambda c: c.key), notes


def _check_manifest_item(item: ManifestItem, *, held: bool, taken_back: bool) -> None:
    """Refuse a manifest entry that is neither a valid new item nor a valid override (gh#1369):
    a held key takes only an override, an unheld one only a new item."""
    key = item.key
    if item.kind is None:
        if not held:
            raise BackfillError(
                f"manifest entry {key}: `fr debt` does not hold this key, so it is a new item "
                "and needs `kind:` and `title:`"
            )
        stray = [f for f in ("title", "issue") if getattr(item, f) not in (None, "")]
        if stray:
            raise BackfillError(
                f"manifest entry {key}: an override of a key `fr debt` holds sets only `pr:`, "
                f"`gate:` and `walk_only:`, not {', '.join(f'`{f}:`' for f in stray)}"
            )
        if item.pr is None and item.gate is None and item.walk_only is None:
            raise BackfillError(
                f"manifest entry {key}: an override of a key `fr debt` holds sets `pr:`, "
                "`gate:` or `walk_only:`"
            )
        return
    if not item.title:
        raise BackfillError(f"manifest entry {key}: a new item needs `title:`")
    if held and not taken_back:
        raise BackfillError(
            f"manifest entry {key}: `fr debt` already holds this key; to set its delivering PR "
            "or gate, drop `kind:` (and `title:`/`issue:`) and keep only `pr:`/`gate:`"
        )


def _settle_trackers(
    cands: list[Candidate],
    issues: list[dict[str, Any]],
    by_ref: dict[str, dict[str, Any]],
    man: dict[str, ManifestItem],
    adopted: set[str],
    ours: set[str],
    notes: list[str],
    owned: frozenset[str] = frozenset(),
) -> list[Candidate]:
    """Attach look-alike trackers, then settle the `issue:` candidates that are trackers."""
    withs = [
        c.model_copy(
            update={"tracker_candidates": tuple(_lookalikes(c, issues, man.get(c.key), owned))}
        )
        for c in cands
    ]
    suggested: dict[str, str] = {}
    for c in withs:
        for t in c.tracker_candidates:
            suggested.setdefault(t, c.key)
    out = []
    for c in withs:
        if split_key(c.key)[0] == "issue" and c.source != "manifest":
            ref = c.key.removeprefix("issue:")
            body = str(by_ref.get(ref, {}).get("body") or "")
            marked = fr_gate_marker(body) or fr_passed_marker(body)  # held or tracked only
            if ref in adopted or (ref in ours and marked is not None):
                notes.append(f"{c.key}: a tracker, not a candidate")
                continue
            if ref in suggested:
                c = c.model_copy(
                    update={
                        "decision": "review",
                        "why": f"looks like the tracker of {suggested[ref]}",
                    }
                )
        out.append(c)
    return out
