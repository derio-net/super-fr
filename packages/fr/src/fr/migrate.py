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
import subprocess
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fr import plan_ops, refs
from fr._urls import is_cross_repo_spec
from fr._yaml import LiteralStr, dump_plan_yaml
from fr.parser import PlanSchemaError
from fr.parser import parse as _parse_v2
from fr.plan.parser import _RE_STEP, _strip_fenced_regions
from fr.plan.parser import parse_plan as _parse_v1
from fr.plan_config import strip_dead_keys


class MigrationError(Exception):
    pass


@dataclass(frozen=True)
class MigrationOutcome:
    plan_path: Path
    new_folder: Path | None  # None = skipped
    reason: str  # "migrated" | "skipped (in-progress)" | "skipped (already migrated)"
    warnings: tuple[str, ...] = ()  # non-fatal lossy-migration notices (#245)


_REWORK_PARENT_RE = re.compile(r"^\*\*Parent plan:\*\*\s*`?([^`\n]+)`?", re.MULTILINE)
_PRIOR_REWORK_RE = re.compile(r"^\*\*Prior rework:\*\*\s*`?([^`\n]+)`?", re.MULTILINE)
_ORIGIN_HEADING_RE = re.compile(r"^## Origin\s*$", re.MULTILINE)

# A v2 rework slug has the form `<parent-slug>-rework-<N>` (anchored at end).
# Plain substring matching on `"-rework-"` false-positives on plans that
# merely *implement* a rework feature (e.g. `2026-04-22-vk-plan-rework-command`).
_REWORK_SLUG_RE = re.compile(r"-rework-\d+$")

# Body-extraction helpers. The v1 parser only recognises canonical
# `### Task N:` headers and `- [x] **Step N: ...**` step markers. Plans
# in the wild use variants the parser drops on the floor — most commonly
# `### Step N:` (content-factory) or sub-items like `- [x] **free-form
# title**` that lack the `Step N:` prefix. When a task ends up with zero
# parsed steps, or a phase with zero parsed tasks, the migrator falls back
# to splicing the raw markdown into the v2 yaml as a single step body so
# nothing is silently dropped.
#
# The `(?:\s+\[(?:agentic|manual)\])?` tail mirrors `_RE_TASK` in the parser:
# both ignore optional task-level tag suffixes so group(2) captures the bare
# title. Without this, title-based body lookup would compare `"Bootstrap"`
# from the parsed `Task` model against `"Bootstrap [agentic]"` in raw md_text
# and silently miss.
_BODY_PHASE_RE = re.compile(r"^## Phase\s+(\S+):", re.MULTILINE)
_BODY_TASKLIKE_RE = re.compile(
    r"^### (?:Task|Step)\s+(\d+(?:\.\d+)*[a-z]?):"
    r"\s*(.+?)(?:\s+\[(?:agentic|manual)\])?\s*$",
    re.MULTILINE,
)


def migrate_repo(
    repo_root: Path,
    *,
    dry_run: bool = True,
    include_in_progress: bool = False,
    force: bool = False,
    target_repo: str | None = None,
) -> list[MigrationOutcome]:
    """Migrate every v1 plan in repo_root. Returns per-plan outcomes.

    When ``force=True``, an existing `<slug>/` folder paired with a
    `<slug>.md.v1-archive` sibling is treated as a re-migration target:
    the folder is removed, the archive renamed back to `<slug>.md`, and
    migration runs fresh. Use this to repair plans migrated by older
    buggy versions (e.g. pre-2.0.4 silently dropped non-canonical step
    formats).
    """
    outcomes: list[MigrationOutcome] = []
    sp = repo_root / "docs" / "superpowers"
    # Canonical layout: active plans/ + implemented/plans/ (the archive,
    # 2026-06-05 spec). Legacy archived-plans/ kept in the walk for direct
    # library callers; the CLI's layout guard prevents reaching it there.
    for sub in ("plans", "implemented/plans", "archived-plans"):
        d = sp / sub
        if not d.is_dir():
            continue
        # When `force` is on we also pick up `<slug>.md.v1-archive` files
        # whose corresponding `<slug>/` folder needs re-migration.
        md_paths = list(d.glob("*.md"))
        if force:
            for archive in d.glob("*.md.v1-archive"):
                # archive.stem is `<slug>.md` (archive.suffix is `.v1-archive`)
                restored = archive.with_suffix("")
                if not restored.exists():
                    md_paths.append(restored)
        for md_path in sorted(md_paths):
            outcomes.append(
                _migrate_one(
                    md_path,
                    repo_root=repo_root,
                    dry_run=dry_run,
                    include_in_progress=include_in_progress,
                    force=force,
                    target_repo=target_repo,
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

    # Strip dead keys from the repo's plan-config.yaml (save_to + dispatch:).
    cfg = sp / "plan-config.yaml"
    if cfg.is_file():
        new_text, removals = strip_dead_keys(cfg.read_text())
        if removals:
            verb = "would remove" if dry_run else "removed"
            outcomes.append(
                MigrationOutcome(
                    plan_path=cfg,
                    new_folder=None,
                    reason=f"plan-config: {verb} {', '.join(removals)}",
                )
            )
            if not dry_run:
                cfg.write_text(new_text)

    return outcomes


def _migrate_one(
    md_path: Path,
    *,
    repo_root: Path,
    dry_run: bool,
    include_in_progress: bool,
    force: bool = False,
    target_repo: str | None = None,
) -> MigrationOutcome:
    """Migrate a single .md plan."""
    slug = md_path.stem
    new_folder = md_path.parent / slug
    archive = md_path.with_suffix(".md.v1-archive")

    if force and new_folder.exists() and archive.exists():
        # Re-migration path: tear down the previously-migrated folder, restore
        # the archived .md, and let the rest of this function run fresh.
        if dry_run:
            return MigrationOutcome(
                plan_path=md_path,
                new_folder=new_folder,
                reason="re-migrated (dry run, --force)",
            )
        shutil.rmtree(new_folder)
        _git_mv_best_effort(repo_root, archive, md_path)

    if new_folder.exists():
        return MigrationOutcome(
            plan_path=md_path,
            new_folder=None,
            reason="skipped (folder already exists)",
        )

    if not md_path.exists():
        # `--force` left the archive in place but the .md isn't here either.
        # Skip silently — the operator might be re-running without expecting
        # all archives to be processable.
        return MigrationOutcome(
            plan_path=md_path,
            new_folder=None,
            reason="skipped (no .md to migrate)",
        )

    try:
        v1plan = _parse_v1(md_path)
    except Exception as e:
        raise MigrationError(f"{md_path}: v1 parse failed: {e}") from e

    if not include_in_progress and (v1plan.status or "").strip() != "Complete":
        return MigrationOutcome(
            plan_path=md_path,
            new_folder=None,
            reason=(
                f"skipped (in-progress; status={v1plan.status!r}; "
                f"use --include-in-progress to convert anyway)"
            ),
        )

    # Resolve the target repo. Precedence:
    #   1. A single per-phase `**Target repo:**` declaration (explicit in plan).
    #   2. The operator-supplied --target-repo (resolves the empty case AND a
    #      multi-repo conflict).
    # Never silently default to the plugin's own repo — that filed Issues
    # against the wrong repo for ~45/71 of frank's migrated plans (#245 Bug 1).
    target_repos: set[str] = {
        tr for p in v1plan.phases if (tr := getattr(p, "target_repo", None)) is not None
    }
    if len(target_repos) > 1:
        if target_repo is None:
            raise MigrationError(
                f"{md_path}: phases declare different target repos {sorted(target_repos)}. "
                f"Split into one plan per target repo, or pass --target-repo to override."
            )
        resolved_target = target_repo
    elif len(target_repos) == 1:
        resolved_target = next(iter(target_repos))
    elif target_repo is not None:
        resolved_target = target_repo
    else:
        raise MigrationError(
            f"{md_path}: no target repo. The v1 plan declares no '**Target repo:**' "
            f"line and no --target-repo was given. Re-run with "
            f"--target-repo owner/repo (the repo Issues should be filed against)."
        )

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
        "target_repo": resolved_target,
        # Match `fr plan create`'s default (fr_version) — migrated plans are v2 plans (#245).
        "fr_version": ">=3.0.0,<4.0.0",
        "created": slug[:10],  # YYYY-MM-DD prefix is enforced above
    }
    if parent_plan:
        meta["parent_plan"] = parent_plan
    if prior_rework:
        meta["prior_rework"] = prior_rework
    if origin_items:
        meta["origin_items"] = origin_items
    (new_folder / "_meta.yaml").write_text(dump_plan_yaml(meta))

    # Flat-format plans (no ## Phase headings) land in v1plan.tasks with an
    # empty v1plan.phases. Wrap them into a synthetic Phase 1 so the migration
    # produces 01.yaml instead of an empty folder.
    phases_to_emit: list[Any]
    if v1plan.phases:
        phases_to_emit = list(v1plan.phases)
    else:
        phases_to_emit = [
            types.SimpleNamespace(
                number=1,
                title=v1plan.title or "Phase 1",
                tag=None,
                depends_on=(),
                tracking_url=None,
                tasks=list(v1plan.tasks),
            )
        ]

    # Generate prose from v1 plan structure (titles + step text, plus
    # whatever lay between headers — we keep this lossy on purpose;
    # spec lives in yaml, prose is for humans only)
    prose_lines = [f"# {v1plan.title or slug}\n"]
    for phase in phases_to_emit:
        prose_lines.append(f"\n## Phase {phase.number}: {phase.title}\n")
        for task in phase.tasks:
            prose_lines.append(f"\n### Task {task.number}: {task.title}\n")
            for step in task.steps:
                step_id = f"P{phase.number}.T{task.number}.S{step.number}"
                prose_lines.append(f"\n- {step_id}: {step.title}\n")
    (new_folder / "_prose.md").write_text("".join(prose_lines))

    # Per-phase yaml. md_text is passed through so the body-preservation
    # fallback can splice raw markdown into phases/tasks the parser left
    # empty (non-canonical step formats, `### Step N:` h3 headers, etc.).
    warnings: list[str] = []
    for phase in phases_to_emit:
        phase_doc = _build_phase_doc_from_v1(phase, md_text=md_text, warnings=warnings)
        (new_folder / f"{phase.number:02d}.yaml").write_text(dump_plan_yaml(phase_doc))

    # Validate the freshly-written folder against the v2 schema BEFORE
    # archiving the source .md. A v1 plan the schema rejects — e.g. a
    # "## Phase 0" heading (numbering starts at 1) — must fail loud at
    # migration time, not surface later as a silent bridge-discovery skip.
    # Tear the folder down so a renumber + re-run isn't blocked by leftovers,
    # and leave the source .md in place for the operator to fix.
    try:
        _parse_v2(new_folder)
    except PlanSchemaError as e:
        shutil.rmtree(new_folder)
        raise MigrationError(f"{md_path.name}: migrated folder fails v2 validation: {e}") from e

    # Stage newly created plan files (#379 Bug 3)
    plan_files = [new_folder / "_meta.yaml", new_folder / "_prose.md"] + [
        new_folder / f"{phase.number:02d}.yaml" for phase in phases_to_emit
    ]
    plan_ops._stage(repo_root, plan_files)

    # Move original .md to .v1-archive sibling
    archive = md_path.with_suffix(".md.v1-archive")
    _git_mv_best_effort(repo_root, md_path, archive)

    # Ensure the spec's Implementation Plans table exists (#379 Bug 1). Scoped
    # to the "section entirely absent" case only — see _ensure_spec_plan_row's
    # docstring for why an existing table is never touched here.
    spec_file = _resolve_spec_file(v1plan.spec, repo_root)
    if spec_file is not None:
        row_warning = _ensure_spec_plan_row(
            spec_file, slug=slug, target_repo=resolved_target, repo_root=repo_root
        )
        if row_warning:
            warnings.append(row_warning)
    elif v1plan.spec:
        warnings.append(
            f"spec {v1plan.spec!r} not found under docs/superpowers/ — couldn't "
            f"ensure its Implementation Plans row for {slug!r}."
        )

    return MigrationOutcome(
        plan_path=md_path,
        new_folder=new_folder,
        reason="migrated",
        warnings=tuple(warnings),
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


def _extract_phase_body(md_text: str, phase_number: int) -> str:
    """Return the markdown body between `## Phase <N>:` and the next phase header.

    Matches numeric, alphabetic, or dotted phase identifiers. Returns empty
    string when no `## Phase` header for `phase_number` exists (e.g. flat-format
    plans). Used as a fallback content source when the parser couldn't extract
    any tasks for a phase.

    Fence-stripping prevents `## Phase N:` examples embedded in fenced code
    blocks (plans that document the plan format) from registering as real
    phase headers. Offsets line up because `_strip_fenced_regions` preserves
    length; content slicing uses the original `md_text`.
    """
    scan_text = _strip_fenced_regions(md_text)
    matches = list(_BODY_PHASE_RE.finditer(scan_text))
    for i, m in enumerate(matches):
        if m.group(1) == str(phase_number):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
            return md_text[start:end].strip()
    return ""


def _extract_sub_sections(body: str) -> list[tuple[str, str, str]]:
    """Return [(label, title, body), ...] for every `### Task|Step <N>:` header in body.

    Used when a phase has zero parsed tasks (e.g. plans that use `### Step N:`
    instead of `### Task N:`). Each captured sub-section becomes a synthetic
    task in the v2 yaml so its content survives the migration.
    """
    scan_text = _strip_fenced_regions(body)
    matches = list(_BODY_TASKLIKE_RE.finditer(scan_text))
    out: list[tuple[str, str, str]] = []
    for i, m in enumerate(matches):
        label = m.group(1)
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out.append((label, title, body[start:end].strip()))
    return out


def _find_task_body(md_text: str, phase_number: int, task_number: int) -> str:
    """Return the body of `### Task|Step <T>:` in phase `<P>` of md_text.

    Used when a parsed task ended up with zero steps and we need to splice
    the raw markdown back in as a fallback. Scoping by phase first avoids
    matching the wrong task when the same task number appears in multiple
    phases (e.g. `Task 1` under each `## Phase N`).

    For flat-format plans the synthetic phase has number 1 but md_text has
    no `## Phase 1:` header — the fallback scans the whole md_text in that
    case, which is correct because flat plans have a single namespace of
    `### Task N:` headers.
    """
    phase_body = _extract_phase_body(md_text, phase_number) or md_text
    scan_text = _strip_fenced_regions(phase_body)
    matches = list(_BODY_TASKLIKE_RE.finditer(scan_text))
    for i, m in enumerate(matches):
        label = m.group(1)
        # Strip any trailing letter on dotted labels (e.g. `5b` → `5`) so we
        # match the integer task.number that `_RE_TASK` exposes on the model.
        try:
            num = int(re.match(r"^\d+", label).group())  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            continue
        if num == task_number:
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(phase_body)
            return phase_body[start:end].strip()
    return ""


# Prose dependency convention the structured `**Depends on:**` parser misses:
# a phase body that says "Blocked by Phase 0" / "Blocked by Phases 0 and 3".
# The capture is anchored to a numeric list grammar (digits / "," / "and") so it
# stops at the first non-number token — without this, a trailing clause like
# "... which took 5 days (v2.1 rollout)" would leak phantom dependencies.
_BLOCKED_BY_RE = re.compile(
    r"Blocked by Phases?\s+(\d+(?:\s*(?:,|and)\s*\d+)*)",
    re.IGNORECASE,
)


def _extract_prose_depends_on(md_text: str, phase_number: int) -> tuple[int, ...]:
    """Recover phase dependencies expressed as prose (#245 Bug 2).

    Scans the phase body (fenced code stripped so examples don't match) for the
    'Blocked by Phase N[, M and K]' convention and returns the referenced phase
    numbers. Self-references are dropped. Empty when no such prose exists.

    Heuristic, not authoritative — the per-plan migration warning tells the
    operator to verify. Note a standalone `## Dependencies` H2 placed after the
    last `## Phase` falls into the LAST phase's body (`_extract_phase_body`
    slices to the next `## Phase` header or EOF), so a plan-level dependencies
    section is attributed to the final phase.
    """
    body = _extract_phase_body(md_text, phase_number)
    if not body:
        return ()
    scan = _strip_fenced_regions(body)
    deps: list[int] = []
    for m in _BLOCKED_BY_RE.finditer(scan):
        for tok in re.findall(r"\d+", m.group(1)):
            n = int(tok)
            if n != phase_number and n not in deps:
                deps.append(n)
    return tuple(deps)


def _find_task_intro(md_text: str, phase_number: int, task_number: int) -> str:
    """Return the body between `### Task <T>:` and its first step marker (#245 Bug 3).

    Captures intro prose and fenced blocks (e.g. ``# manual-operation``) that sit
    before the first ``**Step**``. Returns '' when the task has no pre-step body
    (or no parsed steps — that case is handled by the task-level S1 fallback).

    Fence-stripping locates the first step without letting a fenced step example
    truncate the intro; the returned slice comes from the ORIGINAL text so the
    fenced blocks survive intact.
    """
    phase_body = _extract_phase_body(md_text, phase_number) or md_text
    scan_text = _strip_fenced_regions(phase_body)
    matches = list(_BODY_TASKLIKE_RE.finditer(scan_text))
    for i, m in enumerate(matches):
        try:
            num = int(re.match(r"^\d+", m.group(1)).group())  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            continue
        if num == task_number:
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(phase_body)
            region_scan = scan_text[start:end]
            step_m = _RE_STEP.search(region_scan)
            if step_m is None:
                return ""
            return phase_body[start : start + step_m.start()].strip()
    return ""


def _build_phase_doc_from_v1(
    phase: Any, md_text: str = "", warnings: list[str] | None = None
) -> dict[str, Any]:
    """Convert a v1 Phase model into the v2 phase yaml dict.

    v1 steps have `number`/`title`/`body` (no `id`). We synthesize the
    v2 `P<phase>.T<task>.S<step>` id from the phase + task + step
    numbers. v1 step text is `title` + optional `body`.

    When `md_text` is supplied and the parser produced an empty phase
    (zero tasks) or empty tasks (zero steps), the migrator falls back to
    splicing the raw markdown body into the v2 yaml as a single synthetic
    step. Without this fallback, plans with non-canonical formatting (e.g.
    `### Step N:` h3 headers, or bare `**Step N:**` paragraphs the regex
    can't fully resolve) were emitted with `tasks: []` or `steps: []`,
    silently losing the entire body content of every affected phase.
    """
    tasks_iter: list[Any] = list(phase.tasks)

    # Phase-level fallback: extract `### Task|Step` sub-sections from the raw
    # phase body and present them as synthetic tasks. Triggers when the parser
    # found zero tasks for a phase (e.g. content-factory's `### Step N:`).
    if not tasks_iter and md_text:
        phase_body = _extract_phase_body(md_text, phase.number)
        if phase_body:
            sub_sections = _extract_sub_sections(phase_body)
            if sub_sections:
                tasks_iter = [
                    types.SimpleNamespace(
                        number=i + 1,
                        title=title,
                        steps=(),
                        _fallback_body=body,
                    )
                    for i, (_label, title, body) in enumerate(sub_sections)
                ]
            else:
                tasks_iter = [
                    types.SimpleNamespace(
                        number=1,
                        title="(unstructured content)",
                        steps=(),
                        _fallback_body=phase_body,
                    )
                ]

    tasks: list[dict[str, Any]] = []
    state_steps: dict[str, dict[str, Any]] = {}
    for task in tasks_iter:
        steps_out: list[dict[str, Any]] = []
        for step in task.steps:
            step_id = f"P{phase.number}.T{task.number}.S{step.number}"
            text = step.title
            body = getattr(step, "body", None)
            if body:
                text = f"{step.title}\n{body}".strip()
            steps_out.append({"id": step_id, "text": LiteralStr(text)})
            v1state = getattr(step, "state", " ")
            mapped = v1state if v1state in ("x", "-") else " "
            state_steps[step_id] = {"state": mapped, "ticked_at": None, "note": None}

        # Task-level fallback: if no steps parsed, splice the raw task body
        # in as a single synthetic step so the content isn't dropped.
        if not steps_out:
            fallback = getattr(task, "_fallback_body", None)
            if fallback is None and md_text:
                # Look up this task's body by phase + task number so repeated
                # task numbers across phases (e.g. each phase's Task 1) don't
                # collide.
                fallback = _find_task_body(md_text, phase.number, task.number)
            if fallback and fallback.strip():
                step_id = f"P{phase.number}.T{task.number}.S1"
                steps_out.append({"id": step_id, "text": LiteralStr(fallback.strip())})
                state_steps[step_id] = {"state": " ", "ticked_at": None, "note": None}
        elif md_text:
            # Task-intro fallback (#245 Bug 3): a task WITH parsed steps may still
            # carry intro prose + a fenced `# manual-operation` block before its
            # first step. Preserve it as a synthetic leading step (`.S0`) so the
            # block — discovered by /sync-runbook — isn't silently dropped.
            intro = _find_task_intro(md_text, phase.number, task.number)
            if intro:
                step_id0 = f"P{phase.number}.T{task.number}.S0"
                steps_out.insert(0, {"id": step_id0, "text": LiteralStr(intro)})
                state_steps[step_id0] = {"state": " ", "ticked_at": None, "note": None}

        tasks.append({"number": task.number, "title": task.title, "steps": steps_out})
    tag = "manual" if getattr(phase, "tag", None) == "manual" else "agentic"
    tracking = getattr(phase, "tracking_url", None)

    # depends_on: prefer the structured `**Depends on:**` value; if empty, try to
    # recover the 'Blocked by Phase N' prose convention (#245 Bug 2) so the
    # dependency graph isn't silently flattened to parallel roots.
    depends_on = list(getattr(phase, "depends_on", ()) or [])
    if not depends_on and md_text:
        recovered = _extract_prose_depends_on(md_text, phase.number)
        if recovered:
            depends_on = list(recovered)
            if warnings is not None:
                warnings.append(
                    f"Phase {phase.number}: recovered depends_on {depends_on} from "
                    f"'Blocked by Phase' prose — verify the dependency graph."
                )
        elif warnings is not None:
            body = _extract_phase_body(md_text, phase.number)
            if body and re.search(r"Blocked by Phase", _strip_fenced_regions(body), re.IGNORECASE):
                warnings.append(
                    f"Phase {phase.number}: body mentions 'Blocked by Phase' but no "
                    f"dependency could be extracted — set depends_on manually."
                )

    return {
        "schema_version": 2,
        "phase": {
            "number": phase.number,
            "title": phase.title,
            "tag": tag,
            "depends_on": depends_on,
            "tracking_issue": tracking,
        },
        "tasks": tasks,
        "state": {
            "steps": state_steps,
            "completion": {"at": None, "note": None, "observed_prs": []},
        },
    }


def _git_mv_best_effort(repo_root: Path, src: Path, dst: Path) -> None:
    """Move src -> dst via `git mv` (staged rename, history preserved) when
    src is a tracked file inside a real git working tree; falls back to a
    plain filesystem move otherwise (untracked fixture, no `.git` at all,
    git not on PATH). The fallback preserves pre-existing `migrate_repo`
    behavior for every caller that isn't a committed git checkout — in
    practice this package's own test fixtures; real operators always run
    migration inside a real repo, where `git mv` succeeds and the rename is
    staged for them (#379 Bug 3).
    """
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "mv", str(src), str(dst)],
            check=True,
            capture_output=True,
            text=True,
        )
        return
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass
    shutil.move(str(src), str(dst))


def _resolve_spec_file(spec_ref: str | None, repo_root: Path) -> Path | None:
    """Resolve a v1 plan's raw `**Spec:**` value to a spec file on disk.

    v1's value is whatever was written between backticks — usually a
    repo-relative path (`docs/superpowers/specs/<slug>.md`), occasionally a
    bare slug once a repo is already partway migrated. Cross-repo notation
    (`owner/repo:path`) can't be resolved locally — the file lives in
    another repo's checkout. Returns None when unresolvable so the caller
    can report *why* it couldn't ensure the row, not silently skip.
    """
    if not spec_ref:
        return None
    if is_cross_repo_spec(spec_ref):
        return None
    candidate = repo_root / spec_ref
    if candidate.is_file():
        return candidate
    res = refs.resolve_spec_ref(spec_ref, repo_root)
    return res.path


def _ensure_spec_plan_row(
    spec_path: Path, *, slug: str, target_repo: str, repo_root: Path
) -> str | None:
    """If spec_path has no `## Implementation Plans` section, create the
    canonical 4-column header and append a row for `slug` (#379 Bug 1).

    A no-op (returns None) whenever the section already exists — any column
    count. Those specs' rows are either hand-authored (pre-v1) or normalized
    in place by `_rewrite_spec_table`; backfilling a row for a plan that
    isn't yet in an existing table is deliberately out of scope (risk of
    mis-detecting "already has a row" across mixed legacy column counts
    outweighs the benefit — see the design spec).

    Returns a warning string on failure (defensive — the header we just
    wrote is always canonical, so `_append_spec_row` shouldn't reject it),
    else None.
    """
    text = spec_path.read_text()
    if plan_ops._SPEC_TABLE_HEADER_RE.search(text):
        return None

    sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    text += (
        f"{sep}## Implementation Plans\n\n"
        f"| Plan | Repo | File | Depends on |\n"
        f"|------|------|------|------------|\n"
    )
    spec_path.write_text(text)

    try:
        plan_ops._append_spec_row(
            spec_path, plan_name=slug, repo=target_repo, file=slug, depends_on="—"
        )
    except plan_ops.PlanEditError as e:  # pragma: no cover - defensive
        return f"{spec_path}: failed to append Implementation Plans row for {slug!r}: {e}"

    plan_ops._stage(repo_root, [spec_path])
    return None


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


# ---------------------------------------------------------------------------
# `fr migrate dirs` — legacy archived-plans/ -> implemented/ layout
# (2026-06-05 dispatch-guards spec, Phase 3)


@dataclass(frozen=True)
class DirsMove:
    """One planned `git mv` of the dirs migration."""

    src: Path  # repo-relative
    dst: Path  # repo-relative
    kind: str  # "plans-dir" | "spec"


def _archive_path_variants(
    file_cell: str,
) -> tuple[str | None, str | None, str | None]:
    """(active, implemented, legacy) gh-lookup candidates for a File cell.

    Derived from the bare slug (`vk.refs.plan_slug`, 2026-06-06
    spec-path-repair design), so every historical cell form — bare slug,
    active path, legacy `archived-plans/` path, annotated cell — yields
    the same canonical-layout candidates. (None, None, None) for
    placeholder cells.
    """
    slug = refs.plan_slug(file_cell)
    if not slug:
        return None, None, None
    return tuple(f"docs/superpowers/{root}/{slug}" for root in refs.PLAN_ROOTS)  # type: ignore[return-value]


# The pending-slice recognizer is the canonical classifier in `fr.refs` (beside
# `plan_slug`), shared by the archive sweep, `fr migrate dirs`, and `fr repair`
# (#351, #359). Kept as a module-local alias so `_spec_fully_implemented`'s
# bare-name call and the `from fr.migrate import _is_pending_placeholder` test
# import resolve unchanged.
_is_pending_placeholder = refs.is_pending_placeholder


def _spec_fully_implemented(
    spec_path: Path, repo_root: Path, gh: Any | None = None
) -> tuple[bool, str | None]:
    """(implemented?, blocking-note) for one spec's Implementation Plans rows.

    A spec qualifies for implemented/specs/ when every row with a plan file
    resolves to an archive location (implemented/plans/ — or the legacy
    archived-plans/, which `migrate dirs` is about to rename). Manual rows
    (File cell `—`) never block. A row resolving to an ACTIVE plans/ dir
    blocks, with a note naming the row.

    A row whose File cell is a `pending`/`tbd` placeholder marks a
    decided-but-unbuilt slice (no plan folder yet) and holds the spec
    deterministically — before any local/gh resolution — so a spec delivered
    in slices is never swept while a later slice is pending (#351).

    Cross-repo rows (no local resolution): when `gh` is supplied, the
    narrow contents-API lookup (2026-06-05 spec) checks the OTHER repo —
    active path exists there → blocks; implemented/legacy variant exists
    → counts as done; nothing found (or no gh / gh outage) → blocks with
    a "confirm and re-run" note. Unresolved never silently passes.
    """
    from fr.spec import _resolve_local_plan_dir, parse_spec

    meta = parse_spec(spec_path)
    if not meta.plans:
        return False, "no Implementation Plans rows — leaving in place"
    sp = repo_root / "docs" / "superpowers"
    for ref in meta.plans:
        if not ref.file or ref.file in ("—", "-"):
            continue  # manual/informational row — non-blocking
        if _is_pending_placeholder(ref.file):
            # Decided-but-unbuilt slice (no plan folder yet): hold the spec
            # deterministically, before any local/gh resolution, with an
            # intentional note (#351). Never silently passes.
            return False, f"row {ref.name!r} pending — slice not yet built; leaving spec in place"
        resolved = _resolve_local_plan_dir(ref, repo_root)
        if resolved is None:
            note = f"row {ref.name!r} unresolved locally (cross-repo?) — confirm and re-run"
            if gh is not None and "/" in ref.repo:
                active_path, implemented_path, legacy_path = _archive_path_variants(ref.file)
                try:
                    # Probe the ACTIVE canonical variant (slug cells are not
                    # paths, so the raw cell is never a usable gh path).
                    if active_path and gh.file_exists(ref.repo, active_path):
                        return False, f"row {ref.name!r} still active in {ref.repo}"
                    if (implemented_path and gh.file_exists(ref.repo, implemented_path)) or (
                        legacy_path and gh.file_exists(ref.repo, legacy_path)
                    ):
                        continue  # remote row is archived — counts as done
                except Exception:  # noqa: BLE001 — gh outage degrades to "confirm"
                    pass
            return False, note
        try:
            rel_parts = resolved.relative_to(sp).parts
        except ValueError:
            return False, f"row {ref.name!r} resolves outside docs/superpowers — leaving in place"
        in_archive = rel_parts[:2] == ("implemented", "plans") or rel_parts[0] == "archived-plans"
        if not in_archive:
            return False, f"row {ref.name!r} still active under plans/"
    return True, None


def plan_dirs_migration(repo_root: Path) -> tuple[list[DirsMove], list[str]]:
    """Compute the moves `fr migrate dirs` would perform. Pure planning.

    Returns (moves, notes). Empty moves = nothing to migrate.
    """
    moves: list[DirsMove] = []
    notes: list[str] = []
    sp = repo_root / "docs" / "superpowers"

    legacy = sp / "archived-plans"
    if legacy.is_dir():
        moves.append(
            DirsMove(
                src=legacy.relative_to(repo_root),
                dst=Path("docs/superpowers/implemented/plans"),
                kind="plans-dir",
            )
        )

    # Legacy archived-specs/ rides along too (per-entry moves — the
    # destination dir may already exist and hold newly-archived specs).
    legacy_specs = sp / "archived-specs"
    if legacy_specs.is_dir():
        for entry in sorted(legacy_specs.iterdir()):
            moves.append(
                DirsMove(
                    src=entry.relative_to(repo_root),
                    dst=Path("docs/superpowers/implemented/specs") / entry.name,
                    kind="spec",
                )
            )

    specs_dir = sp / "specs"
    if specs_dir.is_dir():
        for spec_path in sorted(specs_dir.glob("*.md")):
            implemented, note = _spec_fully_implemented(spec_path, repo_root)
            if implemented:
                moves.append(
                    DirsMove(
                        src=spec_path.relative_to(repo_root),
                        dst=Path("docs/superpowers/implemented/specs") / spec_path.name,
                        kind="spec",
                    )
                )
            elif note and "no Implementation Plans rows" not in note:
                notes.append(f"{spec_path.name}: {note}")
    return moves, notes


def migrate_dirs(repo_root: Path, *, dry_run: bool = True) -> tuple[list[DirsMove], list[str]]:
    """Execute (or preview) the dirs migration. Moves are `git mv` so the
    rename history survives; the commit is the operator's."""
    moves, notes = plan_dirs_migration(repo_root)
    if dry_run or not moves:
        return moves, notes
    for m in moves:
        (repo_root / m.dst).parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "-C", str(repo_root), "mv", str(m.src), str(m.dst)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise MigrationError(
                f"git mv {m.src} -> {m.dst} failed: {(e.stderr or '').strip()}"
            ) from e
    # Per-entry moves out of archived-specs/ leave the (untracked, empty)
    # directory husk behind — git mv removes files, not dirs.
    legacy_specs = repo_root / "docs" / "superpowers" / "archived-specs"
    if legacy_specs.is_dir() and not any(legacy_specs.iterdir()):
        legacy_specs.rmdir()
    return moves, notes
