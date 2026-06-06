"""vk skills — regression coverage for the CLI/skill overview command.

The command crashed in installed environments (`ModuleNotFoundError:
No module named 'click'`): skills_cmd imports click directly, so the
package must be a declared dependency, not an accident of resolution.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
from fr.commands import skills_cmd

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_skills_prints_commands_and_skills(capsys: pytest.CaptureFixture[str]) -> None:
    skills_cmd.skills()
    out = capsys.readouterr().out
    assert "Commands:" in out
    assert "Skills (full docs in skills/<name>/SKILL.md):" in out
    # Every top-level sub-app we know about should be listed.
    for verb in ("apply", "pickup", "plan", "spec"):
        assert re.search(rf"^  vk {verb}\b", out, re.MULTILINE), f"missing: vk {verb}"


@pytest.mark.parametrize("name", [entry[0] for entry in skills_cmd.SKILLS])
def test_skills_list_matches_skill_files(name: str) -> None:
    """Every SKILLS tuple must point at a real skills/<name>/SKILL.md."""
    assert (REPO_ROOT / "skills" / name / "SKILL.md").is_file()


def test_skill_files_match_skills_list() -> None:
    """Every skills/<name>/ folder must be summarized in SKILLS (drift guard)."""
    listed = {entry[0] for entry in skills_cmd.SKILLS}
    on_disk = {p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md")}
    assert on_disk == listed


def test_skills_subprocess_smoke() -> None:
    """`python -m fr skills` must exit 0 — covers the direct click import."""
    result = subprocess.run(
        [sys.executable, "-m", "fr", "skills"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "Commands:" in result.stdout


def test_no_direct_click_import_in_src() -> None:
    """typer ≥0.26 vendors click — a bare `import click` breaks installed envs.

    Nothing in src/ may import click directly; introspect typer objects via
    duck typing instead (see _commands).
    """
    offenders = [
        p
        for p in (REPO_ROOT / "src").rglob("*.py")
        if re.search(r"^\s*(import click|from click)", p.read_text(), re.MULTILINE)
    ]
    assert not offenders, f"direct click imports: {offenders}"
