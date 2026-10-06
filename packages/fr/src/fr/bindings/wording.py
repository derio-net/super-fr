"""How a binding change is worded, wherever it is said (spec
2026-10-06-model-binding-churn R7, R11).

`fr models set/check` (an operator's yes), `fr run advance`'s pre-dispatch
guard (fr's own pick) and `fr run start`'s notice all print through here, so
the loud line and the decision a run journal keeps cannot drift apart.
"""

from __future__ import annotations

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
