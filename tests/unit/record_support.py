"""A real fr-goal run in a real linked worktree, walked to `implement`, for
the step-record tests (spec 2026-09-25 §7 items 10-13).

The walk reuses the integration suite's own helpers, so the run these tests
resolve records against is the one the shipped shape actually produces.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import yaml

from tests.integration.test_fr_goal_shape import (
    _drive_to_implement,
    _fr,
    _walk_brief,
    _workspace,
)

__all__ = [
    "RUN",
    "SLUG",
    "commit_all",
    "fr",
    "git",
    "head",
    "implement_record",
    "snapshot",
    "started_run",
    "write_record",
]

RUN = "r1"
SLUG = "2026-09-25-rec"
PLAN_REL = f"docs/superpowers/plans/{SLUG}"
fr = _fr


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def head(root: Path) -> str:
    return git(root, "rev-parse", "HEAD").strip()


def commit_all(root: Path, message: str = "work") -> None:
    git(root, "add", "-A")
    git(root, "commit", "-qm", message, "--no-verify")


def snapshot(root: Path) -> dict[str, str]:
    """sha256 of every file outside `.git` — what "nothing changed" means."""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if ".git" in p.relative_to(root).parts or not p.is_file():
            continue
        out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _plan(root: Path) -> None:
    """One agentic phase: T1 ran red → green with no refactor step (the
    refactor gate's case), T2 is a single step (exempt)."""
    from fr.plan_ops import PhaseSpec, create

    create(
        repo_root=root,
        slug=SLUG,
        spec="docs/spec.md",
        target_repo="derio-net/super-fr",
        fr_version=">=3.0.0,<5.0.0",
        phases=[
            PhaseSpec(
                number=1,
                title="Phase 1",
                tasks=(
                    {
                        "number": 1,
                        "title": "t1",
                        "steps": [
                            {"id": "P1.T1.S1", "text": "RED: write the test"},
                            {"id": "P1.T1.S2", "text": "GREEN: make it pass"},
                        ],
                    },
                    {
                        "number": 2,
                        "title": "t2",
                        "steps": [{"id": "P1.T2.S1", "text": "Run the checks"}],
                    },
                ),
                skeleton=True,
            )
        ],
        prose="# rec\n",
    )
    # One agentic phase that is also the skeleton: the operator override the
    # skeleton gate names, so plan-review (which EXECUTES self-review) passes.
    from datetime import datetime

    from fr.journal.model import JournalEntry, append_journal_entry, journal_path

    append_journal_entry(
        journal_path(root, "spec", "spec"),
        "spec",
        JournalEntry(
            kind="decision",
            scope="spec",
            id=f"skeleton-override-{SLUG}",
            created=datetime.now().replace(microsecond=0).isoformat(),
            title="too small to smoke separately",
            body="one phase",
        ),
    )


def started_run(tmp_path: Path) -> Path:
    """A workspace whose run `r1` has just briefed `implement-phase phase/1`."""
    root = _workspace(tmp_path, "feat/rec")
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "spec.md").write_text(
        "# spec\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
    )
    _plan(root)
    commit_all(root, "spec and plan")
    _drive_to_implement(root, RUN, "feat/rec", "docs/spec.md", PLAN_REL)
    out = fr(root, ["run", "advance", RUN])
    assert out.exit_code == 0, out.output
    brief = _walk_brief(out.stdout)
    assert (brief["step"], brief["item"]) == ("implement-phase", "phase/1"), out.output
    commit_all(root, "cursor")
    return root


def implement_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "schema_version": 1,
        "run": RUN,
        "step": "implement-phase",
        "item": "phase/1",
        "outcome": "done",
        "ticks": ["P1.T1.S1", "P1.T1.S2", "P1.T2.S1"],
        "refactor": {"P1.T1": "none: one function, nothing to extract"},
        "journal": [
            {"kind": "decision", "id": "d-p1", "title": "kept it flat", "body": "why"},
            {
                "kind": "finding",
                "id": "p1-f1",
                "title": "edge case",
                "body": "b",
                "review_scope": "in",
            },
        ],
        "resolves": [{"id": "p1-f1", "state": "fixed", "body": "covered by a test"}],
    }
    record.update(overrides)
    return {k: v for k, v in record.items() if v is not None}


def write_record(root: Path, data: dict[str, object], name: str | None = None) -> Path:
    step = str(data.get("step", "implement-phase"))
    item = data.get("item")
    name = name or (f"{step}__{str(item).replace('/', '-')}" if item else step)
    path = root / "docs" / "superpowers" / "runs" / f"{RUN}.records" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path
