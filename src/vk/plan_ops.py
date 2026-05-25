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
            file=str(folder.resolve().relative_to(repo_root)) + "/",
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


# ---------------------------------------------------------------------------
# vk.plan.rework_create / rework_add_origin / rework_list


_REWORK_SUFFIX_RE = re.compile(r"-rework-(\d+)$")


def _next_rework_number(parent_dir: Path) -> int:
    """Cross-directory N collision check, like v1 next_rework_number."""
    repo_root = parent_dir.parent.parent  # plans/ or archived-plans/ -> superpowers/
    plans_dir = repo_root / "plans"
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
    in_archived = _scan(archived_dir)
    collision = in_plans & in_archived
    if collision:
        n = sorted(collision)[0]
        raise PlanEditError(
            f"ambiguous rework state: {parent_slug}-rework-{n} exists in BOTH "
            f"plans/ and archived-plans/. Resolve manually before scaffolding."
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
    superpowers_dir = parent_dir.parent.parent
    if superpowers_dir.name != "superpowers" or parent_dir.parent.name not in (
        "plans",
        "archived-plans",
    ):
        raise PlanEditError(
            f"parent must live under docs/superpowers/{{plans,archived-plans}}/, got: {parent_dir}"
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

    parent_rel = str(parent_dir.relative_to(repo_root)) + "/" if repo_root else str(parent_dir)
    prior_rework_rel: str | None = None
    if n > 1:
        prior_dir = _find_prior_rework(parent_dir, below=n)
        if prior_dir is not None and repo_root is not None:
            prior_rework_rel = str(prior_dir.resolve().relative_to(repo_root)) + "/"

    meta = {
        "schema_version": 2,
        "plan": rework_slug,
        "spec": parent_plan.meta.spec,
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

    # Append spec row
    if parent_plan.meta.spec and repo_root is not None:
        spec_path = (repo_root / parent_plan.meta.spec).resolve()
        if spec_path.exists():
            _append_spec_row(
                spec_path,
                plan_name=rework_slug,
                repo=parent_plan.meta.target_repo,
                file=str(rework_folder.resolve().relative_to(repo_root)) + "/",
                depends_on=parent_plan.meta.plan,
            )
            written.append(spec_path)

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
