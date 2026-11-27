"""Library functions for v2 plan editing.

These are the writers — every other v2 module is a reader (parse,
render, observe) or a mutator-of-GitHub (diff, apply). Plan-file
writes happen here.

Conventions:
  - All writers stage via `git add` after the file write but do NOT
    commit. The caller (CLI) decides commit cadence.
  - All writers re-parse after writing to confirm the file still
    passes schema validation.
  - `fr.plan.create` and `fr.plan.rework_create` additionally append
    a row to the spec's Implementation Plans table; the spec edit is
    staged in the same change so it lands in the same PR.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

import yaml

from fr import refs
from fr._plan_io import _stage, _yaml_dump
from fr._plan_io import worktree_of as worktree_of
from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.paths import kind_dir, space_for
from fr.journal.model import journal_header, journal_path
from fr.parser import Plan, PlanSchemaError, parse
from fr.plan_errors import PlanEditError as PlanEditError
from fr.plan_review import OPS_FR_FLOOR as OPS_FR_FLOOR
from fr.plan_review import ReviewIssue as ReviewIssue
from fr.plan_review import _manual_placement_issues as _manual_placement_issues
from fr.plan_review import _trailing_manual_block as _trailing_manual_block
from fr.plan_review import self_review as self_review
from fr.plan_rework import ReworkRecord as ReworkRecord
from fr.plan_rework import rework_add_origin as rework_add_origin
from fr.plan_rework import rework_create as rework_create
from fr.plan_rework import rework_list as rework_list
from fr.plan_validator_wrapper import (
    ValidatorWrapperError,
    ensure_validator_wrapper,
    validator_wrapper_path,
)
from fr.spec_table import (
    _SPEC_TABLE_HEADER_RE,
    _append_spec_row,
    _ensure_section_text,
    _validate_spec_section,
)
from fr.types import PHASE_TIERS
from fr.version_floor import admits


class StepSpec(TypedDict):
    """Shape of a single step within a `PhaseSpec.tasks[*]['steps']` list."""

    id: str
    text: str


class TaskSpec(TypedDict):
    """Shape of an entry in `PhaseSpec.tasks` — a task with its step list."""

    number: int
    title: str
    steps: list[StepSpec]


# ---------------------------------------------------------------------------
# helpers


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).isoformat(timespec="seconds")


_TOP_LEVEL_KEY = re.compile(r"^([A-Za-z_][\w-]*):(?:\s|$)")


def _splice_block(text: str, key: str, value: Any) -> str | None:
    """`text` with the top-level `key:` block re-serialised, every other byte
    kept — or None when the block cannot be found exactly once."""
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if _TOP_LEVEL_KEY.match(line)]
    owned = [i for i in starts if _TOP_LEVEL_KEY.match(lines[i]).group(1) == key]  # type: ignore[union-attr]
    if len(owned) != 1:
        return None
    start = owned[0]
    end = next((i for i in starts if i > start), len(lines))
    # A blank or column-0 comment line just above the next key belongs to it.
    while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].startswith("#")):
        end -= 1
    block = _yaml_dump({key: value})
    if end < len(lines) and not block.endswith("\n"):
        block += "\n"
    return "".join(lines[:start]) + block + "".join(lines[end:])


def rewrite_phase_text(original: str, raw: dict[str, Any], *keys: str) -> str:
    """The phase-file text for `raw`, re-serialising only the top-level
    `keys` blocks the caller changed and keeping every other byte of
    `original` (gh#502).

    A phase file is a review artifact: a tick that re-dumps the whole file
    restyles every hand-edited scalar and buries the one-line change in the
    PR's plan diff. The splice is trusted only when the result parses back to
    exactly `raw`; anything else (a duplicated key, a shape the line scan
    misreads) falls back to the whole-file dump this replaced.
    """
    text: str | None = original
    for key in keys:
        text = _splice_block(text, key, raw[key]) if text is not None else None
    try:
        faithful = text is not None and yaml.safe_load(text) == raw
    except yaml.YAMLError:  # e.g. an alias whose anchor sat in the replaced block
        faithful = False
    return text if faithful and text is not None else _yaml_dump(raw)


# ---------------------------------------------------------------------------
# fr.plan.create


@dataclass(frozen=True)
class PhaseSpec:
    """Lightweight phase shape for `create()` callers."""

    number: int
    title: str
    tag: Literal["agentic", "manual"] = "agentic"
    depends_on: tuple[int, ...] = ()
    tasks: tuple[TaskSpec, ...] = ()
    # Acceptance-matrix row ids (2026-07-04 spec) — emitted only when set.
    acceptance: tuple[str, ...] = ()
    # Walking-skeleton marker — emitted only when set (same byte-stability
    # rule as `acceptance`).
    skeleton: bool = False
    # Harness-neutral complexity hint (2026-07-22 fr-goal-subagent-execution
    # spec §B.2) — emitted only when set (same byte-stability rule as
    # `acceptance`/`skeleton`). Validated against `fr.types.PHASE_TIERS` in
    # `create()`'s pre-flight loop, not left to `PhaseHeader`'s Literal at the
    # post-write re-parse (#133: that would strand a half-built folder).
    tier: Literal["mechanical", "standard", "hard"] | None = None
    # Proportionality inputs (2026-09-24 spec §C) — emitted only when set.
    files: tuple[str, ...] = ()
    estimate_lines: int | None = None

    @property
    def declares_scope(self) -> bool:
        """Does this phase use a field that needs fr >= 4.20.0 to parse?"""
        return bool(self.files) or self.estimate_lines is not None


def _preflight_fr_version_error(fr_version: str) -> str | None:
    """Why the plan's own re-parse would refuse `fr_version`, or `None`.

    An explicit `--fr-version` was checked only for admitting an fr that is too
    OLD, never the one running, so a constraint excluding it wrote the plan and
    then failed the post-write parse, stranding the folder, its journal and the
    validator wrapper (gh#855). Same doctrine as the phase pre-flight: refuse
    before the first byte. `fr.parser.INSTALLED_FR_VERSION` is read here, not
    imported by name, so it is the value the re-parse will enforce.
    """
    from packaging.specifiers import InvalidSpecifier

    from fr import parser

    installed = parser.INSTALLED_FR_VERSION
    try:
        if admits(fr_version, installed):
            return None
    except InvalidSpecifier as e:
        return f"invalid fr_version {fr_version!r}: {e}"
    return (
        f"fr_version {fr_version!r} excludes the installed fr {installed}, so the plan "
        f"would fail its own parse; nothing was written. Pass an fr_version that admits "
        f"{installed}, or omit --fr-version for the default."
    )


def _preflight_phase_error(ps: PhaseSpec) -> str | None:
    """The first pre-flight validation error for `ps`, or None.

    Each check here mirrors a `PhaseHeader` schema gate that would otherwise
    only reject at `create()`'s post-write re-parse, stranding a half-built
    plan folder (#133). One function per phase keeps `create()`'s loop a
    single readable rule ("for each phase, raise the first pre-flight
    error") instead of a growing set of inline `if`s.
    """
    if ps.number < 1:
        return f"phase {ps.number} ({ps.title!r}): phase numbering starts at 1, not 0"
    if ps.tier is not None and ps.tier not in PHASE_TIERS:
        return (
            f"phase {ps.number} ({ps.title!r}): tier {ps.tier!r} is not valid, "
            f"must be one of {list(PHASE_TIERS)}"
        )
    if ps.estimate_lines is not None and ps.estimate_lines < 0:
        return (
            f"phase {ps.number} ({ps.title!r}): estimate_lines must be >= 0, "
            f"got {ps.estimate_lines}"
        )
    return None


def create(
    *,
    repo_root: Path,
    slug: str,
    spec: Path | str | None,
    target_repo: str,
    fr_version: str,
    phases: list[PhaseSpec],
    prose: str,
    plans_dir: Path | None = None,
    workflow: str | None = None,
    warn: Callable[[str], None] | None = None,
) -> Plan:
    """Scaffold a new v2 plan folder + append spec row.

    `warn` receives non-fatal notes (a foreign validator wrapper left in
    place). The CLI passes its stderr printer; library callers default to
    this module's logger.

    `workflow` is the shape the plan dispatches at (spec §4.A.1). It is
    written ONLY when given — a `workflow: null` line in every new plan
    would be a gratuitous diff against every plan written before the field
    existed, and absence is meaningful (it resolves the default shape).
    Callers that pass one own flooring `fr_version` at `>=4.0.0`; see
    `fr.commands.plan_cmd` (`PlanMeta` is extra="forbid", so older fr
    cannot parse the key at all).

    Returns the parsed Plan. Raises PlanEditError on collisions.
    """
    if plans_dir is None:
        plans_dir = kind_dir("plan", space_for(repo_root))
    folder = plans_dir / slug

    spec_str = str(spec) if spec is not None else None

    # Pre-flight: validate every external precondition BEFORE mutating the
    # filesystem. A spec whose '## Implementation Plans' table is malformed
    # must fail loud here — not after the folder is half-built — so a re-run
    # after fixing it isn't blocked by a stranded folder (#133). (A spec with
    # no section at all is fine: `create` writes it below.) Mirrors how
    # `fr apply` validates the diff before `--yes` touches GitHub. Same
    # doctrine for phase numbering and tier below: their schema gates
    # (PhaseHeader's `ge=1` and `Literal`) would only reject at the post-write
    # re-parse, stranding the folder (#434 spec-review finding for tier).
    for ps in phases:
        error = _preflight_phase_error(ps)
        if error is not None:
            raise PlanEditError(error)
    error = _preflight_fr_version_error(fr_version)
    if error is not None:
        raise PlanEditError(error)
    spec_path: Path | None = None
    if spec_str:
        candidate = (repo_root / spec_str).resolve()
        if not candidate.exists():
            # Under quiet or stealth the spec sits below the artifact root, so a
            # logical `<specs dir>/<file>` resolves there, as a cursor's does.
            from fr.artifacts.paths import emitted_path

            candidate = emitted_path(repo_root, spec_str).resolve()
        if candidate.exists():
            _validate_spec_section(candidate)
            spec_path = candidate
        # If the spec file doesn't exist yet, we skip the row — the operator
        # can add it by hand when they create the spec file.

    # Build the expected folder contents in memory (no side effects yet).
    meta: dict[str, Any] = {
        "schema_version": 2,
        "plan": slug,
        "spec": refs.canonical_spec_ref(spec_str, repo_root) if spec_str else spec_str,
        "target_repo": target_repo,
        "fr_version": fr_version,
        "created": _dt.date.today().isoformat(),
    }
    if workflow is not None:
        # Last, mirroring `PlanMeta`'s field order — an existing plan's
        # bytes are unaffected and a shaped plan reads bottom-up as
        # "…and this one dispatches at <shape>".
        meta["workflow"] = workflow
    meta_text = _yaml_dump(meta)
    prose_text = prose if prose.endswith("\n") else prose + "\n"
    phase_files = {f"{ps.number:02d}.yaml": _yaml_dump(_build_phase_doc(ps)) for ps in phases}

    written: list[Path] = []
    if folder.exists():
        # Idempotent repair (#133): a prior run may have created the folder but
        # failed before appending the spec row. If the on-disk content matches
        # what we would write, finish the job (append the row below) instead of
        # dead-ending at "already exists". Mismatched content — a slug reused
        # for a different plan — is a real collision and still rejected.
        if not _folder_matches(
            folder,
            meta_text=meta_text,
            prose_text=prose_text,
            phase_files=phase_files,
            repo_root=repo_root,
        ):
            raise PlanEditError(f"plan folder already exists: {folder}")
        # A match may still differ in how `spec:` is spelled: a first run
        # before the spec existed stored it verbatim, and it canonicalizes
        # now that it resolves. Converge on the canonical form, keeping the
        # original scaffold date.
        meta_p = folder / "_meta.yaml"
        on_disk_meta = meta_p.read_text()
        if _strip_created(on_disk_meta) != _strip_created(meta_text):
            created = [ln for ln in on_disk_meta.splitlines() if ln.startswith("created:")]
            write_text_atomic(
                meta_p,
                "".join(
                    created[0] + "\n" if ln.startswith("created:") and created else ln
                    for ln in meta_text.splitlines(keepends=True)
                ),
            )
            written.append(meta_p)
    else:
        plans_dir.mkdir(parents=True, exist_ok=True)
        folder.mkdir()
        write_text_atomic(folder / "_meta.yaml", meta_text)
        write_text_atomic(folder / "_prose.md", prose_text)
        for name, text in phase_files.items():
            write_text_atomic(folder / name, text)
        written.extend([folder / "_meta.yaml", folder / "_prose.md"])
        written.extend(folder / name for name in phase_files)

        # Initialize the plan journal (2026-07-22 fr-goal-subagent-execution
        # spec §A). A plan-scoped journal is a sibling of the plan folder under
        # docs/superpowers/journals/; it holds per-phase discoveries and review
        # findings written during execution. Only created here (not repaired),
        # so a hand-deleted journal on an existing folder stays absent —
        # parsing a plan never depends on its journal (back-compat).
        journal_p = journal_path(repo_root, "plan", slug)
        if not journal_p.exists():
            journal_p.parent.mkdir(parents=True, exist_ok=True)
            write_text_atomic(journal_p, journal_header(slug))
            written.append(journal_p)

    if spec_path is not None:
        spec_text = spec_path.read_text()
        if not _SPEC_TABLE_HEADER_RE.search(spec_text):
            write_text_atomic(spec_path, _ensure_section_text(spec_text))
        _append_spec_row(
            spec_path,
            plan_name=slug,
            repo=target_repo,
            # Canonical lifecycle-independent form (2026-06-06
            # spec-path-repair): the bare slug cannot go stale on archive.
            file=slug,
            depends_on="—",
        )
        written.append(spec_path)

    # A repo scaffolded before its first plan never got a tracked
    # scripts/validate-plans.sh (`fr init scaffold` only writes one when
    # docs/superpowers/plans/ already exists at scaffold time). Installing it
    # here means the wrapper lands in the SAME commit as this plan, so the
    # first-plan PR carries it to the default branch and a later `fr
    # isolation up --base origin/<default>` is never refused over it
    # (2026-09-25 fr-goal-closeout-defects spec §3.B). A foreign file there
    # is left untouched — the same refusal `ensure_validator_wrapper`
    # already makes elsewhere — reported as a warning, not a failure: a
    # plan is still worth creating even when the wrapper can't be.
    # Under quiet the product branch carries no fr file at all (R23): no wrapper.
    if (repo_root / ".git").exists() and space_for(repo_root).placement == "repo":
        try:
            if ensure_validator_wrapper(repo_root):
                written.append(validator_wrapper_path(repo_root))
        except ValidatorWrapperError as err:
            (warn or logging.getLogger(__name__).warning)(
                f"plan {slug}: could not install scripts/validate-plans.sh: {err}"
            )

    if written:
        _stage(repo_root, written)

    # Re-parse to confirm schema integrity
    return parse(folder)


def _folder_matches(
    folder: Path,
    *,
    meta_text: str,
    prose_text: str,
    phase_files: dict[str, str],
    repo_root: Path,
) -> bool:
    """True iff `folder` already holds exactly the content `create()` would write.

    Used to distinguish a repairable partial-success state (re-run with the same
    inputs) from a genuine slug collision. `_meta.yaml`'s `created:` date is
    ignored so a repair the next day still matches, and `spec:` is compared by
    the spec it names rather than by spelling: its canonical form depends on
    whether the spec resolves yet, so the same inputs can spell it two ways.
    """
    meta_p = folder / "_meta.yaml"
    if not meta_p.exists():
        return False
    on_disk = meta_p.read_text()
    if _strip_meta_line(on_disk, "spec") != _strip_meta_line(meta_text, "spec"):
        return False
    try:
        on_disk_doc = yaml.safe_load(on_disk)
    except yaml.YAMLError:
        return False  # a hand-corrupted meta is a mismatch, as the byte compare was
    if not isinstance(on_disk_doc, dict):
        return False
    if not _same_spec(on_disk_doc.get("spec"), yaml.safe_load(meta_text).get("spec"), repo_root):
        return False
    prose_p = folder / "_prose.md"
    if not prose_p.exists() or prose_p.read_text() != prose_text:
        return False
    # The on-disk phase files must be EXACTLY the expected set — not just a
    # superset. A re-run that drops a phase would otherwise "repair" the folder
    # while leaving the removed phase's `NN.yaml` behind as a silent orphan.
    if {p.name for p in folder.glob("[0-9]*.yaml")} != set(phase_files):
        return False
    for name, text in phase_files.items():
        p = folder / name
        if not p.exists() or p.read_text() != text:
            return False
    return True


def _strip_created(meta_text: str) -> str:
    """Drop the `created:` line so meta comparison ignores the scaffold date."""
    return "\n".join(line for line in meta_text.splitlines() if not line.startswith("created:"))


def _strip_meta_line(meta_text: str, key: str) -> str:
    """`_strip_created`, also dropping the top-level `key:` line."""
    return "\n".join(
        line for line in _strip_created(meta_text).splitlines() if not line.startswith(f"{key}:")
    )


def _same_spec(a: object, b: object, repo_root: Path) -> bool:
    """True iff two `spec:` values name the same spec (#697 regression)."""
    if a == b:
        return True
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return refs.canonical_spec_ref(a, repo_root) == refs.canonical_spec_ref(b, repo_root)


def _build_phase_doc(ps: PhaseSpec) -> dict[str, Any]:
    """Convert a PhaseSpec into the yaml-shaped phase doc dict."""
    tasks: list[dict[str, Any]] = []
    state_steps: dict[str, dict[str, Any]] = {}
    for t in ps.tasks:
        steps_out: list[dict[str, Any]] = []
        for s in t["steps"]:
            steps_out.append({"id": s["id"], "text": s["text"]})
            state_steps[s["id"]] = {"state": " ", "ticked_at": None, "note": None}
        tasks.append({"number": t["number"], "title": t["title"], "steps": steps_out})
    phase_header: dict[str, Any] = {
        "number": ps.number,
        "title": ps.title,
        "tag": ps.tag,
        "depends_on": list(ps.depends_on),
        "tracking_issue": None,
    }
    # Optional header fields are emitted only when set, so plans written
    # before each field existed stay byte-stable and parse on older readers.
    if ps.acceptance:
        phase_header["acceptance"] = list(ps.acceptance)
    if ps.skeleton:
        phase_header["skeleton"] = True
    if ps.tier is not None:
        phase_header["tier"] = ps.tier
    if ps.files:
        phase_header["files"] = list(ps.files)
    if ps.estimate_lines is not None:
        phase_header["estimate_lines"] = ps.estimate_lines
    return {
        "schema_version": 2,
        "phase": phase_header,
        "tasks": tasks,
        "state": {
            "steps": state_steps,
            "completion": {"at": None, "note": None, "observed_prs": []},
        },
    }


# ---------------------------------------------------------------------------
# fr.plan.tick / fr.plan.complete_phase


def tick(
    plan_dir: Path,
    step_id: str,
    *,
    state: Literal["x", "-"] = "x",
    note: str | None = None,
) -> None:
    """Mark a step ticked or skipped. Idempotent on re-tick.

    Writes to whichever phase yaml contains the step. Stages but does
    not commit. Validates the result by re-parsing.
    """
    if state == "-" and not note:
        raise PlanEditError("--state - (skipped) requires --note")

    plan = parse(plan_dir)
    repo_root = plan.repo_root

    # Find the phase yaml that owns this step id
    target_phase_n: int | None = None
    for phase in plan.phases:
        for task in phase.tasks:
            for step in task.steps:
                if step.id == step_id:
                    target_phase_n = phase.phase.number
                    break
            if target_phase_n is not None:
                break
        if target_phase_n is not None:
            break
    if target_phase_n is None:
        raise PlanEditError(f"step id {step_id!r} not found in any phase")

    phase_path = plan_dir / f"{target_phase_n:02d}.yaml"
    text = phase_path.read_text()
    raw = yaml.safe_load(text)

    current = raw["state"]["steps"][step_id]
    if current.get("state") == state and (note is None or current.get("note") == note):
        return  # idempotent

    raw["state"]["steps"][step_id] = {
        "state": state,
        "ticked_at": _now_iso(),
        "note": note,
    }
    write_text_atomic(phase_path, rewrite_phase_text(text, raw, "state"))

    # Re-parse to validate schema still holds
    parse(plan_dir)
    _stage(repo_root, [phase_path])


def complete_phase(plan_dir: Path, phase_n: int, *, note: str | None = None) -> None:
    """Mark a phase complete via state.completion.at + (required for manual) note."""
    plan = parse(plan_dir)
    matched = next((p for p in plan.phases if p.phase.number == phase_n), None)
    if matched is None:
        raise PlanEditError(f"phase {phase_n} not found in plan")

    if matched.phase.tag == "manual" and not note:
        raise PlanEditError(f"phase {phase_n} is manual; --note is required")

    if matched.phase.tag == "agentic":
        unticked = [sid for sid, s in matched.state.steps.items() if s.state == " "]
        if unticked:
            raise PlanEditError(
                f"phase {phase_n} (agentic) has unticked steps: {sorted(unticked)}. "
                f"tick them first OR open a rework plan if they're being deferred."
            )

    phase_path = plan_dir / f"{phase_n:02d}.yaml"
    text = phase_path.read_text()
    raw = yaml.safe_load(text)
    raw["state"]["completion"]["at"] = _now_iso()
    if note is not None:
        raw["state"]["completion"]["note"] = note
    write_text_atomic(phase_path, rewrite_phase_text(text, raw, "state"))
    parse(plan_dir)
    _stage(plan.repo_root, [phase_path])


def set_tracking_issue(plan_dir: Path, phase_n: int, url: str) -> None:
    """Persist phase.tracking_issue back to <plan_dir>/<NN>.yaml.

    Idempotent on same url; overwrites on different. Stages but does
    not commit.
    """
    plan = parse(plan_dir)
    phase_path = plan_dir / f"{phase_n:02d}.yaml"
    if not phase_path.exists():
        raise PlanEditError(f"phase {phase_n} yaml not found: {phase_path}")
    text = phase_path.read_text()
    raw = yaml.safe_load(text)
    if raw["phase"].get("tracking_issue") == url:
        return
    raw["phase"]["tracking_issue"] = url
    write_text_atomic(phase_path, rewrite_phase_text(text, raw, "phase"))
    try:
        parse(plan_dir)
    except PlanSchemaError as e:
        raise PlanEditError(f"post-write schema validation failed: {e}") from e
    _stage(plan.repo_root, [phase_path])


def clear_tracking_issue(plan_dir: Path, phase_n: int) -> bool:
    """Null phase.tracking_issue in <plan_dir>/<NN>.yaml (inverse of
    `set_tracking_issue` — the `fr undispatch` writeback).

    Returns True when the field was cleared, False when it was already
    null (no-op; the file is not rewritten, keeping re-runs byte-stable).
    Stages but does not commit.
    """
    plan = parse(plan_dir)
    phase_path = plan_dir / f"{phase_n:02d}.yaml"
    if not phase_path.exists():
        raise PlanEditError(f"phase {phase_n} yaml not found: {phase_path}")
    text = phase_path.read_text()
    raw = yaml.safe_load(text)
    if raw["phase"].get("tracking_issue") is None:
        return False
    raw["phase"]["tracking_issue"] = None
    write_text_atomic(phase_path, rewrite_phase_text(text, raw, "phase"))
    try:
        parse(plan_dir)
    except PlanSchemaError as e:
        raise PlanEditError(f"post-write schema validation failed: {e}") from e
    _stage(plan.repo_root, [phase_path])
    return True
