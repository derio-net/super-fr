"""parse_matrix memoizes parses without sharing results (spec 2026-11-01-ci-speed R1/R2)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import fr.yamlio
from fr.acceptance import model
from fr.acceptance.model import AcceptanceError, Matrix, parse_matrix

REPO = Path(__file__).resolve().parents[2]

ROW = """\
  - id: {id}
    capability: cap
    acceptance: acc
    origin: ["r:x.md"]
    levels:
      unit: ["r:tests/x.py#test_y"]
    status: ci
    notes: n
"""


def _text(*ids: str) -> str:
    return "rows:\n" + "".join(ROW.format(id=i) for i in ids)


@pytest.fixture(autouse=True)
def _clear():
    model._parse_matrix_cached.cache_clear()
    yield
    model._parse_matrix_cached.cache_clear()


def test_same_text_parses_once(monkeypatch):
    calls = []
    real = fr.yamlio.safe_load

    def counting(text):
        calls.append(1)
        return real(text)

    monkeypatch.setattr(fr.yamlio, "safe_load", counting)
    text = _text("a")
    parse_matrix(text)
    parse_matrix(text)
    assert len(calls) == 1


def test_results_are_equal_but_independent():
    text = _text("a")
    r1 = parse_matrix(text)
    r2 = parse_matrix(text)
    assert r1 == r2 and r1 is not r2
    r1.rows[0].levels["extra"] = ["r:z"]
    assert "extra" not in r2.rows[0].levels
    assert "extra" not in parse_matrix(text).rows[0].levels


def test_invalid_yaml_raises_every_time():
    for _ in range(2):
        with pytest.raises(AcceptanceError):
            parse_matrix("rows: [unclosed\n")


def test_duplicate_ids_raise_every_time():
    text = _text("a", "a")
    for _ in range(2):
        with pytest.raises(AcceptanceError, match="duplicate row ids"):
            parse_matrix(text)


def test_real_matrix_equals_plain_pyyaml_build():
    text = (REPO / "docs/acceptance/matrix.yaml").read_text()
    assert parse_matrix(text) == Matrix.model_validate(yaml.safe_load(text))
