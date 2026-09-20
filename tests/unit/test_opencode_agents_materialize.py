"""`fr.opencode_agents.materialize_agents` — the in-place rewrite that makes a
tier binding reach the agent OpenCode dispatches (spec
2026-09-20-opencode-tier-binding-reaches-dispatch §3.A).

Fixtures are SEEDED from the repo's own committed `.opencode/agent/*.md`
mirror (copied verbatim into `tmp_path`), never written inline here — a
constructed fixture would drift from what install.sh actually delivers, and
this whole defect is about the delivered file (plan P1.T1.S1).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MIRROR_DIR = REPO_ROOT / ".opencode" / "agent"


@pytest.fixture()
def config_home(tmp_path: Path) -> Path:
    """A sandboxed config dir seeded with the committed OpenCode agent mirror."""
    agent_dir = tmp_path / "opencode" / "agent"
    agent_dir.mkdir(parents=True)
    for agent_file in MIRROR_DIR.glob("*.md"):
        shutil.copy(agent_file, agent_dir / agent_file.name)
    return tmp_path


def _model_lines(content: str) -> list[str]:
    return [line for line in content.splitlines() if line.startswith("model:")]


def _agent_dir(config_home: Path) -> Path:
    return config_home / "opencode" / "agent"


class TestMaterializeAgents:
    def test_binds_all_three_tiers_after_mode_subagent(self, config_home: Path) -> None:
        from fr.opencode_agents import materialize_agents

        models_cfg = {
            "opencode": {
                "mechanical": "claude-haiku-4-5",
                "standard": "claude-sonnet-5",
                "hard": "claude-opus-4-8",
            }
        }
        materialize_agents(config_home, models_cfg=models_cfg)

        for tier, model in models_cfg["opencode"].items():
            content = (_agent_dir(config_home) / f"fr-phase-executor-{tier}.md").read_text()
            lines = content.splitlines()
            anchor_idx = lines.index("mode: subagent")
            assert lines[anchor_idx + 1] == f"model: {model}"
            assert _model_lines(content) == [f"model: {model}"]

    def test_stale_binding_regression(self, config_home: Path) -> None:
        """spec §1.1 — the reason this spec exists: an agent already carrying
        `model: <A>` must read `<B>` after a rebind, with exactly ONE
        `model:` line, not two and not the stale one."""
        from fr.opencode_agents import materialize_agents

        hard_file = _agent_dir(config_home) / "fr-phase-executor-hard.md"
        # Seed a STALE prior binding, as install.sh's awk (or a previous
        # materialize_agents run) would have left one.
        materialize_agents(config_home, models_cfg={"opencode": {"hard": "model-A"}})
        assert _model_lines(hard_file.read_text()) == ["model: model-A"]

        materialize_agents(config_home, models_cfg={"opencode": {"hard": "model-B"}})

        content = hard_file.read_text()
        assert _model_lines(content) == ["model: model-B"]

    def test_unbound_tier_gets_no_model_key_at_all(self, config_home: Path) -> None:
        from fr.opencode_agents import materialize_agents

        materialize_agents(config_home, models_cfg={"opencode": {}})

        content = (_agent_dir(config_home) / "fr-phase-executor-mechanical.md").read_text()
        assert _model_lines(content) == []
        assert "model:" not in content

    def test_untiered_base_agent_never_gets_a_model(self, config_home: Path) -> None:
        from fr.opencode_agents import materialize_agents

        models_cfg = {"opencode": {"mechanical": "m", "standard": "s", "hard": "h"}}
        materialize_agents(config_home, models_cfg=models_cfg)

        content = (_agent_dir(config_home) / "fr-phase-executor.md").read_text()
        assert _model_lines(content) == []

    def test_targets_are_discovered_by_tier_suffix_not_hardcoded_stem(
        self, config_home: Path
    ) -> None:
        """spec-review r1: a non-canonical agent whose stem ends in a real
        tier IS rewritten; one whose stem ends in something that merely
        looks like a tier is left byte-identical. The module must not
        hardcode `fr-phase-executor` anywhere to make this true."""
        from fr.opencode_agents import materialize_agents

        agent_dir = _agent_dir(config_home)
        other_tiered = agent_dir / "some-other-agent-hard.md"
        other_tiered.write_text("---\nmode: subagent\n---\nbody\n")
        not_a_tier = agent_dir / "foo-turbo.md"
        not_a_tier_before = "---\nmode: subagent\n---\nbody\n"
        not_a_tier.write_text(not_a_tier_before)

        materialize_agents(config_home, models_cfg={"opencode": {"hard": "model-X"}})

        assert _model_lines(other_tiered.read_text()) == ["model: model-X"]
        assert not_a_tier.read_text() == not_a_tier_before

    def test_missing_agent_dir_is_a_reported_no_op_not_an_exception(self, tmp_path: Path) -> None:
        """An operator who never opted into OpenCode delivery has no
        <config_home>/opencode/agent/ at all; `fr models set` must not fail
        for them."""
        from fr.opencode_agents import materialize_agents

        changes = materialize_agents(tmp_path, models_cfg={"opencode": {"hard": "model-X"}})

        assert changes == []

    def test_missing_files_in_an_existing_dir_is_also_a_reported_no_op(
        self, tmp_path: Path
    ) -> None:
        from fr.opencode_agents import materialize_agents

        (tmp_path / "opencode" / "agent").mkdir(parents=True)

        changes = materialize_agents(tmp_path, models_cfg={"opencode": {"hard": "model-X"}})

        assert changes == []

    def test_returns_what_it_changed(self, config_home: Path) -> None:
        from fr.opencode_agents import materialize_agents

        changes = materialize_agents(config_home, models_cfg={"opencode": {"hard": "model-X"}})

        assert len(changes) == 1
        change = changes[0]
        assert change.path == _agent_dir(config_home) / "fr-phase-executor-hard.md"
        assert change.tier == "hard"
        assert change.old_model is None
        assert change.new_model == "model-X"

    def test_writes_nothing_outside_the_agent_dir(self, config_home: Path) -> None:
        from fr.opencode_agents import materialize_agents

        sentinel = config_home / "fr" / "models.yaml"
        sentinel.parent.mkdir(parents=True)
        sentinel_content = "opencode:\n  hard: sentinel-model\n"
        sentinel.write_text(sentinel_content)
        sibling = _agent_dir(config_home).parent / "not-an-agent.txt"
        sibling_content = "leave me alone\n"
        sibling.write_text(sibling_content)

        materialize_agents(
            config_home,
            models_cfg={"opencode": {"mechanical": "m", "standard": "s", "hard": "h"}},
        )

        assert sentinel.read_text() == sentinel_content
        assert sibling.read_text() == sibling_content
