"""`fr lenses check`: what is wrong with `.fr/lenses.yaml` (spec 2026-11-12-review-lenses R3).

Pure over the file's text and the shipped set. The shipped ids are read through
`fr.lenses.resolve` only, so there is one place that knows where shipped lenses live.
"""

from __future__ import annotations

from pathlib import Path

from fr.lenses.model import LensError, parse_config
from fr.lenses.resolve import REPO_CONFIG_REL, shipped_lenses


def check_config(root: Path) -> list[str]:
    """Every problem with `<root>/.fr/lenses.yaml`; no file, no problem."""
    path = root / REPO_CONFIG_REL
    if not path.is_file():
        return []
    try:
        config = parse_config(path.read_text(), source=str(REPO_CONFIG_REL))
    except (LensError, OSError, UnicodeDecodeError) as e:
        return [str(e)]
    shipped = set(shipped_lenses())
    known = shipped | set(config.lenses)
    problems: list[str] = []
    for lens_id in config.disable:
        if lens_id not in shipped:
            problems.append(f"disable names a lens that does not exist: {lens_id}")
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
