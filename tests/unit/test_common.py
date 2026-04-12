"""Tests for shared CLI helpers."""

from __future__ import annotations

import pytest

from vk.commands.common import (
    ConfirmAction,
    MutuallyExclusiveError,
    format_error,
    format_gate_refusal,
    resolve_action,
)


class TestResolveAction:
    """Tests for --dry-run / --yes tri-state resolution."""

    def test_default_returns_prompt(self) -> None:
        assert resolve_action(dry_run=False, yes=False) is ConfirmAction.PROMPT

    def test_dry_run_returns_dry_run(self) -> None:
        assert resolve_action(dry_run=True, yes=False) is ConfirmAction.DRY_RUN

    def test_yes_returns_apply(self) -> None:
        assert resolve_action(dry_run=False, yes=True) is ConfirmAction.APPLY

    def test_both_raises(self) -> None:
        with pytest.raises(MutuallyExclusiveError, match="mutually exclusive"):
            resolve_action(dry_run=True, yes=True)


class TestFormatError:
    """Tests for rich error formatting."""

    def test_format_error_includes_message(self) -> None:
        result = format_error("something broke", hint="try fixing it")
        assert "something broke" in result
        assert "try fixing it" in result

    def test_format_error_without_hint(self) -> None:
        result = format_error("something broke")
        assert "something broke" in result


class TestFormatGateRefusal:
    """Tests for dispatch gate refusal message."""

    def test_gate_refusal_includes_template(self) -> None:
        result = format_gate_refusal()
        assert "dispatch:" in result
        assert "plan-config.yaml" in result
        assert "target: github-issues" in result
        assert "owner:" in result
        assert "project_board:" in result
        assert "labels:" in result
