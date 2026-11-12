"""Review lenses: manifest and config models (spec 2026-11-12-review-lenses R1-R2)."""

from __future__ import annotations

import pytest

from fr.lenses.model import LensError, parse_config, parse_lens


def test_the_package_imports() -> None:
    import fr.lenses

    assert fr.lenses.__doc__


def test_parse_lens_accepts_a_manifest() -> None:
    lens = parse_lens("lens: security\ntitle: Security\nbrief: |\n  look\n", source="x")

    assert (lens.id, lens.title, lens.brief.strip(), lens.source) == (
        "security",
        "Security",
        "look",
        "x",
    )


@pytest.mark.parametrize(
    "text",
    [
        "lens: a\ntitle: A\nbrief: b\nextra: 1\n",
        "lens: a\ntitle: A\nbrief: '  '\n",
        "lens: A\ntitle: A\nbrief: b\n",
        "lens: 1a\ntitle: A\nbrief: b\n",
        "lens: a_b\ntitle: A\nbrief: b\n",
        "- not a mapping\n",
        "lens: [\n",
    ],
)
def test_parse_lens_refuses(text: str) -> None:
    with pytest.raises(LensError):
        parse_lens(text, source="x")


def test_parse_config_accepts_every_key_optional() -> None:
    assert parse_config("").disable == ()
    cfg = parse_config(
        "disable: [errors]\n"
        "lenses:\n  accessibility:\n    title: Accessibility\n    brief: look\n"
        "require:\n  - paths: ['src/**']\n    lenses: [security]\n"
    )

    assert cfg.disable == ("errors",)
    assert cfg.lenses["accessibility"].title == "Accessibility"
    assert cfg.require[0].paths == ("src/**",)
    assert cfg.require[0].lenses == ("security",)


@pytest.mark.parametrize(
    "text",
    [
        "bogus: 1\n",
        "require:\n  - paths: []\n    lenses: [a]\n",
        "require:\n  - paths: ['x']\n    lenses: []\n",
        "- a list\n",
        "lenses:\n  Bad:\n    title: T\n    brief: b\n",
        "lenses:\n  ok:\n    title: T\n    brief: ''\n",
        "disable: [Bad_Id]\n",
        "disable: [a]\ndisable: [b]\n",
    ],
)
def test_parse_config_refuses(text: str) -> None:
    with pytest.raises(LensError):
        parse_config(text, source="x")
