"""`fr.harness.check` — declared (`parity.yaml`) vs. observed (the real
registration files), in BOTH directions. 2026-09-18 harness-parity-matrix
spec §3.B, Phase 2.

The rules, and why they are asymmetric: a registration file can only ever
answer "is this script wired here". It cannot answer "how much of the
surface does it cover" — that judgement is what `state`/`scope_note`
carry. So the check asserts the strongest fact each declared state
implies about registration and no more:

    enforced  -> must be observed present   (overclaim = the dangerous direction)
    partial   -> must be observed present   (partly-enforced still means wired)
    advisory  -> must be observed absent    (prose cannot be a registration)
    absent    -> must be observed absent    (the understatement, live today)
    unsupported -> never a finding
"""

from __future__ import annotations

from pathlib import Path

from fr.harness import load_matrix
from fr.harness.check import Finding, check
from fr.harness.model import parse_matrix
from fr.harness.observe import OBSERVABLE_HARNESSES, observe

REPO_ROOT = Path(__file__).resolve().parents[2]

_BASE = {
    "claude-code": {"state": "absent"},
    "opencode": {"state": "absent"},
    "hermes": {"state": "absent"},
    "codex": {"state": "unsupported"},
    "copilot-cli": {"state": "unsupported"},
}


def _matrix(state: dict, *, harness: str = "claude-code", kind: str = "hook"):
    surface = {
        "id": "x",
        "kind": kind,
        "summary": "s",
        "harnesses": {**_BASE, harness: state},
    }
    if kind == "hook":
        surface["script"] = "x.sh"
    return parse_matrix({"schema": 1, "surfaces": [surface]})


def _observed(**present: bool) -> dict[str, dict[str, str]]:
    return {
        "x.sh": {
            h: ("present" if present.get(h.replace("-", "_"), False) else "absent")
            for h in OBSERVABLE_HARNESSES
        }
    }


# --- (a) the overclaim: declared enforced, observed absent -----------------


def test_declared_enforced_but_observed_absent_is_a_finding() -> None:
    findings = check(_matrix({"state": "enforced"}), _observed())
    assert [(f.surface_id, f.harness, f.declared, f.observed) for f in findings] == [
        ("x", "claude-code", "enforced", "absent")
    ]


def test_an_overclaim_finding_names_the_registration_file_to_edit() -> None:
    (finding,) = check(_matrix({"state": "enforced"}), _observed())
    assert "plugins/super-fr/hooks/hooks.json" in finding.message
    assert "x" in finding.message and "claude-code" in finding.message


# --- (b) the understatement: declared absent, observed present -------------


def test_declared_absent_but_observed_present_is_a_finding() -> None:
    """The case that is live TODAY — `fr-acceptance-nag` on Hermes, which
    issue #436's hand-written table still calls absent."""
    findings = check(_matrix({"state": "absent"}, harness="hermes"), _observed(hermes=True))
    assert [(f.surface_id, f.harness, f.declared, f.observed) for f in findings] == [
        ("x", "hermes", "absent", "present")
    ]


# --- (c) partial REQUIRES the script be observed present -------------------


def test_declared_partial_but_observed_absent_is_a_finding() -> None:
    findings = check(
        _matrix({"state": "partial", "scope_note": "half of it"}, harness="opencode"),
        _observed(),
    )
    assert [(f.surface_id, f.harness, f.declared, f.observed) for f in findings] == [
        ("x", "opencode", "partial", "absent")
    ]


def test_declared_partial_and_observed_present_is_clean() -> None:
    """`hermes` / `fr-isolation-guard` is exactly this cell: declared
    `partial` because the Hermes guard denies only git/gh mutations, yet
    genuinely registered. It must come out clean, not as a finding."""
    findings = check(
        _matrix({"state": "partial", "scope_note": "mutations only"}, harness="hermes"),
        _observed(hermes=True),
    )
    assert findings == []


# --- (d) advisory: prose cannot be a registration --------------------------


def test_declared_advisory_but_observed_present_is_a_finding() -> None:
    findings = check(
        _matrix({"state": "advisory", "scope_note": "asked for in prose"}),
        _observed(claude_code=True),
    )
    assert [(f.surface_id, f.harness, f.declared, f.observed) for f in findings] == [
        ("x", "claude-code", "advisory", "present")
    ]


def test_declared_advisory_and_observed_absent_is_clean() -> None:
    findings = check(
        _matrix({"state": "advisory", "scope_note": "asked for in prose"}),
        _observed(),
    )
    assert findings == []


# --- (e) unsupported is never a finding ------------------------------------


def test_unsupported_never_produces_a_finding_on_any_observation() -> None:
    for present in (True, False):
        matrix = _matrix({"state": "unsupported"}, harness="opencode")
        assert check(matrix, _observed(opencode=present)) == []


def test_the_unobservable_harnesses_never_produce_a_finding() -> None:
    """`codex`/`copilot-cli` have no registration file at all, so there is
    nothing to compare — silence is not evidence of absence."""
    matrix = _matrix({"state": "absent"})
    findings = check(matrix, _observed())
    assert {f.harness for f in findings} <= set(OBSERVABLE_HARNESSES)
    assert findings == []


# --- (f) agreement yields nothing ------------------------------------------


def test_a_matrix_in_agreement_with_its_observation_yields_no_findings() -> None:
    matrix = _matrix({"state": "enforced"}, harness="hermes")
    assert check(matrix, _observed(hermes=True)) == []


def test_interaction_rows_are_never_checked_against_observation() -> None:
    """An interaction surface is not a script; no registration file can
    speak to it, so it carries no `script` and produces no finding."""
    matrix = _matrix({"state": "enforced"}, kind="interaction")
    assert check(matrix, {}) == []


def test_a_hook_row_whose_script_was_never_observed_reads_as_absent() -> None:
    """Nothing named it, so nothing wires it — an `enforced` claim about it
    is an overclaim, not an unanswerable question."""
    findings = check(_matrix({"state": "enforced"}), {})
    assert [(f.harness, f.observed) for f in findings] == [("claude-code", "absent")]


# --- findings are ordered and stringifiable --------------------------------


def test_findings_are_ordered_by_surface_then_harness() -> None:
    matrix = parse_matrix(
        {
            "schema": 1,
            "surfaces": [
                {
                    "id": "b",
                    "kind": "hook",
                    "script": "b.sh",
                    "summary": "s",
                    "harnesses": {**_BASE, "hermes": {"state": "enforced"}},
                },
                {
                    "id": "a",
                    "kind": "hook",
                    "script": "a.sh",
                    "summary": "s",
                    "harnesses": {
                        **_BASE,
                        "claude-code": {"state": "enforced"},
                        "opencode": {"state": "enforced"},
                    },
                },
            ],
        }
    )
    findings = check(matrix, {})
    assert [(f.surface_id, f.harness) for f in findings] == [
        ("a", "claude-code"),
        ("a", "opencode"),
        ("b", "hermes"),
    ]


def test_a_finding_is_comparable_and_hashable() -> None:
    (one,) = check(_matrix({"state": "enforced"}), _observed())
    (two,) = check(_matrix({"state": "enforced"}), _observed())
    assert one == two
    assert isinstance(one, Finding)
    assert len({one, two}) == 1


# --- the live matrix -------------------------------------------------------


def test_this_repos_declared_matrix_agrees_with_its_registration_files() -> None:
    assert check(load_matrix(), observe(REPO_ROOT)) == []


# --- `fr harness parity --check` (spec §3.F) -------------------------------
#
# Content is asserted through `--format json` or through plain `typer.echo`
# lines, never through a rich-rendered table: rich snapshots the console
# width at import, so a table assertion passes only at some widths (finding
# r1-m6, phase 1).

import json  # noqa: E402

from fr.cli import app  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

runner_cli = CliRunner()

_DRIFTED = parse_matrix(
    {
        "schema": 1,
        "surfaces": [
            {
                "id": "fr-session-bind",
                "kind": "hook",
                "script": "fr-session-bind.sh",
                "summary": "s",
                # claude-code IS registered for this script, so it must be
                # declared `enforced` here or it drifts too — leaving exactly
                # one intended disagreement: opencode, which ports nothing.
                "harnesses": {
                    **_BASE,
                    "claude-code": {"state": "enforced"},
                    "opencode": {"state": "enforced"},
                },
            }
        ],
    }
)


def test_check_on_this_repo_exits_zero(monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(REPO_ROOT))
    result = runner_cli.invoke(app, ["harness", "parity", "--check"])
    assert result.exit_code == 0, result.output


def test_check_on_a_drifted_matrix_exits_one_and_names_the_surface(monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(REPO_ROOT))
    monkeypatch.setattr("fr.commands.harness_cmd.load_matrix", lambda: _DRIFTED)
    result = runner_cli.invoke(app, ["harness", "parity", "--check"])
    assert result.exit_code == 1
    assert "fr-session-bind" in result.output
    assert "opencode" in result.output


def test_check_json_reports_each_finding_structurally(monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(REPO_ROOT))
    monkeypatch.setattr("fr.commands.harness_cmd.load_matrix", lambda: _DRIFTED)
    result = runner_cli.invoke(app, ["harness", "parity", "--check", "--format", "json"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert [(f["surface_id"], f["harness"], f["declared"], f["observed"]) for f in payload] == [
        ("fr-session-bind", "opencode", "enforced", "absent")
    ]


def test_check_outside_a_super_fr_checkout_declines_and_exits_zero(monkeypatch, tmp_path) -> None:
    """It needs the registration files, and there are none — so it says so
    and exits 0 rather than inventing a verdict (the `fr acceptance check`
    precedent, spec §3.F)."""
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    result = runner_cli.invoke(app, ["harness", "parity", "--check"])
    assert result.exit_code == 0
    assert "cannot check" in result.output


def test_check_with_a_harness_filter_reports_only_that_harness(monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(REPO_ROOT))
    monkeypatch.setattr("fr.commands.harness_cmd.load_matrix", lambda: _DRIFTED)
    result = runner_cli.invoke(
        app, ["harness", "parity", "--check", "--harness", "hermes", "--format", "json"]
    )
    assert result.exit_code == 0
    assert json.loads(result.output) == []
