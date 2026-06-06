"""Library functions for v2 plan editing.

These are the writers — every other v2 module is a reader (parse,
render, observe) or a mutator-of-GitHub (diff, apply). Plan-file
writes happen here.

Conventions:
  - All writers stage via `git add` after the file write but do NOT
    commit. The caller (CLI) decides commit cadence.
  - All writers re-parse after writing to confirm the file still
    passes schema validation.
  - `vk.plan.create` and `vk.plan.rework_create` additionally append
    a row to the spec's Implementation Plans table; the spec edit is
    staged in the same change so it lands in the same PR.
"""

from __future__ import annotations

import datetime as _dt
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

import yaml

from vk import refs
from vk._urls import is_cross_repo_spec
from vk.labels import MAX_LABEL_NAME_LEN, normalize_label_slug
from vk.parser import Plan, PlanSchemaError, parse


class StepSpec(TypedDict):
    """Shape of a single step within a `PhaseSpec.tasks[*]['steps']` list."""

    id: str
    text: str


class TaskSpec(TypedDict):
    """Shape of an entry in `PhaseSpec.tasks` — a task with its step list."""

    number: int
    title: str
    steps: list[StepSpec]


class PlanEditError(Exception):
    """Raised when an editing operation can't proceed."""


# ---------------------------------------------------------------------------
# helpers


def _stage(repo_root: Path | None, paths: list[Path]) -> None:
    """git add the paths if we're in a git repo."""
    if repo_root is None:
        return
    rels = [str(p.resolve().relative_to(repo_root)) for p in paths]
    subprocess.run(
        ["git", "-C", str(repo_root), "add", *rels],
        check=False,
        capture_output=True,
    )


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).isoformat(timespec="seconds")


def _coerce_step_texts(d: dict[str, Any]) -> dict[str, Any]:
    """Wrap step text values in LiteralStr so they always emit as `|-`.

    Called before every _yaml_dump so round-tripped phase files (loaded via
    yaml.safe_load and mutated for state updates) keep the same consistent
    block-scalar style as freshly-created plans.
    """
    from vk._yaml import LiteralStr

    for task in d.get("tasks", []):
        for step in task.get("steps", []):
            if "text" in step and not isinstance(step["text"], LiteralStr):
                step["text"] = LiteralStr(step["text"])
    return d


def _yaml_dump(d: dict[str, Any]) -> str:
    """Delegate to the shared plan-yaml dumper (literal block scalars for
    multi-line strings, preserved key order, unicode-as-is)."""
    from vk._yaml import dump_plan_yaml

    return dump_plan_yaml(_coerce_step_texts(d))


# ---------------------------------------------------------------------------
# vk.plan.create


@dataclass(frozen=True)
class PhaseSpec:
    """Lightweight phase shape for `create()` callers."""

    number: int
    title: str
    tag: Literal["agentic", "manual"] = "agentic"
    depends_on: tuple[int, ...] = ()
    tasks: tuple[TaskSpec, ...] = ()


def create(
    *,
    repo_root: Path,
    slug: str,
    spec: Path | str | None,
    target_repo: str,
    vk_version: str,
    phases: list[PhaseSpec],
    prose: str,
    plans_dir: Path | None = None,
) -> Plan:
    """Scaffold a new v2 plan folder + append spec row.

    Returns the parsed Plan. Raises PlanEditError on collisions.
    """
    if plans_dir is None:
        plans_dir = repo_root / "docs" / "superpowers" / "plans"
    folder = plans_dir / slug

    spec_str = str(spec) if spec is not None else None

    # Pre-flight: validate every external precondition BEFORE mutating the
    # filesystem. A spec missing its '## Implementation Plans' section must
    # fail loud here — not after the folder is half-built — so a re-run after
    # adding the section isn't blocked by a stranded folder (#133). Mirrors how
    # `vk apply` validates the diff before `--yes` touches GitHub.
    # Same doctrine for phase numbering: the schema gate (PhaseHeader ge=1)
    # would only reject at the post-write re-parse, stranding the folder.
    for ps in phases:
        if ps.number < 1:
            raise PlanEditError(
                f"phase {ps.number} ({ps.title!r}): phase numbering starts at 1, not 0"
            )
    spec_path: Path | None = None
    if spec_str:
        candidate = (repo_root / spec_str).resolve()
        if candidate.exists():
            _validate_spec_section(candidate)
            spec_path = candidate
        # If the spec file doesn't exist yet, we skip the row — the operator
        # can add it by hand when they create the spec file.

    # Build the expected folder contents in memory (no side effects yet).
    meta = {
        "schema_version": 2,
        "plan": slug,
        "spec": spec_str,
        "target_repo": target_repo,
        "vk_version": vk_version,
        "created": _dt.date.today().isoformat(),
    }
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
            folder, meta_text=meta_text, prose_text=prose_text, phase_files=phase_files
        ):
            raise PlanEditError(f"plan folder already exists: {folder}")
    else:
        plans_dir.mkdir(parents=True, exist_ok=True)
        folder.mkdir()
        (folder / "_meta.yaml").write_text(meta_text)
        (folder / "_prose.md").write_text(prose_text)
        for name, text in phase_files.items():
            (folder / name).write_text(text)
        written.extend([folder / "_meta.yaml", folder / "_prose.md"])
        written.extend(folder / name for name in phase_files)

    if spec_path is not None:
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
) -> bool:
    """True iff `folder` already holds exactly the content `create()` would write.

    Used to distinguish a repairable partial-success state (re-run with the same
    inputs) from a genuine slug collision. `_meta.yaml`'s `created:` date is
    ignored so a repair the next day still matches.
    """
    meta_p = folder / "_meta.yaml"
    if not meta_p.exists() or _strip_created(meta_p.read_text()) != _strip_created(meta_text):
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
    return {
        "schema_version": 2,
        "phase": {
            "number": ps.number,
            "title": ps.title,
            "tag": ps.tag,
            "depends_on": list(ps.depends_on),
            "tracking_issue": None,
        },
        "tasks": tasks,
        "state": {
            "steps": state_steps,
            "completion": {"at": None, "note": None, "observed_prs": []},
        },
    }


# ---------------------------------------------------------------------------
# spec table editing


_SPEC_TABLE_HEADER_RE = re.compile(r"^## Implementation Plans\s*$", re.MULTILINE)


def _validate_spec_section(spec_path: Path) -> None:
    """Pre-flight: confirm the spec has an appendable Implementation Plans table.

    Read-only. Raises the same errors `_append_spec_row` would, but BEFORE any
    folder is created so a failed `create` leaves no stranded state (#133).
    """
    text = spec_path.read_text()
    m = _SPEC_TABLE_HEADER_RE.search(text)
    if not m:
        raise PlanEditError(
            f"{spec_path}: no '## Implementation Plans' section found. "
            f"Add the section (with a 4-column table header) before scaffolding plans."
        )
    after = text[m.end() :]
    if not any(line.strip().startswith("|") for line in after.splitlines()):
        raise PlanEditError(f"{spec_path}: '## Implementation Plans' has no table to append to.")


def _append_spec_row(
    spec_path: Path,
    *,
    plan_name: str,
    repo: str,
    file: str,
    depends_on: str,
) -> None:
    """Append a row to the spec's `## Implementation Plans` table.

    Idempotent: if a row with `file == file` already exists, no-op.
    """
    text = spec_path.read_text()
    m = _SPEC_TABLE_HEADER_RE.search(text)
    if not m:
        raise PlanEditError(
            f"{spec_path}: no '## Implementation Plans' section found. "
            f"Add the section (with a 4-column table header) before scaffolding plans."
        )
    if f"`{file}`" in text or f"| {file} |" in text:
        return  # already present

    # Find end of the table (last consecutive "|" line after the header)
    after = text[m.end() :]
    lines = after.splitlines(keepends=True)
    abs_offset = m.end()
    saw_pipe = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            saw_pipe = True
            abs_offset += len(line)
        elif saw_pipe and stripped == "":
            break
        else:
            abs_offset += len(line)
    if not saw_pipe:
        raise PlanEditError(f"{spec_path}: '## Implementation Plans' has no table to append to.")

    new_row = f"| {plan_name} | `{repo}` | `{file}` | {depends_on} |\n"
    new_text = text[:abs_offset] + new_row + text[abs_offset:]
    spec_path.write_text(new_text)


# ---------------------------------------------------------------------------
# vk.plan.tick / vk.plan.complete_phase


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
    raw = yaml.safe_load(phase_path.read_text())

    current = raw["state"]["steps"][step_id]
    if current.get("state") == state and (note is None or current.get("note") == note):
        return  # idempotent

    raw["state"]["steps"][step_id] = {
        "state": state,
        "ticked_at": _now_iso(),
        "note": note,
    }
    phase_path.write_text(_yaml_dump(raw))

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
    raw = yaml.safe_load(phase_path.read_text())
    raw["state"]["completion"]["at"] = _now_iso()
    if note is not None:
        raw["state"]["completion"]["note"] = note
    phase_path.write_text(_yaml_dump(raw))
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
    raw = yaml.safe_load(phase_path.read_text())
    if raw["phase"].get("tracking_issue") == url:
        return
    raw["phase"]["tracking_issue"] = url
    phase_path.write_text(_yaml_dump(raw))
    try:
        parse(plan_dir)
    except PlanSchemaError as e:
        raise PlanEditError(f"post-write schema validation failed: {e}") from e
    _stage(plan.repo_root, [phase_path])


def clear_tracking_issue(plan_dir: Path, phase_n: int) -> bool:
    """Null phase.tracking_issue in <plan_dir>/<NN>.yaml (inverse of
    `set_tracking_issue` — the `vk undispatch` writeback).

    Returns True when the field was cleared, False when it was already
    null (no-op; the file is not rewritten, keeping re-runs byte-stable).
    Stages but does not commit.
    """
    plan = parse(plan_dir)
    phase_path = plan_dir / f"{phase_n:02d}.yaml"
    if not phase_path.exists():
        raise PlanEditError(f"phase {phase_n} yaml not found: {phase_path}")
    raw = yaml.safe_load(phase_path.read_text())
    if raw["phase"].get("tracking_issue") is None:
        return False
    raw["phase"]["tracking_issue"] = None
    phase_path.write_text(_yaml_dump(raw))
    try:
        parse(plan_dir)
    except PlanSchemaError as e:
        raise PlanEditError(f"post-write schema validation failed: {e}") from e
    _stage(plan.repo_root, [phase_path])
    return True


# ---------------------------------------------------------------------------
# vk.plan.rework_create / rework_add_origin / rework_list


_REWORK_SUFFIX_RE = re.compile(r"-rework-(\d+)$")


def _superpowers_dir(parent_dir: Path) -> Path:
    """Resolve the docs/superpowers/ root from a plan dir in any layout:
    plans/<x>, implemented/plans/<x> (canonical archive, 2026-06-05 spec),
    or archived-plans/<x> (legacy)."""
    if parent_dir.parent.name == "plans" and parent_dir.parent.parent.name == "implemented":
        return parent_dir.parent.parent.parent
    return parent_dir.parent.parent


def _next_rework_number(parent_dir: Path) -> int:
    """Cross-directory N collision check, like v1 next_rework_number.

    Scans active plans/, implemented/plans/ (canonical archive), and
    archived-plans/ (legacy) so an archived rework still claims its number.
    """
    repo_root = _superpowers_dir(parent_dir)
    plans_dir = repo_root / "plans"
    implemented_dir = repo_root / "implemented" / "plans"
    archived_dir = repo_root / "archived-plans"

    parent_slug = parent_dir.name

    def _scan(d: Path) -> set[int]:
        if not d.is_dir():
            return set()
        out: set[int] = set()
        for child in d.iterdir():
            if not child.is_dir():
                continue
            if not child.name.startswith(parent_slug + "-rework-"):
                continue
            m = _REWORK_SUFFIX_RE.search(child.name)
            if m:
                out.add(int(m.group(1)))
        return out

    in_plans = _scan(plans_dir)
    in_archived = _scan(implemented_dir) | _scan(archived_dir)
    collision = in_plans & in_archived
    if collision:
        n = sorted(collision)[0]
        raise PlanEditError(
            f"ambiguous rework state: {parent_slug}-rework-{n} exists in BOTH "
            f"plans/ and an archive dir (implemented/plans/ or archived-plans/). "
            f"Resolve manually before scaffolding."
        )
    combined = in_plans | in_archived
    return max(combined) + 1 if combined else 1


def rework_create(parent_plan_dir: Path) -> Plan:
    """Scaffold a sibling rework plan folder + append spec row.

    Parent stays Complete and untouched. Rework folder is empty of phases
    (operator authors them later, informed by origin_items).
    """
    parent_dir = parent_plan_dir.resolve()
    if not parent_dir.is_dir():
        raise PlanEditError(f"parent plan dir not found: {parent_dir}")
    superpowers_dir = _superpowers_dir(parent_dir)
    in_implemented = (
        parent_dir.parent.name == "plans" and parent_dir.parent.parent.name == "implemented"
    )
    in_active_or_legacy = parent_dir.parent.name in ("plans", "archived-plans")
    if superpowers_dir.name != "superpowers" or not (in_implemented or in_active_or_legacy):
        raise PlanEditError(
            f"parent must live under docs/superpowers/"
            f"{{plans,implemented/plans,archived-plans}}/, got: {parent_dir}"
        )

    parent_plan = parse(parent_dir)
    n = _next_rework_number(parent_dir)
    rework_slug = f"{parent_dir.name}-rework-{n}"
    plans_dir = superpowers_dir / "plans"
    rework_folder = plans_dir / rework_slug
    if rework_folder.exists():
        raise PlanEditError(f"rework folder already exists: {rework_folder}")
    rework_folder.mkdir()

    repo_root = parent_plan.repo_root

    # Canonical lifecycle-independent refs (2026-06-06 spec-path-repair):
    # bare slugs cannot go stale when plans archive.
    parent_rel = parent_dir.name
    prior_rework_rel: str | None = None
    if n > 1:
        prior_dir = _find_prior_rework(parent_dir, below=n)
        if prior_dir is not None:
            prior_rework_rel = prior_dir.name

    parent_spec = parent_plan.meta.spec
    if parent_spec and not is_cross_repo_spec(parent_spec):
        # Same-repo spec refs canonicalize to the bare filename.
        parent_spec = refs.plan_slug(parent_spec)

    meta = {
        "schema_version": 2,
        "plan": rework_slug,
        "spec": parent_spec,
        "target_repo": parent_plan.meta.target_repo,
        "vk_version": parent_plan.meta.vk_version,
        "created": _dt.date.today().isoformat(),
        "parent_plan": parent_rel,
    }
    if prior_rework_rel:
        meta["prior_rework"] = prior_rework_rel
    meta["origin_items"] = []
    (rework_folder / "_meta.yaml").write_text(_yaml_dump(meta))

    parent_title = (
        (parent_dir / "_prose.md").read_text().splitlines()[0]
        if (parent_dir / "_prose.md").exists()
        else parent_dir.name
    )
    prose = (
        f"# {parent_title} — Rework {n}\n\n"
        f"Rework plan against `{parent_dir.name}`. See `_meta.yaml` for "
        f"`parent_plan`, `prior_rework`, and `origin_items`.\n"
    )
    (rework_folder / "_prose.md").write_text(prose)

    written: list[Path] = [rework_folder / "_meta.yaml", rework_folder / "_prose.md"]

    # Append spec row — lifecycle-resolved (2026-06-06 spec-path-repair):
    # the spec may have archived to implemented/specs/ since the parent
    # plan recorded it; the old exact-path check silently skipped then.
    if (
        parent_plan.meta.spec
        and repo_root is not None
        and not is_cross_repo_spec(parent_plan.meta.spec)
    ):
        spec_res = refs.resolve_spec_ref(parent_plan.meta.spec, repo_root)
        if spec_res.path is not None:
            _append_spec_row(
                spec_res.path,
                plan_name=rework_slug,
                repo=parent_plan.meta.target_repo,
                file=rework_slug,
                depends_on=parent_plan.meta.plan,
            )
            written.append(spec_res.path)

    _stage(repo_root, written)
    return parse(rework_folder)


def _find_prior_rework(parent_dir: Path, *, below: int) -> Path | None:
    """Highest archived rework N below `below` (in archived-plans/)."""
    superpowers_dir = parent_dir.parent.parent
    archived_dir = superpowers_dir / "archived-plans"
    if not archived_dir.is_dir():
        return None
    parent_slug = parent_dir.name
    best_n = -1
    best: Path | None = None
    for child in archived_dir.iterdir():
        if not child.is_dir():
            continue
        if not child.name.startswith(parent_slug + "-rework-"):
            continue
        m = _REWORK_SUFFIX_RE.search(child.name)
        if m:
            n = int(m.group(1))
            if n < below and n > best_n:
                best_n = n
                best = child
    return best


def rework_add_origin(
    rework_dir: Path,
    *,
    item: str,
    source: str,
    track: str,
) -> int:
    """Append an item to _meta.origin_items. Returns assigned id."""
    plan = parse(rework_dir)
    if plan.meta.parent_plan is None:
        raise PlanEditError(f"{rework_dir} is not a rework plan (no parent_plan in _meta)")

    raw = yaml.safe_load((rework_dir / "_meta.yaml").read_text())
    items = list(raw.get("origin_items") or [])
    next_id = (max((it["id"] for it in items), default=0) + 1) if items else 1
    items.append({"id": next_id, "item": item, "source": source, "track": track})
    raw["origin_items"] = items
    (rework_dir / "_meta.yaml").write_text(_yaml_dump(raw))
    parse(rework_dir)  # validate
    _stage(plan.repo_root, [rework_dir / "_meta.yaml"])
    return next_id


@dataclass(frozen=True)
class ReworkRecord:
    parent_slug: str
    rework_number: int
    status: Literal["Not Started", "In Progress", "Complete"]
    open_steps: int
    origin_item_count: int
    by_track: tuple[tuple[str, int], ...]  # frozen for hashability
    folder_path: Path
    spec_path: Path | None


def rework_list(repo_root: Path, *, include_archived: bool = False) -> list[ReworkRecord]:
    """Glob plan folders; filter by parent_plan; aggregate status."""
    dirs = [repo_root / "docs" / "superpowers" / "plans"]
    if include_archived:
        dirs.append(repo_root / "docs" / "superpowers" / "archived-plans")

    records: list[ReworkRecord] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for folder in sorted(d.iterdir()):
            if not folder.is_dir():
                continue
            try:
                plan = parse(folder)
            except PlanSchemaError:
                continue
            if plan.meta.parent_plan is None:
                continue
            m = _REWORK_SUFFIX_RE.search(folder.name)
            n = int(m.group(1)) if m else 0
            parent_slug = re.sub(r"-rework-\d+$", "", folder.name)

            total_steps = sum(len(t.steps) for p in plan.phases for t in p.tasks)
            ticked = sum(
                1 for p in plan.phases for ss in p.state.steps.values() if ss.state in ("x", "-")
            )
            open_steps = total_steps - ticked
            status: Literal["Not Started", "In Progress", "Complete"]
            if total_steps == 0 or ticked == 0:
                status = "Not Started"
            elif ticked == total_steps:
                status = "Complete"
            else:
                status = "In Progress"

            by_track: dict[str, int] = {}
            for it in plan.meta.origin_items:
                by_track[it.track] = by_track.get(it.track, 0) + 1

            spec_path = (repo_root / plan.meta.spec).resolve() if plan.meta.spec else None
            records.append(
                ReworkRecord(
                    parent_slug=parent_slug,
                    rework_number=n,
                    status=status,
                    open_steps=open_steps,
                    origin_item_count=len(plan.meta.origin_items),
                    by_track=tuple(sorted(by_track.items())),
                    folder_path=folder,
                    spec_path=spec_path,
                )
            )
    return records


# ---------------------------------------------------------------------------
# vk.plan.self_review (lints)

# Agentic-purity gate (#252): a skipped (`state: '-'`) step in an AGENTIC
# phase whose note defers it forward is a mis-scoped manual step — an
# agentic phase must be fully agent-completable. The note either names a
# later phase ("Executed in Phase 5") or uses a defer-phrase.
_PHASE_REF_NOTE_RE = re.compile(r"[Pp]hase\s+(\d+)")
_DEFER_PHRASES = ("defer", "executed in", "moved to")

# Part 2 of the gate: manual-operation language in a pending agentic step.
# Deliberately conservative (precision over recall) — the deferred-step
# lint above is the load-bearing detector; this one catches the authoring
# mistake before any deferral happens. Word-boundary, case-insensitive.
_MANUAL_VERB_RES = tuple(
    re.compile(rf"\b{phrase}\b", re.IGNORECASE)
    for phrase in (
        "manually",
        "by hand",
        "via the UI",
        "in the UI",
        "click",
        "SOPS",
        "operator sets",
        "operator provides",
    )
)


def _note_defers_forward(note: str, phase_number: int) -> bool:
    """True iff `note` defers execution beyond `phase_number`.

    An explicit phase reference decides outright: forward ("Executed in
    Phase 5" on phase 3) is deferral; backward ("ported from Phase 1") is
    history and disarms the defer-phrases. Only refless notes fall through
    to the phrase scan.
    """
    m = _PHASE_REF_NOTE_RE.search(note)
    if m:
        return int(m.group(1)) > phase_number
    lowered = note.lower()
    return any(phrase in lowered for phrase in _DEFER_PHRASES)


@dataclass(frozen=True)
class ReviewIssue:
    severity: Literal["info", "warn", "error"]
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.message}"


def self_review(plan: Plan) -> list[ReviewIssue]:
    """Soft lints beyond schema validation."""
    issues: list[ReviewIssue] = []

    # Cyclic depends_on
    graph = {p.phase.number: set(p.phase.depends_on) for p in plan.phases}
    for n, deps in graph.items():
        if _has_cycle(graph, n):
            issues.append(
                ReviewIssue(
                    severity="error",
                    message=f"phase {n} is in a dependency cycle: depends_on={sorted(deps)}",
                )
            )
            break

    # Manual phase with completion.at but no note
    for phase in plan.phases:
        c = phase.state.completion
        if c.at is not None and phase.phase.tag == "manual" and not c.note:
            issues.append(
                ReviewIssue(
                    severity="error",
                    message=(
                        f"phase {phase.phase.number} is manual and complete but has "
                        f"no completion.note — manual phases require a note."
                    ),
                )
            )

    # Agentic-purity gate (#252). An agentic phase is meant to be fully
    # agent-completable and end in one PR. Two error-severity detectors per
    # agentic phase (the gate is enforced, not advisory):
    #   1. Deferred steps — a step skipped (`'-'`) with a forward-deferring
    #      note was manual by nature and belongs in a manual phase.
    #   2. Manual-operation language in a not-yet-completed step. Completed
    #      ('x') steps are exempt — a ticked step already proved
    #      agent-completable, and the exemption keeps historical plans (or
    #      step texts that merely QUOTE the phrases) from retro-erroring.
    #      At authoring time every step is unticked, so the gate bites
    #      exactly where it should.
    for phase in plan.phases:
        if phase.phase.tag != "agentic":
            continue
        n = phase.phase.number
        for step_id, ss in sorted(phase.state.steps.items()):
            if ss.state != "-" or not ss.note:
                continue
            if _note_defers_forward(ss.note, n):
                issues.append(
                    ReviewIssue(
                        severity="error",
                        message=(
                            f"phase {n} (agentic) step {step_id} is deferred "
                            f"(note: {ss.note!r}) — manual-by-nature work must move "
                            f"into a manual phase; agentic phases must be pure agentic."
                        ),
                    )
                )
        for task in phase.tasks:
            for step in task.steps:
                state = phase.state.steps.get(step.id)
                if state is not None and state.state == "x":
                    continue
                hit = next((p for p in _MANUAL_VERB_RES if p.search(step.text)), None)
                if hit is not None:
                    issues.append(
                        ReviewIssue(
                            severity="error",
                            message=(
                                f"phase {n} (agentic) step {step.id} reads like a "
                                f"manual operation (matched {hit.pattern!r}) — move it "
                                f"into a manual phase; agentic phases must be pure agentic."
                            ),
                        )
                    )

    # Same-repo-form spec that doesn't resolve locally (#248): almost always a
    # malformed cross-repo ref missing the `owner/repo:` prefix, which apply's
    # reachability gate treats as a missing same-repo file and flags unreachable.
    spec = plan.meta.spec
    if (
        spec
        and spec not in ("none", "null", "—", "-")
        and plan.repo_root is not None
        and not is_cross_repo_spec(spec)
        and ("/" in spec or spec.endswith(".md"))
        and not (plan.repo_root / spec).exists()
    ):
        issues.append(
            ReviewIssue(
                severity="warn",
                message=(
                    f"spec {spec!r} does not resolve under the repo root. If the spec "
                    f"lives in another repo, use the cross-repo form "
                    f"'owner/repo:path/to/spec.md' (#248); otherwise create the file."
                ),
            )
        )

    # Over-long plan label (#249): `plan:<slug>` past GitHub's 50-char label
    # cap is auto-truncated+hashed at dispatch, but the operator should know —
    # a hashed routing key is opaque; a shorter slug reads better on the board.
    # Check the NORMALIZED slug — that's the shape that actually ships; a raw
    # dated slug whose date-free form fits is not over-long. Built by hand
    # (not via `labels.plan_label`) on purpose: the factory's `.name` is
    # already bounded to 50 chars, so overflow would be undetectable from it.
    normalized_plan_label = f"plan:{normalize_label_slug(plan.meta.plan)}"
    if len(normalized_plan_label) > MAX_LABEL_NAME_LEN:
        issues.append(
            ReviewIssue(
                severity="warn",
                message=(
                    f"plan label {normalized_plan_label!r} is "
                    f"{len(normalized_plan_label)} chars (>{MAX_LABEL_NAME_LEN}); "
                    f"it will be truncated + hashed for GitHub. Consider a "
                    f"shorter slug (rework suffixes push long slugs over)."
                ),
            )
        )

    return issues


def _has_cycle(graph: dict[int, set[int]], start: int) -> bool:
    """DFS for back-edges starting from `start`."""
    stack: list[tuple[int, set[int]]] = [(start, {start})]
    while stack:
        node, ancestors = stack.pop()
        for dep in graph.get(node, ()):
            if dep in ancestors:
                return True
            stack.append((dep, ancestors | {dep}))
    return False
