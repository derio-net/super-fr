"""No test writes the operator's own fr config or cache (review p3-r6).

`tests/conftest.py`'s autouse `_home_off_the_operators_machine` points `HOME` (and so
every fr config and cache root: `~/.config/fr/forge.yaml`, `~/.config/fr/host-id`,
`~/.cache/fr/triage/`) at a per-test tmp dir. Before it existed, a test that restored a
state ref (`apply_durable` -> `forgeapi.write_default`) wrote the operator's real
`~/.config/fr/forge.yaml`. These tests fail if any of those paths resolves under, or
writes to, the home the suite started with.
"""

from __future__ import annotations

from pathlib import Path

from fr import forgeapi
from fr.triage.model import Scope, legacy_state_dir
from fr.triage.scope_config import host_id_path

from tests.conftest import OPERATOR_HOME


def _snapshot(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def test_fr_config_and_cache_roots_are_not_the_operators() -> None:
    for path in (
        forgeapi.config_path(),
        host_id_path(),
        legacy_state_dir(Scope(kind="repo", target="o/r")),
        Path.home(),
    ):
        assert not path.is_relative_to(OPERATOR_HOME), path


def test_writing_the_forge_default_never_touches_the_operators_file() -> None:
    real = OPERATOR_HOME / ".config" / "fr" / "forge.yaml"
    before = _snapshot(real)

    assert forgeapi.write_default("rest") is True

    assert _snapshot(real) == before
    assert forgeapi.config_path().read_text() == "api: rest\n"


def test_each_test_gets_a_fresh_home() -> None:
    """Run twice in one session (here and above), the write above must not leak here."""
    assert not forgeapi.config_path().exists()


def test_a_global_git_config_write_never_reaches_the_operators_file() -> None:
    """p4-o1: the sandboxed home's own `.gitconfig` is git's global config, holding only
    the operator's identity read once at session start; the real file is never lent, so
    a test's `git config --global` leaves it byte-identical."""
    import os
    import subprocess

    from tests.conftest import OPERATOR_GIT_IDENTITY, OPERATOR_GITCONFIG

    before = _snapshot(OPERATOR_GITCONFIG)
    own = Path.home() / ".gitconfig"
    assert os.environ["GIT_CONFIG_GLOBAL"] == str(own)

    subprocess.run(["git", "config", "--global", "sandbox.probe", "written"], check=True)

    assert _snapshot(OPERATOR_GITCONFIG) == before
    assert "sandbox.probe" not in (before or b"").decode(errors="replace")
    assert "written" in own.read_text()
    for key, value in OPERATOR_GIT_IDENTITY.items():
        got = subprocess.run(
            ["git", "config", "--global", "--get", key], capture_output=True, text=True
        )
        assert got.stdout.strip() == value
