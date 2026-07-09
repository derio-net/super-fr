"""Per-repo plan-validator wrapper lifecycle helpers."""

from __future__ import annotations

from pathlib import Path

PLANS_REL = Path("docs") / "superpowers" / "plans"
REPAIR_COMMAND = (
    "bash ~/.claude/plugins/marketplaces/derio-net/scripts/install-validator-wrapper.sh"
)
WRAPPER_REL = Path("scripts") / "validate-plans.sh"

WRAPPER_TEXT = """#!/usr/bin/env bash
# Thin wrapper — delegates to the canonical validator from the
# super-fr plugin installed at the user level.
exec "$HOME/.claude/plugins/marketplaces/derio-net/scripts/validate-plans.sh" "$@"
"""


class ValidatorWrapperError(RuntimeError):
    """Raised when a repo's plan-validator wrapper cannot be safely managed."""


def plans_dir_exists(repo_root: Path) -> bool:
    return (repo_root / PLANS_REL).is_dir()


def validator_wrapper_path(repo_root: Path) -> Path:
    return repo_root / WRAPPER_REL


def is_super_fr_validator_wrapper(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    text = path.read_text(errors="ignore")
    return (
        ".claude/plugins/marketplaces/derio-net/scripts/validate-plans.sh" in text
        and ("superpowers-for-vk" in text or "super-fr" in text)
    )


def ensure_validator_wrapper(repo_root: Path) -> bool:
    """Install or refresh the wrapper. Returns true when the file was written."""

    target = validator_wrapper_path(repo_root)
    if target.exists() and not is_super_fr_validator_wrapper(target):
        raise ValidatorWrapperError(
            f"{target} already exists and is not a super-fr wrapper. "
            "Refusing to overwrite it."
        )

    before = target.read_text(errors="ignore") if target.exists() else None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(WRAPPER_TEXT)
    target.chmod(0o755)
    return before != WRAPPER_TEXT


def validate_plan_repo_validator(repo_root: Path) -> None:
    if not plans_dir_exists(repo_root):
        return
    target = validator_wrapper_path(repo_root)
    if not target.is_file() or not (target.stat().st_mode & 0o111):
        raise ValidatorWrapperError(
            f"plan repo is missing executable {WRAPPER_REL}; run `{REPAIR_COMMAND}` "
            "from the repo root, then retry `fr isolation up`."
        )
