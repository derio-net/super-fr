"""lib/fr-apply-patch-paths.sh — Codex apply_patch target-path extraction.

Codex reports file edits as tool_name "apply_patch" with the patch text in
`tool_input.command`, and one patch names MULTIPLE targets via `*** <verb>:`
lines. This is the only Codex-specific parsing in the enforcement path; the
allow/deny decision stays in lib/fr-isolation-decision.sh, shared with the
Claude, Hermes and OpenCode ports.

The library is driven as a subprocess, the same way the other hook tests drive
hooks, so the shell is exercised as the hook will actually run it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "lib" / "fr-apply-patch-paths.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None,
    reason="apply_patch path extraction runs in bash",
)

# FIXTURE PROVENANCE — this patch body is DOC-DERIVED, not captured from a live
# Codex session: no Codex session was run against a real hook (journal v4).
# That is a deliberate, recorded deviation from "fixtures captured, never
# constructed" — the capture needs a live session plus a trust grant, which is
# Test Plan step 4/5, post-merge. What IS captured is the hooks.json SCHEMA,
# read from the operator's live ~/.codex/hooks.json (phase 5 uses that).
# Kept as ONE module-level constant so a later capture replaces it in one place.
PATCH = """*** Begin Patch
*** Update File: src/a.py
@@
-old
+new
*** Add File: docs/new.md
+hello
*** Delete File: old/gone.txt
*** Update File: src/b.py
*** Move to: src/c.py
*** End Patch
"""


def paths(patch: str) -> list[str]:
    script = f'. "{LIB}"; fr_apply_patch_paths "$1"'
    r = subprocess.run(
        ["bash", "-c", script, "_", patch],
        capture_output=True,
        text=True,
        check=True,
    )
    return [ln for ln in r.stdout.splitlines() if ln]


def test_every_verb_in_payload_order() -> None:
    # Each verb the patch format uses, in the order the payload names them,
    # with the `Move to:` destination counted as its own target.
    assert paths(PATCH) == [
        "src/a.py",
        "docs/new.md",
        "old/gone.txt",
        "src/b.py",
        "src/c.py",
    ]


def test_no_false_positives() -> None:
    assert paths("") == []
    assert paths("echo hi") == []


def test_path_with_spaces_stays_intact() -> None:
    assert paths("*** Add File: docs/my notes.md\n") == ["docs/my notes.md"]


def test_crlf_input_yields_no_trailing_carriage_return() -> None:
    # repr equality, not `in`: a stray \r would still satisfy a containment
    # check while producing a path that never resolves against cwd.
    assert paths("*** Add File: a.py\r\n") == ["a.py"]


def test_indented_patch_line_is_not_matched() -> None:
    # Anchored at column 0, so patch-like prose quoted in a message body
    # cannot inject a target path into the enforcement path.
    assert paths("  *** Add File: x.py\n") == []
