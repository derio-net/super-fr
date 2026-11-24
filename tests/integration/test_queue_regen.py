"""Generated files and `reviewed:` stamps in the queue's combination, over a real bare
remote (spec 2026-11-24-ci-economy R9-R12, §C).

The fixture repo has two sources, `src/one.txt` and `src/two.txt`, and a mirror,
`scripts/regen.py`, that writes `gen/out.txt` in whole and the `count` block of
`README.md` from them. Each PR edits one source and commits its own regenerated output,
so the outputs conflict while the sources do not.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fr.triage.batch_merge import MergeConflictError
from fr.triage.queue_exec import Regen, build

from tests.integration.queue_git import SCOPE, World, git, world

PY = sys.executable

REGEN = """\
import pathlib, re
one = pathlib.Path("src/one.txt").read_text().strip()
two = pathlib.Path("src/two.txt").read_text().strip()
pathlib.Path("gen").mkdir(exist_ok=True)
pathlib.Path("gen/out.txt").write_text(f"one={one} two={two}\\n")
readme = pathlib.Path("README.md")
block = f"<!-- generated:count -->\\ncount: one={one} two={two}\\n<!-- /generated:count -->"
readme.write_text(re.sub(r"<!-- generated:count -->.*?<!-- /generated:count -->", block,
                         readme.read_text(), flags=re.S))
"""

README = "# Demo\n\nIntro.\n\n<!-- generated:count -->\ncount: {c}\n<!-- /generated:count -->\n"


def _outputs(one: str, two: str) -> dict[str, str]:
    return {
        "src/one.txt": f"{one}\n",
        "src/two.txt": f"{two}\n",
        "gen/out.txt": f"one={one} two={two}\n",
        "README.md": README.format(c=f"one={one} two={two}"),
    }


def _generated_world(tmp_path: Path, *, extra: dict[str, str] | None = None) -> World:
    w = world(tmp_path)
    w.move_main({"scripts/regen.py": REGEN, **_outputs("a", "b")})
    first, second = _outputs("A", "b"), _outputs("a", "B")
    w.pr(1, first)
    w.pr(2, {**{k: v for k, v in second.items() if k != "src/one.txt"}, **(extra or {})})
    w.fetch()
    return w


def _build(w: World, method: str = "squash", regen: Regen | None = None) -> list:  # type: ignore[type-arg]
    return build(
        w.checkout, w.main(), [w.entry(1), w.entry(2)], method, None, scope=SCOPE,  # type: ignore[arg-type]
        slots=(1, 2), scratch=w.scratch, regen=regen or Regen(),
    )  # fmt: skip


def _show(w: World, sha: str, path: str) -> str:
    return git(w.origin, "show", f"{sha}:{path}")


MIRRORS = ((PY, "scripts/regen.py"),)


@pytest.mark.parametrize("method", ["squash", "rebase", "merge"])
def test_a_whole_generated_conflict_is_regenerated_by_the_mirrors(
    tmp_path: Path, method: str
) -> None:
    w = _generated_world(tmp_path)
    _, two = _build(w, method, Regen(mirrors=MIRRORS, generated=("gen/*",)))
    assert _show(w, two.sha, "gen/out.txt") == "one=A two=B"
    assert "count: one=A two=B" in _show(w, two.sha, "README.md")
    assert _show(w, two.sha, "src/one.txt") == "A" and _show(w, two.sha, "src/two.txt") == "B"


def _block_world(tmp_path: Path) -> World:
    w = world(tmp_path)
    w.move_main({"scripts/regen.py": REGEN, **_outputs("a", "b")})
    first, second = _outputs("A", "b"), _outputs("a", "B")
    w.pr(1, {k: v for k, v in first.items() if k != "gen/out.txt"})
    w.pr(2, {k: v for k, v in second.items() if k not in ("gen/out.txt", "src/one.txt")})
    w.fetch()
    return w


def test_a_generated_block_conflict_in_a_doc_is_regenerated(tmp_path: Path) -> None:
    w = _block_world(tmp_path)  # the conflict is README.md's block alone
    _, two = _build(w, regen=Regen(mirrors=MIRRORS, generated=("gen/*",)))
    assert "count: one=A two=B" in _show(w, two.sha, "README.md")
    assert "<<<<<<<" not in _show(w, two.sha, "README.md")


def _page(date: str) -> str:
    return f"---\ntitle: Page\nreviewed: {date} checked\ncovers: [a.txt]\n---\n\nBody.\n"


@pytest.mark.parametrize(
    ("one", "two", "kept"),
    [("2026-11-20", "2026-11-23", "2026-11-23"), ("2026-11-23", "2026-11-20", "2026-11-23")],
)
def test_a_stamp_conflict_takes_the_newer_date_with_no_mirrors(
    tmp_path: Path, one: str, two: str, kept: str
) -> None:
    w = world(tmp_path)
    w.move_main({"docs/page.md": _page("2026-11-01")})
    w.pr(1, {"docs/page.md": _page(one), "b.txt": "bravo\n"})
    w.pr(2, {"docs/page.md": _page(two), "c.txt": "charlie\n"})
    w.fetch()
    _, built = _build(w)
    assert _show(w, built.sha, "docs/page.md") == _page(kept).rstrip("\n")


def test_a_real_conflict_beside_generated_ones_names_only_the_real_path(tmp_path: Path) -> None:
    w = world(tmp_path)
    w.move_main({"scripts/regen.py": REGEN, **_outputs("a", "b")})
    w.pr(1, {**_outputs("A", "b"), "a.txt": "alpha one\n"})
    w.pr(2, {**{k: v for k, v in _outputs("a", "B").items() if k != "src/one.txt"},
             "a.txt": "alpha two\n"})  # fmt: skip
    w.fetch()
    with pytest.raises(MergeConflictError) as raised:
        _build(w, regen=Regen(mirrors=MIRRORS, generated=("gen/*",)))
    assert raised.value.paths == ("a.txt",) and raised.value.batch == "b2"


@pytest.mark.parametrize(
    ("mirror", "timeout", "words"),
    [
        ((PY, "-c", "import sys; sys.exit(1)"), 600.0, "sys.exit(1)"),
        ((PY, "-c", "import time; time.sleep(30)"), 0.5, "timed out"),
    ],
)
def test_a_failing_mirror_hands_the_entry_back_naming_the_command(
    tmp_path: Path, mirror: tuple[str, ...], timeout: float, words: str
) -> None:
    w = _generated_world(tmp_path)
    with pytest.raises(MergeConflictError) as raised:
        _build(w, regen=Regen(mirrors=(mirror,), generated=("gen/*",), timeout=timeout))
    assert set(raised.value.paths) == {"gen/out.txt", "README.md"}
    assert words in str(raised.value) and mirror[-1] in str(raised.value)


def test_a_mirror_writing_outside_the_generated_files_hands_the_entry_back(
    tmp_path: Path,
) -> None:
    stray = (PY, "-c", "import pathlib; pathlib.Path('a.txt').write_text('stray\\n')")
    w = _generated_world(tmp_path)
    with pytest.raises(MergeConflictError) as raised:
        _build(w, regen=Regen(mirrors=(*MIRRORS, stray), generated=("gen/*",)))
    assert raised.value.paths == ("a.txt",)
    assert "outside" in str(raised.value)


def test_a_generated_conflict_with_no_mirrors_is_a_real_conflict(tmp_path: Path) -> None:
    w = _generated_world(tmp_path)
    with pytest.raises(MergeConflictError) as raised:
        _build(w, regen=Regen(generated=("gen/*",)))
    assert set(raised.value.paths) == {"gen/out.txt", "README.md"}
