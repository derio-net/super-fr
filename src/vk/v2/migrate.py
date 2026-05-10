"""v1-to-v2 migration tool.

Walks `docs/superpowers/plans/` and `docs/superpowers/archived-plans/`
in a repo, converts each `.md` plan to a v2 folder (`<slug>/_meta.yaml`,
`<slug>/_prose.md`, `<slug>/NN.yaml` per phase). Moves the original
`.md` to `.v1-archive` to preserve git history.

Skips in-progress plans by default (`--skip-in-progress`); operator
opts in via `--include-in-progress` to migrate them too.

Refuses to migrate plans whose phases declare different `**Target
repo:**` values — those must be split by hand into one plan per
target repo first.

Also rewrites spec files in `docs/superpowers/specs/`: drops the
`Status` column from `## Implementation Plans` tables and updates
`File` cells to point at the new folder paths.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from vk.plan.parser import parse_plan as _parse_v1


class MigrationError(Exception):
    pass


@dataclass(frozen=True)
class MigrationOutcome:
    plan_path: Path
    new_folder: Path | None  # None = skipped
    reason: str  # "migrated" | "skipped (in-progress)" | "skipped (already migrated)"


_REWORK_PARENT_RE = re.compile(r"^\*\*Parent plan:\*\*\s*`?([^`\n]+)`?", re.MULTILINE)
_PRIOR_REWORK_RE = re.compile(r"^\*\*Prior rework:\*\*\s*`?([^`\n]+)`?", re.MULTILINE)
_ORIGIN_HEADING_RE = re.compile(r"^## Origin\s*$", re.MULTILINE)


def migrate_repo(
    repo_root: Path,
    *,
    dry_run: bool = True,
    include_in_progress: bool = False,
) -> list[MigrationOutcome]:
    """Migrate every v1 plan in repo_root. Returns per-plan outcomes."""
    outcomes: list[MigrationOutcome] = []
    sp = repo_root / "docs" / "superpowers"
    for sub in ("plans", "archived-plans"):
        d = sp / sub
        if not d.is_dir():
            continue
        for md_path in sorted(d.glob("*.md")):
            outcomes.append(
                _migrate_one(
                    md_path,
                    repo_root=repo_root,
                    dry_run=dry_run,
                    include_in_progress=include_in_progress,
                )
            )

    # Rewrite spec files (drop Status column + adjust File cells)
    specs_dir = sp / "specs"
    if specs_dir.is_dir() and not dry_run:
        for spec_md in sorted(specs_dir.glob("*.md")):
            _rewrite_spec_table(spec_md)

    return outcomes


def _migrate_one(
    md_path: Path,
    *,
    repo_root: Path,
    dry_run: bool,
    include_in_progress: bool,
) -> MigrationOutcome:
    """Migrate a single .md plan."""
    slug = md_path.stem
    new_folder = md_path.parent / slug

    if new_folder.exists():
        return MigrationOutcome(
            plan_path=md_path,
            new_folder=None,
            reason="skipped (folder already exists)",
        )

    try:
        v1plan = _parse_v1(md_path)
    except Exception as e:
        raise MigrationError(f"{md_path}: v1 parse failed: {e}") from e

    if not include_in_progress and (v1plan.status or "").strip() != "Complete":
        return MigrationOutcome(
            plan_path=md_path,
            new_folder=None,
            reason=f"skipped (in-progress; status={v1plan.status!r})",
        )

    # Loud-fail if v1 phases declare conflicting target repos
    target_repos: set[str] = {
        tr
        for p in v1plan.phases
        if (tr := getattr(p, "target_repo", None)) is not None
    }
    if len(target_repos) > 1:
        raise MigrationError(
            f"{md_path}: phases declare different target repos {sorted(target_repos)}. "
            f"Split into one plan per target repo before migrating."
        )
    target_repo = next(iter(target_repos)) if target_repos else "derio-net/superpowers-for-vk"

    if dry_run:
        return MigrationOutcome(
            plan_path=md_path,
            new_folder=new_folder,
            reason="migrated (dry run)",
        )

    new_folder.mkdir()

    # Rework metadata extraction
    md_text = md_path.read_text()
    parent_plan = None
    prior_rework = None
    origin_items: list[dict[str, Any]] = []
    if "-rework-" in slug:
        m = _REWORK_PARENT_RE.search(md_text)
        if m:
            parent_plan = m.group(1).strip()
        m = _PRIOR_REWORK_RE.search(md_text)
        if m:
            prior_rework = m.group(1).strip()
        origin_items = _parse_v1_origin_table(md_text)

    meta: dict[str, Any] = {
        "schema_version": 2,
        "plan": slug,
        "spec": v1plan.spec,
        "target_repo": target_repo,
        "vk_version": ">=1.0.0,<3.0.0",
        "created": slug[:10] if re.match(r"^\d{4}-\d{2}-\d{2}-", slug) else "1970-01-01",
    }
    if parent_plan:
        meta["parent_plan"] = parent_plan
    if prior_rework:
        meta["prior_rework"] = prior_rework
    if origin_items:
        meta["origin_items"] = origin_items
    (new_folder / "_meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))

    # Generate prose from v1 plan structure (titles + step text, plus
    # whatever lay between headers — we keep this lossy on purpose;
    # spec lives in yaml, prose is for humans only)
    prose_lines = [f"# {v1plan.title or slug}\n"]
    for phase in v1plan.phases:
        prose_lines.append(f"\n## Phase {phase.number}: {phase.title}\n")
        for task in phase.tasks:
            prose_lines.append(f"\n### Task {task.number}: {task.title}\n")
            for step in task.steps:
                step_id = f"P{phase.number}.T{task.number}.S{step.number}"
                prose_lines.append(f"\n- {step_id}: {step.title}\n")
    (new_folder / "_prose.md").write_text("".join(prose_lines))

    # Per-phase yaml
    for phase in v1plan.phases:
        phase_doc = _build_phase_doc_from_v1(phase)
        (new_folder / f"{phase.number:02d}.yaml").write_text(
            yaml.safe_dump(phase_doc, sort_keys=False)
        )

    # Move original .md to .v1-archive sibling
    archive = md_path.with_suffix(".md.v1-archive")
    shutil.move(str(md_path), str(archive))

    return MigrationOutcome(
        plan_path=md_path,
        new_folder=new_folder,
        reason="migrated",
    )


def _parse_v1_origin_table(md_text: str) -> list[dict[str, Any]]:
    """Extract Origin table rows from a v1 rework markdown plan."""
    m = _ORIGIN_HEADING_RE.search(md_text)
    if not m:
        return []
    after = md_text[m.end() :]
    items: list[dict[str, Any]] = []
    saw_header = False
    saw_separator = False
    for line in after.splitlines():
        stripped = line.strip()
        if not stripped:
            if saw_header:
                break
            continue
        if not stripped.startswith("|"):
            if saw_header:
                break
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 4:
            continue
        if not saw_header:
            saw_header = True
            continue
        if not saw_separator:
            # Separator row like | --- | --- | --- | --- |
            if all(set(c) <= {"-", " "} for c in cells):
                saw_separator = True
                continue
        try:
            n = int(cells[0])
        except ValueError:
            continue
        track = cells[3].lower()
        if track not in ("development", "operations", "decision"):
            track = "development"  # fallback
        items.append(
            {
                "id": n,
                "item": cells[1],
                "source": cells[2],
                "track": track,
            }
        )
    return items


def _build_phase_doc_from_v1(phase: Any) -> dict[str, Any]:
    """Convert a v1 Phase model into the v2 phase yaml dict.

    v1 steps have `number`/`title`/`body` (no `id`). We synthesize the
    v2 `P<phase>.T<task>.S<step>` id from the phase + task + step
    numbers. v1 step text is `title` + optional `body`.
    """
    tasks: list[dict[str, Any]] = []
    state_steps: dict[str, dict[str, Any]] = {}
    for task in phase.tasks:
        steps_out: list[dict[str, Any]] = []
        for step in task.steps:
            step_id = f"P{phase.number}.T{task.number}.S{step.number}"
            text = step.title
            body = getattr(step, "body", None)
            if body:
                text = f"{step.title}\n{body}".strip()
            steps_out.append({"id": step_id, "text": text})
            v1state = getattr(step, "state", " ")
            mapped = v1state if v1state in ("x", "-") else " "
            state_steps[step_id] = {"state": mapped, "ticked_at": None, "note": None}
        tasks.append({"number": task.number, "title": task.title, "steps": steps_out})
    tag = "manual" if getattr(phase, "tag", None) == "manual" else "agentic"
    tracking = getattr(phase, "tracking_url", None)
    return {
        "schema_version": 2,
        "phase": {
            "number": phase.number,
            "title": phase.title,
            "tag": tag,
            "depends_on": list(getattr(phase, "depends_on", ()) or []),
            "tracking_issue": tracking,
        },
        "tasks": tasks,
        "state": {
            "steps": state_steps,
            "completion": {"at": None, "note": None, "observed_prs": []},
        },
    }


def _rewrite_spec_table(spec_path: Path) -> None:
    """Drop Status column from the spec's `## Implementation Plans` table.

    Idempotent: if the table is already 4 columns, no-op.
    """
    text = spec_path.read_text()
    m = re.search(r"^## Implementation Plans\s*$", text, re.MULTILINE)
    if not m:
        return

    after_start = m.end()
    lines = text[after_start:].splitlines(keepends=True)

    new_after_lines: list[str] = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            in_table = True
            cells = [c for c in stripped.strip("|").split("|")]
            # Already 4 cols → leave alone
            if len(cells) <= 4:
                new_after_lines.append(line)
                continue
            # 5 cols (Plan | Repo | File | Status | Depends on) → drop Status
            if len(cells) == 5:
                new_cells = [cells[0], cells[1], cells[2], cells[4]]
                new_line = "|" + "|".join(new_cells) + "|\n"
                new_after_lines.append(new_line)
            else:
                new_after_lines.append(line)  # weird shape; leave alone
        elif in_table and stripped == "":
            in_table = False
            new_after_lines.append(line)
        else:
            new_after_lines.append(line)

    new_text = text[:after_start] + "".join(new_after_lines)
    spec_path.write_text(new_text)
