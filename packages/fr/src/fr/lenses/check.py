"""`fr lenses check`: what is wrong with `.fr/lenses.yaml` (spec 2026-11-12-review-lenses R3).

Over the file's text, the shipped set and the path rules in force (`fr.lenses.rules`:
the default branch's rules together with the branch's, so a branch cannot disable a
lens a rule its base holds requires, R6). The shipped ids are read through
`fr.lenses.resolve` only, so there is one place that knows where shipped lenses live.
"""

from __future__ import annotations

from pathlib import Path

from fr.lenses.model import LensError, PathRule
from fr.lenses.resolve import load_config, shipped_lenses
from fr.lenses.rules import rules_in_force_at


def check_config(root: Path, rules: tuple[PathRule, ...] | None = None) -> list[str]:
    """Every problem with `<root>/.fr/lenses.yaml` against the path rules in force
    (`rules`, default: the default branch's together with the branch's, R6)."""
    try:
        config = load_config(root)
        shipped = set(shipped_lenses())
        if rules is None:
            rules = rules_in_force_at(root)
    except LensError as e:
        return [str(e)]
    known = shipped | set(config.lenses)
    problems: list[str] = []
    for lens_id in config.disable:
        if lens_id not in shipped:
            problems.append(f"disable names a lens that does not exist: {lens_id}")
        elif lens_id in config.lenses:
            problems.append(
                f"the file disables and also defines {lens_id}: "
                "drop it from disable to replace the shipped lens"
            )
    for rule in rules:
        for lens_id in rule.lenses:
            if lens_id not in known:
                problems.append(f"a path rule requires a lens that does not exist: {lens_id}")
            elif lens_id in config.disable:
                problems.append(
                    f"the file disables {lens_id} and a path rule "
                    f"({', '.join(rule.paths)}) requires it"
                )
    return problems
