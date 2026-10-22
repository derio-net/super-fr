"""Identities a check runs as (spec 2026-10-22-fr-ops R5).

`.fr/ops.yaml` names each identity's environment as references
(`{from: '<cmd>'}`); each is read live, at check time, and never inlined,
logged or recorded. A reference that cannot be read raises `IdentityError`,
which the engine reports as CANNOT-VERIFY naming the identity — never with the
command's output, which may hold the very value it failed to produce.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from fr.ops.load import OpsConfig
from fr.ops.probe import TIMED_OUT, run_probe


class IdentityError(Exception):
    """An identity is unknown, or one of its references could not be read."""


class IdentityResolver(Protocol):
    def __call__(self, name: str) -> Mapping[str, str]: ...


class LiveIdentities:
    """Resolves an identity's env by running each `from` command, through
    `fr.ops.probe.run_probe` (minimal env, stdin closed, bounded). Each identity is
    resolved once per invocation (memoised), so two ops run as one identity read
    its references once."""

    def __init__(self, config: OpsConfig, repo_root: Path, *, timeout: float | None = None) -> None:
        self.config = config
        self.repo_root = repo_root
        self.timeout = timeout if timeout is not None else config.timeout_seconds
        self._resolved: dict[str, Mapping[str, str]] = {}

    def __call__(self, name: str) -> Mapping[str, str]:
        if name not in self._resolved:
            self._resolved[name] = self._resolve(name)
        return self._resolved[name]

    def _resolve(self, name: str) -> Mapping[str, str]:
        identity = self.config.identities.get(name)
        if identity is None:
            raise IdentityError(f"identity {name!r} is not declared in .fr/ops.yaml")
        env: dict[str, str] = {}
        for var, ref in identity.env.items():
            rc, out = run_probe(
                ref.from_,
                self.repo_root,
                passthrough=self.config.env_passthrough,
                timeout=self.timeout,
            )
            if rc == TIMED_OUT:
                raise IdentityError(f"identity {name!r}: {var} could not be read (timed out)")
            value = out.rstrip("\n")
            if rc != 0 or not value:
                raise IdentityError(f"identity {name!r}: {var} could not be read (exit {rc})")
            env[var] = value
        return env
