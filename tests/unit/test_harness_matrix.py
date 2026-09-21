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


# Review r1-m6: the two original CLI assertions read the TABLE, and rich wraps
# and elides a table to fit its console — whose width it snapshots in
# `Console.__init__`. `harness_cmd.console` is a module-level singleton built at
# import, BEFORE conftest's autouse `_wide_terminal` fixture can widen anything,
# so `COLUMNS=80 pytest` failed both. That is the same wrap-dependent fragility
# the plan journal root-caused for two `test_run_workspace.py` tests, which pass
# only because Linux CI's tmp paths are short. So the CONTENT assertions moved
# to `--format json`, which no console width can reflow, and exactly one thin
# table test stays to prove the table renders at all.
def test_parity_command_exits_zero_and_names_every_harness_and_a_surface() -> None:
    result = runner_cli.invoke(app, ["harness", "parity", "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert {h for s in data["surfaces"] for h in s["harnesses"]} == set(HARNESSES)
    assert any(s["id"] == "fr-isolation-required" for s in data["surfaces"])


@pytest.mark.parametrize("columns", ["60", "80", "200"])
def test_parity_table_renders_at_any_width(columns: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The table must survive a narrow terminal, and every surface id must stay
    legible — `overflow="fold"` wraps where rich's default `ellipsis` would
    collapse `fr-isolation-guard` and `fr-isolation-required` to one `fr-isol…`."""
    monkeypatch.setenv("COLUMNS", columns)
    result = runner_cli.invoke(app, ["harness", "parity"])
    assert result.exit_code == 0, result.output
    assert "Harness parity" in result.output


def test_parity_command_json_round_trips_through_parse_matrix() -> None:
    result = runner_cli.invoke(app, ["harness", "parity", "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    matrix = parse_matrix(data)
    assert matrix.surfaces


def test_parity_command_harness_filter_prints_one_column() -> None:
    """The filter narrows to one harness. The scope_note CONTENT is asserted via
    json above; a note is a sentence rich may wrap at any width, so asserting it
    verbatim in table output is the r1-m6 trap again."""
    result = runner_cli.invoke(app, ["harness", "parity", "--harness", "opencode"])
    assert result.exit_code == 0, result.output
    assert "opencode" in result.output
    assert "hermes" not in result.output


def test_every_scope_note_is_reachable_from_the_json_output() -> None:
    """Every declared scope_note survives into `--format json` — the wrap-proof
    surface an operator or a script can actually read them from."""
    result = runner_cli.invoke(app, ["harness", "parity", "--format", "json"])
    data = json.loads(result.output)
    notes = [
        h["scope_note"]
        for s in data["surfaces"]
        for h in s["harnesses"].values()
        if h["scope_note"]
    ]
    assert notes
    for surface in load_matrix().surfaces:
        for hstate in surface.harnesses.values():
            if hstate.scope_note:
                assert hstate.scope_note in notes


# --- Review r1-m7: the bad-value paths were right but unpinned. -------------
@pytest.mark.parametrize(
    "args",
    [
        ["harness", "parity", "--format", "bogus"],
        ["harness", "parity", "--harness", "bogus"],
    ],
)
def test_parity_command_rejects_bad_option_values(args: list[str]) -> None:
    result = runner_cli.invoke(app, args)
    assert result.exit_code == 2, result.output


# --- Review r1-m3/m4/m5: the file must not silently misstate a cell. --------


def test_a_duplicate_yaml_key_is_refused_rather_than_silently_rewritten() -> None:
    """PyYAML's `safe_load` keeps the LAST occurrence and says nothing, so a
    duplicated harness key rewrites a cell with no trace. This repo already
    shipped that bug once, in `docs/acceptance/matrix.yaml`. For a file whose
    only job is to state cells accurately, the strict loader is the point."""
    text = """
schema: 1
surfaces:
  - id: dup-key
    kind: interaction
    summary: s
    harnesses:
      claude-code: {state: enforced}
      claude-code: {state: absent}
      opencode: {state: absent}
      hermes: {state: absent}
      codex: {state: unsupported}
      copilot-cli: {state: unsupported}
"""
    with pytest.raises(HarnessError, match="duplicate key"):
        parse_matrix(text)


def test_two_rows_claiming_one_surface_id_are_refused() -> None:
    """A duplicate id is a malformed file, not a declared-vs-observed
    disagreement, so it is caught at parse rather than deferred to the derived
    check — the same line `fr.workflow.check` draws for duplicate step ids."""
    row = """
  - id: same-id
    kind: interaction
    summary: s
    harnesses:
      claude-code: {state: enforced}
      opencode: {state: absent}
      hermes: {state: absent}
      codex: {state: unsupported}
      copilot-cli: {state: unsupported}"""
    with pytest.raises(HarnessError, match="duplicate surface id 'same-id'"):
        parse_matrix("schema: 1\nsurfaces:" + row + row)


def test_an_unsupported_schema_version_says_what_it_read_and_what_is_supported() -> None:
    """Matches `fr.workflow.model.parse_manifest`'s message shape. Pydantic's
    native `Input should be 1` names neither the value it saw nor the value it
    wants."""
    with pytest.raises(
        HarnessError, match=r"unsupported parity schema: 2 \(fr supports schema: 1\)"
    ):
        parse_matrix("schema: 2\nsurfaces: []")


def test_a_matrix_with_no_schema_key_is_refused() -> None:
    """`schema:` is required — no default — so a file cannot arrive
    un-versioned and be read as version 1 by accident."""
    with pytest.raises(HarnessError, match="unsupported parity schema"):
        parse_matrix("surfaces: []")


# --- Review r1-i1: a cell that overclaims is the failure mode this exists to
# prevent, and Phase 2's observation cannot catch it (it can only see whether a
# script is REGISTERED, not how much of the surface it covers).


def test_the_hermes_bash_guard_is_declared_partial_not_enforced() -> None:
    """`plugins/super-fr/hooks/hermes/fr-isolation-guard.sh` denies only git/gh
    MUTATIONS; the Claude hook denies every base-repo-cwd command. Declaring it
    `enforced` would have been an overclaim that Phase 2's derived check then
    confirms and test-pins, because both hooks are equally "registered"."""
    matrix = load_matrix()
    surface = next(s for s in matrix.surfaces if s.id == "fr-isolation-guard")
    hermes = surface.harnesses["hermes"]
    assert hermes.state == "partial"
    assert hermes.scope_note is not None
    assert "git/gh" in hermes.scope_note


def test_no_scope_note_was_truncated_by_an_unquoted_yaml_comment() -> None:
    """An unquoted YAML scalar ends at ` #`, so a note mentioning an issue
    number loses everything from the `#` on — silently, with a note that still
    reads like a finished sentence. This shipped: `operator-gate`/opencode
    ended at "...the measured failure of", having dropped "#436 instance 2".

    The strict loader cannot see this (nothing is duplicated) and neither can
    the schema (a shorter string is still a string), so it is checked against
    the RAW file: every `#` written in a `scope_note:` line must survive into
    the parsed value."""
    from importlib.resources import files

    raw = files("fr.harness").joinpath("parity.yaml").read_text()
    notes = {
        n.scope_note for s in load_matrix().surfaces for n in s.harnesses.values() if n.scope_note
    }
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped.startswith("scope_note:"):
            continue
        value = stripped[len("scope_note:") :].strip()
        if value.startswith((">", "|")) or "#" not in value:
            continue
        tail = value.strip('"').strip("'")
        tail = tail[tail.index("#") :]
        assert any(tail in note for note in notes), (
            f"scope_note fragment {tail!r} is in parity.yaml but reached no parsed "
            "note — an unquoted ' #' was read as a YAML comment. Quote the scalar."
        )
