"""`fr triage render` — deterministic, self-contained, safe (spec §3.G).

Facts are built from the CAPTURED `gh` fixtures through `collect_facts`, then
loaded back through the `fr.triage.model` loaders the command uses, so the
renderer is proven to read the derived `Issue.stage` rather than raw JSON
(review r-p2-render-model). Every state directory is under tmp_path.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.triage.model import Facts, Judgements, load_facts, load_judgements
from fr.triage.render import inline, render
from typer.testing import CliRunner

from tests.unit.triage_fixtures import NOW, SUPER_FR, _super_fr_forge


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


# ------------------------------------------------------------ P3.T3 renderer

JUDGEMENTS = """schema: 1
ranked_at: 2026-09-19
tiers:
  - {n: 1, title: Data loss, description: Work destroyed with no prompt or salvage.}
  - {n: 2, title: Silent wrongness, description: "The failure looks like **success**."}
issues:
  "super-fr#529": {tier: 1, theme: isolation, cx: S, verified: true,
                   detail: "`self_heal()` retires a **fresh** one <img src=x onerror=alert(3)>"}
  "super-fr#333": {tier: 2, theme: secrets, cx: M, detail: "waits on upstream"}
patterns:
  - {title: Remote fact justifies local destruction, ids: ["super-fr#529"], body: "`gc` trusts it"}
"""


def _state(tmp_path: Path, *, hostile: bool = False) -> tuple[Facts, Judgements]:
    """Captured facts written to disk and read back through the model loaders."""
    from fr.triage.collect import collect_facts

    facts = collect_facts(_super_fr_forge(), SUPER_FR, now=NOW)
    doc = facts.to_json()
    if hostile:
        doc["issues"][0]["title"] = "<script>alert(1)</script>"
        doc["issues"][0]["body"] = "before </script><script>alert(2)</script> after"
        doc["issues"][0]["labels"] = ['"><svg onload=alert(4)>']
    (tmp_path / "facts.json").write_text(json.dumps(doc), encoding="utf-8")
    (tmp_path / "judgements.yaml").write_text(JUDGEMENTS, encoding="utf-8")
    return load_facts(tmp_path / "facts.json"), load_judgements(tmp_path / "judgements.yaml")


def _sections(page: str) -> list[str]:
    return re.findall(r'<section class="tier\b[^"]*"[^>]*data-tier="([^"]+)"', page)


def _row(page: str, key: str) -> str:
    m = re.search(rf'<details class="row"[^>]*data-key="{re.escape(key)}"[^>]*>', page)
    assert m is not None, f"no row for {key}"
    return m.group(0)


def _section_of(page: str, key: str) -> str:
    idx = page.index(f'data-key="{key}"')
    found: list[str] = re.findall(
        r'<section class="tier\b[^"]*"[^>]*data-tier="([^"]+)"', page[:idx]
    )
    return found[-1]


def test_an_unranked_issue_renders_in_the_first_tier_labelled_not_yet_triaged(
    tmp_path: Path,
) -> None:
    page = render(*_state(tmp_path))

    assert _sections(page)[0] == "unranked"
    assert _section_of(page, "super-fr#535") == "unranked"
    first = page[page.index('data-tier="unranked"') : page.index('data-tier="1"')]
    assert "not yet triaged" in first
    assert "fr-triage" in first


def test_a_judged_issue_renders_in_its_own_tier_with_its_data_attributes(
    tmp_path: Path,
) -> None:
    page = render(*_state(tmp_path))

    assert _sections(page) == ["unranked", "1", "2"]
    assert _section_of(page, "super-fr#529") == "1"
    assert _section_of(page, "super-fr#333") == "2"
    row = _row(page, "super-fr#529")
    for attr in ('data-tier="1"', 'data-cx="S"', 'data-theme="isolation"', "data-stage="):
        assert attr in row


def test_stage_comes_from_the_model_not_from_facts_json(tmp_path: Path) -> None:
    """r-p2-render-model: stage is derived, never on disk — yet every row carries it."""
    facts, judgements = _state(tmp_path)
    page = render(facts, judgements)

    assert '"stage"' not in (tmp_path / "facts.json").read_text(encoding="utf-8")
    for issue in facts.issues:
        assert f'data-stage="{issue.stage}"' in _row(page, issue.key)
    assert 'data-stage="pr-draft"' in _row(page, "super-fr#529")
    assert 'data-stage="blocked"' in _row(page, "super-fr#333")


def test_hostile_facts_render_inert_and_never_inside_a_script(tmp_path: Path) -> None:
    page = render(*_state(tmp_path, hostile=True))

    assert "<script>alert(1)" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "</script><script>alert(2)" not in page
    assert "<img src=x" not in page and "<svg onload" not in page
    assert "<code>self_heal()</code>" in page and "<strong>fresh</strong>" in page
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", page, flags=re.S | re.I)
    assert len(scripts) == 1, "exactly one script element: the viewer's"
    for needle in ("alert", "super-fr#", "Explainer", "isolation"):
        assert needle not in scripts[0]


def test_two_renders_are_byte_identical_whatever_the_clock_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    facts, judgements = _state(tmp_path)

    def at(moment: _dt.datetime) -> str:
        class Frozen(_dt.datetime):
            @classmethod
            def now(cls, tz: _dt.tzinfo | None = None) -> Frozen:
                return cls.fromtimestamp(moment.timestamp(), tz)

            @classmethod
            def today(cls) -> Frozen:
                return cls.fromtimestamp(moment.timestamp())

        monkeypatch.setattr(_dt, "datetime", Frozen)
        monkeypatch.setattr("time.time", lambda: moment.timestamp())
        return render(facts, judgements)

    first = at(_dt.datetime(2020, 1, 1, tzinfo=_dt.UTC))
    second = at(_dt.datetime(2031, 6, 30, 23, 59, tzinfo=_dt.UTC))
    assert first == second


def test_render_reads_no_clock() -> None:
    """The structural half of determinism: render.py imports neither clock."""
    source = (Path(render.__code__.co_filename)).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+(time|datetime)\b", source, flags=re.M)


def test_the_page_carries_collected_at_and_ranked_at(tmp_path: Path) -> None:
    facts, judgements = _state(tmp_path)
    page = render(facts, judgements)

    assert facts.collected_at in page
    assert "2026-09-19" in page and "ranked" in page


def test_the_page_is_self_contained_and_themed(tmp_path: Path) -> None:
    page = render(*_state(tmp_path))

    assert "--accent: #2F6F5E" in page
    assert "@media (prefers-color-scheme: dark)" in page
    assert "IBM Plex Sans" in page and "system-ui" in page
    assert 'name="viewport"' in page
    assert "localStorage" in page and "try" in page


# ------------------------------------------------------------- P3.T4 command


def _render_cmd(tmp_path: Path, *extra: str) -> Any:
    return CliRunner().invoke(
        app, ["triage", "render", "--repo", "derio-net/super-fr", "--dir", str(tmp_path), *extra]
    )


def test_render_writes_triage_html_and_exits_0(tmp_path: Path) -> None:
    facts, judgements = _state(tmp_path)
    result = _render_cmd(tmp_path)

    assert result.exit_code == 0, result.output
    out = tmp_path / "triage.html"
    assert out.read_text(encoding="utf-8") == render(facts, judgements)


def test_render_open_hands_the_file_uri_to_webbrowser_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state(tmp_path)
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url, *a, **k: opened.append(url) or True)
    result = _render_cmd(tmp_path, "--open")

    assert result.exit_code == 0, result.output
    assert opened == [(tmp_path / "triage.html").resolve().as_uri()]


def test_render_without_judgements_renders_everything_unranked(tmp_path: Path) -> None:
    _state(tmp_path)
    (tmp_path / "judgements.yaml").unlink()
    result = _render_cmd(tmp_path)

    assert result.exit_code == 0, result.output
    page = (tmp_path / "triage.html").read_text(encoding="utf-8")
    assert _sections(page) == ["unranked"]
    assert _section_of(page, "super-fr#529") == "unranked"


def test_render_without_facts_names_the_collect_command(tmp_path: Path) -> None:
    result = _render_cmd(tmp_path)

    assert result.exit_code != 0
    assert "fr triage collect --repo derio-net/super-fr" in result.output
    assert not (tmp_path / "triage.html").exists()


# ------------------------------------------- review r-p3-row-overclaims
#
# The acceptance row triage-untrusted-text-inert claims every forge- or
# judgement-sourced string is inert. The hostile test above covers element
# content only; these cover the attribute, href and masthead/tier/pattern
# contexts. Each was proven non-vacuous by mutating render.py (dropping the
# esc() or loosening _safe_url) and watching it go red.

PAYLOAD = '"><img src=x onerror=alert(9)>'
PAYLOAD_RAW = "<img src=x onerror=alert(9)>"
PAYLOAD_ESCAPED = "&quot;&gt;&lt;img src=x onerror=alert(9)&gt;"


class _Elements(HTMLParser):
    """Every start tag's attributes, as the browser's tokenizer would see them."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))


def _elements(page: str) -> list[tuple[str, dict[str, str | None]]]:
    parser = _Elements()
    parser.feed(page)
    return parser.tags


def _state_with(
    tmp_path: Path,
    *,
    facts_edit: Callable[[dict[str, Any]], None] = lambda d: None,
    judgements_edit: Callable[[dict[str, Any]], None] = lambda d: None,
) -> tuple[Facts, Judgements]:
    """`_state`, with the raw facts and judgements documents edited before loading."""
    from fr.triage.collect import collect_facts

    doc = collect_facts(_super_fr_forge(), SUPER_FR, now=NOW).to_json()
    facts_edit(doc)
    jdoc = yaml.safe_load(JUDGEMENTS)
    judgements_edit(jdoc)
    (tmp_path / "facts.json").write_text(json.dumps(doc), encoding="utf-8")
    (tmp_path / "judgements.yaml").write_text(yaml.safe_dump(jdoc), encoding="utf-8")
    return load_facts(tmp_path / "facts.json"), load_judgements(tmp_path / "judgements.yaml")


def _row_block(page: str, key: str) -> str:
    start = page.index(f'data-key="{key}"')
    return page[start : page.index("</details>", start)]


def test_a_title_cannot_break_out_of_the_data_search_attribute(tmp_path: Path) -> None:
    title = 'x" onmouseover="alert(1)'

    def edit(doc: dict[str, Any]) -> None:
        doc["issues"][0]["title"] = title

    facts, judgements = _state_with(tmp_path, facts_edit=edit)
    key = facts.issues[0].key
    page = render(facts, judgements)

    assert '" onmouseover="' not in page
    assert "x&quot; onmouseover=&quot;alert(1)" in _row(page, key)
    for _, attrs in _elements(page):
        assert not any(name.startswith("on") for name in attrs), attrs
    rows = [a for t, a in _elements(page) if t == "details" and a.get("data-key") == key]
    assert len(rows) == 1
    assert rows[0]["data-search"] is not None and title in rows[0]["data-search"]


@pytest.mark.parametrize(
    "url",
    ["javascript:alert(1)", "HTTPS://x.example", "  https://x.example", "data:text/html,x"],
)
def test_a_non_https_url_produces_no_href(tmp_path: Path, url: str) -> None:
    def edit(doc: dict[str, Any]) -> None:
        issue = next(i for i in doc["issues"] if i["prs"])
        issue["url"] = url
        for pr in issue["prs"]:
            pr["url"] = url

    facts, judgements = _state_with(tmp_path, facts_edit=edit)
    issue = next(i for i in facts.issues if i.prs)
    page = render(facts, judgements)

    block = _row_block(page, issue.key)
    assert "href=" not in block
    assert f"issue #{issue.number}" not in block
    hrefs = [a.get("href") for t, a in _elements(page) if t == "a"]
    assert all(h is None or h.startswith("https://") for h in hrefs), hrefs


def _hostile_theme(facts: dict[str, Any], judgements: dict[str, Any]) -> None:
    judgements["issues"]["super-fr#529"]["theme"] = PAYLOAD


def _hostile_tier_title(facts: dict[str, Any], judgements: dict[str, Any]) -> None:
    judgements["tiers"][0]["title"] = PAYLOAD


def _hostile_tier_description(facts: dict[str, Any], judgements: dict[str, Any]) -> None:
    judgements["tiers"][0]["description"] = PAYLOAD


def _hostile_pattern_title(facts: dict[str, Any], judgements: dict[str, Any]) -> None:
    judgements["patterns"][0]["title"] = PAYLOAD


def _hostile_skipped(facts: dict[str, Any], judgements: dict[str, Any]) -> None:
    facts["skipped"] = [{"repo": "derio-net/" + PAYLOAD, "reason": PAYLOAD}]


def _hostile_unviewed_reason(facts: dict[str, Any], judgements: dict[str, Any]) -> None:
    facts["unviewed"] = [{"key": "super-fr#99999", "reason": PAYLOAD}]
    judgements["issues"]["super-fr#99999"] = {"tier": 2, "cx": "S"}


def _hostile_scope(facts: dict[str, Any], judgements: dict[str, Any]) -> None:
    facts["scope"] = PAYLOAD


@pytest.mark.parametrize(
    "edit",
    [
        _hostile_theme,
        _hostile_tier_title,
        _hostile_tier_description,
        _hostile_pattern_title,
        _hostile_skipped,
        _hostile_unviewed_reason,
        _hostile_scope,
    ],
    ids=lambda f: f.__name__.removeprefix("_hostile_"),
)
def test_hostile_text_in_every_context_renders_escaped(
    tmp_path: Path, edit: Callable[[dict[str, Any], dict[str, Any]], None]
) -> None:
    holder: dict[str, dict[str, Any]] = {}
    facts, judgements = _state_with(
        tmp_path,
        facts_edit=lambda d: holder.setdefault("facts", d),
        judgements_edit=lambda d: edit(holder["facts"], d),
    )
    page = render(facts, judgements)

    assert PAYLOAD_RAW not in page
    assert PAYLOAD_ESCAPED in page
    assert not any(t == "img" for t, _ in _elements(page))


def test_hostile_pattern_ids_render_escaped_even_past_the_loader(tmp_path: Path) -> None:
    """The loader refuses a non-key id (r-p2-pattern-ids); the renderer does not rely on it."""
    facts, judgements = _state(tmp_path)
    pattern = judgements.patterns[0].model_copy(update={"ids": ["super-fr#529", PAYLOAD]})
    page = render(facts, judgements.model_copy(update={"patterns": [pattern]}))

    assert PAYLOAD_RAW not in page
    assert PAYLOAD_ESCAPED in page
    assert not any(t == "img" for t, _ in _elements(page))
