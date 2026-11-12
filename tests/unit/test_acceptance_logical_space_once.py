"""A batch of logical refs reads the artifact space once, not once per ref (p2-r4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance import logical
from fr.artifacts import paths


def test_path_view_computes_the_space_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.acceptance.model import Matrix, Row

    calls: list[Path] = []
    real = paths.space_for
    monkeypatch.setattr(paths, "space_for", lambda r: (calls.append(r), real(r))[1])
    refs = tuple(f"spec:s{i}" for i in range(5))
    row = Row.model_construct(
        id="a", capability="c", acceptance="x", origin=refs, levels={}, status="ci", notes=""
    )
    matrix = Matrix.model_construct(rows=(row,))
    logical.path_view(matrix, tmp_path, "o/r")
    assert len(calls) == 1
    assert logical.resolution_problem("spec:zz", tmp_path, ()) is not None
    assert len(calls) == 1  # explicit roots: no space read at all
