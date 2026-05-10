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

from vk._yaml import dump_plan_yaml
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

# A v2 rework slug has the form `<parent-slug>-rework-<N>` (anchored at end).
# Plain substring matching on `"-rework-"` false-positives on plans that
# merely *implement* a rework feature (e.g. `2026-04-22-vk-plan-rework-command`).
_REWORK_SLUG_RE = re.compile(r"-rework-\d+$")


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

    # Rewrite spec files (drop Status column + adjust File cells).
    # File-cell rewrites are gated on the corresponding folder actually
    # existing on disk — if a plan failed to migrate, its row stays
    # pointing at `<slug>.md` and a re-run will fix it once the underlying
    # MigrationError is resolved.
    specs_dir = sp / "specs"
    if specs_dir.is_dir() and not dry_run:
        for spec_md in sorted(specs_dir.glob("*.md")):
            _rewrite_spec_table(spec_md, repo_root=repo_root)

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
        tr for p in v1plan.phases if (tr := getattr(p, "target_repo", None)) is not None
    }
    if len(target_repos) > 1:
        raise MigrationError(
            f"{md_path}: phases declare different target repos {sorted(target_repos)}. "
            f"Split into one plan per target repo before migrating."
        )
    target_repo = next(iter(target_repos)) if target_repos else "derio-net/superpowers-for-vk"

    if not re.match(r"^\d{4}-\d{2}-\d{2}-", slug):
        raise MigrationError(
            f"{md_path}: slug does not start with a YYYY-MM-DD date. "
            f"Rename the file to begin with the plan's creation date "
            f"(e.g. 2026-05-10-{slug}.md) before migrating — v2 plans "
            f"require an authoritative `created` date in _meta.yaml."
        )

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
    if _REWORK_SLUG_RE.search(slug):
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
        "created": slug[:10],  # YYYY-MM-DD prefix is enforced above
    }
    if parent_plan:
        meta["parent_plan"] = parent_plan
    if prior_rework:
        meta["prior_rework"] = prior_rework
    if origin_items:
        meta["origin_items"] = origin_items
    (new_folder / "_meta.yaml").write_text(dump_plan_yaml(meta))

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
        (new_folder / f"{phase.number:02d}.yaml").write_text(dump_plan_yaml(phase_doc))

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
        # Track is free-form per the v2 spec; preserve the original cell
        # verbatim (compounds like "decision → development" or
        # "development (future-triggered)" are valid).
        items.append(
            {
                "id": n,
                "item": cells[1],
                "source": cells[2],
                "track": cells[3],
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


def _rewrite_spec_table(spec_path: Path, *, repo_root: Path) -> None:
    """Drop Status column + rewrite `<path>.md` File cells to `<path>/`.

    Two transformations:
      - 5-col tables (Plan | Repo | File | Status | Depends on) → drop Status.
      - File cells matching `<path>.md` are rewritten to `<path>/` ONLY when
        the corresponding folder exists in the repo. This way a partial
        migration failure leaves stale `.md` cells alone instead of pointing
        at archived files; the next successful re-run completes the rewrite.

    Idempotent: 4-col tables and `<path>/` cells pass through unchanged.
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
            # Drop Status column if present (5 → 4 cells).
            if len(cells) == 5:
                cells = [cells[0], cells[1], cells[2], cells[4]]
            elif len(cells) != 4:
                new_after_lines.append(line)  # weird shape; leave alone
                continue
            # Now 4 cells: rewrite File cell (index 2) if it points at a
            # `.md` file whose v2 folder exists. Strip backticks for the
            # filesystem check, preserve the surrounding spacing/backticks
            # in the rewrite.
            file_cell = cells[2]
            new_file_cell = _rewrite_file_cell(file_cell, repo_root=repo_root)
            cells[2] = new_file_cell
            new_after_lines.append("|" + "|".join(cells) + "|\n")
        elif in_table and stripped == "":
            in_table = False
            new_after_lines.append(line)
        else:
            new_after_lines.append(line)

    new_text = text[:after_start] + "".join(new_after_lines)
    spec_path.write_text(new_text)


_BACKTICKED_PATH_RE = re.compile(r"`([^`]+\.md)`")


def _rewrite_file_cell(cell: str, *, repo_root: Path) -> str:
    """If the cell wraps `<path>.md` and `<path>/` exists, rewrite to `<path>/`.

    Otherwise leave the cell alone (header rows, separators, manual rows
    with `—`, and rows for plans that didn't migrate all pass through).
    """

    def _maybe_swap(m: re.Match[str]) -> str:
        path = m.group(1)
        folder = repo_root / path.removesuffix(".md")
        if folder.is_dir():
            return f"`{path.removesuffix('.md')}/`"
        return m.group(0)

    return _BACKTICKED_PATH_RE.sub(_maybe_swap, cell)
