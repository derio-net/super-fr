"""Effective lenses over a tmp repo (spec 2026-11-12-review-lenses R2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.lenses.model import LensError
from fr.lenses.resolve import effective_lenses, shipped_lenses


def _write(root: Path, text: str) -> None:
    (root / ".fr").mkdir(exist_ok=True)
    (root / ".fr" / "lenses.yaml").write_text(text)


def test_no_config_is_the_four_shipped_lenses(tmp_path: Path) -> None:
    got = effective_lenses(tmp_path)

    assert set(got) == {"security", "tests", "simplicity", "errors"}
    assert {lens.source for lens in got.values()} == {"shipped"}


def test_disable_replace_and_add(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "disable: [errors]\n"
        "lenses:\n"
        "  security:\n    title: Sec\n    brief: mine\n"
        "  accessibility:\n    title: A11y\n    brief: look\n",
    )

    got = effective_lenses(tmp_path)

    assert set(got) == {"security", "tests", "simplicity", "accessibility"}
    assert got["tests"].source == "shipped"
    assert got["security"].source == "repo (replaces shipped)"
    assert got["security"].brief == "mine"
    assert got["accessibility"].source == "repo"


def test_a_shipped_manifest_named_for_another_lens_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "tests.yaml").write_text("lens: security\ntitle: T\nbrief: b\n")
    monkeypatch.setenv("FR_SHIPPED_LENSES_DIR", str(tmp_path))

    with pytest.raises(LensError, match="tests.yaml.*security"):
        shipped_lenses()


def test_an_undecodable_config_is_a_lens_error(tmp_path: Path) -> None:
    (tmp_path / ".fr").mkdir()
    (tmp_path / ".fr" / "lenses.yaml").write_bytes(b"\xff\xfe\x00bad")

    with pytest.raises(LensError, match="lenses.yaml"):
        effective_lenses(tmp_path)


def test_no_shipped_lens_set_is_a_broken_install_not_an_empty_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fr.lenses import resolve

    monkeypatch.setattr(resolve, "shipped_lens_dir", lambda: None)

    with pytest.raises(LensError, match="no shipped lens manifests"):
        shipped_lenses()
