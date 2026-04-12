"""vk init — scaffold plan-config.yaml in a new repo."""

from __future__ import annotations

import os
from pathlib import Path

import typer
import yaml


def _resolve_repo_root() -> Path:
    """Resolve repo root from VK_REPO_ROOT env var or git."""
    env_root = os.environ.get("VK_REPO_ROOT")
    if env_root:
        return Path(env_root)

    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())
    return Path.cwd()


def init(
    dispatch: str | None = typer.Option(
        None,
        "--dispatch",
        help="Enable dispatch with OWNER/REPO.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        help="Project board name.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing config.",
    ),
) -> None:
    """Scaffold plan-config.yaml in a new repo."""
    repo_root = _resolve_repo_root()
    superpowers_dir = repo_root / "docs" / "superpowers"
    config_path = superpowers_dir / "plan-config.yaml"

    if config_path.exists() and not force:
        typer.echo(f"Config already exists: {config_path}")
        typer.echo("Use --force to overwrite.")
        raise typer.Exit(1)

    for subdir in ("specs", "plans", "archived-plans"):
        (superpowers_dir / subdir).mkdir(parents=True, exist_ok=True)

    config: dict[str, object] = {
        "plan": {
            "save_to": "docs/superpowers/plans/",
            "filename": "YYYY-MM-DD-{name}.md",
        },
        "header": {
            "required": ["Spec", "Status"],
            "status_values": ["Not Started", "In Progress", "Complete"],
        },
    }

    if dispatch:
        parts = dispatch.split("/", maxsplit=1)
        if len(parts) != 2:
            typer.echo(f"Invalid --dispatch format: {dispatch!r}. Expected OWNER/REPO.")
            raise typer.Exit(1)

        owner = parts[0]
        project_name = project or "Derio Ops"

        config["dispatch"] = {
            "target": "github-issues",
            "owner": owner,
            "project_board": project_name,
            "default_repo": dispatch,
            "labels": {
                "agentic": "vk-ready",
                "manual": "manual",
            },
        }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    typer.echo(f"Created {config_path}")
