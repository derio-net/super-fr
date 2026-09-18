"""Observation — what the registration files ACTUALLY wire, per harness.

2026-09-18 harness-parity-matrix spec §3.B, Phase 2.

This module never reads `parity.yaml`. That independence is the whole
point: the check is *derived*, not transcribed, so a declared cell cannot
agree with itself. `observe()` answers exactly one question per (script,
harness) pair — is this shipped hook script registered there, yes or no —
and nothing more, because registration is all a file can tell you. How
much of a surface a registered hook actually covers is a human judgement
and lives in `parity.yaml`'s `state`/`scope_note` (which is why the
`partial`/`advisory` rules in `check.py` are the weaker ones they are).

Keys are shipped SCRIPT FILENAMES (`fr-isolation-required.sh`), not
surface ids: an observer that had to know surface ids would have to read
the matrix, and then the two could no longer disagree. `check.py` bridges
the two through each hook row's `script` field.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from fr.harness.model import HARNESSES, HarnessError
from fr.hermes import SNIPPET_RELPATH, HermesError, snippet_entries

Observation = Literal["present", "absent"]

HOOKS_RELPATH = Path("plugins/super-fr/hooks")
HOOKS_JSON_RELPATH = HOOKS_RELPATH / "hooks.json"
OPENCODE_SRC_RELPATH = Path("packages/fr-opencode-plugin/src")

MARKER_PREFIX = "// super-fr-parity:"
"""OpenCode's declaration. See `_observe_opencode`."""


def is_super_fr_checkout(repo_root: Path) -> bool:
    """True when `repo_root` carries the registration files `observe` needs.

    `fr harness parity --check` uses this to decline rather than invent a
    verdict outside a checkout (spec §3.F, the `fr acceptance check`
    precedent)."""
    return (repo_root / HOOKS_JSON_RELPATH).is_file()


def shipped_scripts(repo_root: Path) -> frozenset[str]:
    """Every shipped hook script — `plugins/super-fr/hooks/*.sh`.

    Non-recursive on purpose: `hooks/hermes/*.sh` are per-harness PORTS of
    these same surfaces, not surfaces of their own, and the snippet's
    `hermes/x.sh` command resolves to the same basename."""
    hooks = repo_root / HOOKS_RELPATH
    if not hooks.is_dir():
        return frozenset()
    return frozenset(p.name for p in hooks.glob("*.sh"))


def _read_claude_code(repo_root: Path, shipped: frozenset[str]) -> set[str]:
    """`hooks.json`: every event's `hooks[].command`, by basename.

    Basename rather than stripping the `${CLAUDE_PLUGIN_ROOT}/hooks/`
    prefix literally — the prefix is an installer detail that has moved
    before, and the script's own filename is the identity the matrix keys
    on."""
    path = repo_root / HOOKS_JSON_RELPATH
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(f"cannot read {HOOKS_JSON_RELPATH}: {exc}") from exc
    found: set[str] = set()
    hooks = data.get("hooks") if isinstance(data, dict) else None
    for groups in (hooks or {}).values():
        for group in groups or []:
            for hook in (group or {}).get("hooks") or []:
                command = hook.get("command")
                if isinstance(command, str) and command:
                    found.add(PurePosixPath(command).name)
    return found


def _read_hermes(repo_root: Path, shipped: frozenset[str]) -> set[str]:
    """`.hermes/config.snippet.yaml`, through `fr.hermes.snippet_entries`.

    Reusing the installer's own parser rather than walking that YAML a
    second time (spec §3.B) — two parsers of one file is two chances to
    disagree about what it says, and the installer's is the one whose
    reading actually takes effect."""
    if not (repo_root / SNIPPET_RELPATH).is_file():
        return set()
    try:
        entries = snippet_entries(repo_root, repo_root / HOOKS_RELPATH)
    except HermesError as exc:
        raise HarnessError(f"cannot read {SNIPPET_RELPATH}: {exc}") from exc
    return {Path(str(entry["command"])).name for entry in entries}


def _read_opencode(repo_root: Path, shipped: frozenset[str]) -> set[str]:
    """`packages/fr-opencode-plugin/src/*.ts`, by marker comment.

    Deliberately shallow (spec §3.B): a script is observed present iff the
    plugin source names it in a `// super-fr-parity: <script>` comment. The
    marker IS the declaration — grepping TypeScript for *behaviour* would
    be a second parser to maintain, and one that would quietly rot into
    disagreement with the code it claims to read.

    The one thing this does verify is that a marker names a script that
    exists: a typo must not read as `absent`, because a false `absent` in
    an agreeing matrix is a clean bill of health nobody earned."""
    src = repo_root / OPENCODE_SRC_RELPATH
    if not src.is_dir():
        return set()
    found: set[str] = set()
    for source in sorted(src.glob("*.ts")):
        for line in source.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.startswith(MARKER_PREFIX):
                continue
            script = stripped[len(MARKER_PREFIX) :].strip()
            if script not in shipped:
                raise HarnessError(
                    f"{source.relative_to(repo_root)}: `{MARKER_PREFIX} {script}` names a "
                    f"script that does not exist under {HOOKS_RELPATH}/"
                )
            found.add(script)
    return found


@dataclass(frozen=True)
class _Observer:
    """One harness's registration surface: where it is, and how to read it.

    The dispatch table below is the SINGLE place a harness's observability
    is declared — `OBSERVABLE_HARNESSES` and `REGISTRATION_FILES` are both
    derived from it. Supporting `codex` is then one entry here plus its
    reader, not an entry plus two lists plus a branch, which is how the
    three drift apart."""

    harness: str
    registration_file: str
    """Repo-relative; named in every finding, so the message says which file
    to go and edit."""
    read: Callable[[Path, frozenset[str]], set[str]]
    """`(repo_root, shipped scripts) -> the script names this harness
    registers`. Returns an empty set when the file is simply not there;
    raises `HarnessError` when it is there and cannot be trusted."""


_OBSERVERS: tuple[_Observer, ...] = (
    _Observer("claude-code", str(HOOKS_JSON_RELPATH), _read_claude_code),
    _Observer("opencode", str(OPENCODE_SRC_RELPATH / "index.ts"), _read_opencode),
    _Observer("hermes", str(SNIPPET_RELPATH), _read_hermes),
)

for _observer in _OBSERVERS:
    # The harness names here must be from the same closed set `parity.yaml`
    # validates against, or a typo would produce an observation for a column
    # that does not exist and `check` would never compare it to anything.
    if _observer.harness not in HARNESSES:
        raise HarnessError(f"unknown harness in the observer table: {_observer.harness!r}")

OBSERVABLE_HARNESSES: tuple[str, ...] = tuple(o.harness for o in _OBSERVERS)
"""The harnesses that have a registration file to read — derived from the
table above, never listed twice. `codex` and `copilot-cli` register nothing
anywhere, so there is nothing to observe about them: `check` must never
infer `absent` from silence and report a finding on a row it cannot
actually verify."""

REGISTRATION_FILES: dict[str, str] = {o.harness: o.registration_file for o in _OBSERVERS}
"""The file an operator edits to change what a harness registers — named in
every finding `check.py` emits."""


def observe(repo_root: Path) -> dict[str, dict[str, Observation]]:
    """`{script filename: {harness: "present" | "absent"}}`.

    Covers every shipped script plus anything a registration file names
    that is not shipped (which `check` will not see, but which is worth
    not hiding). Raises `HarnessError` on a registration file that exists
    but cannot be read — an unreadable file is unknown state, and unknown
    state is never "absent"."""
    shipped = shipped_scripts(repo_root)
    registered = {o.harness: o.read(repo_root, shipped) for o in _OBSERVERS}
    scripts = set(shipped).union(*registered.values())
    return {
        script: {
            harness: ("present" if script in registered[harness] else "absent")
            for harness in OBSERVABLE_HARNESSES
        }
        for script in sorted(scripts)
    }


__all__ = [
    "OBSERVABLE_HARNESSES",
    "REGISTRATION_FILES",
    "Observation",
    "is_super_fr_checkout",
    "observe",
    "shipped_scripts",
]
