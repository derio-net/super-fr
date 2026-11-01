"""Safe YAML loading backed by libyaml when it is installed.

Spec 2026-11-01-ci-speed §3.A: PyYAML's pure-Python loader dominates the
acceptance matrix's parse time; ``CSafeLoader`` is the same grammar in C. This
module is the one place that picks the loader. Standardizing every other
``yaml.safe_load`` call site on it is a tracked follow-up issue, not part of
this change.
"""

from __future__ import annotations

from typing import Any

import yaml

SafeLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def safe_load(text: str) -> Any:
    """`yaml.safe_load`, through libyaml's loader when available."""
    return yaml.load(text, Loader=SafeLoader)  # noqa: S506 - a safe loader
