"""`fr usage report --run <id> --format html` end to end, as a real subprocess.

Spec 2026-09-25-lean-cost-aware-process §5.A.5/6, acceptance row
`audit-pages-regenerated`. The unit tests drive the Typer app in-process; this
runs the installed `fr` console script the way the `fr-audit` skill does, over
a temporary repo holding a v6 run cursor, with `FR_TRANSCRIPT_ROOT` at the
committed Claude Code fixture (a redacted capture, tests/fixtures/usage/NOTE.md).
Nothing is written outside `tmp_path`: HOME and the usage cache are both there.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "usage"
REAL_FR = Path(sys.executable).parent / "fr"
SESSION = "145101c9-bdfc-4f5d-a8be-617eeced7485"
GONE = "0000dead-0000-4000-8000-000000000000"
RUN = "2026-09-21-r"


def _repo(root: Path) -> Path:
    repo = root / "repo"
    runs = repo / "docs" / "superpowers" / "runs"
    runs.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (runs / f"{RUN}.yaml").write_text(
        "schema_version: 6\n"
        f"run: {RUN}\n"
        "workflow: fr-goal@1\n"
        "branch: b\n"
        "started: '2026-09-21T11:00:00+00:00'\n"
        "cursor: deliver\n"
        "steps:\n"
        "  brainstorm:\n"
        "    state: done\n"
        "    at: '2026-09-21T11:40:00+00:00'\n"
        "  implement:\n"
        "    state: done\n"
        "    at: '2026-09-21T13:00:00+00:00'\n"
        "    units:\n"
        "      phase/1:\n"
        "        attempts:\n"
        "        - harness: claude-code\n"
        f"          session: {SESSION}\n"
        "      phase/2:\n"
        "        attempts:\n"
        "        - harness: claude-code\n"
        f"          session: {GONE}\n"
    )
    return repo


def _section(page: str, title: str) -> str:
    start = page.index(f"<h2>{title}</h2>")
    end = page.find("<h2>", start + 1)
    return page[start : end if end != -1 else len(page)]


def test_fr_usage_report_renders_the_audit_page_for_a_run(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    out = tmp_path / "pages" / "audit.html"
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "FR_USAGE_CACHE": str(tmp_path / "cache"),
        "FR_TRANSCRIPT_ROOT": str(FIXTURES),
    }
    env.pop("CLAUDE_SESSION_ID", None)
    result = subprocess.run(
        [str(REAL_FR), "usage", "report", "--run", RUN, "--repo", str(repo)]
        + ["--format", "html", "-o", str(out)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "wrote html report for 2 session(s)" in result.stdout

    page = out.read_text()
    assert page.lstrip().lower().startswith("<!doctype html>")
    for title in ("Sessions", "By activity", "By sub-activity", "By model", "By step"):
        assert f"<h2>{title}</h2>" in page, title

    # a By-step ROW for each cursor step the fixture's messages fall in
    steps = _section(page, "By step")
    for step in ("brainstorm", "implement"):
        assert re.search(rf"<tr><td>{step}</td><td>\$[\d.,]+</td><td>\d+</td>", steps), step

    # the `—` rule: the session with no transcript is a dash row, never a zero
    sessions = _section(page, "Sessions")
    gone = next(row for row in sessions.split("<tr>") if GONE[:8] in row)
    assert "<td>—</td>" in gone
    assert "$0.00" not in page and not re.search(r"\$0(?![.,]\d)", page)
    assert "no transcript found" in gone
    # and the measured session carries the harness's own figure
    measured = next(row for row in sessions.split("<tr>") if SESSION[:8] in row)
    assert re.search(r"<td>\$[\d.,]+</td><td>exact</td>", measured)
    # read-only: the repo holds only what the test wrote
    tracked = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert tracked == [f"?? docs/superpowers/runs/{RUN}.yaml"]
