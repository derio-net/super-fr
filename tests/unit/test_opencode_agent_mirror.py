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
import typing
from pathlib import Path

import pytest
import yaml
from fr.types import PhaseHeader

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


def _phase_tier_names() -> tuple[str, ...]:
    """Independently derive the tier vocabulary from `PhaseHeader.tier`'s own
    Literal (typing.get_args) — never hardcoded here — so this test and the
    generator it pins can never quietly disagree about the tier set."""
    annotation = PhaseHeader.model_fields["tier"].annotation
    for arg in typing.get_args(annotation):
        literal_args = typing.get_args(arg)
        if literal_args:
            return literal_args
    raise AssertionError("PhaseHeader.tier has no Literal member to derive tiers from")


def _no_repo_models_path(tmp_path: Path) -> Path:
    """A models.yaml path that does not exist — the 'no repo config' case,
    driven through a fixture path so this test never touches the real
    repo's docs/superpowers/models.yaml."""
    return tmp_path / "models.yaml"


def test_canonical_agents_has_base_plus_one_per_tier(tmp_path: Path) -> None:
    agents = sync_opencode.canonical_agents(models_path=_no_repo_models_path(tmp_path))
    expected = {"fr-phase-executor"} | {f"fr-phase-executor-{tier}" for tier in _phase_tier_names()}
    assert set(agents) == expected


def test_no_model_key_anywhere_without_a_repo_models_yaml(tmp_path: Path) -> None:
    agents = sync_opencode.canonical_agents(models_path=_no_repo_models_path(tmp_path))
    for name, content in agents.items():
        frontmatter, _ = _frontmatter_and_body(content)
        assert "model" not in frontmatter, (
            f"{name}: carries a model: key with no repo models.yaml bound — a missing "
            "binding must mean inherit, never a written-but-empty key"
        )


def test_tier_files_carry_the_repo_bound_model_and_base_file_does_not(tmp_path: Path) -> None:
    bindings = {tier: f"opencode-model-{tier}" for tier in _phase_tier_names()}
    models_path = tmp_path / "models.yaml"
    models_path.write_text(yaml.safe_dump({"opencode": bindings}))

    agents = sync_opencode.canonical_agents(models_path=models_path)

    base_frontmatter, _ = _frontmatter_and_body(agents["fr-phase-executor"])
    assert "model" not in base_frontmatter, "the untiered base file must stay model-free"

    for tier, model in bindings.items():
        frontmatter, _ = _frontmatter_and_body(agents[f"fr-phase-executor-{tier}"])
        assert frontmatter.get("model") == model


def test_model_line_sits_immediately_after_mode_subagent_line(tmp_path: Path) -> None:
    bindings = {tier: f"opencode-model-{tier}" for tier in _phase_tier_names()}
    models_path = tmp_path / "models.yaml"
    models_path.write_text(yaml.safe_dump({"opencode": bindings}))

    agents = sync_opencode.canonical_agents(models_path=models_path)
    tier = next(iter(bindings))
    content = agents[f"fr-phase-executor-{tier}"]
    _, raw_frontmatter, _ = content.split("---", 2)
    lines = raw_frontmatter.splitlines()
    mode_idx = lines.index("mode: subagent")
    assert lines[mode_idx + 1].startswith("model: "), (
        f"model: must sit immediately after mode: subagent — installer's rewrite is "
        f"anchored on exactly that line; got: {lines[mode_idx + 1]!r}"
    )


def test_tier_file_description_names_its_tier_and_body_stays_canonical(tmp_path: Path) -> None:
    canonical_path = sync_opencode.AGENTS_CANONICAL_DIR / "fr-phase-executor.md"
    _, canonical_body = _frontmatter_and_body(canonical_path.read_text())

    agents = sync_opencode.canonical_agents(models_path=_no_repo_models_path(tmp_path))
    for tier in _phase_tier_names():
        frontmatter, body = _frontmatter_and_body(agents[f"fr-phase-executor-{tier}"])
        description = str(frontmatter.get("description", ""))
        assert tier in description, f"fr-phase-executor-{tier}'s description must name its tier"
        assert body.strip() == canonical_body.strip()


def test_no_name_key_in_frontmatter(tmp_path: Path) -> None:
    agents = sync_opencode.canonical_agents(models_path=_no_repo_models_path(tmp_path))
    frontmatter, _ = _frontmatter_and_body(agents["fr-phase-executor"])
    assert "name" not in frontmatter, (
        "OpenCode names an agent by its filename — a name: key is Claude-Code-only frontmatter"
    )


def test_mode_subagent_present(tmp_path: Path) -> None:
    agents = sync_opencode.canonical_agents(models_path=_no_repo_models_path(tmp_path))
    frontmatter, _ = _frontmatter_and_body(agents["fr-phase-executor"])
    assert frontmatter.get("mode") == "subagent"


def test_description_is_single_line_double_quoted_scalar(tmp_path: Path) -> None:
    agents = sync_opencode.canonical_agents(models_path=_no_repo_models_path(tmp_path))
    content = agents["fr-phase-executor"]
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


def test_permission_is_closed_translation_of_canonical_tools(tmp_path: Path) -> None:
    # Canonical tools: Read, Edit, Write, Bash, Grep, Glob
    agents = sync_opencode.canonical_agents(models_path=_no_repo_models_path(tmp_path))
    frontmatter, _ = _frontmatter_and_body(agents["fr-phase-executor"])
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


def test_body_is_canonical_body_verbatim(tmp_path: Path) -> None:
    canonical_path = sync_opencode.AGENTS_CANONICAL_DIR / "fr-phase-executor.md"
    _, canonical_body = _frontmatter_and_body(canonical_path.read_text())

    agents = sync_opencode.canonical_agents(models_path=_no_repo_models_path(tmp_path))
    _, mirror_body = _frontmatter_and_body(agents["fr-phase-executor"])

    assert mirror_body.strip() == canonical_body.strip()


def test_do_not_hand_edit_banner_names_the_sync_script(tmp_path: Path) -> None:
    agents = sync_opencode.canonical_agents(models_path=_no_repo_models_path(tmp_path))
    content = agents["fr-phase-executor"]
    assert "scripts/sync-opencode.py" in content
    assert "not edit" in content.lower() or "do not edit" in content.lower()


# ── review r-p1: the closed translation must actually be closed ──────────
#
# `_agent_permission` looked up each tool in a map of the three it knew and
# dropped everything else, then applied the constant denies with `update()`.
# Two consequences, neither of which anything reported:
#
#   f1  an unknown tool name — a new one, or a typo — vanished silently, so
#       the mirror was quietly LESS capable than the canonical agent. A
#       closed vocabulary that drops what it does not recognise is not
#       closed; this repo's own `fr.harness.model` and `fr.capabilities`
#       raise instead, and `_StrictLoader` exists for exactly this class of
#       silent loss.
#   f2  `update()` let a constant deny overwrite a mapped grant, so a
#       canonical `tools:` line GRANTING WebFetch produced a mirror DENYING
#       it — an inversion of the allowlist the translation claims to carry.


def test_an_unknown_tool_name_is_refused_rather_than_dropped() -> None:
    with pytest.raises(ValueError) as exc:
        sync_opencode._agent_permission("Bash, Edt")
    assert "Edt" in str(exc.value)
    assert "plugins/super-fr/agents" in str(exc.value) or "tools:" in str(exc.value)


def test_every_known_tool_maps_or_is_explicitly_implicit() -> None:
    """Read/Grep/Glob have no OpenCode permission key of their own — they
    must be KNOWN and map to nothing, not be unknown and dropped."""
    assert sync_opencode._agent_permission("Read, Grep, Glob") == {
        "task": "deny",
        "webfetch": "deny",
    }


def test_a_granted_tool_beats_the_default_deny() -> None:
    """The canonical `tools:` allowlist is the source of truth. A default
    deny fills a gap; it never overrides a grant."""
    assert sync_opencode._agent_permission("Bash, WebFetch")["webfetch"] == "allow"
    assert sync_opencode._agent_permission("Bash")["webfetch"] == "deny"


def test_the_shipped_agent_still_denies_task_and_webfetch() -> None:
    """The regression guard for the fix above: fr-phase-executor's canonical
    `tools:` grants neither, so both stay denied — `task: deny` is what keeps
    a phase executor from dispatching further subagents."""
    permission = sync_opencode._agent_permission("Read, Edit, Write, Bash, Grep, Glob")
    assert permission == {"edit": "allow", "bash": "allow", "task": "deny", "webfetch": "deny"}
