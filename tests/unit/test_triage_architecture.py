"""`fr triage architecture render` (wave-driver R11, R12, R16, R20; Test Plan 10).

The measured figures are worked out BY HAND below, never by the code under test. The
fixture repo is a real throwaway git repo under tmp_path with two refs; the repo under
test is never read or written. Fictional owner and repo (`example-org/widgets`).

Fixture repo, by hand (a line is one `\\n`-terminated row):

    ref `then`   core/a.py 3 lines   core/b.py 2   cli/main.py 5   docs/readme.md 4
    ref `HEAD`   core/a.py 6 lines   core/b.py 2   cli/main.py 5   docs/readme.md 4
                 core/c.py 4 (new)

    core  (core/**)     then 2 files /  5 lines    now 3 files / 12 lines
    cli   (cli/*.py)    then 1 file  /  5 lines    now 1 file  /  5 lines
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.triage.architecture import (
    GENERATED,
    Measure,
    Subsystems,
    load_subsystems,
    measure_subsystems,
    render_architecture,
    resolve_manifest,
)
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout
from fr.triage.model import Facts, Judgements
from fr.triage.origins import Origins, OriginsFacts, load_origins
from fr.triage.snapshot import Snapshot, store_snapshot, stored_snapshots, take_snapshot
from fr.triage.views import needs_you
from typer.testing import CliRunner

from tests.unit.triage_board_fixtures import REPO, busy
from tests.unit.triage_origins_fixtures import ROWS, SINCE, classification_yaml

SCOPE = "example-org/widgets"
DASH = "—"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _write(root: Path, files: dict[str, int]) -> None:
    for name, lines in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(f"row {n}\n" for n in range(lines)), encoding="utf-8")


@pytest.fixture
def checkout(tmp_path: Path) -> Checkout:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "--initial-branch=main")
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(repo, "config", k, v)
    _write(repo, {"core/a.py": 3, "core/b.py": 2, "cli/main.py": 5, "docs/readme.md": 4})
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "-m", "then")
    _git(repo, "tag", "then")
    _write(repo, {"core/a.py": 6, "core/c.py": 4})
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "-m", "now")
    return Checkout(repo)


SUBSYSTEMS = {
    "subsystems": [
        {"name": "core", "path": ["core/**"], "then_ref": "then", "themes": ["engine"]},
        {"name": "cli", "path": ["cli/*.py"], "then_ref": "then", "themes": ["cli"]},
    ]
}


def _subsystems() -> Subsystems:
    return Subsystems.model_validate(SUBSYSTEMS)


# ------------------------------------------------------------------- measurements


def test_line_counts_per_subsystem_at_then_and_now_name_their_commits(
    checkout: Checkout,
) -> None:
    measured = measure_subsystems(checkout, _subsystems(), now_ref="HEAD")
    then_sha = _git(checkout.path, "rev-parse", "--short", "then")
    now_sha = _git(checkout.path, "rev-parse", "--short", "HEAD")
    assert then_sha != now_sha
    assert measured["core"].then == Measure(ref="then", commit=then_sha, files=2, lines=5)
    assert measured["core"].now == Measure(ref="HEAD", commit=now_sha, files=3, lines=12)
    assert measured["cli"].then == Measure(ref="then", commit=then_sha, files=1, lines=5)
    assert measured["cli"].now == Measure(ref="HEAD", commit=now_sha, files=1, lines=5)


def test_an_unresolvable_then_ref_is_missing_never_zero(checkout: Checkout) -> None:
    subs = Subsystems.model_validate(
        {"subsystems": [{"name": "core", "path": ["core/**"], "then_ref": "no-such-ref"}]}
    )
    measured = measure_subsystems(checkout, subs, now_ref="HEAD")
    assert measured["core"].then is None
    assert measured["core"].now is not None and measured["core"].now.lines == 12


def test_a_glob_that_matches_nothing_is_missing_never_zero(checkout: Checkout) -> None:
    subs = Subsystems.model_validate(
        {"subsystems": [{"name": "ghost", "path": ["nope/**"], "then_ref": "then"}]}
    )
    measured = measure_subsystems(checkout, subs, now_ref="HEAD")
    assert measured["ghost"].then is None and measured["ghost"].now is None


def test_subsystems_yaml_is_optional_and_a_bad_one_is_refused(tmp_path: Path) -> None:
    assert load_subsystems(tmp_path / "subsystems.yaml").subsystems == []
    bad = tmp_path / "subsystems.yaml"
    bad.write_text("subsystems:\n  - name: core\n", encoding="utf-8")  # no path, no then_ref
    with pytest.raises(TriageError, match="subsystems.yaml"):
        load_subsystems(bad)


@pytest.fixture
def edgy(tmp_path: Path) -> Checkout:
    """A repo with every edge the measurement must classify, committed once."""
    repo = tmp_path / "edgy"
    repo.mkdir()
    _git(repo, "init", "--quiet", "--initial-branch=main")
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(repo, "config", k, v)
    _write(repo, {"src/plain.py": 3})
    (repo / "src" / "blob.bin").write_bytes(b"\x00\x01\x02\xff" * 64 + b"\nmore\n")
    (repo / "src" / "caf\u00e9.py").write_text("one\ntwo\n", encoding="utf-8")
    (repo / "src" / "ff.txt").write_text("a\x0cb\nc\u2028d\ne\n", encoding="utf-8")
    (repo / "src" / "empty.py").write_text("", encoding="utf-8")
    (repo / "src" / "link.py").symlink_to("plain.py")
    _git(repo, "add", ".")
    # a gitlink entry, as a submodule leaves in the tree (no .gitmodules needed)
    _git(
        repo, "update-index", "--add", "--cacheinfo",
        "160000,1234567890123456789012345678901234567890,src/vendored",
    )  # fmt: skip
    _git(repo, "commit", "--quiet", "-m", "edge")
    return Checkout(repo)


def _src(checkout: Checkout) -> Measure | None:
    subs = Subsystems.model_validate(
        {"subsystems": [{"name": "src", "path": ["src/**"], "then_ref": "HEAD"}]}
    )
    return measure_subsystems(checkout, subs, now_ref="HEAD")["src"].now


def test_binaries_symlinks_and_submodules_are_not_counted(edgy: Checkout) -> None:
    m = _src(edgy)
    assert m is not None
    # plain.py 3 + café.py 2 + ff.txt 3 (form feed and U+2028 are not line breaks) + empty 0
    assert (m.files, m.lines) == (4, 8)


def test_a_non_ascii_path_is_counted_not_quoted_away(edgy: Checkout) -> None:
    subs = Subsystems.model_validate(
        {"subsystems": [{"name": "cafe", "path": ["src/caf*"], "then_ref": "HEAD"}]}
    )
    now = measure_subsystems(edgy, subs, now_ref="HEAD")["cafe"].now
    assert now is not None and (now.files, now.lines) == (1, 2)


def test_measurement_spawns_a_constant_number_of_processes(
    edgy: Checkout, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.triage.gitseam as seam

    calls: list[list[str]] = []
    real = subprocess.run

    def spy(argv: list[str], *a: Any, **k: Any) -> Any:
        calls.append(list(argv))
        return real(argv, *a, **k)

    monkeypatch.setattr(seam.subprocess, "run", spy)
    _src(edgy)
    assert len(calls) <= 5, calls  # not per file


def test_the_binary_decode_failure_is_a_dash_never_a_crash(
    edgy: Checkout, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: Checkout, ref: str) -> Any:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(Checkout, "text_line_counts", boom)
    assert _src(edgy) is None


# ---------------------------------------------------------------- the page itself


def _snapshots(f: Facts, jd: Judgements, n: int) -> list[tuple[datetime, Snapshot]]:
    base = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)
    out = []
    for step in range(n):
        shown = Facts.model_validate(
            {
                **f.model_dump(by_alias=True, mode="json"),
                "issues": [i.model_dump(mode="json") for i in f.issues[: len(f.issues) - step]],
            }
        )
        out.append((base + timedelta(days=step), take_snapshot(shown, jd, acceptance=None)))
    return out


def _page(
    *,
    snaps: int = 3,
    fragments: list[tuple[str, str]] | None = None,
    sections: list[str] | None = None,
    notes: list[str] | None = None,
    measured: Any = None,
    origins: bool = False,
) -> str:
    f, jd = busy()
    jd = Judgements.model_validate(
        {
            **jd.model_dump(by_alias=True, mode="json", exclude_none=True),
            "issues": {
                k: {**v, "theme": "engine" if n % 2 else "cli" if n % 3 == 0 else "stray"}
                for n, (k, v) in enumerate(
                    jd.model_dump(mode="json", exclude_none=True)["issues"].items()
                )
            },
        }
    )
    of = oc = None
    if origins:
        of = _origins_facts()
        oc = load_origins_from_text(classification_yaml())
    return render_architecture(
        f,
        jd,
        origins_facts=of,
        origins=oc,
        subsystems=_subsystems(),
        measured=measured or {},
        fragments=dict(fragments or []),
        order=[
            *(sections if sections is not None else GENERATED),
            *(n for n, _ in fragments or []),
        ],
        snapshots=_snapshots(f, jd, snaps),
        notes=notes or [],
    )


def load_origins_from_text(text: str) -> Origins:
    path = Path(tempfile.mkdtemp()) / "origins.yaml"
    path.write_text(text, encoding="utf-8")
    return load_origins(path)


def _origins_facts() -> OriginsFacts:
    return OriginsFacts.model_validate(
        {
            "scope": "example-org--widgets",
            "since": SINCE,
            "collected_at": "2026-09-30T00:00:00+00:00",
            "issues": [
                {
                    "key": f"widgets#{n}",
                    "repo": REPO,
                    "number": n,
                    "title": f"Widget defect {n}",
                    "url": f"https://github.com/{REPO}/issues/{n}",
                    "created_at": created,
                    "closed_at": closed,
                    "state": "closed" if closed else "open",
                }
                for n, created, closed, _reason, *_ in ROWS
            ],
        }
    )


def _pos(page: str, needle: str) -> int:
    i = page.find(needle)
    assert i >= 0, f"{needle!r} not on the page"
    return i


def test_page_has_a_real_title_the_three_theme_blocks_and_the_gutter() -> None:
    page = _page()
    assert re.search(r"<title>Architecture · example-org--widgets</title>", page)
    assert ":root {" in page
    assert "@media (prefers-color-scheme: dark)" in page
    assert ':root[data-theme="light"]' in page and ':root[data-theme="dark"]' in page
    assert re.search(
        r"max-width: 480px\) \{\s*main \{ padding-left: 16px; padding-right: 16px", page
    )
    assert page.count("<script>") == 1


def test_the_sections_follow_r20_timeline_then_measured_then_authored() -> None:
    page = _page(fragments=[("overview.html", "<p>hand drawn</p>")])
    order = [
        'id="snapshot-timeline"',
        'id="summary"',
        'id="waves"',
        'id="subsystems"',
        'id="size-table"',
        'id="filings-per-day"',
        'id="operator-actions"',
        'data-fragment="overview.html"',
    ]
    # filings-per-day needs origins facts, which this page has none of: absent, not misplaced.
    present = [o for o in order if o != 'id="filings-per-day"']
    positions = [_pos(page, o) for o in present]
    assert positions == sorted(positions)


def test_waves_are_the_shared_tabs_with_the_latest_wave_preselected() -> None:
    page = _page()
    waves = page[_pos(page, 'id="waves"') : _pos(page, 'id="subsystems"')]
    assert "data-tabs" in waves
    # busy() has waves 1, 2, 3 and wave 3 still has live batches: it is preselected.
    assert re.search(r'id="wave-tab-3"[^>]*aria-selected="true"', waves)
    assert re.search(r'id="wave-tab-1"[^>]*aria-selected="false"', waves)
    # With scripts off every wave is shown, each labelled by its own heading.
    for n in (1, 2, 3):
        assert f'<h3 class="panel-label">Wave {n}</h3>' in waves
    assert "hidden" not in re.findall(r'<div role="tabpanel"[^>]*>', waves)[0]


def test_the_snapshot_timeline_steps_through_stored_snapshots() -> None:
    page = _page(snaps=4)
    tl = page[_pos(page, 'id="snapshot-timeline"') : _pos(page, 'id="summary"')]
    assert "data-tabs" in tl
    assert len(re.findall(r'role="tabpanel"', tl)) == 4
    assert re.search(r'aria-selected="true"[^>]*>2026-09-28', tl)  # newest preselected
    assert "2026-09-25" in tl


@pytest.mark.parametrize("n", [0, 1])
def test_fewer_than_two_snapshots_falls_back_with_a_sentence(n: int) -> None:
    page = _page(snaps=n)
    tl = page[_pos(page, 'id="snapshot-timeline"') : _pos(page, 'id="summary"')]
    if n == 0:
        assert "No snapshots yet" in tl
    else:
        assert "Only one snapshot" in tl
        assert len(re.findall(r'role="tabpanel"', tl)) == 1


def test_subsystem_cards_place_open_issues_and_the_rest_under_other(
    checkout: Checkout,
) -> None:
    measured = measure_subsystems(checkout, _subsystems(), now_ref="HEAD")
    page = _page(measured=measured)
    cards = page[_pos(page, 'id="subsystems"') : _pos(page, 'id="size-table"')]
    core = re.search(r'<article class="subsystem" data-subsystem="core".*?</article>', cards, re.S)
    other = re.search(
        r'<article class="subsystem" data-subsystem="Other".*?</article>', cards, re.S
    )
    assert core and other
    # busy() open issues: 3,4,5,6,7,8,9,10,11,12,13 (1 and 2 are closed). Themes follow the
    # test's own rule: odd index -> engine, index % 3 == 0 -> cli, else stray.
    assert 'data-issue="widgets#1"' not in cards and 'data-issue="widgets#2"' not in cards
    placed = set(re.findall(r'data-issue="([^"]+)"', cards))
    assert placed == {f"widgets#{n}" for n in range(3, 14)}  # #9 is unjudged: it is in Other
    assert 'data-issue="widgets#9"' in other.group(0)
    # core's own numbers: 5 lines then, 12 now, both commits named.
    assert "5" in core.group(0) and "12" in core.group(0)
    assert measured["core"].then and measured["core"].then.commit in core.group(0)


def test_every_open_issue_lands_somewhere_never_dropped() -> None:
    page = _page()
    cards = page[_pos(page, 'id="subsystems"') : _pos(page, 'id="size-table"')]
    f, _ = busy()
    open_keys = {i.key for i in f.issues if i.state == "open"}
    assert open_keys <= set(re.findall(r'data-issue="([^"]+)"', cards))


def test_the_size_table_shows_dashes_for_what_was_not_measured() -> None:
    page = _page(measured={})
    table = page[_pos(page, 'id="size-table"') : _pos(page, 'id="operator-actions"')]
    assert DASH in table
    assert "<td>0</td>" not in table
    assert '<div class="scroll"><table' in table  # its own overflow wrapper


def test_the_size_table_and_bars_carry_the_measured_numbers(checkout: Checkout) -> None:
    measured = measure_subsystems(checkout, _subsystems(), now_ref="HEAD")
    page = _page(measured=measured)
    table = page[_pos(page, 'id="size-table"') : _pos(page, 'id="operator-actions"')]
    row = re.search(r'<tr data-subsystem="core">.*?</tr>', table, re.S)
    assert row
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row.group(0), re.S)
    text = " ".join(cells)
    for expected in ("2", "5", "3", "12", "+7"):
        assert expected in text.split(), (expected, text)
    # bars are drawn to scale: the longest (core, now: 12) is 100%, core then is 5/12.
    cards = page[_pos(page, 'id="subsystems"') : _pos(page, 'id="size-table"')]
    assert 'data-lines="12" style="width:100.0%"' in cards
    assert 'data-lines="5" style="width:41.7%"' in cards


def test_the_summary_strip_names_its_sources_and_dashes_what_is_absent() -> None:
    page = _page()
    strip = page[_pos(page, 'id="summary"') : _pos(page, 'id="waves"')]
    f, _ = busy()
    open_n = sum(1 for i in f.issues if i.state == "open")
    assert f'data-figure="open issues"><b>{open_n}</b>' in strip
    assert 'data-figure="defects"' in strip
    assert 'data-figure="batches merged"><b>1</b>' in strip  # busy(): only a-merged
    assert f'data-figure="issues filed"><b>{DASH}</b>' in strip  # no origins facts
    assert "facts.json" in strip and "judgements.yaml" in strip


def test_origins_sections_appear_only_when_origins_exist() -> None:
    without = _page()
    assert 'id="origin-counts"' not in without and 'id="filings-per-day"' not in without
    with_ = _page(origins=True)
    assert 'id="origin-counts"' in with_ and 'id="filings-per-day"' in with_
    chart = with_[_pos(with_, 'id="filings-per-day"') :]
    assert '<div class="scroll"><svg class="chart"' in chart  # natural size, own wrapper
    assert 'data-figure="issues filed"><b>15</b>' in with_


def test_operator_actions_are_the_boards_needs_you_now_rows() -> None:
    page = _page()
    actions = page[_pos(page, 'id="operator-actions"') :]
    f, jd = busy()
    rows = needs_you(f, jd)
    assert rows
    assert len(re.findall(r'<li class="need"', actions)) == len(rows)
    for r in rows:
        assert f'data-need="{r.kind}" data-ref="{r.ref}"' in actions


def test_fragments_are_inlined_in_manifest_order_each_in_its_own_wrapper() -> None:
    page = _page(fragments=[("zeta.html", "<p>ZETA</p>"), ("alpha.html", "<svg><circle/></svg>")])
    z, a = _pos(page, "ZETA"), _pos(page, "<circle/>")
    assert z < a  # manifest order, not alphabetical
    assert re.search(
        r'<section class="fragment" data-fragment="zeta.html"><div class="scroll"><p>ZETA</p>', page
    )


def test_a_missing_manifest_entry_is_shown_on_the_page() -> None:
    page = _page(notes=["manifest entry diagram.html has no file"])
    assert "manifest entry diagram.html has no file" in page


def test_no_horizontal_page_scroll_rules_are_present() -> None:
    page = _page()
    assert "overflow-x: hidden" in page
    assert ".scroll { overflow-x: auto; }" in page


def test_a_long_unbreakable_token_wraps_inside_its_subsystem_card() -> None:
    """gh#901: at 400px an issue title carrying a long test name overflowed its card.

    `min-width: 0` keeps the card in its grid track, but the text inside it still
    needs a break opportunity, or `html { overflow-x: hidden }` clips it. The rule
    sits on the card so the title, the subsystem name and the path list all wrap.
    """
    from fr.triage.architecture import CSS

    m = re.search(r"^article\.subsystem \{([^}]*)\}", CSS, flags=re.M)
    assert m is not None
    decls = {
        k.strip(): v.strip()
        for k, v in (d.split(":", 1) for d in m.group(1).split(";") if d.strip())
    }
    assert decls.get("min-width") == "0"
    assert decls.get("overflow-wrap") == "anywhere"


# ---------------------------------------------------------------------- manifest


def _arch(tmp_path: Path, manifest: str, **files: str) -> Path:
    d = tmp_path / "architecture"
    d.mkdir()
    (d / "manifest.yaml").write_text(manifest, encoding="utf-8")
    for name, text in files.items():
        (d / name.replace("__", ".")).write_text(text, encoding="utf-8")
    return d


def test_manifest_resolves_generated_names_and_fragment_files_in_order(tmp_path: Path) -> None:
    d = _arch(
        tmp_path,
        "sections:\n  - waves\n  - overview.html\n  - size-table\n  - second.html\n",
        overview__html="<p>one</p>",
        second__html="<p>two</p>",
    )
    resolved = resolve_manifest(d)
    named = ["waves", "overview.html", "size-table", "second.html"]
    assert resolved.order == [*named, *(g for g in GENERATED if g not in named)]
    assert resolved.fragments == {"overview.html": "<p>one</p>", "second.html": "<p>two</p>"}
    assert resolved.missing == []


def test_a_manifest_entry_with_no_file_is_reported(tmp_path: Path) -> None:
    d = _arch(tmp_path, "sections:\n  - summary\n  - gone.html\n")
    resolved = resolve_manifest(d)
    assert resolved.missing == ["gone.html"]
    assert "gone.html" not in resolved.fragments


def test_a_malformed_fragment_is_refused_and_named(tmp_path: Path) -> None:
    d = _arch(
        tmp_path, "sections:\n  - ok.html\n  - bad.html\n",
        ok__html="<p>fine</p>", bad__html="<div><p>never closed</div>",
    )  # fmt: skip
    with pytest.raises(TriageError, match=r"bad\.html"):
        resolve_manifest(d)


@pytest.mark.parametrize(
    "text",
    ["<div>open", "</p>", "<ul><li>x</ul>", "<svg><g></svg>", "<html><body>x</body></html>",
     "<script>alert(1)</script>"],
)  # fmt: skip
def test_malformed_or_document_level_fragments_are_refused(tmp_path: Path, text: str) -> None:
    d = _arch(tmp_path, "sections:\n  - f.html\n", f__html=text)
    with pytest.raises(TriageError, match=r"f\.html"):
        resolve_manifest(d)


def test_well_formed_fragments_with_void_and_self_closing_tags_pass(tmp_path: Path) -> None:
    d = _arch(
        tmp_path,
        "sections:\n  - f.html\n",
        f__html=(
            '<p>a<br>b</p><img src="x.png" alt=""><svg viewBox="0 0 4 4"><path d="M0 0"/></svg>'
        ),
    )
    assert "f.html" in resolve_manifest(d).fragments


@pytest.mark.parametrize(
    "text",
    [
        "<style>p{color:red}</style>",
        '<link rel="stylesheet" href="x.css">',
        '<iframe src="https://example.com"></iframe>',
        '<object data="x.swf"></object>',
        '<embed src="x.swf">',
        '<meta http-equiv="refresh" content="0">',
        '<base href="https://example.com/">',
        '<form action="/x"><p>x</p></form>',
        "<head><p>x</p></head>",
        "<body><p>x</p></body>",
        "<title>Page</title>",
        '<p onclick="go()">x</p>',
        '<svg><g onload="go()"></g></svg>',
        '<a href="javascript:alert(1)">x</a>',
        '<a href="  JaVa\tScript:alert(1)">x</a>',
        '<img src="data:text/html;base64,AAAA" alt="">',
        '<svg><a xlink:href="javascript:alert(1)"><text>x</text></a></svg>',
    ],
)
def test_forbidden_constructs_are_each_refused(tmp_path: Path, text: str) -> None:
    d = _arch(tmp_path, "sections:\n  - f.html\n", f__html=text)
    with pytest.raises(TriageError, match=r"f\.html"):
        resolve_manifest(d)


def test_a_title_inside_an_svg_is_an_accessible_name_and_allowed(tmp_path: Path) -> None:
    d = _arch(
        tmp_path,
        "sections:\n  - f.html\n",
        f__html='<svg viewBox="0 0 4 4"><title>Flow of work</title><rect/></svg>',
    )
    assert "f.html" in resolve_manifest(d).fragments


def test_ordinary_links_and_https_urls_are_allowed(tmp_path: Path) -> None:
    d = _arch(
        tmp_path,
        "sections:\n  - f.html\n",
        f__html=(
            '<p><a href="https://example.com/x">x</a> '
            '<img src="data:image/png;base64,AA" alt=""></p>'
        ),
    )
    assert "f.html" in resolve_manifest(d).fragments


def test_a_self_closing_non_void_html_tag_is_refused_with_line_and_tag(tmp_path: Path) -> None:
    d = _arch(tmp_path, "sections:\n  - f.html\n", f__html="<p>a</p>\n<div/>\n")
    with pytest.raises(TriageError, match=r"<div/>.*line 2|line 2.*<div/>"):
        resolve_manifest(d)


def test_self_closing_is_fine_on_svg_shapes(tmp_path: Path) -> None:
    d = _arch(tmp_path, "sections:\n  - f.html\n", f__html="<svg><g/><circle/></svg><br/>")
    assert "f.html" in resolve_manifest(d).fragments


def test_a_manifest_naming_only_fragments_keeps_every_generated_section(tmp_path: Path) -> None:
    d = _arch(tmp_path, "sections:\n  - one.html\n", one__html="<p>1</p>")
    resolved = resolve_manifest(d)
    assert resolved.order == ["one.html", *GENERATED]
    assert resolved.appended == list(GENERATED)
    page = _page(fragments=[("one.html", "<p>1</p>")])
    assert _pos(page, 'id="summary"') < _pos(page, 'data-fragment="one.html"')  # groups fixed


def test_appended_sections_are_reported_on_the_page_by_the_command(
    tmp_path: Path, checkout: Checkout
) -> None:
    state = _state(tmp_path)
    arch = state / "architecture"
    arch.mkdir()
    (arch / "manifest.yaml").write_text("sections:\n  - one.html\n", encoding="utf-8")
    (arch / "one.html").write_text("<p>1</p>", encoding="utf-8")
    result = _run(state, checkout)
    assert result.exit_code == 0, result.output
    page = (state / "architecture.html").read_text(encoding="utf-8")
    assert 'id="summary"' in page and 'id="operator-actions"' in page
    assert "does not name" in page and "summary" in page


def test_a_fragment_path_may_not_leave_the_architecture_directory(tmp_path: Path) -> None:
    d = _arch(tmp_path, "sections:\n  - ../secret.html\n")
    with pytest.raises(TriageError, match="architecture"):
        resolve_manifest(d)


def test_no_manifest_means_every_generated_section_and_no_fragments(tmp_path: Path) -> None:
    resolved = resolve_manifest(tmp_path / "architecture")
    assert resolved.order == list(GENERATED)
    assert resolved.fragments == {} and resolved.missing == []


# ------------------------------------------------------------------ the command


def _state(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    state.mkdir()
    f, jd = busy()
    (state / "facts.json").write_text(json.dumps(f.to_json()), encoding="utf-8")
    (state / "judgements.yaml").write_text(
        yaml.safe_dump(jd.model_dump(mode="json", by_alias=True, exclude_none=True)),
        encoding="utf-8",
    )
    return state


def _run(state: Path, checkout: Checkout, *extra: str) -> Any:
    return CliRunner().invoke(
        app,
        ["triage", "architecture", "render", "--repo", SCOPE, "--dir", str(state),
         "--checkout", str(checkout.path), *extra],
    )  # fmt: skip


def test_render_writes_only_under_the_state_directory(tmp_path: Path, checkout: Checkout) -> None:
    state = _state(tmp_path)
    (state / "subsystems.yaml").write_text(yaml.safe_dump(SUBSYSTEMS), encoding="utf-8")
    before = _git(checkout.path, "status", "--porcelain")
    result = _run(state, checkout)
    assert result.exit_code == 0, result.output
    page = (state / "architecture.html").read_text(encoding="utf-8")
    assert 'data-subsystem="core"' in page
    assert _git(checkout.path, "status", "--porcelain") == before  # the checkout is untouched
    assert sorted(p.name for p in state.iterdir()) == [
        "architecture.html", "facts.json", "judgements.yaml", "subsystems.yaml",
    ]  # fmt: skip


def test_render_reads_stored_snapshots(tmp_path: Path, checkout: Checkout) -> None:
    state = _state(tmp_path)
    f, jd = busy()
    for step in range(3):
        snap = take_snapshot(f, jd, acceptance=None).model_copy(update={"figures": {"open": step}})
        store_snapshot(state, snap, datetime(2026, 9, 25 + step, 9, 0, tzinfo=UTC))
    assert len(stored_snapshots(state)) == 3
    result = _run(state, checkout)
    assert result.exit_code == 0, result.output
    page = (state / "architecture.html").read_text(encoding="utf-8")
    assert len(re.findall(r'id="snapshot-tab-', page)) == 3


def test_render_refuses_a_malformed_fragment_and_writes_nothing(
    tmp_path: Path, checkout: Checkout
) -> None:
    state = _state(tmp_path)
    arch = state / "architecture"
    arch.mkdir()
    (arch / "manifest.yaml").write_text("sections:\n  - bad.html\n", encoding="utf-8")
    (arch / "bad.html").write_text("<div>open", encoding="utf-8")
    result = _run(state, checkout)
    assert result.exit_code == 2
    assert "bad.html" in result.output
    assert not (state / "architecture.html").exists()


def test_render_reports_a_manifest_entry_with_no_file(tmp_path: Path, checkout: Checkout) -> None:
    state = _state(tmp_path)
    arch = state / "architecture"
    arch.mkdir()
    (arch / "manifest.yaml").write_text("sections:\n  - summary\n  - gone.html\n", encoding="utf-8")
    result = _run(state, checkout)
    assert result.exit_code == 0, result.output
    assert "gone.html" in result.output
    assert "gone.html" in (state / "architecture.html").read_text(encoding="utf-8")


def test_render_without_facts_names_collect(tmp_path: Path, checkout: Checkout) -> None:
    state = tmp_path / "empty"
    state.mkdir()
    result = _run(state, checkout)
    assert result.exit_code == 2
    assert "collect" in result.output


def test_render_outside_a_git_checkout_dashes_the_measurements(tmp_path: Path) -> None:
    state = _state(tmp_path)
    (state / "subsystems.yaml").write_text(yaml.safe_dump(SUBSYSTEMS), encoding="utf-8")
    bare = tmp_path / "plain"
    bare.mkdir()
    result = CliRunner().invoke(
        app,
        ["triage", "architecture", "render", "--repo", SCOPE, "--dir", str(state),
         "--checkout", str(bare)],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    page = (state / "architecture.html").read_text(encoding="utf-8")
    table = page[_pos(page, 'id="size-table"') :]
    assert DASH in table


@pytest.mark.parametrize("body", ["{not json", '{"schema": 1}', "\xff\xfe"])
def test_a_corrupt_origins_facts_file_is_exit_2_naming_it(
    tmp_path: Path, checkout: Checkout, body: str
) -> None:
    state = _state(tmp_path)
    (state / "origins-facts.json").write_bytes(body.encode("latin-1"))
    result = _run(state, checkout)
    assert result.exit_code == 2
    assert "origins-facts.json" in result.output
    assert not (state / "architecture.html").exists()


def test_the_page_states_the_counting_rule_and_labels_utc(
    tmp_path: Path, checkout: Checkout
) -> None:
    state = _state(tmp_path)
    (state / "subsystems.yaml").write_text(yaml.safe_dump(SUBSYSTEMS), encoding="utf-8")
    f, jd = busy()
    store_snapshot(state, take_snapshot(f, jd, acceptance=None), datetime(2026, 9, 25, tzinfo=UTC))
    assert _run(state, checkout).exit_code == 0
    page = (state / "architecture.html").read_text(encoding="utf-8")
    assert "binary files, symlinks and submodules are not counted" in page
    assert "a moved file moves its lines between subsystems" in page
    assert "<th>Source lines" not in page and "Source lines" not in page
    assert "UTC" in page[_pos(page, 'id="snapshot-timeline"') : _pos(page, 'id="summary"')]
