"""`fr lenses check`: what is wrong with `.fr/lenses.yaml` (spec 2026-11-12-review-lenses R3).

Pure over the file's text and the shipped set. The shipped ids are read through
`fr.lenses.resolve` only, so there is one place that knows where shipped lenses live.
"""

from __future__ import annotations

from pathlib import Path

from fr.lenses.model import LensError
from fr.lenses.resolve import REPO_CONFIG_REL, load_config, shipped_lenses


def check_config(root: Path) -> list[str]:
    """Every problem with `<root>/.fr/lenses.yaml`; no file, no problem."""
    if not (root / REPO_CONFIG_REL).is_file():
        return []
    try:
        config = load_config(root)
        shipped = set(shipped_lenses())
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
    for rule in config.require:
        for lens_id in rule.lenses:
            if lens_id not in known:
                problems.append(f"a path rule requires a lens that does not exist: {lens_id}")
            elif lens_id in config.disable:
                problems.append(
                    f"the file disables {lens_id} and a path rule "
                    f"({', '.join(rule.paths)}) requires it"
                )
    return problems
