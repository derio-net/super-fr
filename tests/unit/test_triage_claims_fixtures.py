"""The triage-claims scenario fixtures are the generator's output, byte for byte."""

from __future__ import annotations

import importlib.util

from tests.conftest import REPO_ROOT

FIXTURES = REPO_ROOT / "tests" / "scenarios" / "fixtures"


def test_the_committed_claim_fixtures_match_their_generator() -> None:
    spec = importlib.util.spec_from_file_location(
        "make_claims_facts", FIXTURES / "make_claims_facts.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, facts in module.FIXTURES.items():
        assert (FIXTURES / name).read_text(encoding="utf-8") == module.render(facts), name


def test_the_committed_config_skew_fixture_matches_its_generator() -> None:
    spec = importlib.util.spec_from_file_location(
        "make_config_skew_facts", FIXTURES / "make_config_skew_facts.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    name = "config-skew-facts.json"
    assert (FIXTURES / name).read_text(encoding="utf-8") == module.render(module.facts())


def test_the_committed_cancelled_terminal_fixture_matches_its_generator() -> None:
    spec = importlib.util.spec_from_file_location(
        "make_cancelled_terminal_facts", FIXTURES / "make_cancelled_terminal_facts.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    name = "cancelled-terminal-facts.json"
    assert (FIXTURES / name).read_text(encoding="utf-8") == module.render(module.facts())
