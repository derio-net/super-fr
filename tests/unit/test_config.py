"""Tests for vk.config — dispatch gate truth table and profile loading."""

from pathlib import Path

import pytest

from vk.config import (
    PlanConfig,
    load_profile,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "configs"


# --- Dispatch gate truth table (7 cases) ---


def test_gate_file_missing(tmp_path: Path) -> None:
    """File missing -> dispatch disabled."""
    profile = load_profile(tmp_path / "nonexistent.yaml")
    assert profile.dispatch_enabled is False
    assert profile.dispatch is None


def test_gate_no_dispatch_key() -> None:
    """File exists, no ``dispatch`` key -> dispatch disabled."""
    profile = load_profile(FIXTURES / "no-dispatch-key.yaml")
    assert profile.dispatch_enabled is False
    assert profile.dispatch is None


def test_gate_dispatch_false() -> None:
    """``dispatch: false`` -> dispatch disabled."""
    profile = load_profile(FIXTURES / "dispatch-false.yaml")
    assert profile.dispatch_enabled is False
    assert profile.dispatch is None


def test_gate_dispatch_null(tmp_path: Path) -> None:
    """``dispatch: null`` -> dispatch disabled."""
    cfg = tmp_path / "plan-config.yaml"
    cfg.write_text("dispatch: null\n")
    profile = load_profile(cfg)
    assert profile.dispatch_enabled is False
    assert profile.dispatch is None


def test_gate_dispatch_true_scalar(tmp_path: Path) -> None:
    """``dispatch: true`` (scalar, not map) -> dispatch disabled + warning."""
    cfg = tmp_path / "plan-config.yaml"
    cfg.write_text("dispatch: true\n")
    with pytest.warns(UserWarning, match="dispatch.*must be a map"):
        profile = load_profile(cfg)
    assert profile.dispatch_enabled is False
    assert profile.dispatch is None


def test_gate_dispatch_empty_map() -> None:
    """``dispatch: {}`` -> dispatch enabled with defaults."""
    profile = load_profile(FIXTURES / "dispatch-minimal.yaml")
    assert profile.dispatch_enabled is True
    assert profile.dispatch is not None
    assert profile.dispatch.owner == "derio-net"
    assert profile.dispatch.project_board == "Derio Ops"
    assert profile.dispatch.target == "github-issues"
    assert profile.dispatch.labels == {"agentic": "vk-ready", "manual": "manual"}


def test_gate_dispatch_full_map() -> None:
    """``dispatch: {owner: foo, ...}`` -> dispatch enabled with explicit values."""
    profile = load_profile(FIXTURES / "dispatch-enabled.yaml")
    assert profile.dispatch_enabled is True
    assert profile.dispatch is not None
    assert profile.dispatch.owner == "derio-net"
    assert profile.dispatch.project_board == "Derio Ops"
    assert profile.dispatch.default_repo == "derio-net/some-repo"
    assert profile.dispatch.target == "github-issues"
    assert profile.dispatch.labels == {"agentic": "vk-ready", "manual": "manual"}


# --- Format derived from dispatch ---


def test_format_flat_when_no_dispatch() -> None:
    """No dispatch -> flat format."""
    from vk.plan.format import PlanFormat

    profile = load_profile(FIXTURES / "no-dispatch-key.yaml")
    assert profile.format is PlanFormat.FLAT


def test_format_phased_when_dispatch_enabled() -> None:
    """Dispatch enabled -> phased format."""
    from vk.plan.format import PlanFormat

    profile = load_profile(FIXTURES / "dispatch-enabled.yaml")
    assert profile.format is PlanFormat.PHASED


# --- PlanConfig and HeaderConfig ---


def test_plan_config_defaults(tmp_path: Path) -> None:
    """Missing plan/header sections get sensible defaults."""
    cfg = tmp_path / "plan-config.yaml"
    cfg.write_text("# minimal\n")
    profile = load_profile(cfg)
    assert profile.plan.filename == "YYYY-MM-DD-{name}.md"
    assert profile.plan.save_to == "docs/superpowers/plans/"
    assert "Spec" in profile.header.required
    assert "Status" in profile.header.required


def test_plan_config_loaded() -> None:
    """Explicit plan config is loaded correctly."""
    profile = load_profile(FIXTURES / "dispatch-enabled.yaml")
    assert profile.plan.filename == "YYYY-MM-DD-{name}.md"
    assert profile.plan.save_to == "docs/superpowers/plans/"
    assert profile.header.required == ("Spec", "Status")
    assert "Not Started" in profile.header.status_values
    assert "In Progress" in profile.header.status_values
    assert "Complete" in profile.header.status_values


# --- Dataclass immutability ---


def test_profile_is_frozen() -> None:
    """Profile and sub-configs are immutable."""
    profile = load_profile(FIXTURES / "dispatch-enabled.yaml")
    with pytest.raises(AttributeError):
        profile.plan = PlanConfig(filename="x", save_to="y")  # type: ignore[misc]
    with pytest.raises(AttributeError):
        profile.dispatch = None  # type: ignore[misc]


def test_empty_file_gives_defaults() -> None:
    """Empty YAML file gives all-default profile."""
    profile = load_profile(FIXTURES / "empty.yaml")
    assert profile.dispatch_enabled is False
    assert profile.plan.filename == "YYYY-MM-DD-{name}.md"
