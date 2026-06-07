"""In-place vk→fr spelling migration for a repo's isolation surfaces (#272).

Counterpart of the dual-read in types.py/local.py: dual-read keeps an
unmigrated repo working with a warning; `fr init migrate` retires the
warning by rewriting the repo to the fr spellings. Host-side secrets are
NEVER moved by this code — the operator gets a printed, idempotent,
copy-no-clobber block instead (cross-host actions stay human-owned).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from fr.isolation.types import IsolationError

SECRETS_BLOCK = """\
# host secrets move (run yourself, per machine; copy-no-clobber — the vk dir
# stays until the fallback-removal release):
mkdir -p ~/.config/fr/secrets
[ -d ~/.config/vk/secrets ] && cp -an ~/.config/vk/secrets/. ~/.config/fr/secrets/
"""


def _is_tracked(repo_root: Path, rel: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", rel],
            capture_output=True,
        ).returncode
        == 0
    )


def _rewrite_devcontainer(config_path: Path) -> str | None:
    """Return the rewritten JSON text, or None when already migrated."""
    config = json.loads(config_path.read_text())
    changed = False

    run_args = config.get("runArgs", [])
    for i, arg in enumerate(run_args):
        if isinstance(arg, str) and "/.config/vk/secrets/" in arg:
            run_args[i] = arg.replace("/.config/vk/secrets/", "/.config/fr/secrets/")
            changed = True

    customizations = config.get("customizations", {})
    if "vk" in customizations and "fr" not in customizations:
        customizations["fr"] = customizations.pop("vk")
        changed = True

    return json.dumps(config, indent=2, ensure_ascii=False) + "\n" if changed else None


def migrate_repo(repo_root: Path, yes: bool) -> list[str]:
    """Compute (and with yes=True, apply) the vk→fr migration actions."""
    if not (repo_root / ".git").exists():
        raise IsolationError(f"{repo_root} is not a git repo — fr init migrate needs one.")

    actions: list[str] = []

    vk_yaml = repo_root / ".devcontainer" / "vk-profiles.yaml"
    fr_yaml = repo_root / ".devcontainer" / "fr-profiles.yaml"
    if vk_yaml.is_file() and not fr_yaml.exists():
        actions.append("rename .devcontainer/vk-profiles.yaml -> .devcontainer/fr-profiles.yaml")
        if yes:
            if _is_tracked(repo_root, ".devcontainer/vk-profiles.yaml"):
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo_root),
                        "mv",
                        ".devcontainer/vk-profiles.yaml",
                        ".devcontainer/fr-profiles.yaml",
                    ],
                    check=True,
                )
            else:
                vk_yaml.rename(fr_yaml)

    for config_path in sorted((repo_root / ".devcontainer").glob("*/devcontainer.json")):
        rel = config_path.relative_to(repo_root)
        try:
            rewritten = _rewrite_devcontainer(config_path)
        except json.JSONDecodeError:
            # devcontainer.json permits JSONC; a json round-trip would lose
            # comments anyway — leave the file alone and tell the operator.
            actions.append(f"SKIP {rel}: not strict JSON (JSONC comments?) — migrate by hand")
            continue
        if rewritten is not None:
            actions.append(f"rewrite {rel}: customizations.vk -> .fr, vk secrets mount -> fr")
            if yes:
                config_path.write_text(rewritten)

    vk_state = repo_root / ".git" / "vk" / "isolation"
    fr_state = repo_root / ".git" / "fr" / "isolation"
    if vk_state.is_dir() and any(vk_state.iterdir()):
        actions.append("move .git/vk/isolation/ -> .git/fr/isolation/")
        if yes:
            fr_state.mkdir(parents=True, exist_ok=True)
            for f in vk_state.iterdir():
                shutil.move(str(f), str(fr_state / f.name))
            vk_state.rmdir()

    return actions
