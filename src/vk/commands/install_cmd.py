"""vk install-skills — install skills and rules into ~/.claude/."""

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


def _clean_marketplace_skills(skills_src: Path) -> None:
    """Remove vk-* skills from the plugin marketplace to avoid duplicates."""
    marketplace_dir = Path.home() / ".claude" / "plugins" / "marketplaces" / "derio-net" / "skills"
    if not marketplace_dir.exists():
        return
    for skill_dir in sorted(skills_src.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
            continue
        stale = marketplace_dir / skill_dir.name
        if stale.exists():
            shutil.rmtree(stale)
            typer.echo(f"  removed marketplace duplicate: {stale}")


def _find_rules_dir() -> Path | None:
    """Find the rules/ directory relative to the vk package."""
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

    rules_dir = repo_root / "rules"
    return rules_dir if rules_dir.exists() else None


def _install_rules(copy: bool) -> int:
    """Copy or symlink rule files into ~/.claude/rules/."""
    rules_src = _find_rules_dir()
    if not rules_src:
        return 0

    claude_rules = Path.home() / ".claude" / "rules"
    claude_rules.mkdir(parents=True, exist_ok=True)

    count = 0
    for rule_file in sorted(rules_src.glob("*.md")):
        target = claude_rules / rule_file.name

        if target.exists() or target.is_symlink():
            if target.is_symlink():
                target.unlink()
            else:
                target.unlink()

        if copy:
            shutil.copy2(rule_file, target)
        else:
            target.symlink_to(rule_file)

        count += 1
        mode = "copied" if copy else "symlinked"
        typer.echo(f"  {mode}: {rule_file.name} -> {target}")

    return count


def install_skills(
    copy: bool = typer.Option(False, "--copy", help="Copy instead of symlink."),
) -> None:
    """Install skills and rules into ~/.claude/."""
    skills_src = _find_skills_dir()
    claude_skills = Path.home() / ".claude" / "skills"
    claude_skills.mkdir(parents=True, exist_ok=True)

    _clean_marketplace_skills(skills_src)

    skill_count = 0
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

        skill_count += 1
        mode = "copied" if copy else "symlinked"
        typer.echo(f"  {mode}: {skill_dir.name} -> {target}")

    rule_count = _install_rules(copy)

    typer.echo(f"\n{skill_count} skill(s) + {rule_count} rule(s) installed.")
