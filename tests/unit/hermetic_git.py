"""The hermetic-git environment shared by the tests that run real git (spec 2026-11-27 R5).

No operator git config, global or system. Opt in per module with
`pytestmark = pytest.mark.usefixtures("hermetic_git")`; the fixture is not autouse.
"""

from __future__ import annotations

import os

import pytest


def apply_hermetic_git(mp: pytest.MonkeyPatch) -> None:
    """Point git's global config at the null device and ignore the system config."""
    mp.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    mp.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    apply_hermetic_git(monkeypatch)
