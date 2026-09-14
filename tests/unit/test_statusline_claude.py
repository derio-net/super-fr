"""fr-statusline-claude.sh — golden lines (spec 2026-09-14 §5.B).

The Claude Code reference status line prints exactly three lines:

1. model (context size) | ``ctx:NN% of X`` | ``5h:NN% 7d:NN%`` — each part
   omitted when its JSON field is absent;
2. the segment's branch row (green ``fr``, purple ``none``) | ``~/cwd`` (blue);
3. the segment's worktree row (same colour).

The fixture is shared with the segment tests (imported, not duplicated).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit.test_statusline_segment import World, _git, world_fixture  # noqa: F401

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="status line requires jq")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "scripts" / "fr-statusline-claude.sh"

BOLD = "\x1b[1m"
DIM = "\x1b[2m"
CYAN = "\x1b[36m"
BLUE = "\x1b[34m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
RED = "\x1b[31m"
PURPLE = "\x1b[35m"
RESET = "\x1b[0m"
SEP = f"{DIM} | {RESET}"

FULL = {
    "model": {"display_name": "Claude Opus 5"},
    "context_window": {"context_window_size": 1000000, "used_percentage": 8},
    "rate_limits": {
        "five_hour": {"used_percentage": 62.4},
        "seven_day": {"used_percentage": 80},
    },
}


def run(
    w: World, payload: dict[str, object], script: Path = SCRIPT
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script)],
        input=json.dumps(payload),
        env=w.env(),
        capture_output=True,
        text=True,
        check=False,
    )


def lines(res: subprocess.CompletedProcess[str]) -> tuple[str, str, str]:
    assert res.returncode == 0, res.stderr
    assert res.stdout.endswith("\n"), res.stdout
    out = res.stdout[:-1].split("\n")
    assert len(out) == 3, f"status line must be exactly three lines: {res.stdout!r}"
    return out[0], out[1], out[2]


def test_full_payload_unbound(world: World) -> None:
    payload = {**FULL, "session_id": "sess-1", "workspace": {"current_dir": str(world.repo)}}
    l1, l2, l3 = lines(run(world, payload))
    assert l1 == (
        f"{BOLD}{CYAN}Opus 5{RESET} {DIM}(1M context){RESET}{SEP}"
        f"{DIM}ctx:{RESET}{GREEN}8%{RESET}{DIM} of 1M{RESET}{SEP}"
        f"{DIM}5h:{RESET}{YELLOW}62%{RESET} {DIM}7d:{RESET}{RED}80%{RESET}"
    )
    assert l2 == f"{PURPLE}branch: main{RESET}{SEP}{BLUE}~/Docs/acme{RESET}"
    assert l3 == f"{PURPLE}no fr-isolation{RESET}"


def test_bound_rows_are_green(world: World) -> None:
    world.bind()
    payload = {**FULL, "session_id": "sess-1", "workspace": {"current_dir": str(world.repo)}}
    _, l2, l3 = lines(run(world, payload))
    assert l2 == f"{GREEN}branch: feat/x{RESET}{SEP}{BLUE}~/Docs/acme{RESET}"
    assert l3 == f"{GREEN}worktree: {world.featx}{RESET}"


# `plain` lives under tmp_path, outside world.home, so it stays absolute.
def test_minimal_payload_outside_home(world: World, tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    payload = {
        "model": {"display_name": "Claude Sonnet 5"},
        "workspace": {"current_dir": str(plain)},
    }
    l1, l2, l3 = lines(run(world, payload))
    assert l1 == f"{BOLD}{CYAN}Sonnet 5{RESET}"
    assert l2 == f"{PURPLE}no branch{RESET}{SEP}{BLUE}{plain}{RESET}"
    assert l3 == f"{PURPLE}no fr-isolation{RESET}"


# A symlink to the script (e.g. ~/.claude/statusline.sh -> the plugin copy)
# must still find the segment that lives beside the real file.
def test_symlinked_script_finds_segment(world: World, tmp_path: Path) -> None:
    link = tmp_path / "statusline.sh"
    link.symlink_to(SCRIPT)
    payload = {**FULL, "session_id": "sess-1", "workspace": {"current_dir": str(world.repo)}}
    _, l2, l3 = lines(run(world, payload, link))
    assert l2 == f"{PURPLE}branch: main{RESET}{SEP}{BLUE}~/Docs/acme{RESET}"
    assert l3 == f"{PURPLE}no fr-isolation{RESET}"


# Copied alone (no segment beside it), the rows degrade to the purple defaults
# instead of a bare separator and an empty third line.
def test_missing_segment_degrades_to_none_rows(world: World, tmp_path: Path) -> None:
    lone = tmp_path / "lone" / "fr-statusline-claude.sh"
    lone.parent.mkdir()
    shutil.copy(SCRIPT, lone)
    payload = {
        "model": {"display_name": "Claude Opus 5"},
        "workspace": {"current_dir": str(world.repo)},
    }
    _, l2, l3 = lines(run(world, payload, lone))
    assert l2 == f"{PURPLE}no branch{RESET}{SEP}{BLUE}~/Docs/acme{RESET}"
    assert l3 == f"{PURPLE}no fr-isolation{RESET}"


# jq can render a tiny float in exponent form (1e-07); percentages are floored
# in jq so the integer colour test never sees a non-integer.
def test_non_integer_percentages_are_floored(world: World, tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    payload = {
        "model": {"display_name": "Claude Opus 5"},
        "context_window": {"context_window_size": 200000, "used_percentage": 1e-07},
        "rate_limits": {"five_hour": {"used_percentage": 99.99999}},
        "workspace": {"current_dir": str(plain)},
    }
    res = run(world, payload)
    l1, _, _ = lines(res)
    assert res.stderr == ""
    assert l1 == (
        f"{BOLD}{CYAN}Opus 5{RESET} {DIM}(200k context){RESET}{SEP}"
        f"{DIM}ctx:{RESET}{GREEN}0%{RESET}{DIM} of 200k{RESET}{SEP}"
        f"{DIM}5h:{RESET}{RED}99%{RESET}"
    )
