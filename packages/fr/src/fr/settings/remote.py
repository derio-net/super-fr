"""A repo's forge policy, wherever fr stands (spec 2026-11-04-repo-feature-settings, R9).

From the repo's own checkout the policy is `fr.settings.load_settings` (the default ref's
revision) plus the checkout's tracking declaration. A command acting on a repo it has no
checkout of (`--repo`, a triage scope, the bridge's spec fan-out) reads that repo's
`.fr/settings.yaml` at its default branch through the forge client's contents read
(`GhClient.read_file`): absent means the defaults; any other failure raises
`SettingsError`, so the write it would have decided is refused. Policy is never assumed.

The remote read sees the settings file only: a repo's `tracking: none` lives in its
`.devcontainer/fr-profiles.yaml`, which only a checkout carries.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from fr.settings import SettingsError, setting_block
from fr.settings.model import Forge

REMOTE_TTL_SECONDS: Final = 300.0
"""How long `client_policy` keeps a remote answer: a long-running driver sees a changed
setting within minutes, and one pass never reads the same repo's file twice."""


@dataclass(frozen=True)
class RepoPolicy:
    """One repo's forge policy: its `forge` settings and whether it declares no tracker."""

    forge: Forge
    tracking_none: bool = False

    def block(self, kind: str) -> str | None:
        """A tracker write of *kind*: the setting, then `tracking: none` (R9)."""
        from fr.settings import TRACKING_NONE

        why = setting_block(self.forge, kind)
        if why is not None:
            return why
        return TRACKING_NONE if self.tracking_none else None

    def allows(self, kind: str) -> bool:
        return self.block(kind) is None

    def ledger_block(self, kind: str) -> str | None:
        """The PR gate ledger's one rule: only the setting decides (`fr.settings.ledger_block`)."""
        from fr.settings import LEDGER_KINDS

        if kind not in LEDGER_KINDS:
            raise ValueError(f"{kind!r} is not a gate-ledger kind; kinds are {LEDGER_KINDS}")
        return setting_block(self.forge, kind)

    def first_block(self, *kinds: str) -> str | None:
        """The first of *kinds* (tracker writes) the policy forbids, else None."""
        return next((why for k in kinds if (why := self.block(k)) is not None), None)


def local_policy(repo_root: Path, *, lenient: bool = True) -> RepoPolicy:
    """The policy of the checkout at *repo_root* (`SettingsError` when unreadable)."""
    from fr.settings import load_settings, tracking_none

    forge = load_settings(repo_root).settings.forge
    return RepoPolicy(forge, tracking_none(repo_root, lenient=lenient))


def _not_found(exc: BaseException) -> bool:
    text = f"{exc} {getattr(exc, 'stderr', '')}".lower()
    return "404" in text or "not found" in text


def remote_settings_text(client: Any, repo: str) -> str | None:
    """*repo*'s `.fr/settings.yaml` at its default branch, None when it has none."""
    from fr.settings.load import SETTINGS_PATH

    try:
        return str(client.read_file(repo, SETTINGS_PATH))
    except Exception as exc:  # noqa: BLE001 — every backend's error; only a 404 is "absent"
        if _not_found(exc):
            return None
        raise SettingsError(
            f"{repo}: cannot read {SETTINGS_PATH} at its default branch through the forge, so "
            f"its policy is unknown and nothing was written: {exc}"
        ) from exc


def remote_policy(client: Any, repo: str) -> RepoPolicy:
    """*repo*'s policy read through *client* (R9): absent is the defaults, a failed or
    invalid read raises `SettingsError`."""
    from fr.settings.load import SETTINGS_PATH, parse_settings_text

    text = remote_settings_text(client, repo)
    settings = parse_settings_text(text, source=f"{repo}:{SETTINGS_PATH}")
    return RepoPolicy(settings.forge)


_CLIENT_CACHE: dict[tuple[int, str], tuple[object, RepoPolicy, float]] = {}


def client_policy(client: Any, repo: str) -> RepoPolicy:
    """`remote_policy`, kept per (client, repo) for `REMOTE_TTL_SECONDS`: the one reader
    of the modules that hold a client and no checkout (claim writes, the bridge's
    stamp). The client is held with its answer, so its identity is never reused."""
    key = (id(client), repo.lower())
    now = time.monotonic()
    hit = _CLIENT_CACHE.get(key)
    if hit is not None and hit[0] is client and now - hit[2] < REMOTE_TTL_SECONDS:
        return hit[1]
    policy = remote_policy(client, repo)
    _CLIENT_CACHE[key] = (client, policy, now)
    return policy


def clear_client_cache() -> None:
    _CLIENT_CACHE.clear()


@dataclass
class PolicyReader:
    """Policies of the repos one command or pass writes to, each read once: from the
    repo's checkout when *checkout_of* names one, else through *client_for*'s forge."""

    client_for: Callable[[str], Any]
    checkout_of: Callable[[str], Path | None] = lambda repo: None
    _seen: dict[str, RepoPolicy] = field(default_factory=dict)

    def policy(self, repo: str) -> RepoPolicy:
        key = repo.lower()
        if key not in self._seen:
            path = self.checkout_of(repo)
            self._seen[key] = (
                local_policy(path)
                if path is not None
                else remote_policy(self.client_for(repo), repo)
            )
        return self._seen[key]


__all__ = [
    "REMOTE_TTL_SECONDS",
    "PolicyReader",
    "RepoPolicy",
    "clear_client_cache",
    "client_policy",
    "local_policy",
    "remote_policy",
    "remote_settings_text",
]
