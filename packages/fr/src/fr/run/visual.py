"""The `visual` derived evidence (spec 2026-09-28-ui-visual-evidence §C).

A unit that owes a `visual` acceptance row proves two things when it resolves
`done`: its record's `visual:` section names screenshots that cover every state
and interaction the row declares (checks 1–3, pure, here), and the unit's
WITNESS TRANSCRIPT shows those screenshots opened — and any named capture
script re-run — since the unit opened (checks 4–5, `fr.run.telemetry`'s
three-valued predicates).

`fr run resolve` calls `derive_visual` and records what it returns; it owns no
rule of its own.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from fr.acceptance.model import Matrix, Row
from fr.record.model import VisualEvidence
from fr.run.telemetry import parse_timestamp

if TYPE_CHECKING:
    from fr.parser import Plan
    from fr.run.observed import ObservedSession
    from fr.verification.rows import SpecVerification

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
"""What a shot may be (§B) — compared case-insensitively."""

NONE = "none"
"""The witness when nothing is owed."""

UNOBSERVED_SUFFIX = ":unobserved"

SLACK = _dt.timedelta(seconds=1)
"""Freshness slack, as `tests=`: the cursor stamps at second precision."""

Role = Literal["holder", "reviewer", "orchestrator"]
"""Whose transcript owes the reads (§C, check 4): the unit's claimed holder
(`implement-phase`; the orchestrator itself when it ran inline), the offered
`reviewer` (`review-phase`), or the orchestrator's own stream (`deliver`)."""


def owed_rows(
    matrix: Matrix,
    *,
    phase_rows: Sequence[str] | None = None,
    spec_ref: str | None = None,
    verification: SpecVerification | None = None,
) -> list[Row]:
    """The rows a unit owes visual evidence for: a phase unit's header
    `acceptance:` rows (`phase_rows`), or `deliver`'s rows citing the run's
    spec (`spec_ref`) — only those declaring `visual` whose effective
    strategy is not post-merge (only a live run after merge can prove those;
    spec 2026-10-06-verification-strategies §B). Without `verification`, only
    a row's own `verify` counts, resolved against the shipped strategies. A
    strategy that does not resolve owes the evidence (fail closed)."""
    from fr.requirements import rows_citing

    if phase_rows is not None:
        wanted = set(phase_rows)
        rows = [r for r in matrix.rows if r.id in wanted]
    elif spec_ref is not None:
        rows = rows_citing(matrix, spec_ref)
    else:
        rows = []
    return [r for r in rows if r.visual is not None and not _post_merge(r, verification)]


def _post_merge(row: Row, verification: SpecVerification | None) -> bool:
    from fr.verification.effective import is_post_merge
    from fr.verification.model import StrategyError

    try:
        if verification is None:
            return is_post_merge(row.verify, None)
        return verification.is_post_merge(row)
    except StrategyError:
        return False


@dataclass(frozen=True)
class RowCheck:
    """One owed row that passed checks 1–3: its shot files (resolved, in path
    order), its capture script (resolved) if the entry names one, and the
    digest of the shot bytes."""

    row: str
    shots: tuple[Path, ...]
    script: Path | None
    digest: str

    def witness(self, *, unobserved: bool = False) -> str:
        tail = UNOBSERVED_SUFFIX if unobserved else ""
        return f"{self.row}:{len(self.shots)}:{self.digest}{tail}"


@dataclass(frozen=True)
class VisualCheck:
    problems: tuple[str, ...]
    rows: tuple[RowCheck, ...]

    def witness(self, *, unobserved: bool = False) -> str:
        """`<row>:<n>:<sha256[:12]>[:unobserved]`, joined by `,` — `none` when
        nothing is owed."""
        if not self.rows:
            return NONE
        return ",".join(r.witness(unobserved=unobserved) for r in self.rows)


def _resolve(path: str, repo_root: Path) -> Path:
    candidate = Path(path)
    return (candidate if candidate.is_absolute() else repo_root / candidate).resolve()


def _inside(path: Path, root: Path) -> bool:
    return path.is_relative_to(root.resolve())


def check_visual(
    owed: Iterable[Row],
    entries: Iterable[VisualEvidence],
    *,
    opened: _dt.datetime | None,
    fresh_required: bool,
    repo_root: Path,
    records_dir: Path,
    is_ignored: Callable[[Path], bool],
) -> VisualCheck:
    """Checks 1–3 of §C over every owed row — every problem, not the first.

    1. the record's `visual` section has exactly one entry for the row (a
       repeated `row` id is refused, naming it);
    2. every state and interaction the row declares is named by some shot's
       `shows`, and `shows` names nothing the row does not declare;
    3. every shot has an image suffix, is not in `<run>.records/`, is
       git-ignored when inside the repo, exists and is non-empty — and, when
       `fresh_required` (`review-phase`, `deliver`), was modified at or after
       the unit opened (one second of slack); a named capture script exists."""
    by_row: dict[str, VisualEvidence] = {}
    repeated: list[str] = []
    for given in entries:
        if given.row in by_row and given.row not in repeated:
            repeated.append(given.row)
        by_row.setdefault(given.row, given)
    problems = [
        f"row {rid}: the record names it in more than one `visual` entry — merge its "
        "shots into one entry"
        for rid in repeated
    ]
    checked: list[RowCheck] = []
    for row in owed:
        assert row.visual is not None  # `owed_rows` keeps only visual rows
        entry = by_row.get(row.id)
        if entry is None:
            problems.append(
                f"row {row.id}: the record has no `visual` entry for it — capture every "
                "named state and interaction, open each screenshot, and list them under "
                f"`visual: [{{row: {row.id}, shots: [...]}}]`"
            )
            continue
        before = len(problems)
        declared = [*row.visual.states, *row.visual.interactions]
        shown = {name for shot in entry.shots for name in shot.shows}
        for name in declared:
            if name not in shown:
                problems.append(
                    f"row {row.id}: no shot shows {name!r} — capture it and name it in "
                    "that shot's `shows`"
                )
        for name in sorted(shown - set(declared)):
            problems.append(
                f"row {row.id}: a shot shows {name!r}, but the row declares no such state "
                f"or interaction (it declares: {', '.join(declared)})"
            )
        paths = sorted({_resolve(shot.path, repo_root) for shot in entry.shots}, key=str)
        for path in paths:
            problems.extend(
                f"row {row.id}: {path} {p}"
                for p in _shot_problems(
                    path,
                    opened=opened if fresh_required else None,
                    repo_root=repo_root,
                    records_dir=records_dir,
                    is_ignored=is_ignored,
                )
            )
        script = _resolve(entry.script, repo_root) if entry.script else None
        if script is not None and not script.is_file():
            problems.append(f"row {row.id}: the capture script {script} does not exist")
        if len(problems) > before:
            continue
        digest = hashlib.sha256(b"".join(p.read_bytes() for p in paths)).hexdigest()[:12]
        checked.append(RowCheck(row.id, tuple(paths), script, digest))
    return VisualCheck(tuple(problems), tuple(checked))


def _shot_problems(
    path: Path,
    *,
    opened: _dt.datetime | None,
    repo_root: Path,
    records_dir: Path,
    is_ignored: Callable[[Path], bool],
) -> list[str]:
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        return [f"has no image suffix ({', '.join(sorted(IMAGE_SUFFIXES))})"]
    if _inside(path, records_dir):
        return [
            "is inside the run's records dir, which holds step records only and is "
            "emptied by fr — write screenshots outside the repo (e.g. $TMPDIR) or to a "
            "git-ignored directory"
        ]
    if _inside(path, repo_root) and not is_ignored(path):
        return [
            "is inside the repo and not git-ignored, so it could be committed — write it "
            "to a git-ignored directory or outside the repo"
        ]
    try:
        size = path.stat().st_size if path.is_file() else 0
    except OSError:
        size = 0
    if not size:
        return ["is missing or empty — the screenshot must exist where fr runs (the host)"]
    if opened is not None:
        modified = _dt.datetime.fromtimestamp(path.stat().st_mtime, tz=_dt.UTC)
        if modified < opened - SLACK:
            return [
                f"predates this unit (opened {opened.isoformat()}) — re-capture it now "
                "and open the fresh screenshot"
            ]
    return []


def git_ignored(repo_root: Path) -> Callable[[Path], bool]:
    """`is_ignored` for `check_visual`: `git check-ignore -q` in `repo_root`."""

    def ignored(path: Path) -> bool:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", "--", str(path)],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
        return proc.returncode == 0

    return ignored


class VisualRefusedError(Exception):
    """A `visual` refusal: `lines[0]` the headline, the rest one problem each."""

    def __init__(self, lines: list[str]) -> None:
        super().__init__(lines[0])
        self.lines = lines


@dataclass(frozen=True)
class Derived:
    witness: str
    unobserved: bool
    why: str | None = None
    """Why checks 4–5 could not be read, when `unobserved` — printed by the
    caller in its warning."""


def role_for(evidence: Sequence[str], phase: int | None) -> Role:
    """Whose transcript owes a unit's reads, from the step's shape: a step that
    declares `reviewer` is a review (the reviewer's); any other phase unit is
    the implementer's (its holder, or the orchestrator when inline); a flat
    step — `deliver` — is the orchestrator's own."""
    if "reviewer" in evidence:
        return "reviewer"
    return "holder" if phase is not None else "orchestrator"


def owed_for_unit(
    repo_root: Path, *, plan_rel: str | None, phase: int | None, spec_rel: str | None
) -> list[Row]:
    """The rows a unit owes (§C): phase `phase`'s header rows, or — for a flat
    unit — the rows citing the run's spec. A missing matrix owes nothing; an
    unreadable plan or matrix raises `VisualRefusedError` (fail-closed)."""
    from fr.acceptance.model import AcceptanceError, load_matrix
    from fr.commands.acceptance_cmd import MATRIX_REL
    from fr.parser import PlanSchemaError, parse
    from fr.requirements import load_spec_matrix

    why = "cannot derive visual evidence"
    try:
        if phase is not None:
            if plan_rel is None:
                raise VisualRefusedError([f"{why} — no plan recorded yet"])
            try:
                plan = parse(repo_root / plan_rel)
            except PlanSchemaError as e:
                raise VisualRefusedError([f"{why} — plan {plan_rel} does not parse: {e}"]) from e
            linked = next((p.phase.acceptance for p in plan.phases if p.phase.number == phase), ())
            if not linked or not (repo_root / MATRIX_REL).exists():
                return []
            return owed_rows(
                load_matrix(repo_root / MATRIX_REL),
                phase_rows=linked,
                verification=_verification(repo_root, plan.spec_path or plan.meta.spec, plan),
            )
        if spec_rel is None or not (repo_root / MATRIX_REL).exists():
            return []
        matrix, spec_ref = load_spec_matrix(repo_root, spec_rel)
        flat_plan: Plan | None = None
        if plan_rel is not None:
            try:
                flat_plan = parse(repo_root / plan_rel)
            except PlanSchemaError:
                flat_plan = None
        return owed_rows(
            matrix, spec_ref=spec_ref, verification=_verification(repo_root, spec_rel, flat_plan)
        )
    except AcceptanceError as e:
        raise VisualRefusedError([f"{why} — {e}"]) from e


def _verification(repo_root: Path, spec_rel: str | None, plan: Plan | None) -> SpecVerification:
    """The spec's verification inputs, the shape default read from the plan's
    workflow. A malformed section or an unresolvable shape degrades to "the
    row's own `verify` only" — self-review refuses the section by name, and
    owing evidence is the fail-closed side here."""
    from fr.verification.rows import SpecVerification, spec_section_at
    from fr.verification.spec_section import SectionError
    from fr.workflow.model import WorkflowError
    from fr.workflow.resolve import workflow_for_plan

    try:
        section = spec_section_at(repo_root, spec_rel)
    except (SectionError, OSError):
        section = None
    shape: str | None = None
    if plan is not None:
        try:
            shape = workflow_for_plan(plan, repo_root).verification
        except WorkflowError:
            shape = None
    return SpecVerification(repo_root, section, shape)


def derive_visual(
    owed: Sequence[Row],
    entries: Sequence[VisualEvidence] | None,
    *,
    role: Role,
    since: str | None,
    holder: str | None,
    reviewer: str | None,
    repo_root: Path,
    records_dir: Path,
    env: Mapping[str, str],
    dispatched_as: str | None = None,
    claim_hint: str = "fr run claim <run> --step <step> --item <item> --agent <id>",
) -> Derived:
    """The `visual` witness for one unit resolving `done` — or `VisualRefusedError`.

    `entries` is the record's `visual:` section, `None` on the flag form (which
    can carry none, so a unit that owes a row is refused and pointed at
    `--record`). Checks 1–3 (`check_visual`) always apply; checks 4–5 read the
    witness transcript and are skipped — the witness marked `unobserved`, with
    `Derived.why` saying why — only when it cannot be read.

    `dispatched_as` is the agent type the unit's attempt was dispatched to
    (`None` when fr recorded no dispatch). A `holder` unit with no holder named
    ran inline — the orchestrator's stream is its witness — UNLESS this session
    shows a dispatch of that agent type since the unit opened: then an executor
    did the work and must be claimed (`claim_hint`), because the orchestrator
    opening the shots is not the executor opening them (review p2-r4)."""
    if not owed:
        return Derived(NONE, unobserved=False)
    ids = ", ".join(r.id for r in owed)
    if entries is None:
        raise VisualRefusedError(
            [
                f"refused — this unit owes visual evidence for {ids}, which only a step "
                "record can carry. Fill its `visual:` section and resolve with "
                "`fr run resolve ... --record <record>`."
            ]
        )
    opened = parse_timestamp(since)
    check = check_visual(
        owed,
        entries,
        opened=opened,
        fresh_required=role != "holder",
        repo_root=repo_root,
        records_dir=records_dir,
        is_ignored=git_ignored(repo_root),
    )
    if check.problems:
        raise VisualRefusedError(
            [f"refused — the visual evidence for {ids} is incomplete:", *check.problems]
        )

    def unobserved(why: str) -> Derived:
        return Derived(check.witness(unobserved=True), unobserved=True, why=why)

    if since is None:
        return unobserved("the unit's open time is not recorded, so there is no window to read")
    witness = _witness_file(
        env,
        role,
        holder=holder,
        reviewer=reviewer,
        since=since,
        dispatched_as=dispatched_as,
    )
    if isinstance(witness, str):
        return unobserved(witness)
    view, whose, agent = witness
    if view is False:
        raise VisualRefusedError(
            [
                f"refused — the visual evidence for {ids} names {whose}, but {agent!r} "
                "names no subagent this session dispatched. The screenshots must be opened "
                "by a dispatched agent (a separate context), named by the id its dispatch "
                "returned."
            ]
        )
    if view == "unclaimed":
        raise VisualRefusedError(
            [
                f"refused — this unit was dispatched to {dispatched_as}, and this session "
                "shows that dispatch, but no holder was claimed, so fr cannot tell whose "
                f"transcript owes the screenshot reads for {ids}. Claim the executor: "
                f"`{claim_hint}` (or name it as `evidence: {{agent: <id>}}` in the record), "
                "then resolve again."
            ]
        )
    assert not isinstance(view, str)
    opened_at = opened  # the unit's open time, parsed above
    assert opened_at is not None
    problems: list[str] = []
    for row in check.rows:
        for shot in row.shots:
            written = _dt.datetime.fromtimestamp(shot.stat().st_mtime, tz=_dt.UTC)
            seen = view.first_read(shot, opened_at, not_before=written - SLACK)
            if seen is None:
                return unobserved(f"the transcript of {whose} could not be read")
            if seen is False:
                problems.append(
                    f"row {row.row}: {shot} was not opened in the transcript of {whose} "
                    f"since this unit opened at {since} and the file was last written "
                    f"({written.isoformat()}) — open it with an image read and look at it"
                )
        if row.script is not None:
            ran = view.first_shell_executing(row.script, opened_at)
            if ran is None:
                return unobserved(f"the transcript of {whose} could not be read")
            if ran is False:
                problems.append(
                    f"row {row.row}: no shell call in the transcript of {whose} executed "
                    f"the capture script {row.script} since this unit opened at {since} — "
                    "re-run it by name (e.g. `node <script>`), then open its fresh "
                    "screenshots"
                )
    if problems:
        raise VisualRefusedError(
            [f"refused — the visual evidence for {ids} was not witnessed:", *problems]
        )
    return Derived(check.witness(), unobserved=False)


def _unobservable(env: Mapping[str, str]) -> str:
    """Why no session transcript can be read here — visual's own wording."""
    from fr.harness.detect import detect_harness
    from fr.harness.model import HarnessError

    try:
        harness = detect_harness(env)
    except HarnessError:
        harness = None
    if harness is None:
        return "no harness detected, so there is no transcript to find the screenshot reads in"
    if harness == "opencode":
        return (
            "no readable OpenCode session to find the screenshot reads in "
            "(FR_OPENCODE_SESSION_ID is unset, or names a session the database does not hold)"
        )
    if harness != "claude-code":
        return f"fr cannot yet read file opens from {harness}'s transcripts"
    return "no readable transcript for this session"


def _same_agent(observed: str | None, expected: str) -> bool:
    """`observed` is `expected`, plugin-qualified or bare and with or without
    an OpenCode tier suffix, on either side (`fr.run.observed.agent_name`)."""
    from fr.run.observed import agent_name

    if observed is None:
        return False
    return agent_name(observed) == agent_name(expected)


_Witness = tuple["ObservedSession | Literal[False, 'unclaimed']", str, str | None]
"""`(view, whose, agent)`: the session whose parts owe the reads."""


def _witness_file(
    env: Mapping[str, str],
    role: Role,
    *,
    holder: str | None,
    reviewer: str | None,
    since: str,
    dispatched_as: str | None,
) -> _Witness | str:
    """The witness session (§C, check 4; spec 2026-10-02 §G) as `(view, whose,
    agent id)` — the view `False` for an agent id this session never dispatched,
    `"unclaimed"` for a dispatched holder unit nobody claimed — or, when it
    cannot be read, the reason (a `str`). The session is chosen as it always
    was: the reviewer's child, the claimed holder's child, or the run
    session's own parts; what reads it is the harness's `ObservedSession`."""
    from fr.run.observed import observed_session

    view = observed_session(env)
    if view is None or view.harness not in ("claude-code", "opencode"):
        return _unobservable(env)
    opened = parse_timestamp(since)
    if role == "reviewer":
        if reviewer is None:
            return "no reviewer was named, so there is no reviewer transcript to read"
        agent, whose = reviewer, f"the reviewer {reviewer}"
    elif role == "holder" and holder is not None:
        agent, whose = holder, f"the executor {holder} (the unit's holder)"
    elif role == "holder":
        agent = None
        whose = "the orchestrator (the unit ran inline — no executor was claimed)"
        if dispatched_as is not None and opened is not None:
            dispatched = [
                d
                for d in view.dispatches(opened) or []
                if _same_agent(d.agent_type, dispatched_as)
                and d.started is not None
                and d.started >= opened
            ]
            if dispatched:
                return ("unclaimed", whose, None)
    else:
        agent, whose = None, "the orchestrator"
    if agent is None:
        return (view, whose, None)
    child = view.child(agent)
    if child is None:
        return f"the session {view.session} could not be read"
    return (child, whose, agent)
