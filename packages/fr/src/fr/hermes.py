"""Hermes Agent install/uninstall core — the invasive, reversible mutations.

install.sh is jq-only and cannot safely merge into the user's YAML
`cli-config.yaml`, so the risky Hermes install steps live here as tested Python
(reusing the workspace `yaml` dep), invoked by install.sh's Hermes path:

- merge/strip super-fr's `hooks:` registrations in `~/.hermes/cli-config.yaml`
  (idempotent, keyed by event+command; unrelated keys preserved),
- add/remove `~/.hermes/shell-hooks-allowlist.json` approvals so non-TTY
  registration succeeds without a prompt,
- apply/strip the delimited super-fr managed block in `~/.hermes/SOUL.md`
  (content outside the markers is never touched),
- copy the shipped hook tree into `~/.hermes/super-fr-hooks/` (preserving the
  `hermes/` + `lib/` layout the guards' `../lib` sourcing depends on).

Every mutation is idempotent and fully reversed by `uninstall`. NOTE: PyYAML
does not preserve comments in `cli-config.yaml`; the managed block is confined
to the `hooks:` key, but surrounding comments in that file are not round-tripped.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import yaml

SOUL_BLOCK_START = "<!-- super-fr:rules START -->"
SOUL_BLOCK_END = "<!-- super-fr:rules END -->"
HOOKS_SUBDIR = "super-fr-hooks"
ALLOWLIST_FILENAME = "shell-hooks-allowlist.json"
CONFIG_FILENAME = "cli-config.yaml"
SOUL_FILENAME = "SOUL.md"
SNIPPET_RELPATH = Path(".hermes") / "cli-config.snippet.yaml"
SOUL_BLOCK_RELPATH = Path(".hermes") / "SOUL.d" / "super-fr-rules.md"
HOOKS_RELPATH = Path("plugins") / "super-fr" / "hooks"


class HermesError(Exception):
    """Raised when a Hermes install/uninstall precondition fails."""


def hermes_home() -> Path:
    """The Hermes home dir: $HERMES_HOME, else ~/.hermes."""
    env = os.environ.get("HERMES_HOME")
    return Path(env) if env else Path.home() / ".hermes"


# ---------------------------------------------------------------------------
# hooks: block in cli-config.yaml


def snippet_entries(source_root: Path, hooks_install_dir: Path) -> list[dict[str, Any]]:
    """Parse the shipped snippet into {event, matcher, command} with the command
    rewritten to an absolute path under the installed hooks dir."""
    snippet_path = source_root / SNIPPET_RELPATH
    data = yaml.safe_load(snippet_path.read_text()) or {}
    out: list[dict[str, Any]] = []
    for event, entries in (data.get("hooks") or {}).items():
        for entry in entries or []:
            out.append(
                {
                    "event": str(event),
                    "matcher": entry.get("matcher"),
                    "command": str(hooks_install_dir / entry["command"]),
                }
            )
    return out


def _load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    loaded = yaml.safe_load(config_path.read_text())
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise HermesError(
            f"{config_path} is not a YAML mapping — refusing to touch it. "
            "Fix or move it, then re-run `fr hermes install`."
        )
    return loaded


def _dump_config(config_path: Path, cfg: dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False))


def merge_hooks(config_path: Path, entries: list[dict[str, Any]]) -> None:
    """Idempotently add super-fr's hook entries to the config's hooks: block."""
    cfg = _load_config(config_path)
    hooks = cfg.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise HermesError(f"{config_path}: `hooks` must be a mapping of event -> list")
    for e in entries:
        lst = hooks.setdefault(e["event"], [])
        item: dict[str, str] = {"command": e["command"]}
        if e.get("matcher"):
            item["matcher"] = e["matcher"]
        existing = next(
            (x for x in lst if isinstance(x, dict) and x.get("command") == e["command"]),
            None,
        )
        if existing is None:
            lst.append(item)
        else:
            existing.update(item)  # converge matcher/timeout on our value
    _dump_config(config_path, cfg)


def unmerge_hooks(config_path: Path, entries: list[dict[str, Any]]) -> None:
    """Remove exactly the super-fr hook entries (by command); leave the rest."""
    if not config_path.exists():
        return
    cfg = _load_config(config_path)
    hooks = cfg.get("hooks")
    if not isinstance(hooks, dict):
        return
    ours = {e["command"] for e in entries}
    for event in list(hooks):
        lst = hooks[event]
        if not isinstance(lst, list):
            continue
        hooks[event] = [
            x for x in lst if not (isinstance(x, dict) and x.get("command") in ours)
        ]
        if not hooks[event]:
            del hooks[event]
    if not hooks:
        cfg.pop("hooks", None)
    _dump_config(config_path, cfg)


# ---------------------------------------------------------------------------
# shell-hooks-allowlist.json


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text() or "{}")
    return loaded if isinstance(loaded, dict) else {}


def _dump_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def add_allowlist(path: Path, pairs: list[tuple[str, str]]) -> None:
    data = _load_json(path)
    approvals = data.setdefault("approvals", [])
    for event, command in pairs:
        if not any(
            isinstance(a, dict)
            and a.get("event") == event
            and a.get("command") == command
            for a in approvals
        ):
            approvals.append({"event": event, "command": command})
    _dump_json(path, data)


def remove_allowlist(path: Path, pairs: list[tuple[str, str]]) -> None:
    if not path.exists():
        return
    data = _load_json(path)
    ours = set(pairs)
    data["approvals"] = [
        a
        for a in data.get("approvals", [])
        if not (isinstance(a, dict) and (a.get("event"), a.get("command")) in ours)
    ]
    _dump_json(path, data)


# ---------------------------------------------------------------------------
# SOUL.md managed block


def _split_managed(text: str) -> tuple[str, str]:
    """(before, after) with the managed block removed; (text, '') if absent."""
    start = text.find(SOUL_BLOCK_START)
    if start == -1:
        return text, ""
    end = text.find(SOUL_BLOCK_END, start)
    if end == -1:
        return text[:start], ""  # malformed: drop the dangling start onward
    return text[:start], text[end + len(SOUL_BLOCK_END) :]


def _user_content(text: str) -> str:
    before, after = _split_managed(text)
    if before.strip() and after.strip():
        return before.rstrip("\n") + "\n\n" + after.strip("\n")
    return (before + after).strip("\n")


def apply_soul_block(soul_path: Path, block_text: str) -> None:
    """Apply/replace the super-fr managed block; preserve all other content."""
    block = block_text.strip("\n") + "\n"
    existing = soul_path.read_text() if soul_path.exists() else ""
    user = _user_content(existing)
    soul_path.parent.mkdir(parents=True, exist_ok=True)
    soul_path.write_text(f"{user}\n\n{block}" if user else block)


def strip_soul_block(soul_path: Path) -> None:
    """Remove the super-fr managed block; preserve all other content."""
    if not soul_path.exists():
        return
    user = _user_content(soul_path.read_text())
    soul_path.write_text(f"{user}\n" if user else "")


# ---------------------------------------------------------------------------
# orchestration


def install(source_root: Path, home: Path) -> None:
    """Copy the hook tree, merge hooks, allowlist them, and apply the SOUL block."""
    hooks_install_dir = home / HOOKS_SUBDIR
    src_hooks = source_root / HOOKS_RELPATH
    if not src_hooks.is_dir():
        raise HermesError(f"shipped hooks not found at {src_hooks}")
    shutil.copytree(src_hooks, hooks_install_dir, dirs_exist_ok=True)

    entries = snippet_entries(source_root, hooks_install_dir)
    merge_hooks(home / CONFIG_FILENAME, entries)
    add_allowlist(home / ALLOWLIST_FILENAME, [(e["event"], e["command"]) for e in entries])

    block = (source_root / SOUL_BLOCK_RELPATH).read_text()
    apply_soul_block(home / SOUL_FILENAME, block)


def uninstall(source_root: Path, home: Path) -> None:
    """Reverse install: strip hooks, allowlist, SOUL block, and the hook tree."""
    hooks_install_dir = home / HOOKS_SUBDIR
    entries = snippet_entries(source_root, hooks_install_dir)
    unmerge_hooks(home / CONFIG_FILENAME, entries)
    remove_allowlist(home / ALLOWLIST_FILENAME, [(e["event"], e["command"]) for e in entries])
    strip_soul_block(home / SOUL_FILENAME)
    if hooks_install_dir.is_dir():
        shutil.rmtree(hooks_install_dir)
