"""Rework plans: scaffold a sibling rework of a plan, record its origin items, list them
(moved from `fr.plan_ops`, spec 2026-11-27-plan-ops-split R7)."""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from fr import refs
from fr._plan_io import _stage, _yaml_dump
from fr._urls import is_cross_repo_spec
from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.paths import KIND_DIRS, feature_roots, kind_dir, space_for
from fr.parser import Plan, PlanSchemaError, _find_repo_root, parse
from fr.plan_errors import PlanEditError
from fr.spec_table import _append_spec_row
from fr.version_floor import CEILING_VERSION

_REWORK_SUFFIX_RE = re.compile(r"-rework-(\d+)$")


_PLAN_HOMES = ("plan", "plan-archived", "plan-legacy-archived")
"""The plan directories a parent plan may live in: active, canonical archive
(2026-06-05 spec), legacy archive."""


def _feature_root_of(parent_dir: Path, repo_root: Path | None) -> Path | None:
    """The feature root whose plan directory holds *parent_dir*, found through the path
    resolver (`KIND_DIRS` below each `feature_roots` entry), or None when it sits in none
    of `_PLAN_HOMES`. *repo_root* is the real checkout root, never walked up to."""
    if repo_root is None:
        return None
    for froot in feature_roots(space_for(repo_root)):
        if any(froot / KIND_DIRS[kind] == parent_dir.parent for kind in _PLAN_HOMES):
            return froot
    return None


def _next_rework_number(parent_dir: Path, froot: Path) -> int:
    """Cross-directory N collision check, like v1 next_rework_number.

    Scans active plans/, implemented/plans/ (canonical archive), and
    archived-plans/ (legacy) so an archived rework still claims its number.
    """
    plans_dir = froot / KIND_DIRS["plan"]
    implemented_dir = froot / KIND_DIRS["plan-archived"]
    archived_dir = froot / KIND_DIRS["plan-legacy-archived"]

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

    The parent may be live (plans/) or archived (implemented/plans/, archived-plans/),
    complete or not; it stays untouched. Rework folder is empty of phases
    (operator authors them later, informed by origin_items).
    """
    parent_dir = parent_plan_dir.resolve()
    if not parent_dir.is_dir():
        raise PlanEditError(f"parent plan dir not found: {parent_dir}")
    froot = _feature_root_of(parent_dir, _find_repo_root(parent_dir))
    if froot is None:
        raise PlanEditError(
            f"parent must live under {KIND_DIRS['superpowers']}/"
            f"{{plans,implemented/plans,archived-plans}}/, got: {parent_dir}"
        )

    parent_plan = parse(parent_dir)
    n = _next_rework_number(parent_dir, froot)
    rework_slug = f"{parent_dir.name}-rework-{n}"
    plans_dir = froot / KIND_DIRS["plan"]
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
        prior_dir = _find_prior_rework(parent_dir, froot, below=n)
        if prior_dir is not None:
            prior_rework_rel = prior_dir.name

    parent_spec = parent_plan.meta.spec
    if parent_spec:
        # The one canonical `spec:` form, shared with create and repair (#686).
        parent_spec = refs.canonical_spec_ref(parent_spec, repo_root or froot)

    meta = {
        "schema_version": 2,
        "plan": rework_slug,
        "spec": parent_spec,
        "target_repo": parent_plan.meta.target_repo,
        # Widened past the 4.0.0 major bump, same reasoning as plan_cmd.py's default.
        "fr_version": parent_plan.meta.fr_version or f">=3.0.0,<{CEILING_VERSION}",
        "created": _dt.date.today().isoformat(),
        "parent_plan": parent_rel,
    }
    if prior_rework_rel:
        meta["prior_rework"] = prior_rework_rel
    meta["origin_items"] = []
    write_text_atomic(rework_folder / "_meta.yaml", _yaml_dump(meta))

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
    write_text_atomic(rework_folder / "_prose.md", prose)

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


def _find_prior_rework(parent_dir: Path, froot: Path, *, below: int) -> Path | None:
    """Highest archived rework N below `below` (in archived-plans/)."""
    archived_dir = froot / KIND_DIRS["plan-legacy-archived"]
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
    write_text_atomic(rework_dir / "_meta.yaml", _yaml_dump(raw))
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
    dirs = [kind_dir("plan", space_for(repo_root))]
    if include_archived:
        dirs.append(kind_dir("plan-legacy-archived", space_for(repo_root)))

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

            spec_path = None
            if plan.meta.spec:
                if plan.spec_file is not None:
                    spec_path = plan.spec_file.resolve()
                else:
                    spec_path = (repo_root / plan.meta.spec).resolve()
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
