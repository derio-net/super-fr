"""`fr.harness` vocabulary, schema, shipped data, and `fr harness parity` —
2026-09-18 harness-parity-matrix spec §3.A/§3.F, Phase 1 (walking skeleton).

Phase 1 is deliberately narrow: the closed vocabulary (`HARNESSES`,
`STATES`), the pydantic schema (`Surface`/`Matrix`/`parse_matrix`), the
shipped `parity.yaml` loaded via `importlib.resources` (never a
repo-relative path — the whole point is that this resolves from an
installed wheel, not just an in-checkout test run), and the render-only
`fr harness parity` CLI. `--check` (declared vs. observed) is Phase 2.
"""

from __future__ import annotations

import json

import pytest
from fr.cli import app
from fr.harness import HARNESSES, STATES, load_matrix
from fr.harness.model import HarnessError, parse_matrix
from typer.testing import CliRunner

runner_cli = CliRunner()


# --- (a) the closed vocabulary ---------------------------------------------


def test_harnesses_is_the_exact_ordered_tuple() -> None:
    assert HARNESSES == ("claude-code", "opencode", "hermes", "codex", "copilot-cli")


def test_states_is_the_exact_closed_set() -> None:
    assert STATES == frozenset({"enforced", "partial", "advisory", "absent", "unsupported"})


# --- (b) load_matrix() reads the shipped parity.yaml ------------------------


def test_load_matrix_returns_every_row_covering_every_harness() -> None:
    matrix = load_matrix()
    assert matrix.surfaces
    for surface in matrix.surfaces:
        assert set(surface.harnesses) == set(HARNESSES), surface.id


def test_load_matrix_contains_known_surface_ids() -> None:
    matrix = load_matrix()
    ids = {s.id for s in matrix.surfaces}
    assert "fr-isolation-required" in ids
    assert "operator-gate" in ids


# --- (c) partial/advisory require a scope_note ------------------------------

_BASE_HARNESSES = {
    "claude-code": {"state": "enforced"},
    "opencode": {"state": "absent"},
    "hermes": {"state": "absent"},
    "codex": {"state": "unsupported"},
    "copilot-cli": {"state": "unsupported"},
}


def _matrix_with(surface: dict) -> dict:
    return {"schema": 1, "surfaces": [surface]}


def test_partial_without_scope_note_raises() -> None:
    surface = {
        "id": "x",
        "kind": "hook",
        "script": "x.sh",
        "summary": "s",
        "harnesses": {**_BASE_HARNESSES, "opencode": {"state": "partial"}},
    }
    with pytest.raises(HarnessError):
        parse_matrix(_matrix_with(surface))


def test_partial_with_scope_note_parses() -> None:
    surface = {
        "id": "x",
        "kind": "hook",
        "script": "x.sh",
        "summary": "s",
        "harnesses": {
            **_BASE_HARNESSES,
            "opencode": {"state": "partial", "scope_note": "some scope"},
        },
    }
    matrix = parse_matrix(_matrix_with(surface))
    assert matrix.surfaces[0].harnesses["opencode"].scope_note == "some scope"


def test_advisory_without_scope_note_raises() -> None:
    surface = {
        "id": "x",
        "kind": "interaction",
        "summary": "s",
        "harnesses": {**_BASE_HARNESSES, "hermes": {"state": "advisory"}},
    }
    with pytest.raises(HarnessError):
        parse_matrix(_matrix_with(surface))


def test_advisory_with_scope_note_parses() -> None:
    surface = {
        "id": "x",
        "kind": "interaction",
        "summary": "s",
        "harnesses": {
            **_BASE_HARNESSES,
            "hermes": {"state": "advisory", "scope_note": "prose only"},
        },
    }
    matrix = parse_matrix(_matrix_with(surface))
    assert matrix.surfaces[0].harnesses["hermes"].scope_note == "prose only"


# --- (d) unknown state / unknown harness key raise --------------------------


def test_unknown_state_raises() -> None:
    surface = {
        "id": "x",
        "kind": "hook",
        "script": "x.sh",
        "summary": "s",
        "harnesses": {**_BASE_HARNESSES, "opencode": {"state": "not-a-state"}},
    }
    with pytest.raises(HarnessError):
        parse_matrix(_matrix_with(surface))


def test_unknown_harness_key_raises() -> None:
    bad = dict(_BASE_HARNESSES)
    bad["windows-terminal"] = {"state": "unsupported"}
    surface = {
        "id": "x",
        "kind": "hook",
        "script": "x.sh",
        "summary": "s",
        "harnesses": bad,
    }
    with pytest.raises(HarnessError):
        parse_matrix(_matrix_with(surface))


def test_missing_harness_key_raises() -> None:
    incomplete = dict(_BASE_HARNESSES)
    del incomplete["codex"]
    surface = {
        "id": "x",
        "kind": "hook",
        "script": "x.sh",
        "summary": "s",
        "harnesses": incomplete,
    }
    with pytest.raises(HarnessError):
        parse_matrix(_matrix_with(surface))


def test_hook_kind_requires_script() -> None:
    surface = {
        "id": "x",
        "kind": "hook",
        "summary": "s",
        "harnesses": _BASE_HARNESSES,
    }
    with pytest.raises(HarnessError):
        parse_matrix(_matrix_with(surface))


def test_interaction_kind_forbids_script() -> None:
    surface = {
        "id": "x",
        "kind": "interaction",
        "script": "x.sh",
        "summary": "s",
        "harnesses": _BASE_HARNESSES,
    }
    with pytest.raises(HarnessError):
        parse_matrix(_matrix_with(surface))


def test_harness_error_names_the_surface_id() -> None:
    surface = {
        "id": "my-surface",
        "kind": "hook",
        "script": "x.sh",
        "summary": "s",
        "harnesses": {**_BASE_HARNESSES, "opencode": {"state": "partial"}},
    }
    with pytest.raises(HarnessError, match="my-surface"):
        parse_matrix(_matrix_with(surface))


# --- `fr harness parity` CLI -------------------------------------------------


def test_parity_command_exits_zero_and_names_every_harness_and_a_surface() -> None:
    result = runner_cli.invoke(app, ["harness", "parity"])
    assert result.exit_code == 0, result.output
    for harness in HARNESSES:
        assert harness in result.output
    assert "fr-isolation-required" in result.output


def test_parity_command_json_round_trips_through_parse_matrix() -> None:
    result = runner_cli.invoke(app, ["harness", "parity", "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    matrix = parse_matrix(data)
    assert matrix.surfaces


def test_parity_command_harness_filter_prints_one_column_with_scope_notes() -> None:
    result = runner_cli.invoke(app, ["harness", "parity", "--harness", "opencode"])
    assert result.exit_code == 0, result.output
    assert "opencode" in result.output
    matrix = load_matrix()
    surface = next(s for s in matrix.surfaces if s.id == "fr-isolation-required")
    note = surface.harnesses["opencode"].scope_note
    assert note is not None
    assert note in result.output
