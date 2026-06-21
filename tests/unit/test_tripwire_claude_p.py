"""CI tripwire: no `claude -p` batch invocation in package source (#328 Task 2).

Each `claude -p` call cold-starts a full Claude Code session (~22k tokens,
~$0.37, ~5s) — ruinous per-element. The convention
(`plugins/super-fr/rules/no-claude-p-batch.md`) says use a persistent agent
session / subagent fan-out / batched prompts instead. super-fr's own packages
never legitimately shell out to claude, so this guard fails loud if they do.

The matcher requires a quote immediately before `claude` (an argv token or a
shell-string command), so it catches real invocations while ignoring prose
mentions like a docstring's backtick-wrapped ``claude -p``.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_CLAUDE_P = re.compile(r"""['"]claude['"]?\s*(?:,\s*)?['"]?(?:-p|--print)\b""")


def scan_claude_p(text: str) -> bool:
    return bool(_CLAUDE_P.search(text))


def test_scan_detects_invocations() -> None:
    assert scan_claude_p('subprocess.run(["claude", "-p", prompt])')
    assert scan_claude_p('cmd = "claude -p some prompt"')
    assert scan_claude_p("argv = ['claude', '--print']")


def test_scan_ignores_prose_and_non_batch() -> None:
    assert not scan_claude_p("a headless `claude -p` daemon")  # backtick prose
    assert not scan_claude_p('executor="CLAUDE_CODE"')
    assert not scan_claude_p('subprocess.run(["claude", "chat"])')


def test_no_claude_p_in_package_source() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in sorted((REPO_ROOT / "packages").glob("*/src/**/*.py"))
        if scan_claude_p(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"claude -p batch invocation(s) found: {offenders}"
