"""Telling a cloud user how to fix the environment (spec 2026-10-07-cloud-triage R23, §H, d11).

A Claude Code cloud session runs fr in a container its environment's setup script
prepared. When that script is missing a step this design relies on — the REST backend
setting, the registered plugin, a current `fr`, `rsync` — or the repo lacks its `agents`
artifact, fr fails in ways that read like fr bugs. This module names the cause once:

- `detect()` — true only when `CLAUDE_CODE_REMOTE=true` (the harness sets it in every
  shell of a cloud session). No other signal, so a host is never mistaken for the cloud
  and nothing here ever prints on one.
- `check()` — every cloud prerequisite with its state and fix; `fr cloud doctor`.
- `remedy_block(items)` — the one wording every failure appends, `remedy_for(items)` the
  same gated on `detect()`. A failure deep in fr (a GraphQL 403, a newer run cursor)
  does not append it to its own message, which callers join and persist (p7-r3): it
  `note_remedy`s its items, and the CLI boundary prints `take_remedy()` once, after
  fr's own error. `setup_script()` — the template `fr cloud setup-script`
  prints, shipped as wheel data (`fr/data/cloud-setup.sh`), never run by fr.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

CLOUD_ENV = "CLAUDE_CODE_REMOTE"
PLUGIN_ID = "super-fr@derio-net--super-fr"
RELEASE_REPO = "derio-net/super-fr"
SOURCE_URL = f"https://github.com/{RELEASE_REPO}.git"
DOCS_URL = "https://code.claude.com/docs/en/claude-code-on-the-web"

FORGE_API_ITEM = "forge.api: rest"
PLUGIN_ITEM = "the super-fr plugin"
AGENTS_ITEM = "the repo's `agents` artifact"
FR_ITEM = "a current fr"
RSYNC_ITEM = "rsync"

CHECK_NAMES: tuple[str, ...] = ("forge.api", "plugin", "agents", "fr", "rsync")


@dataclass(frozen=True)
class Check:
    """One prerequisite: whether it holds, what fr saw, and how to fix it."""

    name: str
    ok: bool
    detail: str
    fix: str = ""
    item: str = ""
    """The words `remedy_block` lists for this prerequisite when it fails."""


def detect(env: Mapping[str, str] | None = None) -> bool:
    """Is this a Claude Code cloud session? Only `CLAUDE_CODE_REMOTE=true` says so."""
    return (os.environ if env is None else env).get(CLOUD_ENV) == "true"


def remedy_block(items: Sequence[str]) -> str:
    """The fix, worded once for every failure that appends it (§H)."""
    return (
        f"This is a Claude Code cloud session, and its environment is missing: "
        f"{', '.join(items)}.\n"
        "Fix it once for every future session: open the cloud environment menu in the\n"
        "session's title bar → Edit → Setup script, paste the output of\n"
        "`fr cloud setup-script`, and start a new session (new sessions run the script;\n"
        "this one does not). Or create a new environment with that script.\n"
        f"Docs: {DOCS_URL}"
    )


_NOTED: dict[str, None] = {}
"""The cloud items failures noted in this process, in order, for the CLI boundary."""


def note_remedy(items: Sequence[str]) -> tuple[str, ...]:
    """Record *items* for the one block the CLI prints when the command ends; returns
    them in a cloud session and `()` on a host, where nothing is ever noted."""
    if not detect():
        return ()
    for item in items:
        _NOTED.setdefault(item)
    return tuple(items)


def take_remedy() -> str | None:
    """The block for every item noted so far, once: it clears what it returns."""
    if not _NOTED:
        return None
    block = remedy_block(list(_NOTED))
    _NOTED.clear()
    return block


def remedy_for(items: Sequence[str]) -> str:
    """`remedy_block(items)` after a blank line in a cloud session; `""` on a host, so a
    caller appends it to its own error unconditionally."""
    return "\n\n" + remedy_block(items) if detect() else ""


def setup_script(repo: str | None = None) -> str:
    """The cloud environment setup script (§H), filled for `repo` when one is named."""
    text = (resources.files("fr") / "data" / "cloud-setup.sh").read_text(encoding="utf-8")
    return text.replace("{for_repo}", f" for {repo}" if repo else "").replace(
        "{source}", SOURCE_URL
    )


# --------------------------------------------------------------------- the checks


def _home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


def _installed_fr() -> str:
    from fr import __version__

    return __version__


def _latest_release() -> str | None:
    """The latest super-fr release tag through the forge adapter, or `None` when the
    forge cannot say (offline, not logged in): an unknown answer is never a failure."""
    from fr.hostclient import client_for_url

    try:
        return client_for_url(f"https://github.com/{RELEASE_REPO}").latest_release(RELEASE_REPO)
    except Exception:  # noqa: BLE001 - doctor reports "unknown", never crashes on it
        return None


def _version_tuple(text: str) -> tuple[int, ...] | None:
    core = text.strip().lstrip("v").split("+", 1)[0].split("-", 1)[0]
    try:
        return tuple(int(p) for p in core.split("."))
    except ValueError:
        return None


def _check_forge_api() -> Check:
    from fr import forgeapi

    try:
        api = forgeapi.resolve()
    except forgeapi.ForgeApiError as exc:
        api, why = None, str(exc)
    else:
        why = f"forge.api is {api}"
    return Check(
        "forge.api",
        api == "rest",
        why,
        fix=f"write `api: rest` to {forgeapi.config_path()} (the setup script does)",
        item=FORGE_API_ITEM,
    )


def _check_plugin() -> Check:
    path = _home() / ".claude" / "plugins" / "installed_plugins.json"
    fix = "run the setup script: it seeds the file and runs super-fr's install.sh"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Check("plugin", False, f"{path} does not exist", fix, PLUGIN_ITEM)
    except (OSError, ValueError) as exc:
        return Check("plugin", False, f"{path} cannot be read ({exc})", fix, PLUGIN_ITEM)
    plugins = data.get("plugins") if isinstance(data, dict) else None
    ok = isinstance(plugins, dict) and PLUGIN_ID in plugins
    detail = f"{PLUGIN_ID} {'is' if ok else 'is not'} registered in {path}"
    return Check("plugin", ok, detail, fix, PLUGIN_ITEM)


def _check_agents(repo_root: Path | None) -> Check:
    fix = "run `fr init agents` (or `fr migrate artifacts --yes`) and merge the result"
    if repo_root is None:
        return Check("agents", True, "not in a git repository: nothing to check", fix, AGENTS_ITEM)
    from fr.agents import AGENT_NAMES, agent_path
    from fr.artifacts.registry import ARTIFACT_KINDS
    from fr.artifacts.validate import validate_artifact

    kind = ARTIFACT_KINDS["agents"]
    problems: list[str] = []
    for name in AGENT_NAMES:
        path = agent_path(repo_root, name)
        if not path.is_file():
            problems.append(f"{name}.md missing")
            continue
        problems += [f"{name}.md: {i.message}" for i in validate_artifact(kind, path)]
    detail = "; ".join(problems) if problems else f"both agents at version {kind.current_version}"
    return Check("agents", not problems, detail, fix, AGENTS_ITEM)


def _check_fr(installed: str, latest: str | None) -> Check:
    fix = "start a new session (the setup script installs the latest release)"
    if latest is None:
        return Check("fr", True, f"fr {installed} (latest release unknown)", fix, FR_ITEM)
    have, want = _version_tuple(installed), _version_tuple(latest)
    ok = have is None or want is None or have >= want
    return Check("fr", ok, f"fr {installed}, latest release {latest.lstrip('v')}", fix, FR_ITEM)


def _check_rsync(which: Callable[[str], str | None]) -> Check:
    found = which("rsync")
    return Check(
        "rsync",
        found is not None,
        f"rsync at {found}" if found else "rsync is not on PATH",
        "the setup script installs it (`apt-get install -y rsync`)",
        RSYNC_ITEM,
    )


def repo_root_of(cwd: Path | None = None) -> Path | None:
    """The git toplevel of `cwd` (default: the working directory), or `None`."""
    try:
        done = subprocess.run(
            ["git", "-C", str(cwd or Path.cwd()), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    out = done.stdout.strip()
    return Path(out) if done.returncode == 0 and out else None


def check(
    *,
    repo_root: Path | None = None,
    latest_release: Callable[[], str | None] | None = None,
    which: Callable[[str], str | None] | None = None,
    installed: str | None = None,
) -> list[Check]:
    """Every cloud prerequisite, in `CHECK_NAMES` order."""
    return [
        _check_forge_api(),
        _check_plugin(),
        _check_agents(repo_root),
        _check_fr(installed or _installed_fr(), (latest_release or _latest_release)()),
        _check_rsync(which or shutil.which),
    ]


__all__ = [
    "AGENTS_ITEM",
    "CHECK_NAMES",
    "CLOUD_ENV",
    "FORGE_API_ITEM",
    "FR_ITEM",
    "PLUGIN_ID",
    "PLUGIN_ITEM",
    "RSYNC_ITEM",
    "Check",
    "check",
    "detect",
    "note_remedy",
    "remedy_block",
    "remedy_for",
    "repo_root_of",
    "setup_script",
    "take_remedy",
]
