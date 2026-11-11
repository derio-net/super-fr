"""Config and page front matter for `fr docs` (spec 2026-11-11-docs-currency R2, R4)."""

from __future__ import annotations

import pytest
from fr.docs.model import DocsConfig, Page, PageError, parse_page
from pydantic import ValidationError

GOOD = (
    "---\ntitle: T\ncovers:\n  - a/*.py\nreviewed: 2026-11-11 written with the page\n---\n# Body\n"
)


def test_a_config_takes_pages_and_must_cover() -> None:
    cfg = DocsConfig.model_validate({"pages": ["docs/*.md"], "must_cover": ["x/**"]})
    assert cfg.pages == ["docs/*.md"] and cfg.must_cover == ["x/**"]


def test_must_cover_is_optional() -> None:
    assert DocsConfig.model_validate({"pages": ["docs/*.md"]}).must_cover == []


def test_a_config_refuses_extra_keys() -> None:
    with pytest.raises(ValidationError):
        DocsConfig.model_validate({"pages": [], "bogus": 1})


def test_a_page_parses_covers_and_reviewed() -> None:
    page = parse_page("docs/a.md", GOOD)
    assert isinstance(page, Page)
    assert page.path == "docs/a.md"
    assert page.covers == ("a/*.py",)
    assert page.reviewed == "2026-11-11 written with the page"


def test_unknown_front_matter_keys_are_ignored() -> None:
    text = GOOD.replace("title: T", "title: T\ntldr: x\nstandalone_style: broadsheet")
    assert isinstance(parse_page("p.md", text), Page)


def test_empty_covers_is_legal() -> None:
    text = "---\ncovers: []\nreviewed: 2026-11-11 index\n---\n"
    page = parse_page("p.md", text)
    assert isinstance(page, Page) and page.covers == ()


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("# no front matter\n", "front matter"),
        ("---\ncovers: [unclosed\n---\n", "unreadable"),
        ("---\nreviewed: 2026-11-11 x\n---\n", "covers"),
        ("---\ncovers: []\n---\n", "reviewed"),
        ("---\ncovers: []\nreviewed: yesterday something\n---\n", "reviewed"),
        ("---\ncovers: []\nreviewed: 2026-11-11\n---\n", "reviewed"),
        ("---\ncovers: a.py\nreviewed: 2026-11-11 x\n---\n", "covers"),
        ("---\n- a\n- b\n---\n", "front matter"),
    ],
)
def test_a_bad_page_is_a_page_error(text: str, fragment: str) -> None:
    result = parse_page("docs/a.md", text)
    assert isinstance(result, PageError)
    assert result.path == "docs/a.md"
    assert fragment in result.message
