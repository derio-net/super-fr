"""`.fr/triage.yaml`'s `exit:` block (spec 2026-10-14 exit-gates R4)."""

from __future__ import annotations

import pytest
from fr.triage.model import TriageConfig, parse_triage_config
from pydantic import ValidationError


def test_the_default_config_has_no_exit_block() -> None:
    assert TriageConfig().exit is None


def test_a_gate_remap_parses() -> None:
    config, ignored = parse_triage_config({"exit": {"gates": {"candidate": "tester"}}})

    assert ignored == ()
    assert config.exit is not None
    assert config.exit.gates == {"candidate": "tester"}


@pytest.mark.parametrize("gate", ["wizard", "none-ish", ""])
def test_an_unknown_gate_is_refused(gate: str) -> None:
    with pytest.raises(ValidationError):
        parse_triage_config({"exit": {"gates": {"candidate": gate}}})


def test_an_unknown_key_inside_exit_is_refused() -> None:
    with pytest.raises(ValidationError):
        parse_triage_config({"exit": {"nope": 1}})
