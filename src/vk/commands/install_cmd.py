"""vk install-skills — symlink SKILL.md files into ~/.claude/skills/."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer


def _find_skills_dir() -> Path:
    """Find the skills/ directory relative to the vk package."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        repo_root = Path(__file__).parent.parent.parent.parent

    skills_dir = repo_root / "skills"
    if not skills_dir.exists():
        typer.echo(f"Skills directory not found: {skills_dir}")
        raise typer.Exit(1)
    return skills_dir


def install_skills(
    copy: bool = typer.Option(False, "--copy", help="Copy instead of symlink."),
) -> None:
    """Symlink SKILL.md files into ~/.claude/skills/."""
    skills_src = _find_skills_dir()
    claude_skills = Path.home() / ".claude" / "skills"
    claude_skills.mkdir(parents=True, exist_ok=True)

    count = 0
    for skill_dir in sorted(skills_src.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
            continue

        target = claude_skills / skill_dir.name

        if target.exists() or target.is_symlink():
            if target.is_symlink():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)

        if copy:
            shutil.copytree(skill_dir, target)
        else:
            target.symlink_to(skill_dir)

        count += 1
        mode = "copied" if copy else "symlinked"
        typer.echo(f"  {mode}: {skill_dir.name} -> {target}")

    typer.echo(f"\n{count} skill(s) installed.")
