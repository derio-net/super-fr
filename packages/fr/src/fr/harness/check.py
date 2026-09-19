"""The derived check — declared (`parity.yaml`) vs. observed (the real
registration files). 2026-09-18 harness-parity-matrix spec §3.B, Phase 2.

Drift is reported in BOTH directions, because both are real failures with
different shapes:

- declared `enforced`, observed `absent` — an **overclaim**. The dangerous
  direction: the matrix tells an operator a surface is guarded when nothing
  guards it.
- declared `absent`, observed `present` — an **understatement**. Less
  dangerous but live today: `fr-acceptance-nag` is registered on Hermes
  and issue #436's hand-written table still calls it absent. Left
  unreported, this is how a matrix rots into a document nobody trusts.

What the check deliberately does NOT try to verify is *how much* of a
surface a registered hook covers. A registration file cannot answer that;
only a human reading both scripts can, which is what `state` +
`scope_note` record. So `partial` and `advisory` are checked against the
weaker fact the files CAN answer — see `_EXPECTED_OBSERVATION`.
"""

from __future__ import annotations

from dataclasses import dataclass

from fr.harness.model import Matrix
from fr.harness.observe import OBSERVABLE_HARNESSES, REGISTRATION_FILES, Observation

HOOKS_DIR = "plugins/super-fr/hooks/"
"""The other side of the row<->script pairing, named in every `pairing`
finding so the operator knows which directory is being compared."""

PARITY_FILE = "packages/fr/src/fr/harness/parity.yaml"
"""Named in every finding: one of the two files the operator must edit, and
the one to edit when the code is right and the matrix is stale."""

_EXPECTED_OBSERVATION: dict[str, Observation] = {
    "enforced": "present",
    "partial": "present",
    "advisory": "absent",
    "absent": "absent",
}
"""Declared state -> the registration fact it implies.

`unsupported` is deliberately absent from this table rather than mapped to
anything: "the harness is not supported, the question does not arise" makes
no claim about registration, so no observation can contradict it. A
missing key means "never a finding", which is why this is a lookup and not
an if/elif chain — adding a sixth state is one row here."""


@dataclass(frozen=True, order=True)
class Finding:
    """One thing wrong with the matrix — a drifted cell, or a row and a script
    that do not pair up.

    `declared` and `observed` were `Observation`-typed when cell drift was the
    only finding. They are plain `str` since review r2-i1 folded `pairing` into
    the same type and the same exit-1 path: a missing row is not an observation
    of anything ("shipped" / "no script"), and neither is `unsupported` claimed
    on a harness fr can actually read ("n/a"). Widening beat inventing a second
    finding type for `_run_check` to merge — but `message` is the field an
    operator reads, and these two remain a short machine-readable summary for
    `--format json`, not a closed vocabulary anything branches on."""

    surface_id: str
    harness: str
    declared: str
    observed: str
    message: str


def _message(surface_id: str, harness: str, declared: str, observed: Observation) -> str:
    registration = REGISTRATION_FILES.get(harness, "the harness's registration file")
    direction = (
        f"declared {declared!r} but NOT registered in {registration}"
        if observed == "absent"
        else f"declared {declared!r} but IS registered in {registration}"
    )
    return f"{surface_id} / {harness}: {direction} — fix that file or {PARITY_FILE}"


def pairing(matrix: Matrix, shipped: frozenset[str]) -> list[Finding]:
    """Rows and scripts that do not pair up, in both directions.

    Split out of `check` because it compares the matrix against the *files on
    disk* rather than against a reading of them, but reported through the SAME
    `Finding` type and the same exit-1 path — review finding r2-i1. Before that
    fix this lived only in `tests/unit/test_tripwire_harness_parity.py`, so
    `fr harness parity --check` printed "declared matrix agrees with the
    registration files" on a repo carrying an undeclared hook script: the
    command a human consults gave a clean bill of health for a state the
    repo's own CI called drift. A check that is honest in pytest and
    reassuring on the terminal is the failure mode this feature exists to
    stop, wearing the feature's own clothes.

    The tripwire now calls this too, so there is one implementation rather
    than two that can disagree."""
    declared = {s.script: s for s in matrix.surfaces if s.kind == "hook" and s.script}

    findings = [
        Finding(
            surface_id=script,
            harness="-",
            declared="(no row)",
            observed="shipped",
            message=(
                f"{script}: shipped in {HOOKS_DIR} but has no `kind: hook` row — "
                f"add one to {PARITY_FILE}, declaring its state on every harness"
            ),
        )
        for script in sorted(shipped - set(declared))
    ]
    findings += [
        Finding(
            surface_id=surface.id,
            harness="-",
            declared="(row)",
            observed="no script",
            message=(
                f"{surface.id}: row names script {surface.script!r}, which is not in "
                f"{HOOKS_DIR} — remove the row from {PARITY_FILE} or restore the script"
            ),
        )
        for script, surface in sorted(declared.items())
        if script not in shipped
    ]
    return findings


def check(matrix: Matrix, observed: dict[str, dict[str, Observation]]) -> list[Finding]:
    """Every disagreement between `matrix` and `observed`, ordered.

    Only `kind: hook` rows are checked: an interaction surface is not a
    script, so no registration file can speak to it and the matrix is the
    only record there is. Only `OBSERVABLE_HARNESSES` are checked: `codex`
    and `copilot-cli` register nothing anywhere, and silence is not
    evidence of absence.

    A hook row whose script appears in no observation at all reads as
    `absent` everywhere — nothing named it, so nothing wires it. (That its
    script exists on disk at all is the structural tripwire's job, not
    this function's: `check` compares two readings of the world, it does
    not validate the file.)"""
    findings: list[Finding] = []
    for surface in sorted(matrix.surfaces, key=lambda s: s.id):
        if surface.kind != "hook" or surface.script is None:
            continue
        per_harness = observed.get(surface.script, {})
        for harness in OBSERVABLE_HARNESSES:
            declared = surface.harnesses[harness].state
            expected = _EXPECTED_OBSERVATION.get(declared)
            if expected is None:
                # `unsupported` makes no claim about registration, so nothing
                # can contradict it — but only where fr genuinely cannot look.
                # On a harness that HAS an observer it would be a green button
                # for any drifting cell (review r2-m5): spec §3.A scopes the
                # state to "the harness is not supported", and this loop only
                # ever visits observable ones, so reaching here at all is the
                # misuse.
                findings.append(
                    Finding(
                        surface_id=surface.id,
                        harness=harness,
                        declared=declared,
                        observed="n/a",
                        message=(
                            f"{surface.id} / {harness}: declared 'unsupported', but "
                            f"{harness} is a supported harness fr reads "
                            f"{REGISTRATION_FILES.get(harness, 'a registration file')} for. "
                            f"Use a state that makes a claim — fix {PARITY_FILE}"
                        ),
                    )
                )
                continue
            seen: Observation = per_harness.get(harness, "absent")
            if seen != expected:
                findings.append(
                    Finding(
                        surface_id=surface.id,
                        harness=harness,
                        declared=declared,
                        observed=seen,
                        message=_message(surface.id, harness, declared, seen),
                    )
                )
    return findings


__all__ = ["HOOKS_DIR", "PARITY_FILE", "Finding", "check", "pairing"]
