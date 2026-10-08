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
