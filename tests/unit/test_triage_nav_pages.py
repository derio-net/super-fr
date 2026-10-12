"""One page registry, navs kept in agreement (spec 2026-10-12-board-truth §F; R9-R12).

Rows `triage-nav-present-pages`. Every command here is the real CLI over a state
directory in `tmp_path`; nothing reaches a forge, a runner or a browser.
"""

from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path

import pytest
import yaml
from fr.artifacts import atomic
from fr.cli import app
from fr.commands import triage_kanban_cmd
from fr.triage.components import (
    NAV_BLOCK,
    PAGES,
    nav_html,
    page_header,
    pages_present,
    refresh_navs,
    strip_nav,
)
from typer.testing import CliRunner

from tests.unit.test_triage_batch_drive_cmd import REPO, World, _batch, _state
from tests.unit.test_triage_kanban_cmd import _Inspector, _use

ALL = tuple(p.key for p in PAGES)


def _links(page: str) -> list[str]:
    block = NAV_BLOCK.search(page)
    assert block, "no nav block"
    return re.findall(r'href="([^"]+)"', block.group(0))


def _cli(tmp_path: Path, *words: str) -> tuple[int, str]:
    result = CliRunner().invoke(app, ["triage", *words, "--repo", REPO, "--dir", str(tmp_path)])
    return result.exit_code, result.output


def _state_dir(tmp_path: Path) -> Path:
    world = World()
    world.issues[1] = "open"
    return _state(tmp_path, world, _batch("b1", 1))


# ------------------------------------------------------------------ the registry


def test_pages_present_is_the_files_that_exist_plus_the_current_page(tmp_path: Path) -> None:
    assert pages_present(tmp_path, "history") == ("history",)
    (tmp_path / "triage.html").write_text("x", encoding="utf-8")
    (tmp_path / "origins.html").write_text("x", encoding="utf-8")
    (tmp_path / "board").mkdir()  # the fragments directory is not the page
    assert pages_present(tmp_path, "batches") == ("backlog", "batches", "origins")
    assert pages_present(tmp_path, "origins") == ("backlog", "origins")


def test_page_header_links_only_present_pages_marks_current_then_states_the_goal() -> None:
    h = page_header("batches", ("backlog", "batches", "history"))
    assert _links(h) == ["triage.html", "board.html", "history.html"]
    assert h.count('aria-current="page"') == 1
    assert re.search(r'<a href="board.html" aria-current="page">Batches</a>', h)
    assert h.endswith('<p class="goal">What is running, and what needs me?</p>')
    assert "origins.html" not in h and "architecture.html" not in h


# ----------------------------------------------------------------- the board page


def test_the_board_carries_its_nav_its_goal_and_the_batches_title(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_dir(tmp_path)
    _use(monkeypatch, _Inspector())
    code, said = _cli(tmp_path, "board")
    assert code == 0, said
    page = (tmp_path / "board.html").read_text(encoding="utf-8")
    assert "<h1>Batches</h1>" in page and "<title>Batches · " in page
    assert "Batch board" not in page
    assert _links(page) == ["board.html"]  # nothing else rendered yet
    assert 'class="goal">What is running, and what needs me?<' in page
    assert page.index("</header>") < page.index('class="pages"')


def test_the_skew_banner_sits_under_the_nav(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage import components as c

    monkeypatch.setattr(triage_kanban_cmd, "skew_banner", lambda facts: '<div class="skew">S</div>')
    _state_dir(tmp_path)
    _use(monkeypatch, _Inspector())
    assert _cli(tmp_path, "board")[0] == 0
    page = (tmp_path / "board.html").read_text(encoding="utf-8")
    assert page.index('class="goal"') < page.index('class="skew"')
    assert c.NAV_BLOCK.search(page)


# ---------------------------------------------------- navs agree after any render


def test_rendering_the_board_updates_the_other_pages_navs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_dir(tmp_path)
    _use(monkeypatch, _Inspector())
    assert _cli(tmp_path, "render")[0] == 0
    assert _cli(tmp_path, "history", "render")[0] == 0
    history = (tmp_path / "history.html").read_text(encoding="utf-8")
    assert _links(history) == ["triage.html", "history.html"]

    assert _cli(tmp_path, "board")[0] == 0
    history = (tmp_path / "history.html").read_text(encoding="utf-8")
    backlog = (tmp_path / "triage.html").read_text(encoding="utf-8")
    board = (tmp_path / "board.html").read_text(encoding="utf-8")
    for page in (history, backlog, board):
        assert _links(page) == ["triage.html", "board.html", "history.html"]
    assert re.search(r'<a href="history.html" aria-current="page">', history)
    assert re.search(r'<a href="triage.html" aria-current="page">', backlog)
    for page in (history, backlog, board):
        assert "origins.html" not in page and "architecture.html" not in page


def test_rendering_a_page_adds_it_to_the_pages_already_there(tmp_path: Path) -> None:
    _state_dir(tmp_path)
    assert _cli(tmp_path, "history", "render")[0] == 0
    assert _cli(tmp_path, "render")[0] == 0
    history = (tmp_path / "history.html").read_text(encoding="utf-8")
    assert _links(history) == ["triage.html", "history.html"]


def _seed(tmp_path: Path, **pages: str) -> None:
    for key, nav in pages.items():
        page = next(p for p in PAGES if p.key == key)
        (tmp_path / page.file).write_text(
            f'<html>{nav}<p class="goal">g</p>BODY</html>\n', encoding="utf-8"
        )


def test_a_page_whose_nav_is_already_current_is_not_rewritten(tmp_path: Path) -> None:
    present = ("backlog", "history")
    _seed(tmp_path, history=nav_html("history", present))
    (tmp_path / "triage.html").write_text("x", encoding="utf-8")
    path = tmp_path / "history.html"
    os.utime(path, ns=(1_000_000_000, 1_000_000_000))
    before = path.read_bytes()
    refresh_navs(tmp_path, "backlog")
    assert path.read_bytes() == before and path.stat().st_mtime_ns == 1_000_000_000


def test_a_stale_nav_is_replaced_atomically_and_nothing_else_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(tmp_path, history=nav_html("history", ("history",)))
    (tmp_path / "triage.html").write_text("x", encoding="utf-8")
    written: list[Path] = []
    real = atomic.write_text_atomic

    def spy(path: Path, text: str) -> None:
        written.append(Path(path))
        real(path, text)

    monkeypatch.setattr(atomic, "write_text_atomic", spy)
    refresh_navs(tmp_path, "backlog")
    assert written == [tmp_path / "history.html"]
    page = (tmp_path / "history.html").read_text(encoding="utf-8")
    assert page == (
        f'<html>{nav_html("history", ("backlog", "history"))}<p class="goal">g</p>BODY</html>\n'
    )


def test_a_page_without_a_nav_block_is_left_byte_identical_and_named(tmp_path: Path) -> None:
    (tmp_path / "history.html").write_text("<html>hand-written</html>\n", encoding="utf-8")
    (tmp_path / "triage.html").write_text("x", encoding="utf-8")
    seen: list[str] = []
    refresh_navs(tmp_path, "backlog", warn=seen.append)
    assert (tmp_path / "history.html").read_bytes() == b"<html>hand-written</html>\n"
    assert len(seen) == 1 and "history.html" in seen[0]


def test_the_command_warns_for_a_page_without_a_nav_block(tmp_path: Path) -> None:
    _state_dir(tmp_path)
    (tmp_path / "history.html").write_text("<html>old</html>\n", encoding="utf-8")
    code, said = _cli(tmp_path, "render")
    assert code == 0 and "history.html" in said and "nav" in said
    assert (tmp_path / "history.html").read_bytes() == b"<html>old</html>\n"


# --------------------------------------------------------------------- the publish copy


def test_the_publish_command_gets_a_copy_without_the_nav_and_the_local_board_keeps_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_dir(tmp_path)
    _use(monkeypatch, _Inspector())
    assert _cli(tmp_path, "render")[0] == 0
    sent = tmp_path / "sent.html"
    cwd = tmp_path / "cwd.txt"
    code = (
        "import os, sys; open(sys.argv[2], 'w').write(os.getcwd());"
        "open(sys.argv[1], 'w').write(open(sys.argv[3]).read())"
    )
    cfg = {"publish": [sys.executable, "-c", code, str(sent), str(cwd), "{board}"]}
    (tmp_path / "scope.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    code_, said = _cli(tmp_path, "board", "--publish")
    assert code_ == 0, said
    copy = sent.read_text(encoding="utf-8")
    assert '<nav class="pages"' not in copy and "<h1>Batches</h1>" in copy
    local = (tmp_path / "board.html").read_text(encoding="utf-8")
    assert _links(local) == ["triage.html", "board.html"]
    assert Path(cwd.read_text(encoding="utf-8")).resolve() == tmp_path.resolve()


def test_a_page_with_two_nav_blocks_is_treated_alike_by_refresh_and_strip(
    tmp_path: Path,
) -> None:
    old = nav_html("history", ("history",))
    (tmp_path / "triage.html").write_text("x", encoding="utf-8")
    (tmp_path / "history.html").write_text(f"<a>{old}<b>{old}<c>\n", encoding="utf-8")
    refresh_navs(tmp_path, "backlog")
    new = nav_html("history", ("backlog", "history"))
    assert (tmp_path / "history.html").read_text(encoding="utf-8") == f"<a>{new}<b>{new}<c>\n"
    assert strip_nav(f"<a>{old}<b>{old}<c>") == "<a><b><c>"


# ------------------------------------------------------------- review p4-r1 .. r4


def _spy(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    written: list[Path] = []
    real = atomic.write_text_atomic

    def spy(path: Path, text: str) -> None:
        written.append(Path(path))
        real(path, text)

    monkeypatch.setattr(atomic, "write_text_atomic", spy)
    for mod in (
        "triage_cmd",
        "triage_history_cmd",
        "triage_origins_cmd",
        "triage_architecture_cmd",
    ):
        module = importlib.import_module(f"fr.commands.{mod}")
        if hasattr(module, "write_text_atomic"):
            monkeypatch.setattr(module, "write_text_atomic", spy)
    return written


@pytest.mark.parametrize(
    ("words", "page"),
    [(("render",), "triage.html"), (("history", "render"), "history.html")],
)
def test_a_render_writes_its_own_page_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, words: tuple[str, ...], page: str
) -> None:
    _state_dir(tmp_path)
    written = _spy(monkeypatch)
    code, said = _cli(tmp_path, *words)
    assert code == 0, said
    assert tmp_path / page in written


def test_a_page_changed_between_read_and_write_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(tmp_path, history=nav_html("history", ("history",)))
    (tmp_path / "triage.html").write_text("x", encoding="utf-8")
    path = tmp_path / "history.html"
    other = "<html>another render got here first</html>\n"
    real = Path.read_text
    reads = {"n": 0}

    def racing(self: Path, *a: object, **k: object) -> str:
        text = real(self, *a, **k)  # type: ignore[arg-type]
        if self == path:
            reads["n"] += 1
            if reads["n"] == 1:
                path.write_text(other, encoding="utf-8")  # lands after our first read
        return text

    monkeypatch.setattr(Path, "read_text", racing)
    refresh_navs(tmp_path, "backlog")
    assert path.read_text(encoding="utf-8") == other


def test_a_failed_nav_write_warns_naming_the_page_and_never_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(tmp_path, history=nav_html("history", ("history",)))
    (tmp_path / "triage.html").write_text("x", encoding="utf-8")

    def boom(path: Path, text: str) -> None:
        raise PermissionError("read-only")

    monkeypatch.setattr(atomic, "write_text_atomic", boom)
    seen: list[str] = []
    refresh_navs(tmp_path, "backlog", warn=seen.append)
    assert len(seen) == 1 and "history.html" in seen[0] and "read-only" in seen[0]


def test_a_render_still_stores_its_snapshot_when_a_nav_cannot_be_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_dir(tmp_path)
    assert _cli(tmp_path, "history", "render")[0] == 0
    monkeypatch.setattr(atomic, "write_text_atomic", _fail_for("history.html"))
    code, said = _cli(tmp_path, "render")
    assert code == 0 and "history.html" in said
    assert list((tmp_path / "snapshots").glob("*"))


def _fail_for(name: str):  # type: ignore[no-untyped-def]
    real = atomic.write_text_atomic

    def write(path: Path, text: str) -> None:
        if Path(path).name == name:
            raise PermissionError("read-only")
        real(path, text)

    return write


# ------------------------------------------------------------------------ review p4-r3


def test_the_no_nav_warning_is_said_once_across_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_dir(tmp_path)
    _use(monkeypatch, _Inspector())
    (tmp_path / "history.html").write_text("<html>old</html>\n", encoding="utf-8")
    first = _cli(tmp_path, "board")[1]
    second = _cli(tmp_path, "board")[1]
    assert first.count("no nav block") == 1 and second.count("no nav block") == 0


# ------------------------------------------------------------------ review p4-r7 / r9


def test_the_publish_copy_is_gone_once_the_command_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _state_dir(tmp_path)
    _use(monkeypatch, _Inspector())
    seen = tmp_path / "seen.txt"
    code = "import sys; open(sys.argv[1], 'w').write(sys.argv[2])"
    cfg = {"publish": [sys.executable, "-c", code, str(seen), "{board}"]}
    (tmp_path / "scope.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert _cli(tmp_path, "board", "--publish")[0] == 0
    copy = Path(seen.read_text(encoding="utf-8"))
    assert copy.name == "board.html" and copy != tmp_path / "board.html"
    assert not copy.exists() and not copy.parent.exists()


def test_the_backlog_names_the_batches_page_not_the_board() -> None:
    from fr.triage.render import render

    from tests.unit.triage_board_fixtures import busy

    page = render(*busy(), board=True)
    assert "Open the Batches page</a>" in page and "live board" not in page
