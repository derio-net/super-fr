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
from fr.opencode_agents import materialize_agents

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

        result = materialize_agents(tmp_path, models_cfg={"opencode": {"hard": "model-X"}})

        assert result.considered == 0
        assert result.changes == []

    def test_missing_files_in_an_existing_dir_is_also_a_reported_no_op(
        self, tmp_path: Path
    ) -> None:
        from fr.opencode_agents import materialize_agents

        (tmp_path / "opencode" / "agent").mkdir(parents=True)

        result = materialize_agents(tmp_path, models_cfg={"opencode": {"hard": "model-X"}})

        assert result.considered == 0
        assert result.changes == []

    def test_returns_what_it_changed(self, config_home: Path) -> None:
        from fr.opencode_agents import materialize_agents

        result = materialize_agents(config_home, models_cfg={"opencode": {"hard": "model-X"}})

        # One `-hard` file per canonical agent: fr-phase-executor and, since
        # 2026-09-24 spec §E, fr-spec-reviewer.
        assert sorted(c.path.name for c in result.changes) == [
            "fr-phase-executor-hard.md",
            "fr-spec-reviewer-hard.md",
        ]
        change = next(c for c in result.changes if c.path.name == "fr-phase-executor-hard.md")
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


# ── review r-p1: three defects found by probing the module directly ──────
#
# f3 is the serious one and it is this spec's own defect class, one level in:
# when the `mode: subagent` anchor is absent (a hand-edited file, or a future
# generator change), `_rewrite` inserts nothing — but a Change was appended
# regardless, so the function REPORTED writing a model it had not written.
# A materialiser whose whole job is "make the binding real, and say so"
# cannot be allowed to say so falsely.
#
# f1: the rewrite ran over the WHOLE file, so a markdown BODY line beginning
# `model:` — a future agent documenting its own frontmatter, say — was
# silently deleted. Inherited from install.sh's awk (`/^model:/ { next }`),
# which had no way to know where the frontmatter ended.
#
# f2: the `old_model == model` early-skip left a correct-but-MISPLACED
# `model:` line alone, so the "immediately after the anchor" invariant the
# module documents did not actually hold for every file it had seen.


def _seed(agent_dir: Path, name: str, content: str) -> Path:
    agent_dir.mkdir(parents=True, exist_ok=True)
    path = agent_dir / name
    path.write_text(content)
    return path


def test_a_file_missing_the_anchor_is_reported_as_a_problem_not_a_change(
    tmp_path: Path,
) -> None:
    """f3. Nothing is written, and the report says so — the one thing this
    function must never do is claim a binding took effect when it did not."""
    agent_dir = tmp_path / "opencode" / "agent"
    path = _seed(
        agent_dir,
        "x-hard.md",
        '---\ndescription: "x"\npermission:\n  edit: allow\n---\nbody\n',
    )
    before = path.read_text()

    result = materialize_agents(tmp_path, models_cfg={"opencode": {"hard": "provider/B"}})

    assert len(result.changes) == 1
    (change,) = result.changes
    assert change.problem is not None, "a file that could not be rewritten must say so"
    assert "mode: subagent" in change.problem
    assert change.new_model is None, "must not claim a model it did not write"
    assert path.read_text() == before, "a file it cannot rewrite must be left untouched"


def test_a_body_line_beginning_model_is_not_eaten(tmp_path: Path) -> None:
    """f1. The rewrite is scoped to the frontmatter; the body is content."""
    agent_dir = tmp_path / "opencode" / "agent"
    path = _seed(
        agent_dir,
        "y-hard.md",
        '---\ndescription: "y"\nmode: subagent\n---\n'
        "Frontmatter keys you may set:\n\nmodel: <provider/id>\n\nEnd.\n",
    )

    materialize_agents(tmp_path, models_cfg={"opencode": {"hard": "provider/B"}})

    body = path.read_text().split("---\n", 2)[2]
    assert "model: <provider/id>" in body, "the body's own prose must survive"
    frontmatter = path.read_text().split("---\n", 2)[1]
    assert "model: provider/B" in frontmatter


def test_a_correct_but_misplaced_model_is_moved_to_the_anchor(tmp_path: Path) -> None:
    """f2. The early-skip compared model VALUES, so a right value in the
    wrong place was left there and the documented invariant quietly failed."""
    agent_dir = tmp_path / "opencode" / "agent"
    path = _seed(
        agent_dir,
        "z-hard.md",
        '---\nmodel: provider/B\ndescription: "z"\nmode: subagent\n---\nbody\n',
    )

    materialize_agents(tmp_path, models_cfg={"opencode": {"hard": "provider/B"}})

    lines = path.read_text().splitlines()
    assert lines.count("model: provider/B") == 1
    assert lines[lines.index("mode: subagent") + 1] == "model: provider/B"


def test_an_already_correct_file_is_not_rewritten(tmp_path: Path) -> None:
    """The other half of f2: idempotence must survive the fix — a file that
    already renders correctly reports no change and is not touched."""
    agent_dir = tmp_path / "opencode" / "agent"
    path = _seed(
        agent_dir,
        "w-hard.md",
        '---\ndescription: "w"\nmode: subagent\nmodel: provider/B\n---\nbody\n',
    )
    before = path.stat().st_mtime_ns

    result = materialize_agents(tmp_path, models_cfg={"opencode": {"hard": "provider/B"}})

    assert result.changes == []
    assert result.considered == 1, "one tier-suffixed agent file was discovered"
    assert path.stat().st_mtime_ns == before, "an already-correct file must not be rewritten"


def test_reports_count_of_discovered_agent_files_separately_from_changes(
    tmp_path: Path,
) -> None:
    """Phase 1.T1: assert that the materializer reports the count of
    discovered supported-tier agent files separately from changes. Both
    when no matching files exist and when files are found but no changes
    are needed, the result must include the discovery count so the CLI
    can distinguish the two no-op cases."""
    agent_dir = tmp_path / "opencode" / "agent"

    # Case 1: No matching agent files at all — discovered count is 0
    (agent_dir).mkdir(parents=True, exist_ok=True)
    # Add an unrelated .md file that should not count
    (agent_dir / "README.md").write_text("# Not an agent\n")

    result = materialize_agents(tmp_path, models_cfg={"opencode": {"hard": "model-X"}})

    assert hasattr(result, "considered"), (
        "result must carry a considered count separate from changes"
    )
    assert result.considered == 0, "unrelated .md files must not count"
    assert result.changes == [], "no tier-suffixed agent files means no changes"

    # Case 2: Agent files exist and are already correct — discovered count > 0
    agent_dir = tmp_path / "opencode" / "agent"
    _seed(
        agent_dir,
        "x-hard.md",
        '---\ndescription: "x"\nmode: subagent\nmodel: model-X\n---\nbody\n',
    )

    result = materialize_agents(tmp_path, models_cfg={"opencode": {"hard": "model-X"}})

    assert result.considered == 1, "one tier-suffixed agent file was discovered"
    assert result.changes == [], (
        "correct file not rewritten, so changes is empty, but considered is not"
    )
