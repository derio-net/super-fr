"""Tests for validate_issue_body."""

from __future__ import annotations

import pytest

from vk.commands.dispatch_body_validator import BodyValidationError, validate_issue_body


class TestValidateIssueBody:
    def test_accepts_complete_phase_zero_body(self) -> None:
        body = (
            "📦 Repo:   org/repo\n\n---\n\n"
            "## Instruction\n\nUse ...\n\n"
            "## Workspace\n\nRepos: org/repo\n\n"
            "## Dependencies\n\nNone — no blocking phases.\n"
        )
        validate_issue_body(body, phase_number=0)  # no raise

    def test_accepts_complete_phase_n_body(self) -> None:
        body = (
            "## Instruction\n\nUse ...\n\n"
            "## Workspace\n\nRepos: org/repo\n\n"
            "## Dependencies\n\n- Blocked by #42\n"
        )
        validate_issue_body(body, phase_number=2)

    def test_rejects_missing_instruction(self) -> None:
        body = "## Workspace\n\nRepos: x\n\n## Dependencies\n\n- Blocked by #1\n"
        with pytest.raises(BodyValidationError, match="## Instruction"):
            validate_issue_body(body, phase_number=1)

    def test_rejects_missing_workspace(self) -> None:
        body = "## Instruction\n\nUse ...\n\n## Dependencies\n\n- Blocked by #1\n"
        with pytest.raises(BodyValidationError, match="## Workspace"):
            validate_issue_body(body, phase_number=1)

    def test_rejects_missing_dependencies(self) -> None:
        body = "## Instruction\n\nUse ...\n\n## Workspace\n\nRepos: x\n"
        with pytest.raises(BodyValidationError, match="## Dependencies"):
            validate_issue_body(body, phase_number=1)

    def test_rejects_phase_n_without_dash_blocker(self) -> None:
        body = (
            "## Instruction\n\nUse ...\n\n"
            "## Workspace\n\nRepos: x\n\n"
            "## Dependencies\n\nBlocked by #42\n"  # missing dash prefix
        )
        with pytest.raises(BodyValidationError, match="- Blocked by"):
            validate_issue_body(body, phase_number=2)


class TestRelaxedValidator:
    """Validator accepts None literal or >=1 '- Blocked by #N' lines."""

    def _body_with_deps(self, deps_block: str) -> str:
        return (
            "📦 Repo: o/r\n\n---\n\n"
            "## Instruction\n\nDo stuff.\n\n"
            "## Workspace\n\nRepos: o/r\n\n"
            "## Dependencies\n\n"
            f"{deps_block}\n"
        )

    def test_accepts_none_literal_for_root_phase(self) -> None:
        validate_issue_body(self._body_with_deps("None — no blocking phases."), phase_number=1)

    def test_accepts_single_blocker_for_non_root(self) -> None:
        validate_issue_body(self._body_with_deps("- Blocked by #42"), phase_number=2)

    def test_accepts_multiple_blockers(self) -> None:
        validate_issue_body(
            self._body_with_deps("- Blocked by #42\n- Blocked by #43"),
            phase_number=3,
        )

    def test_rejects_missing_dependencies_section(self) -> None:
        body = "## Instruction\n\nDo.\n\n## Workspace\n\nRepos: o/r\n\n"
        with pytest.raises(BodyValidationError, match="Dependencies"):
            validate_issue_body(body, phase_number=2)

    def test_rejects_undashed_blocker_line(self) -> None:
        body = self._body_with_deps("Blocked by #42")
        with pytest.raises(BodyValidationError, match="dash-prefixed"):
            validate_issue_body(body, phase_number=2)

    def test_rejects_empty_dependencies_section_for_non_root(self) -> None:
        body = self._body_with_deps("")
        with pytest.raises(BodyValidationError):
            validate_issue_body(body, phase_number=2)
