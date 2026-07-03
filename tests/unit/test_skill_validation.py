"""Tests for SKILL.md file validation — replacement for validate-skills.sh."""

from pathlib import Path

import pytest
import yaml

PLUGINS_DIR = Path(__file__).parent.parent.parent / "plugins"
# Every skill across both plugins; a glob miss collapses the matrix
# silently, so a floor assertion guards collection (2026-06-06).
_SKILL_DIRS = sorted(PLUGINS_DIR.glob("*/skills/fr-*"))
assert len(_SKILL_DIRS) >= 9, f"skill glob collapsed: {_SKILL_DIRS}"


@pytest.mark.parametrize(
    "skill_dir",
    _SKILL_DIRS,
    ids=lambda p: p.name,
)
class TestSkillValidation:
    def test_skill_file_exists(self, skill_dir: Path) -> None:
        assert (skill_dir / "SKILL.md").exists()

    def test_first_line_is_frontmatter(self, skill_dir: Path) -> None:
        text = (skill_dir / "SKILL.md").read_text().strip()
        first_line = text.split("\n")[0]
        assert first_line == "---", f"First line must be '---', got: {first_line!r}"

    def test_frontmatter_parses(self, skill_dir: Path) -> None:
        text = (skill_dir / "SKILL.md").read_text()
        parts = text.split("---", 2)
        assert len(parts) >= 3, "Must have YAML frontmatter between --- markers"
        frontmatter = yaml.safe_load(parts[1])
        assert isinstance(frontmatter, dict)

    def test_name_field_present(self, skill_dir: Path) -> None:
        text = (skill_dir / "SKILL.md").read_text()
        parts = text.split("---", 2)
        frontmatter = yaml.safe_load(parts[1])
        assert "name" in frontmatter
        assert frontmatter["name"]

    def test_description_field_present(self, skill_dir: Path) -> None:
        text = (skill_dir / "SKILL.md").read_text()
        parts = text.split("---", 2)
        frontmatter = yaml.safe_load(parts[1])
        assert "description" in frontmatter
        assert frontmatter["description"]

    def test_under_120_lines(self, skill_dir: Path) -> None:
        text = (skill_dir / "SKILL.md").read_text()
        line_count = len(text.strip().split("\n"))
        assert line_count <= 120, f"{skill_dir.name}/SKILL.md has {line_count} lines (max 120)"

    def test_fr_execute_uses_v2_pickup(self, skill_dir: Path) -> None:
        """fr-execute must point at `fr pickup` for phase scope (v2 entry point)."""
        if skill_dir.name != "fr-execute":
            pytest.skip("Only applies to fr-execute")
        text = (skill_dir / "SKILL.md").read_text()
        assert "fr pickup" in text, "fr-execute must reference fr pickup"

    def test_fr_execute_uses_v2_apply_for_reconciliation(self, skill_dir: Path) -> None:
        """fr-execute must hand reconciliation back to `fr apply` (no manual claim/pr-opened)."""
        if skill_dir.name != "fr-execute":
            pytest.skip("Only applies to fr-execute")
        text = (skill_dir / "SKILL.md").read_text()
        assert "fr apply" in text, "fr-execute must reference fr apply"

    def test_fr_execute_mentions_pr_ready_label(self, skill_dir: Path) -> None:
        if skill_dir.name != "fr-execute":
            pytest.skip("Only applies to fr-execute")
        text = (skill_dir / "SKILL.md").read_text()
        assert "pr-ready" in text, "fr-execute must document the pr-ready lifecycle stage"

    def test_fr_execute_mentions_unified_pr_title(self, skill_dir: Path) -> None:
        if skill_dir.name != "fr-execute":
            pytest.skip("Only applies to fr-execute")
        text = (skill_dir / "SKILL.md").read_text()
        assert "[{owner}/{repo}]" in text or "[owner/repo]" in text, (
            "fr-execute must document the unified PR title format"
        )

    def test_fr_plan_tdd_names_all_three_beats(self, skill_dir: Path) -> None:
        """fr-plan's TDD rule must name the full red → green → refactor cycle.

        Guards against the #340 paraphrase leak where "test first, always"
        silently dropped the Refactor beat.
        """
        if skill_dir.name != "fr-plan":
            pytest.skip("Only applies to fr-plan")
        text = (skill_dir / "SKILL.md").read_text().lower()
        assert "red → green → refactor" in text, (
            "fr-plan's TDD rule must name all three beats (red → green → refactor), "
            "not just test-first — see #340"
        )

    def test_fr_plan_routes_to_canonical_tdd_skill(self, skill_dir: Path) -> None:
        """fr-plan must route to the canonical TDD skill, not re-paraphrase it."""
        if skill_dir.name != "fr-plan":
            pytest.skip("Only applies to fr-plan")
        text = (skill_dir / "SKILL.md").read_text()
        assert "superpowers:test-driven-development" in text, (
            "fr-plan must route to superpowers:test-driven-development (#340)"
        )

    def test_fr_goal_routes_to_canonical_tdd_skill(self, skill_dir: Path) -> None:
        """fr-goal's TDD references must route to the canonical skill (#340)."""
        if skill_dir.name != "fr-goal":
            pytest.skip("Only applies to fr-goal")
        text = (skill_dir / "SKILL.md").read_text()
        assert "superpowers:test-driven-development" in text, (
            "fr-goal must route to superpowers:test-driven-development (#340)"
        )
