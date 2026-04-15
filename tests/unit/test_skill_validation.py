"""Tests for SKILL.md file validation — replacement for validate-skills.sh."""

from pathlib import Path

import pytest
import yaml

SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


@pytest.mark.parametrize(
    "skill_dir",
    sorted(SKILLS_DIR.glob("vk-*")),
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

    def test_vk_execute_has_lifecycle_transition(self, skill_dir: Path) -> None:
        """vk-execute must include the post-PR lifecycle transition step."""
        if skill_dir.name != "vk-execute":
            pytest.skip("Only applies to vk-execute")
        text = (skill_dir / "SKILL.md").read_text()
        assert "In Review" in text, "vk-execute must reference 'In Review' lifecycle transition"

    def test_vk_execute_mentions_pr_ready_label(self, skill_dir: Path) -> None:
        if skill_dir.name != "vk-execute":
            pytest.skip("Only applies to vk-execute")
        text = (skill_dir / "SKILL.md").read_text()
        assert "pr-ready" in text, "vk-execute must document the pr-ready label swap"

    def test_vk_execute_mentions_unified_pr_title(self, skill_dir: Path) -> None:
        if skill_dir.name != "vk-execute":
            pytest.skip("Only applies to vk-execute")
        text = (skill_dir / "SKILL.md").read_text()
        assert "[{owner}/{repo}]" in text or "[owner/repo]" in text, (
            "vk-execute must document the unified PR title format"
        )
