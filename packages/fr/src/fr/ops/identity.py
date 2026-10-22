"""Identities a check runs as (spec 2026-10-22-fr-ops R5).

`.fr/ops.yaml` names each identity's environment as references
(`{from: '<cmd>'}`); each is read live, at check time, and never inlined,
logged or recorded. A reference that cannot be read raises `IdentityError`,
which the engine reports as CANNOT-VERIFY naming the identity — never with the
command's output, which may hold the very value it failed to produce.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from fr.ops.load import OpsConfig


class IdentityError(Exception):
    """An identity is unknown, or one of its references could not be read."""


class IdentityResolver(Protocol):
    def __call__(self, name: str) -> Mapping[str, str]: ...


class LiveIdentities:
    """Resolves an identity's env by running each `from` command now."""

    def __init__(self, config: OpsConfig, repo_root: Path) -> None:
        self.config = config
        self.repo_root = repo_root

    def __call__(self, name: str) -> Mapping[str, str]:
        identity = self.config.identities.get(name)
        if identity is None:
            raise IdentityError(f"identity {name!r} is not declared in .fr/ops.yaml")
        env: dict[str, str] = {}
        for var, ref in identity.env.items():
            try:
                done = subprocess.run(
                    ["bash", "-euo", "pipefail", "-c", ref.from_],
                    cwd=self.repo_root,
                    env=dict(os.environ),
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                raise IdentityError(f"identity {name!r}: {var} could not be read") from None
            value = done.stdout.rstrip("\n")
            if done.returncode != 0 or not value:
                raise IdentityError(
                    f"identity {name!r}: {var} could not be read (exit {done.returncode})"
                )
            env[var] = value
        return env
