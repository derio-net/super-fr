"""Tests for vk.config — dispatch gate truth table and profile loading."""

from pathlib import Path

import pytest

from vk.config import (
    DispatchConfig,
    PlanConfig,
    _parse_dispatch,
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
    assert profile.dispatch.target == "github-issues"
    assert profile.dispatch.labels == {
        "agentic": "vk-ready",
        "manual": "manual",
        "in_progress": "in-progress",
        "pr_ready": "pr-ready",
    }


def test_gate_dispatch_full_map() -> None:
    """``dispatch: {owner: foo, ...}`` -> dispatch enabled with explicit values."""
    profile = load_profile(FIXTURES / "dispatch-enabled.yaml")
    assert profile.dispatch_enabled is True
    assert profile.dispatch is not None
    assert profile.dispatch.owner == "derio-net"
    assert profile.dispatch.default_repo == "derio-net/some-repo"
    assert profile.dispatch.target == "github-issues"
    # The fixture only sets agentic/manual; the new keys merge in from defaults.
    assert profile.dispatch.labels == {
        "agentic": "vk-ready",
        "manual": "manual",
        "in_progress": "in-progress",
        "pr_ready": "pr-ready",
    }


class TestDispatchConfigNoProjectBoard:
    def test_dataclass_has_no_project_board_field(self) -> None:
        from dataclasses import fields

        from vk.config import DispatchConfig

        names = {f.name for f in fields(DispatchConfig)}
        assert "project_board" not in names

    def test_yaml_with_project_board_key_does_not_break(self) -> None:
        # Backward-compat: existing plan-config.yaml files in the wild still
        # have the key. Parser must ignore it, not error.
        raw = {
            "target": "github-issues",
            "owner": "o",
            "project_board": "Some Board",
            "default_repo": "o/r",
        }
        cfg = _parse_dispatch(raw)
        assert cfg is not None
        assert not hasattr(cfg, "project_board")


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


def test_plan_archive_to_default(tmp_path: Path) -> None:
    p = tmp_path / "plan-config.yaml"
    p.write_text("plan:\n  save_to: docs/plans/\n")
    profile = load_profile(p)
    assert profile.plan.archive_to == "docs/superpowers/archived-plans/"


def test_plan_archive_to_override(tmp_path: Path) -> None:
    p = tmp_path / "plan-config.yaml"
    p.write_text("plan:\n  archive_to: custom/archive/\n")
    profile = load_profile(p)
    assert profile.plan.archive_to == "custom/archive/"


def test_empty_file_gives_defaults() -> None:
    """Empty YAML file gives all-default profile."""
    profile = load_profile(FIXTURES / "empty.yaml")
    assert profile.dispatch_enabled is False
    assert profile.plan.filename == "YYYY-MM-DD-{name}.md"


# --- DispatchConfig label defaults and merge behaviour ---


class TestDispatchLabelDefaults:
    def test_default_includes_all_four_lifecycle_keys(self) -> None:
        cfg = DispatchConfig()
        assert cfg.labels == {
            "agentic": "vk-ready",
            "manual": "manual",
            "in_progress": "in-progress",
            "pr_ready": "pr-ready",
        }

    def test_yaml_partial_override_merges_with_defaults(self) -> None:
        # Simulates a user plan-config.yaml with only old keys present
        raw = {
            "target": "github-issues",
            "owner": "o",
            "labels": {"agentic": "ready", "manual": "human-only"},
        }
        cfg = _parse_dispatch(raw)
        assert cfg is not None
        assert cfg.labels["agentic"] == "ready"  # override
        assert cfg.labels["manual"] == "human-only"  # override
        assert cfg.labels["in_progress"] == "in-progress"  # default
        assert cfg.labels["pr_ready"] == "pr-ready"  # default

    def test_yaml_full_override(self) -> None:
        raw = {
            "target": "github-issues",
            "owner": "o",
            "labels": {
                "agentic": "a",
                "manual": "m",
                "in_progress": "ip",
                "pr_ready": "pr",
            },
        }
        cfg = _parse_dispatch(raw)
        assert cfg is not None
        assert cfg.labels == {
            "agentic": "a",
            "manual": "m",
            "in_progress": "ip",
            "pr_ready": "pr",
        }

    def test_non_dict_labels_value_falls_back_to_defaults(self) -> None:
        # A misconfigured plan-config.yaml with labels: "bad-string" must not
        # raise TypeError — it silently falls back to all defaults.
        for bad_value in ("bad-string", ["a", "b"], 42):
            raw = {"target": "github-issues", "owner": "o", "labels": bad_value}
            cfg = _parse_dispatch(raw)
            assert cfg is not None, f"Expected DispatchConfig for labels={bad_value!r}"
            assert cfg.labels == {
                "agentic": "vk-ready",
                "manual": "manual",
                "in_progress": "in-progress",
                "pr_ready": "pr-ready",
            }, f"Expected defaults for labels={bad_value!r}"
