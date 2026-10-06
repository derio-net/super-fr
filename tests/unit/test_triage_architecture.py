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
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.triage.architecture import (
    GENERATED,
    MOVED,
    Measure,
    Subsystems,
    load_subsystems,
    measure_subsystems,
    render_architecture,
)
from fr.triage.errors import TriageError
from fr.triage.fragments import Entry, Resolved
from fr.triage.gitseam import Checkout
from fr.triage.model import Judgements
from typer.testing import CliRunner

from tests.unit.triage_board_fixtures import busy

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


def _page(
    *,
    fragments: list[tuple[str, str]] | None = None,
    sections: list[str] | None = None,
    notes: list[str] | None = None,
    measured: Any = None,
    subsystems: Subsystems | None = None,
    entries: list[Entry] | None = None,
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
    order = entries or [
        *(Entry(n) for n in (sections if sections is not None else GENERATED)),
        *(Entry(n) for n, _ in fragments or []),
    ]
    return render_architecture(
        f,
        jd,
        subsystems=subsystems or _subsystems(),
        measured=measured or {},
        resolved=Resolved(order=order, fragments=dict(fragments or [])),
        notes=notes or [],
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
    assert "<script>" not in page  # no tabs here any more, so no script


def test_the_sections_are_summary_cards_size_table_then_authored() -> None:
    page = _page(fragments=[("overview.html", "<p>hand drawn</p>")])
    order = ['id="summary"', 'id="subsystems"', 'id="size-table"', 'data-fragment="overview.html"']
    positions = [_pos(page, o) for o in order]
    assert positions == sorted(positions)


def test_the_page_no_longer_shows_what_other_pages_own() -> None:
    page = _page()
    for gone in (
        "snapshot-timeline",
        'id="waves"',
        "filings-per-day",
        "origin-counts",
        "operator-actions",
    ):
        assert gone not in page, gone


def test_the_page_opens_with_its_nav_and_goal() -> None:
    page = _page()
    assert 'aria-current="page"' in page and 'href="history.html"' in page
    assert re.search(r'class="goal">What is the system, and where does it hurt\?<', page)
    assert page.index("</header>") < page.index('class="pages"') < page.index('id="summary"')


def test_a_fragment_between_generated_sections_renders_there() -> None:
    page = _page(
        entries=[Entry("summary"), Entry("mid.html"), Entry("subsystems"), Entry("size-table")],
        fragments=[("mid.html", "<p>MID</p>")],
    )
    at = [_pos(page, x) for x in ('id="summary"', "MID", 'id="subsystems"', 'id="size-table"')]
    assert at == sorted(at)


def test_the_summary_shows_lines_then_and_now_summed_over_the_measured(
    checkout: Checkout,
) -> None:
    measured = measure_subsystems(checkout, _subsystems(), now_ref="HEAD")
    page = _page(measured=measured)
    strip = page[_pos(page, 'id="summary"') : _pos(page, 'id="subsystems"')]
    then = sum(m.then.lines for m in measured.values() if m.then)
    now = sum(m.now.lines for m in measured.values() if m.now)
    assert f'data-figure="lines then"><b>{then}</b>' in strip
    assert f'data-figure="lines now"><b>{now}</b>' in strip


def test_unmeasured_lines_are_dashes_in_the_summary() -> None:
    page = _page(measured={})
    strip = page[_pos(page, 'id="summary"') : _pos(page, 'id="subsystems"')]
    assert f'data-figure="lines then"><b>{DASH}</b>' in strip
    assert f'data-figure="lines now"><b>{DASH}</b>' in strip


def test_where_it_hurts_lists_the_three_subsystems_with_most_open_defects() -> None:
    from fr.triage.architecture import Subsystem

    f, jd = busy()
    raw = jd.model_dump(by_alias=True, mode="json", exclude_none=True)
    open_keys = [i.key for i in f.issues if i.state == "open"]
    # Open issues 1..: themes a(x4 defects), b(x3), c(x3, more open in total), d(x1), e(x0).
    plan = ["a"] * 4 + ["b"] * 3 + ["c"] * 3 + ["d"]
    themes: dict[str, tuple[str, str]] = {}
    for key, theme in zip(open_keys, plan, strict=False):
        themes[key] = (theme, "defect")
    for extra, key in zip(open_keys[len(plan) :], ["c-plain"] * 5, strict=False):
        themes[extra] = ("c", "feature")  # c has more open issues than b: wins the tie
    raw["issues"] = {
        k: {
            **v,
            "theme": themes.get(k, ("e", "feature"))[0],
            "kind": themes.get(k, ("e", "feature"))[1],
        }
        for k, v in raw["issues"].items()
    }
    jd2 = Judgements.model_validate(raw)
    subs = Subsystems(
        subsystems=[
            Subsystem(name=n.upper(), path=["x/*"], then_ref="HEAD", themes=[n]) for n in "abcde"
        ]
    )
    page = render_architecture(
        f,
        jd2,
        subsystems=subs,
        measured={},
        resolved=Resolved(order=[Entry("summary"), Entry("subsystems")]),
    )
    hurts = re.findall(r'<li><a href="#subsystem-([a-z-]+)">', page)
    assert hurts == ["a", "c", "b"]  # d has a defect but is fourth
    for slug in hurts:
        assert f'<article class="subsystem" id="subsystem-{slug}"' in page


def test_subsystem_cards_place_open_issues_and_the_rest_under_other(
    checkout: Checkout,
) -> None:
    measured = measure_subsystems(checkout, _subsystems(), now_ref="HEAD")
    page = _page(measured=measured)
    cards = page[_pos(page, 'id="subsystems"') : _pos(page, 'id="size-table"')]
    core = re.search(
        r'<article class="subsystem"[^>]*data-subsystem="core".*?</article>', cards, re.S
    )
    other = re.search(
        r'<article class="subsystem"[^>]*data-subsystem="Other".*?</article>', cards, re.S
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
    table = page[_pos(page, 'id="size-table"') :]
    assert DASH in table
    assert "<td>0</td>" not in table
    assert '<div class="scroll"><table' in table  # its own overflow wrapper


def test_the_size_table_and_bars_carry_the_measured_numbers(checkout: Checkout) -> None:
    measured = measure_subsystems(checkout, _subsystems(), now_ref="HEAD")
    page = _page(measured=measured)
    table = page[_pos(page, 'id="size-table"') :]
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


def test_the_page_states_the_counting_rule(tmp_path: Path, checkout: Checkout) -> None:
    state = _state(tmp_path)
    (state / "subsystems.yaml").write_text(yaml.safe_dump(SUBSYSTEMS), encoding="utf-8")
    assert _run(state, checkout).exit_code == 0
    page = (state / "architecture.html").read_text(encoding="utf-8")
    assert "binary files, symlinks and submodules are not counted" in page
    assert "a moved file moves its lines between subsystems" in page
    assert "<th>Source lines" not in page and "Source lines" not in page


def test_the_command_does_not_read_origins_files(tmp_path: Path, checkout: Checkout) -> None:
    state = _state(tmp_path)
    (state / "origins-facts.json").write_text("{not json", encoding="utf-8")
    (state / "origins.yaml").write_text(": : bad", encoding="utf-8")
    result = _run(state, checkout)
    assert result.exit_code == 0, result.output
    assert (state / "architecture.html").exists()


def test_a_manifest_naming_a_moved_section_notes_the_owning_page(
    tmp_path: Path, checkout: Checkout
) -> None:
    state = _state(tmp_path)
    arch = state / "architecture"
    arch.mkdir()
    (arch / "manifest.yaml").write_text(
        "sections:\n  - waves\n  - timeline\n  - summary\n", encoding="utf-8"
    )
    result = _run(state, checkout)
    assert result.exit_code == 0, result.output
    page = (state / "architecture.html").read_text(encoding="utf-8")
    assert "`waves`, which is now on the board page" in page
    assert "`timeline`, which is now on the history page" in page
    assert "no file" not in page and "no file" not in result.output
    assert 'id="waves"' not in page and "snapshot-timeline" not in page
    assert set(MOVED) >= {
        "waves",
        "operator-actions",
        "filings-per-day",
        "origin-counts",
        "timeline",
    }


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
    assert 'id="summary"' in page and "does not name" in page
