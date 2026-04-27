"""Tests for vk.plan.filename — slug derivation from plan file paths."""

from pathlib import Path

import pytest

from vk.plan.filename import derive_plan_name, derive_slug, derive_spec_slug


def test_single_dash_pattern() -> None:
    """YYYY-MM-DD-name.md -> name"""
    assert derive_slug(Path("docs/plans/2026-04-12-scaffold.md")) == "scaffold"


def test_double_dash_pattern() -> None:
    """YYYY-MM-DD--layer--details.md -> layer--details"""
    path = Path("docs/plans/2026-04-12--vk-cli--p0-scaffold.md")
    assert derive_slug(path) == "vk-cli--p0-scaffold"


def test_multi_word_slug() -> None:
    """Hyphenated name after date prefix."""
    assert derive_slug(Path("2026-04-12-vk-cli-p1-core-modules.md")) == "vk-cli-p1-core-modules"


def test_deep_path() -> None:
    """Works with deeply nested paths."""
    p = Path("/home/user/docs/superpowers/plans/2026-01-01-my-plan.md")
    assert derive_slug(p) == "my-plan"


def test_no_date_prefix_raises() -> None:
    """Filename without YYYY-MM-DD prefix raises ValueError."""
    with pytest.raises(ValueError, match="must start with YYYY-MM-DD"):
        derive_slug(Path("no-date-plan.md"))


def test_empty_slug_raises() -> None:
    """Date-only filename (no slug part) raises ValueError."""
    with pytest.raises(ValueError, match="Empty slug"):
        derive_slug(Path("2026-04-12.md"))


def test_date_only_with_trailing_dashes_raises() -> None:
    """Date with only dashes after it raises ValueError."""
    with pytest.raises(ValueError, match="Empty slug"):
        derive_slug(Path("2026-04-12--.md"))


def test_lstrip_single_dash() -> None:
    """Single leading dash is stripped."""
    assert derive_slug(Path("2026-04-12-foo.md")) == "foo"


def test_lstrip_double_dash() -> None:
    """Double leading dashes are stripped."""
    assert derive_slug(Path("2026-04-12--foo.md")) == "foo"


def test_lstrip_triple_dash() -> None:
    """Triple leading dashes are stripped."""
    assert derive_slug(Path("2026-04-12---foo.md")) == "foo"


# -- derive_spec_slug -----------------------------------------------------


def test_spec_slug_strips_date_and_design_suffix() -> None:
    assert derive_spec_slug(Path("docs/specs/2026-04-27-foo-design.md")) == "foo"


def test_spec_slug_handles_no_design_suffix() -> None:
    assert derive_spec_slug(Path("2026-04-27-foo.md")) == "foo"


def test_spec_slug_lenient_without_date_prefix() -> None:
    """Tests/fixtures may use simple paths without YYYY-MM-DD."""
    assert derive_spec_slug(Path("foo-design.md")) == "foo"
    assert derive_spec_slug("simple-spec.md") == "simple-spec"


def test_spec_slug_empty_after_strip_raises() -> None:
    with pytest.raises(ValueError, match="Empty spec slug"):
        derive_spec_slug(Path("2026-04-27.md"))


# -- derive_plan_name -----------------------------------------------------


def test_plan_name_strips_spec_prefix_and_phase_n() -> None:
    """`<spec>-phase-N-<descriptor>` yields just `<descriptor>`."""
    name = derive_plan_name(
        Path("2026-04-27-label-lifecycle-fix-phase-3-labels-sync.md"),
        spec_slug="label-lifecycle-fix",
    )
    assert name == "labels-sync"


def test_plan_name_falls_back_to_phase_n_when_no_descriptor() -> None:
    """`<spec>-phase-N` (no descriptor tail) falls back to `phase-N`."""
    name = derive_plan_name(
        Path("2026-04-27-label-lifecycle-fix-phase-1.md"),
        spec_slug="label-lifecycle-fix",
    )
    assert name == "phase-1"


def test_plan_name_keeps_long_descriptor() -> None:
    name = derive_plan_name(
        Path("2026-04-27-label-lifecycle-fix-phase-2-project-board-excision.md"),
        spec_slug="label-lifecycle-fix",
    )
    assert name == "project-board-excision"


def test_plan_name_passthrough_when_no_phase_pattern() -> None:
    """Plans whose tail doesn't match `phase-N-...` keep the tail as-is."""
    name = derive_plan_name(
        Path("2026-04-27-label-lifecycle-fix-something-else.md"),
        spec_slug="label-lifecycle-fix",
    )
    assert name == "something-else"
