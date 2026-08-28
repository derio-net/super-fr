"""CI tripwire: the published explainer HTML must not lag its markdown source.

`docs/explainers/` is deployed to https://derio-net.github.io/super-fr by
`.github/workflows/pages.yml`. Pages serves the **`.html`**; the `.md` beside it
is only the source. So a PR that edits the prose and not the rendered page looks
complete, passes every other gate, and leaves the published article stale — the
same shape as every other silent no-op this repo has had to learn about.

The check is a heuristic, deliberately: the renderer lives in the blog-craft
plugin, not here, so CI cannot re-render and diff. What it *can* do is insist the
rendered page still contains the source's title and every one of its section
headings. That catches the realistic failure — prose restructured, sections added
or renamed, page never regenerated — without pretending to prove byte-equality.

Regenerate with the command recorded in `.claude/rules/explainers-currency.md`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPLAINERS = REPO_ROOT / "docs" / "explainers"

# Pages with no committed `.md` in this repo: their source lives elsewhere, so
# nothing here can check or regenerate them. Pinned as a closed set so a THIRD
# sourceless page cannot appear unnoticed — that would be new undocumented debt,
# not the known kind. See `.claude/rules/explainers-currency.md`, gap 2.
SOURCELESS = {"index.html", "fr-isolation.html"}


def _headings(md: str) -> list[str]:
    body = md.split("\n---\n", 1)[-1]
    return [m.group(2).strip() for m in re.finditer(r"(?m)^(#{2,3})\s+(.+?)\s*$", body)]


def _title(md: str) -> str | None:
    m = re.search(r'(?m)^title:\s*"?(.+?)"?\s*$', md)
    return m.group(1) if m else None


def _text(value: str) -> str:
    """Flatten one side of the comparison to comparable plain text.

    Both sides need normalizing, not just the HTML: a source heading like
    ``1. Establish the boundary (`fr run start`)`` renders as ``<code>`` with the
    backticks consumed, so comparing raw markdown against stripped HTML reports
    every code-bearing heading as missing. That is a defect in the check, not
    staleness in the page — so markdown emphasis markers come out here too.
    """
    stripped = re.sub(r"<[^>]+>", "", value)
    for entity, char in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
                         ("&#39;", "'"), ("&nbsp;", " "), ("&#160;", " ")):
        stripped = stripped.replace(entity, char)
    stripped = stripped.replace("`", "").replace("**", "").replace("*", "")
    return " ".join(stripped.split())


def test_every_markdown_explainer_has_a_rendered_page() -> None:
    sources = sorted(EXPLAINERS.glob("*.md"))
    assert sources, "no explainer sources found — the glob is wrong"
    for md_path in sources:
        assert md_path.with_suffix(".html").is_file(), (
            f"{md_path.name} has no rendered sibling — Pages serves the .html, "
            "so an unrendered source is invisible to every reader"
        )


def test_rendered_pages_carry_their_sources_headings() -> None:
    for md_path in sorted(EXPLAINERS.glob("*.md")):
        md = md_path.read_text(encoding="utf-8")
        rendered = _text(md_path.with_suffix(".html").read_text(encoding="utf-8"))

        title = _title(md)
        assert title and _text(title) in rendered, (
            f"{md_path.name}: rendered page does not carry the source title "
            f"{title!r} — regenerate it (see .claude/rules/explainers-currency.md)"
        )

        missing = [h for h in _headings(md) if _text(h) not in rendered]
        assert not missing, (
            f"{md_path.name}: the rendered page is missing {len(missing)} heading(s) "
            f"present in the source — it is stale. Regenerate per "
            f".claude/rules/explainers-currency.md. Missing: {missing[:5]}"
        )


def test_sourceless_pages_remain_a_known_closed_set() -> None:
    """Two published pages have no source here (rule gap 2). That is tracked
    debt; a third appearing silently would be untracked debt."""
    actual = {
        p.name for p in EXPLAINERS.glob("*.html")
        if not p.with_suffix(".md").is_file()
    }
    assert actual == SOURCELESS, (
        "the set of explainer pages with no committed markdown source changed: "
        f"expected {sorted(SOURCELESS)}, found {sorted(actual)}. Adding a page "
        "whose source lives outside this repo means nobody here can update it."
    )
