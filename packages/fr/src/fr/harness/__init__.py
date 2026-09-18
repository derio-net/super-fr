"""`fr.harness` — the harness-parity vocabulary, schema, and shipped matrix.

2026-09-18 harness-parity-matrix spec §3.A, Phase 1 (walking skeleton).
`parity.yaml` sits inside this package (`src/fr/harness/parity.yaml`), so
hatchling's `packages = ["src/fr"]` ships it with no manifest work — the
same trick `fr/workflows/fr-goal.yaml` already uses (spec §3.A).
`load_matrix()` resolves it via `importlib.resources`, never a
repo-relative path, so it works from an installed wheel with no checkout
present (the Phase 1 skeleton smoke: `fr harness parity` run from outside
the repo).
"""

from __future__ import annotations

import importlib.resources

from fr.harness.model import (
    HARNESSES,
    STATES,
    HarnessError,
    HarnessState,
    Matrix,
    Surface,
    parse_matrix,
)

__all__ = [
    "HARNESSES",
    "STATES",
    "HarnessError",
    "HarnessState",
    "Matrix",
    "Surface",
    "load_matrix",
    "parse_matrix",
]


def load_matrix() -> Matrix:
    """The shipped `parity.yaml`, parsed — the one matrix every render and
    check starts from.

    Reads via `importlib.resources.files("fr.harness")`, which resolves
    correctly whether `fr` is an editable checkout install or a zipped
    wheel — `fr.harness` is a real package (carries `__init__.py`), so no
    `as_file` extraction dance is needed the way `fr.workflow.resolve`
    needs one for the data-only `fr.workflows` directory."""
    text = (
        importlib.resources.files("fr.harness").joinpath("parity.yaml").read_text(encoding="utf-8")
    )
    return parse_matrix(text)
