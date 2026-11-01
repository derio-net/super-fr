"""fr.yamlio: libyaml-backed safe loading (spec 2026-11-01-ci-speed §3.A)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import yaml

import fr.yamlio as yamlio

REPO = Path(__file__).resolve().parents[2]


def test_loader_is_the_c_loader_when_libyaml_is_present():
    if yaml.__with_libyaml__:
        assert yamlio.SafeLoader is yaml.CSafeLoader
    else:
        assert yamlio.SafeLoader is yaml.SafeLoader


def test_loader_falls_back_without_the_c_loader(monkeypatch):
    monkeypatch.delattr(yaml, "CSafeLoader", raising=False)
    try:
        reloaded = importlib.reload(yamlio)
        assert reloaded.SafeLoader is yaml.SafeLoader
    finally:
        monkeypatch.undo()
        importlib.reload(yamlio)


@pytest.mark.parametrize(
    "text",
    [
        "42",
        "hello",
        "a:\n  b: [1, 2, {c: d}]\n  e:\n    - x\n    - y: z\n",
        "note: \"has: a colon\"\nother: 'q: r'\n",
        "",
    ],
)
def test_safe_load_matches_pyyaml(text):
    assert yamlio.safe_load(text) == yaml.safe_load(text)


def test_empty_text_is_none():
    assert yamlio.safe_load("") is None


def test_safe_load_matches_pyyaml_on_the_real_matrix():
    text = (REPO / "docs/acceptance/matrix.yaml").read_text()
    assert yamlio.safe_load(text) == yaml.safe_load(text)


def test_invalid_yaml_raises_yaml_error():
    with pytest.raises(yaml.YAMLError):
        yamlio.safe_load("a: [unclosed\n")
