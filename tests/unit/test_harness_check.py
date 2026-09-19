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
from fr.harness.check import Finding, check, pairing
from fr.harness.model import Matrix, parse_matrix
from fr.harness.observe import OBSERVABLE_HARNESSES, observe, shipped_scripts

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


def test_unsupported_makes_no_claim_an_observation_can_contradict() -> None:
    """The narrowed form of what this test used to assert. `unsupported` is a
    missing key in the rule table, so no observation contradicts it — but that
    only holds where fr genuinely cannot look. This test originally declared
    `unsupported` on OPENCODE, an observable harness, and asserted silence,
    which is the green button review r2-m5 found. The silence claim belongs to
    the unobservable harnesses, and they get their own test below."""
    matrix = _matrix({"state": "unsupported"}, harness="codex")
    for present in (True, False):
        assert [f for f in check(matrix, _observed(opencode=present)) if f.harness == "codex"] == []


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
    _only_cell_drift(monkeypatch)
    result = runner_cli.invoke(app, ["harness", "parity", "--check"])
    assert result.exit_code == 1
    assert "fr-session-bind" in result.output
    assert "opencode" in result.output


def _only_cell_drift(monkeypatch) -> None:
    """Point `--check` at the drifted fixture AND make the row/script pairing
    vacuous, so these tests measure cell drift alone.

    `pairing` (review r2-i1) compares the matrix against the real repo's ten
    shipped scripts, and `_DRIFTED` declares two — without this the fixture
    reports eight "no row" findings that have nothing to do with what is under
    test. Pairing gets its own CLI test below."""
    monkeypatch.setenv("VK_REPO_ROOT", str(REPO_ROOT))
    monkeypatch.setattr("fr.commands.harness_cmd.load_matrix", lambda: _DRIFTED)
    monkeypatch.setattr(
        "fr.commands.harness_cmd.shipped_scripts",
        lambda root: frozenset(s.script for s in _DRIFTED.surfaces if s.script),
    )


def test_check_json_reports_each_finding_structurally(monkeypatch) -> None:
    _only_cell_drift(monkeypatch)
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
    _only_cell_drift(monkeypatch)
    result = runner_cli.invoke(
        app, ["harness", "parity", "--check", "--harness", "hermes", "--format", "json"]
    )
    assert result.exit_code == 0
    assert json.loads(result.output) == []


# --- Review r2-i1: the operator-facing command must not be more reassuring
# than CI. ------------------------------------------------------------------


def _matrix_with(script: str, *, state: str = "absent") -> Matrix:
    return parse_matrix(
        {
            "schema": 1,
            "surfaces": [
                {
                    "id": "only",
                    "kind": "hook",
                    "script": script,
                    "summary": "s",
                    "harnesses": {
                        "claude-code": {"state": state},
                        "opencode": {"state": "absent"},
                        "hermes": {"state": "absent"},
                        "codex": {"state": "unsupported"},
                        "copilot-cli": {"state": "unsupported"},
                    },
                }
            ],
        }
    )


def test_a_shipped_script_with_no_row_is_a_pairing_finding() -> None:
    """Before this, the pairing lived only in the pytest tripwire, so
    `fr harness parity --check` printed "agrees with the registration files"
    on a repo carrying an undeclared hook — the surface a human consults was
    the one that lied."""
    findings = pairing(_matrix_with("only.sh"), frozenset({"only.sh", "new-hook.sh"}))
    assert [f.surface_id for f in findings] == ["new-hook.sh"]
    assert "has no `kind: hook` row" in findings[0].message


def test_a_row_naming_a_script_that_does_not_ship_is_a_pairing_finding() -> None:
    """Both directions fire here, and that is correct: `other.sh` ships with no
    row AND the `only` row names a script that does not ship."""
    findings = pairing(_matrix_with("deleted.sh"), frozenset({"other.sh"}))
    dangling = [f for f in findings if f.declared == "(row)"]
    assert [f.surface_id for f in dangling] == ["only"]
    assert "is not in" in dangling[0].message


def test_pairing_is_silent_when_rows_and_scripts_agree() -> None:
    assert pairing(_matrix_with("only.sh"), frozenset({"only.sh"})) == []


def test_a_pairing_finding_is_not_scoped_to_one_harness() -> None:
    """`harness="-"`: a row missing entirely is not one harness's problem, so
    `--check --harness X` must still surface it."""
    findings = pairing(_matrix_with("only.sh"), frozenset({"only.sh", "new.sh"}))
    assert findings[0].harness == "-"


# --- Review r2-m5: `unsupported` must not silence an observable harness. ----


def test_unsupported_on_an_observable_harness_is_itself_a_finding() -> None:
    """`unsupported` makes no claim about registration, which is exactly why
    it is a missing key in the rule table — and exactly why, on a harness fr
    DOES read a registration file for, it would be a green button for any
    drifting cell."""
    matrix = _matrix_with("only.sh", state="unsupported")
    findings = check(matrix, {"only.sh": {"claude-code": "present"}})
    claude = [f for f in findings if f.harness == "claude-code"]
    assert claude, "declaring a supported harness `unsupported` must not pass silently"
    assert "is a supported harness" in claude[0].message


def test_check_reports_an_undeclared_shipped_hook_through_the_cli(monkeypatch) -> None:
    """The r2-i1 regression, end to end. With an undeclared script on disk,
    `fr harness parity --check` must exit 1 — before the fix it printed
    "declared matrix agrees with the registration files" and exited 0 while
    the pytest tripwire went red on the very same repo."""
    monkeypatch.setenv("VK_REPO_ROOT", str(REPO_ROOT))
    real = shipped_scripts(REPO_ROOT)
    monkeypatch.setattr(
        "fr.commands.harness_cmd.shipped_scripts",
        lambda root: real | {"zz-undeclared-probe.sh"},
    )
    result = runner_cli.invoke(app, ["harness", "parity", "--check"])
    assert result.exit_code == 1, result.output
    assert "zz-undeclared-probe.sh" in result.output


def test_a_pairing_finding_survives_the_harness_filter(monkeypatch) -> None:
    """`--harness hermes` must not hide a missing row: it is not one harness's
    problem, so it is not filtered away."""
    monkeypatch.setenv("VK_REPO_ROOT", str(REPO_ROOT))
    real = shipped_scripts(REPO_ROOT)
    monkeypatch.setattr(
        "fr.commands.harness_cmd.shipped_scripts",
        lambda root: real | {"zz-undeclared-probe.sh"},
    )
    result = runner_cli.invoke(app, ["harness", "parity", "--check", "--harness", "hermes"])
    assert result.exit_code == 1, result.output
    assert "zz-undeclared-probe.sh" in result.output
