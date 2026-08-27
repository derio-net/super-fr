"""Workflow shape resolution: repo > shipped — spec §4.A, Phase 6.

Mirrors `fr.models`' repo-over-user precedent (`fr.models.resolve`), but the
"shipped" side is the installed plugin's manifest directory rather than a
user config file — `resolve_workflow` takes it as an explicit, injectable
`shipped_root` (default: the Claude Code marketplace clone path,
`default_shipped_workflows_dir()`) precisely so tests never touch
`~/.claude`.

Override is WHOLESALE (spec §4.A: "no merge semantics, because
partial-override of a step graph is a class of subtle breakage nobody wants
to debug") — a repo manifest with fewer steps than the shipped one of the
same name yields exactly those steps, never a union.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.workflow.model import WorkflowError
from fr.workflow.resolve import (
    MARKETPLACE_ROOT,
    SHIPPED_WORKFLOWS_REL,
    default_shipped_workflows_dir,
    resolve_workflow,
)

SHIPPED_TEXT = """
workflow: fr-goal
schema: 1
description: shipped
unit: run
requires: [git]
steps:
  - id: a
    kind: cli
    run: echo shipped-a
  - id: b
    kind: cli
    run: echo shipped-b
"""

REPO_TEXT = """
workflow: fr-goal
schema: 1
description: repo override
unit: run
requires: [git, tests]
steps:
  - id: only-one
    kind: cli
    run: echo repo-only
"""


def _make_dirs(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    shipped_root = tmp_path / "shipped"
    (repo_root / "docs" / "superpowers" / "workflows").mkdir(parents=True)
    shipped_root.mkdir(parents=True)
    return repo_root, shipped_root


def test_prefers_repo_over_shipped(tmp_path: Path) -> None:
    repo_root, shipped_root = _make_dirs(tmp_path)
    (repo_root / "docs/superpowers/workflows/fr-goal.yaml").write_text(REPO_TEXT)
    (shipped_root / "fr-goal.yaml").write_text(SHIPPED_TEXT)

    manifest = resolve_workflow("fr-goal", repo_root, shipped_root=shipped_root)

    assert manifest.description == "repo override"
    assert [s.id for s in manifest.steps] == ["only-one"]


def test_falls_back_to_shipped_when_repo_file_absent(tmp_path: Path) -> None:
    repo_root, shipped_root = _make_dirs(tmp_path)
    (shipped_root / "fr-goal.yaml").write_text(SHIPPED_TEXT)

    manifest = resolve_workflow("fr-goal", repo_root, shipped_root=shipped_root)

    assert manifest.description == "shipped"
    assert [s.id for s in manifest.steps] == ["a", "b"]


def test_override_is_wholesale_never_merged(tmp_path: Path) -> None:
    """A repo manifest with FEWER steps than shipped yields exactly those
    steps — no union of the two step lists, no merge of any kind."""
    repo_root, shipped_root = _make_dirs(tmp_path)
    (repo_root / "docs/superpowers/workflows/fr-goal.yaml").write_text(REPO_TEXT)
    (shipped_root / "fr-goal.yaml").write_text(SHIPPED_TEXT)

    manifest = resolve_workflow("fr-goal", repo_root, shipped_root=shipped_root)

    assert len(manifest.steps) == 1
    assert manifest.requires == ("git", "tests")


def test_unknown_workflow_names_both_searched_paths(tmp_path: Path) -> None:
    repo_root, shipped_root = _make_dirs(tmp_path)

    with pytest.raises(WorkflowError) as exc_info:
        resolve_workflow("nonexistent-shape", repo_root, shipped_root=shipped_root)

    message = str(exc_info.value)
    assert "nonexistent-shape" in message
    assert str(repo_root / "docs/superpowers/workflows/nonexistent-shape.yaml") in message
    assert str(shipped_root / "nonexistent-shape.yaml") in message


def test_a_second_shape_name_resolves_independently(tmp_path: Path) -> None:
    repo_root, shipped_root = _make_dirs(tmp_path)
    (shipped_root / "ux-research.yaml").write_text(
        "workflow: ux-research\nschema: 1\nunit: run\nsteps: []\n"
    )

    manifest = resolve_workflow("ux-research", repo_root, shipped_root=shipped_root)
    assert manifest.workflow == "ux-research"


def test_default_shipped_workflows_dir_honors_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FR_SHIPPED_WORKFLOWS_DIR", str(tmp_path / "custom"))
    assert default_shipped_workflows_dir() == tmp_path / "custom"


def test_default_shipped_workflows_dir_falls_back_to_the_marketplace_clone_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No `$FR_SHIPPED_WORKFLOWS_DIR` → the `$HOME`-relative marketplace
    path, built from the SAME `MARKETPLACE_ROOT` constant
    `plan_validator_wrapper.py`/`isolation/local.py` hardcode as a literal
    string — so a future marketplace rename only has one constant to fix,
    not a retyped path this test would silently stop protecting."""
    monkeypatch.delenv("FR_SHIPPED_WORKFLOWS_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    result = default_shipped_workflows_dir()

    assert result == tmp_path / MARKETPLACE_ROOT / SHIPPED_WORKFLOWS_REL
    # Names the exact convention every other "shipped resource" lookup uses
    # (plan_validator_wrapper.py:16,35; isolation/local.py:982) — spelled
    # out here, not just via the constant, so a drift between this
    # constant's VALUE and that convention still fails loud.
    assert str(result).endswith(
        ".claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/workflows"
    )


def test_resolve_workflow_without_shipped_root_consults_the_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wiring test: `resolve_workflow(name, repo_root)` called with NO
    `shipped_root` kwarg must actually reach `default_shipped_workflows_dir()`
    — proving the production call site, not just the helper in isolation
    (which the two tests above already cover)."""
    repo_root = tmp_path / "repo"
    (repo_root / "docs" / "superpowers" / "workflows").mkdir(parents=True)
    default_dir = tmp_path / "shipped-via-default"
    default_dir.mkdir()
    (default_dir / "fr-goal.yaml").write_text(SHIPPED_TEXT)
    monkeypatch.setenv("FR_SHIPPED_WORKFLOWS_DIR", str(default_dir))

    manifest = resolve_workflow("fr-goal", repo_root)

    assert manifest.description == "shipped"
    assert [s.id for s in manifest.steps] == ["a", "b"]
