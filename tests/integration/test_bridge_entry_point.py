"""E2: `python -m fr.bridge --dry-run` exits 0 in a clean environment.

The dry-run path must short-circuit before any gh / MCP subprocess
starts, so an operator (or a hermetic CI runner) can sanity-check the
install without network access.
"""

from __future__ import annotations

import subprocess
import sys

import fr


def test_python_dash_m_dry_run_exits_zero():
    """Run `python -m fr.bridge --dry-run` with most env stripped."""
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp",
        # Strip vars the real tick would consume so accidental real work
        # would surface as a missing-config failure.
    }
    # PYTHONPATH must include the in-repo `src` so the test sees the
    # version under test (the agent runs from a worktree without editable
    # install). This is independent of "MCP / gh side effects".

    src_root = str(__import__("pathlib").Path(fr.__file__).parent.parent)
    env["PYTHONPATH"] = src_root

    result = subprocess.run(
        [sys.executable, "-m", "fr.bridge", "--dry-run"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"fr.bridge --dry-run failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
