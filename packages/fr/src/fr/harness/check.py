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
    """One cell where `parity.yaml` and the registration files disagree."""

    surface_id: str
    harness: str
    declared: str
    observed: Observation
    message: str


def _message(surface_id: str, harness: str, declared: str, observed: Observation) -> str:
    registration = REGISTRATION_FILES.get(harness, "the harness's registration file")
    direction = (
        f"declared {declared!r} but NOT registered in {registration}"
        if observed == "absent"
        else f"declared {declared!r} but IS registered in {registration}"
    )
    return f"{surface_id} / {harness}: {direction} — fix that file or {PARITY_FILE}"


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
            if expected is None:  # `unsupported` — makes no claim to contradict
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


__all__ = ["PARITY_FILE", "Finding", "check"]
