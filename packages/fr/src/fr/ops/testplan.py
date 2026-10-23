"""A Test Plan step's effective gate (spec 2026-10-22-fr-ops R12, §G).

A step's literal tag (`[devops]`/`[tester]`, parsed by `fr.spec.test_plan_steps`)
wins. An untagged step takes `devops` when the run's effective gates (its `Exit`,
with the R13 promotion) include it, else `tester` when they include that, else it
stays ungated and is handled exactly as before.
"""

from __future__ import annotations

from collections.abc import Iterable, Set

from fr.spec import Step, StepGate


def effective_step_gate(step: Step, exit_gates: Set[str]) -> StepGate | None:
    """The gate that owns `step` under a run whose effective gates are `exit_gates`."""
    if step.gate is not None:
        return step.gate
    if "devops" in exit_gates:
        return "devops"
    if "tester" in exit_gates:
        return "tester"
    return None


def steps_gated(steps: Iterable[Step], exit_gates: Set[str], gate: StepGate) -> list[Step]:
    """The steps whose effective gate is `gate`, in order."""
    return [s for s in steps if effective_step_gate(s, exit_gates) == gate]
