"""CI tripwire: the presentation deck's index.html must not lag slides.md.

`docs/presentation/reveal/slides.md` holds every word of the talk;
`index.html` is generated from it by `build.py` and is the file a browser
actually opens. So a PR that edits the prose and forgets to rebuild looks
complete, passes every other gate, and leaves the deck stale — the same silent
no-op shape as the explainers tripwire next door.

Unlike the explainers renderer, this generator lives in *this* repo, so the
check is exact rather than heuristic: re-render and compare byte for byte.

Regenerate with:

    uv run --no-project python docs/presentation/reveal/build.py
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DECK = REPO_ROOT / "docs" / "presentation" / "reveal"


def _build_module():
    spec = importlib.util.spec_from_file_location("deck_build", DECK / "build.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


build = _build_module()


def test_index_html_is_current_with_slides_md() -> None:
    """index.html is exactly what build.py renders from slides.md."""
    assert build.render() == (DECK / "index.html").read_text(), (
        "docs/presentation/reveal/index.html is stale with respect to slides.md. "
        "Run: uv run --no-project python docs/presentation/reveal/build.py"
    )


def test_generated_index_carries_the_do_not_edit_banner() -> None:
    """A reader who opens index.html is told where the source is."""
    assert build.BANNER in (DECK / "index.html").read_text()


def test_every_slide_body_is_wrapped_in_a_script_template() -> None:
    """The wrapper reveal's markdown plugin needs in order to see raw HTML.

    Without `<script type="text/template">` the plugin reads
    `section.textContent`, which has already discarded every tag — so layout
    wrappers, images, links and slide classes vanish at render time while the
    deck still looks fine. Pin the wrapper so that regression cannot return.
    """
    html = (DECK / "index.html").read_text()
    assert html.count("data-markdown") == html.count('<script type="text/template">')


def test_a_note_that_is_not_last_is_refused() -> None:
    """Content after `Note:` is swallowed into the speaker notes."""
    with pytest.raises(build.DeckError, match="swallowed"):
        build.render_slides('## X\n\nNote: a note\n\n<img class="side" src="y.png">\n')


def test_a_note_that_is_last_is_accepted() -> None:
    assert build.render_slides('## X\n\n<img class="side" src="y.png">\n\nNote: a note')


def test_separators_inside_fenced_code_do_not_split_slides() -> None:
    """A YAML document marker in a code block is content, not a slide break."""
    markdown = "## X\n\n```yaml\n---\nkey: value\n```\n\n---\n\n## Y"
    assert build.render_slides(markdown).count('<script type="text/template">') == 2


def test_the_theme_uses_no_viewport_units() -> None:
    """`vh`/`vw` inside a slide break reveal's scaling.

    Reveal lays slides out on a fixed 960x700 logical canvas and scales that
    with a CSS transform. Lengths in px/em/% live inside the scaled coordinate
    system; `vh` and `vw` are measured against the real window instead, so a
    rule mixing them re-lays-out as the window resizes while every other slide
    holds still. The title slide had exactly that bug: `padding-top: 6vh` moved
    its heading between 37 and 54 logical px depending on window size.
    """
    css = (DECK / "theme-industrial.css").read_text()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)  # comments may discuss vh
    offenders = [
        line.strip() for line in css.splitlines() if re.search(r"\b\d*\.?\d+v(h|w|min|max)\b", line)
    ]
    assert offenders == [], (
        "viewport units in the deck theme do not scale with reveal's transform; "
        f"use logical px instead: {offenders}"
    )
