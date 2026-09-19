"""RED/GREEN pin for the agents sync category in scripts/sync-opencode.py.

Claude Code and OpenCode use two different subagent frontmatter dialects —
see spec docs/superpowers/specs/2026-09-19-opencode-subagent-dispatch-design.md
§3.B. `canonical_agents()` therefore returns GENERATED content (the commands
category's shape: `dict[str, str]` of mirror-filename-stem -> expected file
content), not a byte-copy map like the skills category. This test loads
scripts/sync-opencode.py the way test_tripwire_opencode_commands_sync.py
does (importlib.util.spec_from_file_location — the script is not a package)
and pins the translation's MEANING via yaml.safe_load, plus one literal
assertion for the one fact safe_load erases: the single-line
double-quoted `description:` layout that spec §3.C's install-time rewrite
depends on.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "sync_opencode", REPO_ROOT / "scripts" / "sync-opencode.py"
)
assert _spec is not None and _spec.loader is not None
sync_opencode = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_opencode)


def _frontmatter_and_body(content: str) -> tuple[dict[str, object], str]:
    _, raw_frontmatter, body = content.split("---", 2)
    frontmatter = yaml.safe_load(raw_frontmatter)
    assert isinstance(frontmatter, dict)
    return frontmatter, body


def test_canonical_agents_has_exactly_one_key_today() -> None:
    agents = sync_opencode.canonical_agents()
    assert set(agents) == {"fr-phase-executor"}


def test_no_name_key_in_frontmatter() -> None:
    frontmatter, _ = _frontmatter_and_body(sync_opencode.canonical_agents()["fr-phase-executor"])
    assert "name" not in frontmatter, (
        "OpenCode names an agent by its filename — a name: key is Claude-Code-only frontmatter"
    )


def test_mode_subagent_present() -> None:
    frontmatter, _ = _frontmatter_and_body(sync_opencode.canonical_agents()["fr-phase-executor"])
    assert frontmatter.get("mode") == "subagent"


def test_description_is_single_line_double_quoted_scalar() -> None:
    content = sync_opencode.canonical_agents()["fr-phase-executor"]
    # A literal layout assertion — yaml.safe_load can't tell a folded `>`
    # block from a single-line double-quoted scalar, both parse to the same
    # str. Find the description line directly in the raw frontmatter text.
    _, raw_frontmatter, _ = content.split("---", 2)
    description_lines = [
        line for line in raw_frontmatter.splitlines() if line.startswith("description:")
    ]
    assert len(description_lines) == 1, "description: must appear exactly once, on its own line"
    line = description_lines[0]
    assert line.startswith('description: "'), (
        f"description: must be a single-line double-quoted scalar, got: {line!r}"
    )
    assert line.rstrip().endswith('"'), (
        f"description: must close its double quote on the same line, got: {line!r}"
    )


def test_permission_is_closed_translation_of_canonical_tools() -> None:
    # Canonical tools: Read, Edit, Write, Bash, Grep, Glob
    frontmatter, _ = _frontmatter_and_body(sync_opencode.canonical_agents()["fr-phase-executor"])
    permission = frontmatter.get("permission")
    assert isinstance(permission, dict)
    assert permission.get("edit") == "allow"
    assert permission.get("bash") == "allow"
    # The denies are the load-bearing half of the translation (spec-review
    # r3): Claude Code's tools: is an allowlist, OpenCode's defaults are
    # permissive, so the classes the canonical tools: line withholds must be
    # explicitly denied or the mirror is strictly more powerful than its
    # source. task: deny in particular is what keeps a phase executor from
    # dispatching further subagents.
    assert permission.get("task") == "deny"
    assert permission.get("webfetch") == "deny"


def test_body_is_canonical_body_verbatim() -> None:
    canonical_path = sync_opencode.AGENTS_CANONICAL_DIR / "fr-phase-executor.md"
    _, canonical_body = _frontmatter_and_body(canonical_path.read_text())

    _, mirror_body = _frontmatter_and_body(sync_opencode.canonical_agents()["fr-phase-executor"])

    assert mirror_body.strip() == canonical_body.strip()


def test_do_not_hand_edit_banner_names_the_sync_script() -> None:
    content = sync_opencode.canonical_agents()["fr-phase-executor"]
    assert "scripts/sync-opencode.py" in content
    assert "not edit" in content.lower() or "do not edit" in content.lower()
