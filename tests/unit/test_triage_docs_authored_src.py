"""docs/triage's authored-src keeps building as pinned issues close (gh#1005).

`pipeline.py` pins open issues on the pipeline diagram from a hand-written table, and
`build.py` runs it before writing the history fragments. Issues closing is the normal
lifecycle, so a closed pin must drop off the diagram visibly rather than abort the build,
and a diagram that does fail must not take the independent history fragments with it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "docs" / "triage" / "derio-net--super-fr" / "authored-src"

OPEN_PINNED = 552  # pinned on "plan" in pipeline.py's table
CLOSED_PINNED = 985  # pinned on "judge + board"
UNPINNED = 99999


def _state(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    shutil.copytree(SRC, state / "authored-src")
    (state / "architecture").mkdir(parents=True)
    return state


def _facts(state: Path) -> None:
    issues = [
        {"number": OPEN_PINNED, "title": "plan add-phase", "state": "open"},
        {"number": CLOSED_PINNED, "title": "partial in Done", "state": "closed"},
        {"number": UNPINNED, "title": "elsewhere", "state": "open"},
    ]
    (state / "facts.json").write_text(json.dumps({"issues": issues}))


def _run(
    state: Path, script: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(state / "authored-src" / script)],
        cwd="/",
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def test_a_closed_pin_drops_off_the_diagram_instead_of_aborting(tmp_path: Path) -> None:
    state = _state(tmp_path)
    _facts(state)

    result = _run(state, "pipeline.py")

    assert result.returncode == 0, result.stderr
    page = (state / "architecture" / "pipeline.html").read_text()
    assert f'<tspan font-weight="600">#{OPEN_PINNED}</tspan>' in page
    assert f'<tspan font-weight="600">#{CLOSED_PINNED}</tspan>' not in page
    # dropped visibly: named on the page and on stderr, never silently
    assert f"#{CLOSED_PINNED}" in page.split("dropped", 1)[1]
    assert str(CLOSED_PINNED) in result.stderr
    assert f"issues/{UNPINNED}" in page


def test_history_fragments_build_even_when_the_diagram_fails(tmp_path: Path) -> None:
    state = _state(tmp_path)  # no facts.json: pipeline.py cannot run
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text("#!/bin/sh\necho '[]'\n")
    gh.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"}

    result = _run(state, "build.py", env)

    assert result.returncode != 0
    assert "pipeline.py" in result.stderr
    for name in ("closing-order.html", "origins-2026-10-02.html", "history-2026-10-02.html"):
        assert (state / "history" / name).is_file(), name
