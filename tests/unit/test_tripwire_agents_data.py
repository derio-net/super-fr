"""CI tripwire: the `fr` wheel's copy of the two agents fr renders into a repo
(the `agents` artifact kind, spec 2026-10-07-cloud-triage R19, §H).

`plugins/super-fr/agents/` is canonical; `packages/fr/src/fr/agents/*.md` is the
generated wheel copy (`scripts/sync-agents-data.py`). The pin in
`fr.agents.CANONICAL_SHA256` is what turns "a canonical agent changed" into "the
`agents` kind's `current_version` moved": every repo's rendered copy carries the
version it was rendered for, so a changed agent under an unmoved version would
never reach a repo that already has one.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fr.agents import AGENT_NAMES, CANONICAL_SHA256, PINNED_AT_VERSION, canonical_text
from fr.artifacts.registry import ARTIFACT_KINDS

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_DIR = REPO_ROOT / "plugins" / "super-fr" / "agents"
PACKAGED_DIR = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "agents"

_SYNC_HINT = "run: uv run --no-project python scripts/sync-agents-data.py (the plugin is canonical)"
_BUMP_HINT = (
    "a canonical agent changed: move the `agents` kind's current_version in "
    "fr/artifacts/registry.py, register its re-render migration "
    "(fr.artifacts.agents_kind.rerender_migration), update fr.agents.CANONICAL_SHA256 "
    "and PINNED_AT_VERSION, then run `fr migrate artifacts --yes`"
)


def test_the_rendered_agents_are_exactly_the_two_the_spec_names() -> None:
    assert set(AGENT_NAMES) == {"fr-spec-reviewer", "fr-phase-executor"}
    assert set(CANONICAL_SHA256) == set(AGENT_NAMES)


def test_the_packaged_copy_is_byte_identical_to_the_plugin() -> None:
    for name in AGENT_NAMES:
        shipped = SHIPPED_DIR / f"{name}.md"
        packaged = PACKAGED_DIR / f"{name}.md"
        assert packaged.is_file(), f"{packaged} missing — {_SYNC_HINT}"
        assert packaged.read_bytes() == shipped.read_bytes(), f"{packaged} drifted — {_SYNC_HINT}"


def test_the_packaged_copy_is_read_through_importlib_resources() -> None:
    for name in AGENT_NAMES:
        assert canonical_text(name) == (SHIPPED_DIR / f"{name}.md").read_text(encoding="utf-8")


def test_the_pin_matches_the_canonical_agents() -> None:
    for name in AGENT_NAMES:
        digest = hashlib.sha256((SHIPPED_DIR / f"{name}.md").read_bytes()).hexdigest()
        assert digest == CANONICAL_SHA256[name], f"{name}: {_BUMP_HINT}"


def test_the_pin_was_taken_at_the_kinds_current_version() -> None:
    assert PINNED_AT_VERSION == ARTIFACT_KINDS["agents"].current_version, _BUMP_HINT


def test_this_repos_own_agents_are_the_rendered_files() -> None:
    """super-fr dogfoods the kind: its `.claude/agents/` holds rendered, stamped
    files, not the symlinks the cloud-triage branch first tried."""
    from fr.agents import render_agent

    version = ARTIFACT_KINDS["agents"].current_version
    for name in AGENT_NAMES:
        path = REPO_ROOT / ".claude" / "agents" / f"{name}.md"
        assert not path.is_symlink(), f"{path} is a symlink — run `uv run fr init agents`"
        assert path.read_text(encoding="utf-8") == render_agent(name, version), (
            f"{path} is not what this fr renders — run `uv run fr migrate artifacts --yes`"
        )
