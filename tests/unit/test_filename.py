"""Tests for vk.plan.filename — slug derivation from plan file paths."""

from pathlib import Path

import pytest

from vk.plan.filename import derive_slug


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
