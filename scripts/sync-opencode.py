#!/usr/bin/env python3
"""Sync super-fr skills and rules into OpenCode-discoverable mirrors.

OpenCode (github.com/anomalyco/opencode) discovers skills as plain
`SKILL.md` files under `.opencode/skills/<name>/`, `.claude/skills/<name>/`,
or `.agents/skills/<name>/` — it has no concept of the Claude Code
plugin/marketplace layout this repo ships skills through
(`plugins/super-fr/skills/<name>/SKILL.md`). Its project-level custom-
instructions surface is `opencode.json`'s `instructions` array (arbitrary
markdown files), not a `~/.claude/rules/` directory. Separately, OpenCode's
slash commands (`/name`, docs: https://opencode.ai/docs/commands) are a
third, independent surface from `commands/<name>.md` files — NOT the same
thing as a skill, and not invoked by typing a skill's own trigger phrase.
A fourth surface, subagents (`.opencode/agent/<name>.md`, docs:
https://opencode.ai/docs/agents), is dispatched by name via the task tool —
its frontmatter dialect differs from Claude Code's own agent files
(`name:` becomes the filename, `tools:` becomes a `permission:` map; see
spec docs/superpowers/specs/2026-09-19-opencode-subagent-dispatch-design.md
§3.B for the full translation). This script generates all four mirrors so
OpenCode sessions in this repo (or any repo that receives it via
install.sh) see the same skills, rules, slash commands, and subagents with
zero extra setup.

`plugins/super-fr/skills/`, `plugins/super-fr/rules/` (plus
`.claude/rules/acceptance-matrix.md`, a repo-local-only rule with no plugin
equivalent), and `plugins/super-fr/agents/` stay the canonical sources —
never hand-edit `.opencode/skills/<name>/SKILL.md`,
`.opencode/instructions/<rule>.md`, `.opencode/commands/<name>.md`, or
`.opencode/agent/<name>.md` directly; all four are overwritten on sync.
Commands have no canonical file of their own — each is mechanically derived
from its matching skill's own SKILL.md frontmatter (`name` + `description`),
so a new skill automatically gets a matching command with zero extra
authoring. Agents are likewise generated, not byte-copied, because the two
frontmatter dialects differ.

Run via `uv run scripts/sync-opencode.py` — this module imports `yaml`
(a `packages/fr/pyproject.toml` workspace dependency), so a bare system
`python3` without the workspace venv active will not have it.

Usage:
    uv run scripts/sync-opencode.py          # write/update all four mirrors
    uv run scripts/sync-opencode.py --check  # exit non-zero on drift, no writes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

SKILLS_CANONICAL_DIR = REPO_ROOT / "plugins" / "super-fr" / "skills"
SKILLS_MIRROR_DIR = REPO_ROOT / ".opencode" / "skills"

# Canonical rule sources: every installer-shipped rule, plus the one
# repo-local-only rule that has no plugins/super-fr/rules/ counterpart.
RULES_CANONICAL_DIR = REPO_ROOT / "plugins" / "super-fr" / "rules"
REPO_LOCAL_ONLY_RULES = (
    REPO_ROOT / ".claude" / "rules" / "acceptance-matrix.md",
    REPO_ROOT / ".claude" / "rules" / "artifact-versioning.md",
    REPO_ROOT / ".claude" / "rules" / "explainers-currency.md",
    REPO_ROOT / ".claude" / "rules" / "third-party-privacy.md",
)
INSTRUCTIONS_MIRROR_DIR = REPO_ROOT / ".opencode" / "instructions"

COMMANDS_MIRROR_DIR = REPO_ROOT / ".opencode" / "commands"

AGENTS_CANONICAL_DIR = REPO_ROOT / "plugins" / "super-fr" / "agents"
# .opencode/agent/ — SINGULAR. All three documented agent-definition forms
# (opencode.json's `agent` key, `.opencode/agents/`, `.opencode/agent/`)
# were verified to register on opencode 1.18.31 (spec §3.A); the singular
# form is pinned here so nobody re-litigates it.
AGENTS_MIRROR_DIR = REPO_ROOT / ".opencode" / "agent"


# ---------------------------------------------------------------------------
# shared drift-detection helper


def _canonical_content(value: Path | str) -> str:
    """Read a canonical entry's content, whether it's a source Path or already-generated str."""
    return value.read_text() if isinstance(value, Path) else value


def _find_category_drift(
    canonical: dict[str, Path | str],
    mirror: dict[str, Path],
    mirror_dir_label: str,
    extra_message: str,
    differs_message: str,
) -> list[str]:
    """Shared missing/extra/differing-content comparison over two name->X maps.

    Each of the four categories (skills, commands, instructions, agents)
    calls this with its own directory label and message wording, so the
    four public `find_*_drift()` functions keep their existing,
    tripwire-pinned message text byte-identical.
    """
    problems = []

    missing = sorted(set(canonical) - set(mirror))
    extra = sorted(set(mirror) - set(canonical))
    for name in missing:
        problems.append(f"{name}: missing from {mirror_dir_label}")
    for name in extra:
        problems.append(f"{name}: present in {mirror_dir_label} with {extra_message}")

    for name in sorted(set(canonical) & set(mirror)):
        if mirror[name].read_text() != _canonical_content(canonical[name]):
            problems.append(f"{name}: {mirror_dir_label} content differs from {differs_message}")

    return problems


# ---------------------------------------------------------------------------
# skills


def canonical_skills() -> dict[str, Path]:
    """Map of skill name -> canonical SKILL.md path."""
    return {p.parent.name: p for p in sorted(SKILLS_CANONICAL_DIR.glob("*/SKILL.md"))}


def mirror_skills() -> dict[str, Path]:
    """Map of skill name -> existing mirror SKILL.md path (if any)."""
    if not SKILLS_MIRROR_DIR.is_dir():
        return {}
    return {p.parent.name: p for p in sorted(SKILLS_MIRROR_DIR.glob("*/SKILL.md"))}


def find_drift() -> list[str]:
    """Human-readable skill mirror drift descriptions; empty means in sync."""
    return _find_category_drift(
        canonical_skills(), mirror_skills(), ".opencode/skills/", "no canonical source", "canonical"
    )


def sync_skills() -> None:
    """Write/overwrite the skills mirror to match canonical exactly."""
    canonical = canonical_skills()

    for name, path in mirror_skills().items():
        if name not in canonical:
            skill_dir = path.parent
            for child in skill_dir.iterdir():
                child.unlink()
            skill_dir.rmdir()

    for name, src in canonical.items():
        dest_dir = SKILLS_MIRROR_DIR / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "SKILL.md"
        dest.write_text(src.read_text())
        # Sibling breadcrumb pointing back at the canonical source — purely
        # informational, never parsed by OpenCode (it only reads SKILL.md).
        source_note = dest_dir / ".source"
        source_note.write_text(
            f"Generated from {src.relative_to(REPO_ROOT)} by "
            f"scripts/sync-opencode.py. Do not edit SKILL.md here directly.\n"
        )


# ---------------------------------------------------------------------------
# commands (derived from skill frontmatter — no canonical file of their own)


def _skill_frontmatter(skill_md: Path) -> dict[str, object]:
    """Parse a SKILL.md's YAML frontmatter block.

    Same idiom as tests/unit/test_skill_validation.py: split on the `---`
    delimiters and safe_load the middle part. SKILL.md frontmatter only ever
    carries simple scalar/mapping fields (name, description, license,
    compatibility, metadata — see https://opencode.ai/docs/skills), so this
    is deliberately not a full markdown-frontmatter library dependency.
    """
    text = skill_md.read_text()
    parts = text.split("---", 2)
    frontmatter = yaml.safe_load(parts[1])
    assert isinstance(frontmatter, dict)
    return frontmatter


def render_command(name: str, description: str) -> str:
    """Render a `.opencode/commands/<name>.md` command wrapping a skill.

    The command's whole job is to give the skill a real, registered `/name`
    slash-command surface (OpenCode docs: commands and skills are separate
    mechanisms — a skill is agent-invoked via description matching, a
    command is operator-invoked via `/name`). No `agent` / `subtask` /
    `model` frontmatter keys are set: the command must run in whatever
    agent/mode is already active, exactly like a natural-language skill
    trigger would, not force a subagent detour. `$ARGUMENTS` passes the
    operator's trailing text straight through; empty is fine (e.g. bare
    `/fr-progress`) — the agent, once it has loaded the skill's full
    instructions, interprets whatever it gets.
    """
    frontmatter = yaml.safe_dump({"description": description}, sort_keys=False, allow_unicode=True)
    return f"---\n{frontmatter}---\nUse the `{name}` skill to handle this request.\n\n$ARGUMENTS\n"


def canonical_commands() -> dict[str, str]:
    """Map of command name -> expected .opencode/commands/<name>.md content.

    Derived from canonical_skills() — one command per already-OpenCode-
    mirrored skill, so a new skill automatically gets a matching command
    with zero extra authoring, and a retired skill's command disappears the
    same way its skill mirror does.
    """
    result = {}
    for name, skill_md in canonical_skills().items():
        frontmatter = _skill_frontmatter(skill_md)
        description = str(frontmatter.get("description", "")).strip()
        result[name] = render_command(name, description)
    return result


def mirror_commands() -> dict[str, Path]:
    """Map of command name -> existing mirror command path (if any)."""
    if not COMMANDS_MIRROR_DIR.is_dir():
        return {}
    return {p.stem: p for p in sorted(COMMANDS_MIRROR_DIR.glob("*.md"))}


def find_commands_drift() -> list[str]:
    """Human-readable command mirror drift descriptions; empty means in sync."""
    return _find_category_drift(
        canonical_commands(),
        mirror_commands(),
        ".opencode/commands/",
        "no matching skill",
        "generated canonical",
    )


def sync_commands() -> None:
    """Write/overwrite the commands mirror to match canonical_commands() exactly."""
    canonical = canonical_commands()

    for name, path in mirror_commands().items():
        if name not in canonical:
            path.unlink()

    COMMANDS_MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in canonical.items():
        dest = COMMANDS_MIRROR_DIR / f"{name}.md"
        dest.write_text(content)


# ---------------------------------------------------------------------------
# agents (generated — Claude Code and OpenCode use different frontmatter
# dialects, so this category is content-generated like commands, never a
# byte-copy like skills/instructions)

# Closed translation of Claude Code's `tools:` allowlist to OpenCode's
# `permission:` map (spec §3.B). CLOSED means every tool name this repo may
# put in a canonical agent appears here — including the ones that map to
# NOTHING, because OpenCode has no separate permission key for them. A name
# that maps to `None` is "known, deliberately not a permission"; a name that
# is absent is an error (review r-p1/f1). The distinction is the whole point:
# a vocabulary that silently drops what it does not recognise is not closed,
# and this repo already raises rather than drops in `fr.harness.model`
# (unknown harness key), `fr.capabilities`, and `_StrictLoader` (duplicate
# YAML key) for exactly this class of silent loss.
_TOOL_PERMISSIONS: dict[str, tuple[str, str] | None] = {
    "Edit": ("edit", "allow"),
    "Write": ("edit", "allow"),
    "NotebookEdit": ("edit", "allow"),
    "Bash": ("bash", "allow"),
    "WebFetch": ("webfetch", "allow"),
    "WebSearch": ("webfetch", "allow"),
    "Agent": ("task", "allow"),
    "Task": ("task", "allow"),
    # No OpenCode permission key of their own — implicit, never denied.
    "Read": None,
    "Grep": None,
    "Glob": None,
    "TodoWrite": None,
}
# The capability classes a canonical `tools:` line does not grant must be
# denied explicitly, or the mirror ends up strictly more powerful than its
# source (spec-review r3): Claude Code's `tools:` is an allowlist, OpenCode's
# permission defaults are permissive. `task: deny` is the load-bearing one —
# it is what keeps a phase executor from dispatching further subagents.
#
# These are DEFAULTS, filling a gap the allowlist left. They never override a
# grant (review r-p1/f2): applied with `update()` they did, so a canonical
# `tools:` line granting WebFetch produced a mirror denying it — an inversion
# of the very allowlist this function exists to carry.
_PERMISSION_DEFAULT_DENIES: dict[str, str] = {"task": "deny", "webfetch": "deny"}


class AgentTranslationError(ValueError):
    """A canonical agent names a tool this translation does not know.

    Loud by design: the alternative is a mirror that is quietly less capable
    than the agent it claims to mirror, with nothing anywhere reporting it.
    """


def _agent_permission(tools: str, *, source: str = "plugins/super-fr/agents/") -> dict[str, str]:
    """Translate a canonical `tools:` value into an OpenCode `permission:` map.

    Raises `AgentTranslationError` on an unrecognised tool name — a new
    Claude Code tool, or a typo, both of which must be a decision rather than
    a silent omission.
    """
    permission: dict[str, str] = {}
    for raw in tools.split(","):
        tool = raw.strip()
        if not tool:
            continue
        if tool not in _TOOL_PERMISSIONS:
            raise AgentTranslationError(
                f"{source}: `tools:` names {tool!r}, which has no entry in "
                "_TOOL_PERMISSIONS (scripts/sync-opencode.py). Add it — mapping it to an "
                "OpenCode permission, or to None if OpenCode has no separate key for it. "
                "Dropping it would make the mirror quietly less capable than its source."
            )
        mapped = _TOOL_PERMISSIONS[tool]
        if mapped is not None:
            key, value = mapped
            permission[key] = value
    for key, value in _PERMISSION_DEFAULT_DENIES.items():
        permission.setdefault(key, value)
    return permission


def render_agent(name: str, frontmatter: dict[str, object], body: str) -> str:
    """Render a `.opencode/agent/<name>.md` mirror of a Claude Code agent.

    Rendered from an explicit template with a FIXED key order, never a
    `yaml.safe_dump` of the whole frontmatter: install.sh's `model:` rewrite
    (spec §3.C) is a bash edit anchored on `description:` being a
    single-line double-quoted scalar and `mode: subagent` sitting on its own
    line immediately after — a generic dumper does not guarantee that
    layout. `name:` is dropped entirely: OpenCode names an agent by its
    mirror filename, not a frontmatter field.
    """
    description = str(frontmatter.get("description", "")).strip()
    description_line = yaml.safe_dump(
        description, default_style='"', allow_unicode=True, width=1_000_000
    ).strip()

    permission = _agent_permission(
        str(frontmatter.get("tools", "")),
        source=f"plugins/super-fr/agents/{name}.md",
    )
    permission_lines = "\n".join(f"  {key}: {value}" for key, value in permission.items())

    banner = (
        f"# Generated from plugins/super-fr/agents/{name}.md by "
        "scripts/sync-opencode.py — do not edit this file directly."
    )

    return (
        "---\n"
        f"{banner}\n"
        f"description: {description_line}\n"
        "mode: subagent\n"
        "permission:\n"
        f"{permission_lines}\n"
        "---\n"
        f"{body.strip()}\n"
    )


def canonical_agents() -> dict[str, str]:
    """Map of agent name -> expected .opencode/agent/<name>.md content.

    Generated, like commands — the two frontmatter dialects differ, so this
    is not a byte-copy of plugins/super-fr/agents/*.md.
    """
    result = {}
    for path in sorted(AGENTS_CANONICAL_DIR.glob("*.md")):
        name = path.stem
        frontmatter = _skill_frontmatter(path)
        _, _, body = path.read_text().split("---", 2)
        result[name] = render_agent(name, frontmatter, body)
    return result


def mirror_agents() -> dict[str, Path]:
    """Map of agent name -> existing mirror agent path (if any)."""
    if not AGENTS_MIRROR_DIR.is_dir():
        return {}
    return {p.stem: p for p in sorted(AGENTS_MIRROR_DIR.glob("*.md"))}


def find_agents_drift() -> list[str]:
    """Human-readable agent mirror drift descriptions; empty means in sync."""
    return _find_category_drift(
        canonical_agents(),
        mirror_agents(),
        ".opencode/agent/",
        "no canonical source",
        "generated canonical",
    )


def sync_agents() -> None:
    """Write/overwrite the agents mirror to match canonical_agents() exactly."""
    canonical = canonical_agents()

    for name, path in mirror_agents().items():
        if name not in canonical:
            path.unlink()

    AGENTS_MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in canonical.items():
        dest = AGENTS_MIRROR_DIR / f"{name}.md"
        dest.write_text(content)


# ---------------------------------------------------------------------------
# rules / instructions


def canonical_instructions() -> dict[str, Path]:
    """Map of rule name (no .md) -> canonical rule markdown path."""
    result = {p.stem: p for p in sorted(RULES_CANONICAL_DIR.glob("*.md"))}
    for path in REPO_LOCAL_ONLY_RULES:
        if path.is_file():
            result[path.stem] = path
    return result


def mirror_instructions() -> dict[str, Path]:
    """Map of rule name -> existing mirror markdown path (if any)."""
    if not INSTRUCTIONS_MIRROR_DIR.is_dir():
        return {}
    return {p.stem: p for p in sorted(INSTRUCTIONS_MIRROR_DIR.glob("*.md"))}


def find_instructions_drift() -> list[str]:
    """Human-readable instructions mirror drift descriptions; empty means in sync."""
    return _find_category_drift(
        canonical_instructions(),
        mirror_instructions(),
        ".opencode/instructions/",
        "no canonical source",
        "canonical",
    )


def sync_instructions() -> None:
    """Write/overwrite the instructions mirror to match canonical exactly."""
    canonical = canonical_instructions()

    for name, path in mirror_instructions().items():
        if name not in canonical:
            path.unlink()

    INSTRUCTIONS_MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    for name, src in canonical.items():
        dest = INSTRUCTIONS_MIRROR_DIR / f"{name}.md"
        dest.write_text(src.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if either mirror is out of sync; make no writes.",
    )
    args = parser.parse_args()

    if args.check:
        drift = (
            find_drift() + find_instructions_drift() + find_commands_drift() + find_agents_drift()
        )
        if drift:
            print("scripts/sync-opencode.py --check: drift detected:", file=sys.stderr)
            for line in drift:
                print(f"  - {line}", file=sys.stderr)
            print("Run `scripts/sync-opencode.py` (no --check) to fix.", file=sys.stderr)
            return 1
        print("scripts/sync-opencode.py --check: .opencode/ mirrors are in sync.")
        return 0

    sync_skills()
    sync_instructions()
    sync_commands()
    sync_agents()
    print(
        f"Synced {len(canonical_skills())} skill(s) into "
        f"{SKILLS_MIRROR_DIR.relative_to(REPO_ROOT)}/, "
        f"{len(canonical_instructions())} instruction file(s) into "
        f"{INSTRUCTIONS_MIRROR_DIR.relative_to(REPO_ROOT)}/, "
        f"{len(canonical_commands())} command file(s) into "
        f"{COMMANDS_MIRROR_DIR.relative_to(REPO_ROOT)}/, and "
        f"{len(canonical_agents())} agent file(s) into "
        f"{AGENTS_MIRROR_DIR.relative_to(REPO_ROOT)}/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
