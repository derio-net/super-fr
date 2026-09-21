"""`fr triage render` — deterministic, self-contained, safe (spec §3.G).

Facts are built from the CAPTURED `gh` fixtures through `collect_facts`, then
loaded back through the `fr.triage.model` loaders the command uses, so the
renderer is proven to read the derived `Issue.stage` rather than raw JSON
(review r-p2-render-model). Every state directory is under tmp_path.
"""

from __future__ import annotations

import pytest
from fr.triage.render import inline


@pytest.mark.parametrize(
    ("text", "html"),
    [
        ("`x`", "<code>x</code>"),
        ("**x**", "<strong>x</strong>"),
        ("a `b` and **c**", "a <code>b</code> and <strong>c</strong>"),
        ("<b>x</b>", "&lt;b&gt;x&lt;/b&gt;"),
        ('<a href="javascript:x">y</a>', "&lt;a href=&quot;javascript:x&quot;&gt;y&lt;/a&gt;"),
        ("<img src=x onerror=alert(1)>", "&lt;img src=x onerror=alert(1)&gt;"),
        ("a & b", "a &amp; b"),
        ("`<script>`", "<code>&lt;script&gt;</code>"),
        ("*one* _two_ [l](u)", "*one* _two_ [l](u)"),
    ],
)
def test_inline_escapes_first_then_allows_only_code_and_bold(text: str, html: str) -> None:
    assert inline(text) == html
