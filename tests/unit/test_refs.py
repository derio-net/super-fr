"""vk.refs — lifecycle-independent ref normalization + resolution.

Truth table for the 2026-06-06 spec-path-repair design: refs in any
historical form (bare slug, active path, implemented path, legacy
archived-plans path, backticked/annotated table cell) normalize to the
bare slug and resolve against every lifecycle root, active first.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vk.refs import plan_slug, resolve_plan_ref, resolve_spec_ref

SLUG = "2026-06-04--obs--security-trace-analyst"


# ── plan_slug normalization ─────────────────────────────────────────


@pytest.mark.parametrize(
    "ref",
    [
        SLUG,
        f"{SLUG}/",
        f"docs/superpowers/plans/{SLUG}",
        f"docs/superpowers/plans/{SLUG}/",
        f"docs/superpowers/implemented/plans/{SLUG}",
        f"docs/superpowers/archived-plans/{SLUG}/",
        f"docs/{SLUG}",
        f"`docs/superpowers/archived-plans/{SLUG}/`",
        f"`docs/superpowers/archived-plans/{SLUG}/` (shipped via PR #146, archived 2026-05-17)",
    ],
)
def test_plan_slug_normalizes_every_historical_form(ref: str) -> None:
    assert plan_slug(ref) == SLUG


@pytest.mark.parametrize("placeholder", ["—", "-", ""])
def test_plan_slug_placeholder_passthrough_is_empty(placeholder: str) -> None:
    assert plan_slug(placeholder) == ""


# ── resolution fixtures ─────────────────────────────────────────────


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "docs/superpowers/plans").mkdir(parents=True)
    (tmp_path / "docs/superpowers/implemented/plans").mkdir(parents=True)
    (tmp_path / "docs/superpowers/specs").mkdir(parents=True)
    (tmp_path / "docs/superpowers/implemented/specs").mkdir(parents=True)
    return tmp_path


# ── resolve_plan_ref ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ref",
    [
        SLUG,
        f"docs/superpowers/plans/{SLUG}/",
        f"docs/superpowers/archived-plans/{SLUG}/",
        f"`docs/superpowers/archived-plans/{SLUG}/` (shipped via PR #146)",
    ],
)
@pytest.mark.parametrize("root", ["plans", "implemented/plans", "archived-plans"])
def test_resolve_plan_ref_any_form_any_root(repo: Path, ref: str, root: str) -> None:
    actual = repo / "docs/superpowers" / root / SLUG
    actual.mkdir(parents=True, exist_ok=True)
    res = resolve_plan_ref(ref, repo)
    assert res.path == actual
    assert res.slug == SLUG


def test_resolve_plan_ref_absent_reports_all_tried(repo: Path) -> None:
    res = resolve_plan_ref(SLUG, repo)
    assert res.path is None
    tried = [str(p.relative_to(repo)) for p in res.tried]
    assert tried == [
        f"docs/superpowers/plans/{SLUG}",
        f"docs/superpowers/implemented/plans/{SLUG}",
        f"docs/superpowers/archived-plans/{SLUG}",
    ]


def test_resolve_plan_ref_duplicate_roots_active_wins(repo: Path) -> None:
    active = repo / "docs/superpowers/plans" / SLUG
    archived = repo / "docs/superpowers/implemented/plans" / SLUG
    active.mkdir(parents=True)
    archived.mkdir(parents=True)
    res = resolve_plan_ref(SLUG, repo)
    assert res.path == active
    assert res.matches == (active, archived)  # ambiguity surfaced


@pytest.mark.parametrize("placeholder", ["—", "-", ""])
def test_resolve_plan_ref_placeholder_is_none(repo: Path, placeholder: str) -> None:
    res = resolve_plan_ref(placeholder, repo)
    assert res.path is None
    assert res.tried == ()


# ── resolve_spec_ref ────────────────────────────────────────────────

SPEC = "2026-06-06-spec-path-repair-design.md"


@pytest.mark.parametrize(
    "ref",
    [
        SPEC,
        SPEC.removesuffix(".md"),  # forgiving: bare name without extension
        f"docs/superpowers/specs/{SPEC}",
        f"docs/superpowers/archived-specs/{SPEC}",
        f"`docs/superpowers/specs/{SPEC}`",
    ],
)
@pytest.mark.parametrize("root", ["specs", "implemented/specs", "archived-specs"])
def test_resolve_spec_ref_any_form_any_root(repo: Path, ref: str, root: str) -> None:
    actual = repo / "docs/superpowers" / root / SPEC
    actual.parent.mkdir(parents=True, exist_ok=True)
    actual.write_text("# spec\n")
    res = resolve_spec_ref(ref, repo)
    assert res.path == actual


def test_resolve_spec_ref_absent_reports_all_tried(repo: Path) -> None:
    res = resolve_spec_ref(SPEC, repo)
    assert res.path is None
    tried = [str(p.relative_to(repo)) for p in res.tried]
    assert tried == [
        f"docs/superpowers/specs/{SPEC}",
        f"docs/superpowers/implemented/specs/{SPEC}",
        f"docs/superpowers/archived-specs/{SPEC}",
    ]


def test_resolve_spec_ref_duplicate_roots_active_wins(repo: Path) -> None:
    active = repo / "docs/superpowers/specs" / SPEC
    archived = repo / "docs/superpowers/implemented/specs" / SPEC
    active.write_text("# a\n")
    archived.write_text("# b\n")
    res = resolve_spec_ref(SPEC, repo)
    assert res.path == active
    assert res.matches == (active, archived)
