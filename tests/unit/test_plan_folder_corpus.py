"""Round-trip test for the parity fixtures corpus (cnc-fr spec §3.3).

`tests/fixtures/plan_folders/` is the cross-language contract: the
umbrella repo vendors it and cncd's Go parser must produce the same
accept/reject verdicts (golden tests keyed on `manifest.yaml` codes).
This test keeps the Python side honest:

  - every `valid/` fixture parses under `fr.parser.parse_strict`,
  - every `invalid/` fixture raises `PlanSchemaError` whose message
    matches the manifest's `match` substring,
  - the manifest and the on-disk corpus cover each other exactly, so a
    fixture can't silently drop out of the contract.

The legacy `tests/fixtures/plans/*.md` Markdown-AST fixtures are a
different corpus (v1) and are not part of this contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "plan_folders"
MANIFEST = yaml.safe_load((CORPUS / "manifest.yaml").read_text())

VALID: list[str] = MANIFEST["valid"]
INVALID: dict[str, dict[str, str]] = MANIFEST["invalid"]


def _dirs(sub: str) -> set[str]:
    root = CORPUS / sub
    return {p.name for p in root.iterdir() if p.is_dir()}


def test_manifest_covers_the_corpus_exactly():
    assert MANIFEST["schema_version"] == 2
    assert set(VALID) == _dirs("valid")
    assert set(INVALID) == _dirs("invalid")


def test_invalid_codes_are_unique_and_stable_tokens():
    codes = [entry["code"] for entry in INVALID.values()]
    assert len(codes) == len(set(codes)), "duplicate error codes in manifest"
    assert all(c.replace("_", "").isalnum() and c == c.lower() for c in codes)


@pytest.mark.parametrize("name", VALID)
def test_valid_fixture_parses_strict(name: str):
    from fr.parser import parse_strict

    plan = parse_strict(CORPUS / "valid" / name)
    assert plan.prose is not None
    numbers = [p.phase.number for p in plan.phases]
    assert numbers == list(range(1, len(numbers) + 1))


def test_full_featured_round_trips_the_optional_fields():
    """The rich fixture must actually exercise the surface it claims to."""
    from fr.parser import parse_strict

    plan = parse_strict(CORPUS / "valid" / "full-featured")
    m = plan.meta
    assert m.spec is not None and ":" in m.spec  # cross-repo form
    assert m.vk_version is not None  # inert legacy field retained
    assert m.parent_plan and m.prior_rework
    assert [o.id for o in m.origin_items] == [1, 2]
    tags = [p.phase.tag for p in plan.phases]
    assert tags == ["agentic", "agentic", "manual"]
    p1 = plan.phases[0]
    assert p1.state.completion.at is not None
    assert p1.state.completion.observed_prs
    p2_states = {s.state for s in plan.phases[1].state.steps.values()}
    assert p2_states == {"x", "-", " "}


@pytest.mark.parametrize("name", sorted(INVALID))
def test_invalid_fixture_rejected_with_expected_error(name: str):
    from fr.parser import PlanSchemaError, parse_strict

    entry = INVALID[name]
    with pytest.raises(PlanSchemaError) as excinfo:
        parse_strict(CORPUS / "invalid" / name)
    assert entry["match"] in str(excinfo.value), (
        f"{name}: expected {entry['match']!r} in error, got: {excinfo.value}"
    )
