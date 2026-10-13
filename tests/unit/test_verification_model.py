"""`fr.verification.model` — the strategy manifest (spec 2026-10-06 §A, R1/R2)."""

from __future__ import annotations

import pytest
from fr.verification.model import PLACEHOLDERS, RESERVED, StrategyError, parse_strategy


def test_the_verification_package_imports() -> None:
    import fr.verification  # noqa: F401


VALID = """\
verification: candidate
schema: 1
description: install the PR's build into a throwaway prefix
when: pre-merge
driver: agent
install: .fr/candidate-install {prefix} {worktree}
scenario: "{scenario}"
source: worktree
notes: nothing else
"""


def test_a_valid_manifest_parses() -> None:
    m = parse_strategy(VALID, source="candidate.yaml")

    assert m.verification == "candidate"
    assert m.schema_version == 1
    assert m.when == "pre-merge"
    assert m.driver == "agent"
    assert m.install == (".fr/candidate-install", "{prefix}", "{worktree}")
    assert m.scenario == ("{scenario}",)
    assert m.source == "worktree"
    assert m.notes == "nothing else"


def test_install_and_scenario_may_be_null_or_a_list() -> None:
    m = parse_strategy(
        "verification: live\nschema: 1\nwhen: post-merge\ndriver: operator\n"
        "install: null\nscenario: [run, '{scenario}']\n",
        source="live.yaml",
    )

    assert m.install is None
    assert m.scenario == ("run", "{scenario}")
    assert m.source == "none"


def test_the_placeholder_set_is_closed() -> None:
    assert PLACEHOLDERS == {
        "repo", "worktree", "prefix", "bin", "fixture", "client", "scenario", "source",
    }  # fmt: skip
    assert RESERVED == "none"


@pytest.mark.parametrize(
    ("patch", "field"),
    [
        ("extra: 1\n", "extra"),
        ("when: later\n", "when"),
        ("driver: robot\n", "driver"),
        ("install: do {nonsense}\n", "install"),
        ("scenario: run {nope}\n", "scenario"),
        ("schema: 3\n", "schema"),
    ],
)
def test_a_bad_manifest_is_refused_naming_the_field(patch: str, field: str) -> None:
    key = patch.split(":")[0]
    base = "\n".join(line for line in VALID.splitlines() if not line.startswith(key + ":"))
    with pytest.raises(StrategyError, match=field):
        parse_strategy(base + "\n" + patch, source="x.yaml")


def test_the_reserved_name_none_is_refused() -> None:
    with pytest.raises(StrategyError, match="none"):
        parse_strategy(VALID.replace("verification: candidate", "verification: none"), source="x")


def test_a_non_mapping_or_invalid_yaml_is_a_strategy_error() -> None:
    with pytest.raises(StrategyError):
        parse_strategy("- a\n- b\n", source="x")
    with pytest.raises(StrategyError):
        parse_strategy("a: [", source="x")


def test_the_error_names_its_source() -> None:
    with pytest.raises(StrategyError, match="somewhere/x.yaml"):
        parse_strategy("when: later\n", source="somewhere/x.yaml")


def test_a_schema_1_manifest_with_a_gate_is_refused_naming_schema_2() -> None:
    with pytest.raises(StrategyError, match="schema: 2"):
        parse_strategy(VALID + "gate: tester\n", source="x.yaml")


def test_a_schema_2_manifest_with_a_gate_parses() -> None:
    m = parse_strategy(VALID.replace("schema: 1", "schema: 2") + "gate: tester\n", source="x")

    assert m.schema_version == 2
    assert m.gate == "tester"


def test_an_absent_gate_reads_none_and_a_schema_2_gate_is_closed() -> None:
    assert parse_strategy(VALID, source="x").gate == "none"
    with pytest.raises(StrategyError, match="gate"):
        parse_strategy(VALID.replace("schema: 1", "schema: 2") + "gate: owner\n", source="x")


def test_the_shipped_gates() -> None:
    from fr.verification.resolve import resolve_strategy

    assert resolve_strategy("live", None).gate == "tester"
    for name in ("candidate", "client-live", "prerelease"):
        assert resolve_strategy(name, None).gate == "none", name
