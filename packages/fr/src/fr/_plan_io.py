"""Staging and YAML dumping shared by the plan writers (moved from `fr.plan_ops`,
spec 2026-11-27-plan-ops-split R6)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def worktree_of(path: Path, fallback: Path) -> Path:
    """The git checkout holding *path*: the nearest ancestor with a `.git`. Under quiet a
    plan lives in the `fr` worktree, not the product checkout (`fallback`)."""
    for parent in path.resolve().parents:
        if (parent / ".git").exists():
            return parent
    return fallback


def _stage(repo_root: Path | None, paths: list[Path]) -> None:
    """git add the paths if we're in a git repo, each in the checkout that holds it."""
    if repo_root is None:
        return
    groups: dict[Path, list[str]] = {}
    for p in paths:
        top = worktree_of(p, Path(repo_root).resolve())
        groups.setdefault(top, []).append(str(p.resolve().relative_to(top)))
    for top, rels in groups.items():
        subprocess.run(
            ["git", "-C", str(top), "add", *rels],
            check=False,
            capture_output=True,
        )


def _coerce_step_texts(d: dict[str, Any]) -> dict[str, Any]:
    """Wrap step text values in LiteralStr so they always emit as `|-`.

    Called before every _yaml_dump so round-tripped phase files (loaded via
    yaml.safe_load and mutated for state updates) keep the same consistent
    block-scalar style as freshly-created plans.
    """
    from fr._yaml import LiteralStr

    for task in d.get("tasks", []):
        for step in task.get("steps", []):
            if "text" in step and not isinstance(step["text"], LiteralStr):
                step["text"] = LiteralStr(step["text"])
    return d


def _yaml_dump(d: dict[str, Any]) -> str:
    """Delegate to the shared plan-yaml dumper (literal block scalars for
    multi-line strings, preserved key order, unicode-as-is)."""
    from fr._yaml import dump_plan_yaml

    return dump_plan_yaml(_coerce_step_texts(d))
