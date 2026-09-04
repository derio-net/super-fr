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


# =========================================================================
# review r5-e14: precedence, and where the wheel copy sits in it
# =========================================================================


def test_the_wheel_copy_beats_a_stale_marketplace_clone(tmp_path, monkeypatch) -> None:
    """The clone is updated independently of the `fr` wheel, so an operator
    who upgrades `fr` without re-running `install.sh` would otherwise keep
    resolving a STALE shape — silently, possibly at the wrong granularity.
    The wheel copy ships with the code that reads it and cannot disagree."""
    from fr.workflow.resolve import MARKETPLACE_ROOT, SHIPPED_WORKFLOWS_REL, resolve_workflow

    home = tmp_path / "home"
    clone = home / MARKETPLACE_ROOT / SHIPPED_WORKFLOWS_REL
    clone.mkdir(parents=True)
    (clone / "fr-goal.yaml").write_text(
        "workflow: fr-goal\nschema: 1\nunit: run\n"
        "steps:\n  - id: stale-clone\n    kind: cli\n    run: 'true'\n"
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("FR_SHIPPED_WORKFLOWS_DIR", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    manifest = resolve_workflow("fr-goal", tmp_path / "repo")

    assert [s.id for s in manifest.steps] != ["stale-clone"]


def test_the_explicit_env_override_beats_everything_but_the_repo(tmp_path, monkeypatch) -> None:
    """`$FR_SHIPPED_WORKFLOWS_DIR` is set on purpose, so it cannot surprise
    anyone — that is what makes it, not the clone, the way to override."""
    from fr.workflow.resolve import resolve_workflow

    shipped = tmp_path / "explicit"
    shipped.mkdir()
    (shipped / "fr-goal.yaml").write_text(
        "workflow: fr-goal\nschema: 1\nunit: run\n"
        "steps:\n  - id: from-env\n    kind: cli\n    run: 'true'\n"
    )
    monkeypatch.setenv("FR_SHIPPED_WORKFLOWS_DIR", str(shipped))

    manifest = resolve_workflow("fr-goal", tmp_path / "repo")

    assert [s.id for s in manifest.steps] == ["from-env"]


def test_a_repo_override_still_beats_every_shipped_source(tmp_path, monkeypatch) -> None:
    from fr.workflow.resolve import REPO_WORKFLOWS_REL, resolve_workflow

    repo = tmp_path / "repo"
    (repo / REPO_WORKFLOWS_REL).mkdir(parents=True)
    (repo / REPO_WORKFLOWS_REL / "fr-goal.yaml").write_text(
        "workflow: fr-goal\nschema: 1\nunit: run\n"
        "steps:\n  - id: from-repo\n    kind: cli\n    run: 'true'\n"
    )
    monkeypatch.delenv("FR_SHIPPED_WORKFLOWS_DIR", raising=False)

    manifest = resolve_workflow("fr-goal", repo)

    assert [s.id for s in manifest.steps] == ["from-repo"]


def test_the_shipped_fr_goal_resolves_with_an_empty_home_and_no_repo_override(
    tmp_path, monkeypatch
) -> None:
    """The clean-install case, unit-level: nothing but the `fr` wheel."""
    from fr.workflow.resolve import resolve_workflow

    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    monkeypatch.setenv("HOME", str(empty_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: empty_home))
    monkeypatch.delenv("FR_SHIPPED_WORKFLOWS_DIR", raising=False)

    manifest = resolve_workflow("fr-goal", tmp_path / "no-such-repo")

    assert manifest.workflow == "fr-goal"
    assert manifest.unit == "run"


def test_the_lookup_order_is_the_one_the_docstring_states(tmp_path, monkeypatch) -> None:
    from fr.workflow.resolve import (
        MARKETPLACE_ROOT,
        SHIPPED_WORKFLOWS_REL,
        packaged_shipped_workflows_dir,
        shipped_workflow_dirs,
    )

    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("FR_SHIPPED_WORKFLOWS_DIR", raising=False)

    assert shipped_workflow_dirs() == [
        packaged_shipped_workflows_dir(),
        home / MARKETPLACE_ROOT / SHIPPED_WORKFLOWS_REL,
    ]

    monkeypatch.setenv("FR_SHIPPED_WORKFLOWS_DIR", str(tmp_path / "env"))
    assert shipped_workflow_dirs()[0] == tmp_path / "env"
