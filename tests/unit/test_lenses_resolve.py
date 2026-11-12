"""Effective lenses over a tmp repo (spec 2026-11-12-review-lenses R2)."""

from __future__ import annotations

from pathlib import Path

from fr.lenses.resolve import effective_lenses


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
