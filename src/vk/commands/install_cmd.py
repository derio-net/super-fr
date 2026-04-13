"""vk install-skills — update plugin cache and install extras the plugin system can't handle."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer

CLAUDE_DIR = Path.home() / ".claude"
MARKETPLACE_DIR = CLAUDE_DIR / "plugins" / "marketplaces" / "derio-net"
CACHE_DIR = CLAUDE_DIR / "plugins" / "cache" / "derio-net" / "superpowers-for-vk"
SKILL_NAMES = ("vk-plan", "vk-dispatch", "vk-execute", "vk-progress")


def _repo_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path(__file__).parent.parent.parent.parent


def _pull_marketplace() -> None:
    """Pull the marketplace clone so the plugin system sees the latest version."""
    if not (MARKETPLACE_DIR / ".git").exists():
        typer.echo(f"  marketplace clone not found at {MARKETPLACE_DIR} — skipping pull")
        return
    result = subprocess.run(
        ["git", "-C", str(MARKETPLACE_DIR), "pull", "--ff-only", "origin", "main"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        typer.echo("  marketplace clone updated")
    else:
        typer.echo(f"  WARNING: marketplace pull failed: {result.stderr.strip()}")


def _clear_stale_cache() -> None:
    """Remove old version dirs from the plugin cache so the next restart fetches fresh."""
    if not CACHE_DIR.exists():
        return
    # Read the current version from the marketplace clone
    manifest = MARKETPLACE_DIR / ".claude-plugin" / "marketplace.json"
    current_version = None
    if manifest.exists():
        import json

        data = json.loads(manifest.read_text())
        for plugin in data.get("plugins", []):
            if plugin.get("name") == "superpowers-for-vk":
                current_version = plugin.get("version")
                break

    for version_dir in sorted(CACHE_DIR.iterdir()):
        if not version_dir.is_dir():
            continue
        if current_version and version_dir.name == current_version:
            continue
        shutil.rmtree(version_dir)
        typer.echo(f"  cleared stale cache: {version_dir.name}")


def _clean_stale_skills() -> None:
    """Remove vk-* skill dirs from ~/.claude/skills/ — the plugin system delivers these now."""
    skills_dir = CLAUDE_DIR / "skills"
    for name in SKILL_NAMES:
        target = skills_dir / name
        if target.exists() or target.is_symlink():
            if target.is_symlink():
                target.unlink()
            else:
                shutil.rmtree(target)
            typer.echo(f"  removed stale skill: {target}")


def _install_rules() -> int:
    """Copy rule files into ~/.claude/rules/."""
    rules_src = _repo_root() / "rules"
    if not rules_src.exists():
        return 0

    claude_rules = CLAUDE_DIR / "rules"
    claude_rules.mkdir(parents=True, exist_ok=True)

    count = 0
    for rule_file in sorted(rules_src.glob("*.md")):
        target = claude_rules / rule_file.name
        if target.exists() or target.is_symlink():
            target.unlink()
        shutil.copy2(rule_file, target)
        count += 1
        typer.echo(f"  installed rule: {rule_file.name}")

    return count


def install_skills() -> None:
    """Update the plugin marketplace clone, clear stale cache, install rules, and clean up."""
    typer.echo("Updating superpowers-for-vk...")

    _pull_marketplace()
    _clear_stale_cache()
    _clean_stale_skills()
    rule_count = _install_rules()

    typer.echo(f"\nDone. {rule_count} rule(s) installed.")
    typer.echo("Skills are delivered by the plugin system — restart Claude Code to pick up changes.")
