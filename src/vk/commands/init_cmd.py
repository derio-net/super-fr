"""vk init — scaffold plan-config.yaml in a new repo."""

from __future__ import annotations

import typer
import yaml

from vk.commands.common import resolve_repo_root


def init(
    dispatch: str | None = typer.Option(
        None,
        "--dispatch",
        help="Enable dispatch with OWNER/REPO.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing config.",
    ),
) -> None:
    """Scaffold plan-config.yaml in a new repo."""
    repo_root = resolve_repo_root()
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

        config["dispatch"] = {
            "target": "github-issues",
            "owner": owner,
            "default_repo": dispatch,
            "labels": {
                "agentic": "vk-ready",
                "manual": "manual",
            },
        }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    typer.echo(f"Created {config_path}")
