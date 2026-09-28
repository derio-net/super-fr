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
from typing import Literal

from fr.acceptance.model import Matrix, Row
from fr.record.model import VisualEvidence
from fr.run.telemetry import parse_timestamp, read_file_since, shell_named_since

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
) -> list[Row]:
    """The rows a unit owes visual evidence for: a phase unit's header
    `acceptance:` rows (`phase_rows`), or `deliver`'s rows citing the run's
    spec (`spec_ref`) — only those declaring `visual` and not
    `verify: post-merge` (only a live run after merge can prove those)."""
    from fr.requirements import rows_citing

    if phase_rows is not None:
        wanted = set(phase_rows)
        rows = [r for r in matrix.rows if r.id in wanted]
    elif spec_ref is not None:
        rows = rows_citing(matrix, spec_ref)
    else:
        rows = []
    return [r for r in rows if r.visual is not None and r.verify != "post-merge"]


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

    1. the record's `visual` section has an entry for the row;
    2. every state and interaction the row declares is named by some shot's
       `shows`, and `shows` names nothing the row does not declare;
    3. every shot has an image suffix, is not in `<run>.records/`, is
       git-ignored when inside the repo, exists and is non-empty — and, when
       `fresh_required` (`review-phase`, `deliver`), was modified at or after
       the unit opened (one second of slack); a named capture script exists."""
    by_row: dict[str, VisualEvidence] = {}
    for given in entries:
        by_row.setdefault(given.row, given)
    problems: list[str] = []
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
            return owed_rows(load_matrix(repo_root / MATRIX_REL), phase_rows=linked)
        if spec_rel is None or not (repo_root / MATRIX_REL).exists():
            return []
        matrix, spec_ref = load_spec_matrix(repo_root, spec_rel)
        return owed_rows(matrix, spec_ref=spec_ref)
    except AcceptanceError as e:
        raise VisualRefusedError([f"{why} — {e}"]) from e


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
) -> Derived:
    """The `visual` witness for one unit resolving `done` — or `VisualRefusedError`.

    `entries` is the record's `visual:` section, `None` on the flag form (which
    can carry none, so a unit that owes a row is refused and pointed at
    `--record`). Checks 1–3 (`check_visual`) always apply; checks 4–5 read the
    witness transcript and are skipped — the witness marked `unobserved` —
    only when it cannot be read."""
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
    problems: list[str] = []
    transcript = _witness_file(env, role, holder=holder, reviewer=reviewer)
    if transcript is None or since is None:
        return Derived(check.witness(unobserved=True), unobserved=True)
    whose = _whose(role, holder=holder, reviewer=reviewer)
    for row in check.rows:
        for shot in row.shots:
            seen = read_file_since(transcript, shot, since)
            if seen is None:
                return Derived(check.witness(unobserved=True), unobserved=True)
            if seen is False:
                problems.append(
                    f"row {row.row}: {shot} was not opened by {whose} since this unit "
                    f"opened at {since} — open it with an image read and look at it"
                )
        if row.script is not None:
            ran = shell_named_since(transcript, row.script, since)
            if ran is None:
                return Derived(check.witness(unobserved=True), unobserved=True)
            if ran is False:
                problems.append(
                    f"row {row.row}: no shell call by {whose} named the capture script "
                    f"{row.script} since this unit opened at {since} — re-run it, then "
                    "open its fresh screenshots"
                )
    if problems:
        raise VisualRefusedError(
            [f"refused — the visual evidence for {ids} was not witnessed:", *problems]
        )
    return Derived(check.witness(), unobserved=False)


def _whose(role: Role, *, holder: str | None, reviewer: str | None) -> str:
    if role == "reviewer":
        return f"the reviewer {reviewer}"
    if role == "holder" and holder is not None:
        return f"the unit's holder {holder}"
    return "the orchestrator"


def _witness_file(
    env: Mapping[str, str], role: Role, *, holder: str | None, reviewer: str | None
) -> Path | None:
    """The witness transcript (§C, check 4), or `None` when unreadable."""
    from fr.run.telemetry import _this_session, witness_transcript

    session = _this_session(env)
    if session is None:
        return None
    agent = reviewer if role == "reviewer" else holder if role == "holder" else None
    if role == "reviewer" and agent is None:
        return None
    return witness_transcript(session, agent)
