"""How a binding change is worded, wherever it is said (spec
2026-10-06-model-binding-churn R7, R11).

`fr models set/check` (an operator's yes), `fr run advance`'s pre-dispatch
guard (fr's own pick) and `fr run start`'s notice all print through here, so
the loud line and the decision a run journal keeps cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fr.bindings.choose import Choice, is_autonomous


def ratio_text(ratio: float | None) -> str:
    """``×1.0``, or ``×?`` when the price ratio is unknown."""
    return "×?" if ratio is None else f"×{ratio:.1f}"


def proposal_text(choice: Choice) -> str:
    """``prov/m (rule family, price ×1.0)``; an operator-only pick says so."""
    text = f"{choice.model} (rule {choice.rule}, price {ratio_text(choice.price_ratio)}"
    if not is_autonomous(choice):
        text += ", operator-only"
    return text + ")"


@dataclass(frozen=True)
class Substitution:
    """One applied binding change: R7's five fields (old, new, reason,
    decider, rule) plus the price ratio, for whoever decided it."""

    harness: str
    tier: str
    old: str
    new: str
    reason: Literal["retired", "upgrade"]
    decider: Literal["operator", "autonomous"]
    rule: str
    price_ratio: float | None = None


def substitution_line(s: Substitution) -> str:
    """R11's one loud line."""
    return (
        f"SUBSTITUTED {s.harness}/{s.tier}: {s.old} → {s.new} "
        f"(reason: {s.reason}, decider: {s.decider}, rule: {s.rule})"
    )


def decision_title(s: Substitution) -> str:
    return f"model substitution: {s.harness}/{s.tier} {s.old} → {s.new}"


def decision_body(s: Substitution) -> str:
    """The body of the run-journal `decision` that records ``s`` — the same
    five fields fr-goal's question round writes for an operator's answer (R7)."""
    return "\n".join(
        [
            f"- old: {s.old}",
            f"- new: {s.new}",
            f"- reason: {s.reason}",
            f"- decider: {s.decider}",
            f"- rule: {s.rule}",
            f"- price ratio: {ratio_text(s.price_ratio)}",
        ]
    )
