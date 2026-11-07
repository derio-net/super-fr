"""Load a repo's settings from the DEFAULT REF (spec 2026-11-04-repo-feature-settings, R2, R4).

The policy keys are read from the default branch's revision of `.fr/settings.yaml`,
never the working tree: a branch that edits them gets no effect until the edit lands
there, so a branch can never relax its own controls. An edit that has not landed is
reported (`pending_edit`), not applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml
from pydantic import BaseModel

from fr.git import GitRefusal, GitUnavailableError, git_answer, remote_default_ref
from fr.settings import SettingsError
from fr.settings.model import PLACEMENTS, Settings, parse_settings

SETTINGS_PATH: Final = ".fr/settings.yaml"
SERVABLE_PLACEMENTS: Final = frozenset({"repo"})
"""The placements this fr can serve. Quiet and stealth arrive with a later plan (R29)."""


@dataclass(frozen=True)
class EffectiveSettings:
    settings: Settings
    sources: dict[str, str]
    """Dotted key -> `default` or `repo`, for every leaf key."""
    ref: str | None
    ref_note: str
    pending_edit: str | None


_CACHE: dict[tuple[str, str], tuple[Settings, dict[str, str]]] = {}


def _leaf_keys(model: Any, prefix: str = "") -> list[str]:
    keys: list[str] = []
    for name, field in type(model).model_fields.items():
        value = getattr(model, name)
        dotted = f"{prefix}{field.alias or name}"
        if isinstance(value, BaseModel):
            keys.extend(_leaf_keys(value, f"{dotted}."))
        else:
            keys.append(dotted)
    return keys


def _present(data: object, dotted: str) -> bool:
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _show(root: Path, ref: str) -> str | None:
    done = git_answer(root, "show", f"{ref}:{SETTINGS_PATH}")
    return done.stdout if done.returncode == 0 else None


def _resolve_ref(root: Path) -> tuple[str | None, str]:
    """(ref to read, note). `None` when there is nothing to read from."""
    named = remote_default_ref(root)
    if isinstance(named, GitRefusal):
        raise SettingsError(f"cannot establish the default branch: {named.reason}")
    if named is not None:
        return named, f"read from {named}"
    return "HEAD", "no origin default branch: read the committed file at HEAD"


def _pending(root: Path, committed: str | None) -> str | None:
    path = root / SETTINGS_PATH
    try:
        current = path.read_text() if path.is_file() else None
    except OSError:
        return None
    if current == committed:
        return None
    return (
        f"{SETTINGS_PATH} differs from the default branch's revision; the edit has no effect "
        "until it lands there"
    )


def load_settings(repo_root: Path) -> EffectiveSettings:
    """The effective settings of *repo_root*, with per-key provenance.

    Raises `SettingsError` for an unparseable or invalid file and for a placement this
    fr cannot serve — the refusal is the loader's, so every reader gets it.
    """
    root = Path(repo_root)
    try:
        in_repo = git_answer(root, "rev-parse", "--git-dir").returncode == 0
        ref, note = _resolve_ref(root) if in_repo else (None, "")
        sha = None
        if ref is not None:
            done = git_answer(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
            sha = done.stdout.strip() if done.returncode == 0 else None
    except GitUnavailableError:
        ref, note, sha = None, "git unavailable: defaults", None
    if ref is None or sha is None:
        # Not a repo, or no commit yet: nothing is committed, so nothing is set.
        defaults = parse_settings({}, source="defaults")
        return EffectiveSettings(
            defaults,
            dict.fromkeys(_leaf_keys(defaults), "default"),
            None,
            "no commit to read settings from: defaults",
            _pending(root, None),
        )
    text = _show(root, ref)
    pending = _pending(root, text)
    key = (str(root), sha)
    cached = _CACHE.get(key)
    if cached is None:
        data: object = None
        if text is not None:
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError as e:
                raise SettingsError(f"{SETTINGS_PATH}: not valid YAML: {e}") from e
        settings = parse_settings(data, source=SETTINGS_PATH)
        if settings.placement not in SERVABLE_PLACEMENTS:
            assert settings.placement in PLACEMENTS
            raise SettingsError(
                f"{SETTINGS_PATH}: placement: {settings.placement} is not yet available "
                "in this fr (only `repo` is served)"
            )
        sources = {k: ("repo" if _present(data, k) else "default") for k in _leaf_keys(settings)}
        cached = (settings, sources)
        _CACHE[key] = cached
    settings, sources = cached
    return EffectiveSettings(settings, dict(sources), ref, note, pending)
