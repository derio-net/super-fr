"""Phase 4: `fr models` CLI — set / get / resolve + persistence.

Spec §B.2: the runtime fallback persists the operator's tier→model choice to
~/.config/fr/models.yaml so it is chosen once per harness, not once per run.

Spec 2026-09-20-opencode-tier-binding-reaches-dispatch §3.A adds a second
job to ``set``: a binding must take effect in the run that made it, not just
get written to config. ``TestModelsSetClosesTheLoop`` below pins that —
fixtures are seeded from the repo's OWN committed ``.opencode/agent/*.md``
mirror (never written inline here), same discipline as
``test_opencode_agents_materialize.py``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

runner = CliRunner()

REPO_ROOT = Path(__file__).resolve().parents[2]
MIRROR_DIR = REPO_ROOT / ".opencode" / "agent"


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the user config dir at a per-test sandbox.

    `default_models_path()` honors ``$XDG_CONFIG_HOME`` FIRST, then ``$HOME``.
    A CI runner sets XDG_CONFIG_HOME, so isolating only HOME (as an earlier
    draft did) leaked into the runner's real config and cross-polluted tests —
    the #390 CI failure. Set BOTH so the path resolves into tmp_path.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    return tmp_path


class TestModelsCmd:
    def test_set_persists_to_models_yaml(self, tmp_path: Path) -> None:
        res = runner.invoke(
            app,
            [
                "models",
                "set",
                "--harness",
                "claude-code",
                "--tier",
                "hard",
                "--model",
                "claude-opus-4-8",
            ],
        )
        assert res.exit_code == 0, res.output
        cfg = tmp_path / ".config/fr/models.yaml"
        assert cfg.exists()
        import yaml

        data = yaml.safe_load(cfg.read_text())
        assert data["claude-code"]["hard"] == "claude-opus-4-8"

    def test_set_then_resolve(self, tmp_path: Path) -> None:
        runner.invoke(
            app,
            [
                "models",
                "set",
                "--harness",
                "claude-code",
                "--tier",
                "standard",
                "--model",
                "claude-sonnet-5",
            ],
        )
        res = runner.invoke(
            app, ["models", "resolve", "--harness", "claude-code", "--tier", "standard"]
        )
        assert res.exit_code == 0
        assert res.output.strip() == "claude-sonnet-5"

    def test_resolve_unknown_prints_nothing_exit_zero(self, tmp_path: Path) -> None:
        res = runner.invoke(
            app, ["models", "resolve", "--harness", "claude-code", "--tier", "hard"]
        )
        assert res.exit_code == 0
        assert res.output.strip() == ""


def _seed_opencode_agents(config_home: Path) -> Path:
    agent_dir = config_home / "opencode" / "agent"
    agent_dir.mkdir(parents=True)
    for agent_file in MIRROR_DIR.glob("*.md"):
        shutil.copy(agent_file, agent_dir / agent_file.name)
    return agent_dir


class TestModelsSetClosesTheLoop:
    """The exact gap #498 reports, at the exact point the operator's answer
    is made: `fr models set --harness opencode ...` must rewrite the
    INSTALLED agent file, not just persist config nothing else reads until
    the next install."""

    def test_set_opencode_binding_rewrites_the_installed_agent_file(self, tmp_path: Path) -> None:
        agent_dir = _seed_opencode_agents(tmp_path / ".config")

        res = runner.invoke(
            app,
            ["models", "set", "--harness", "opencode", "--tier", "hard", "--model", "provider/B"],
        )

        assert res.exit_code == 0, res.output
        content = (agent_dir / "fr-phase-executor-hard.md").read_text()
        assert "model: provider/B" in content

    def test_set_names_the_file_it_changed(self, tmp_path: Path) -> None:
        agent_dir = _seed_opencode_agents(tmp_path / ".config")

        res = runner.invoke(
            app,
            ["models", "set", "--harness", "opencode", "--tier", "hard", "--model", "provider/B"],
        )

        assert str(agent_dir / "fr-phase-executor-hard.md") in res.output, (
            "a silent side effect on a path outside the repo is worse than none — "
            f"the command must name the file it changed, got: {res.output!r}"
        )

    def test_set_for_a_different_harness_touches_no_agent_file(self, tmp_path: Path) -> None:
        agent_dir = _seed_opencode_agents(tmp_path / ".config")
        before = {p.name: p.read_text() for p in agent_dir.glob("*.md")}

        res = runner.invoke(
            app,
            [
                "models",
                "set",
                "--harness",
                "claude-code",
                "--tier",
                "hard",
                "--model",
                "claude-opus-4-8",
            ],
        )

        assert res.exit_code == 0, res.output
        after = {p.name: p.read_text() for p in agent_dir.glob("*.md")}
        assert after == before, "a claude-code binding must not touch any OpenCode agent file"

    def test_set_with_no_opencode_agent_dir_still_succeeds(self, tmp_path: Path) -> None:
        """An operator who never opted into OpenCode delivery has no
        <config_home>/opencode/agent/ at all; `fr models set` must not fail
        for them, and must say plainly there was nothing to update."""
        res = runner.invoke(
            app,
            ["models", "set", "--harness", "opencode", "--tier", "hard", "--model", "provider/B"],
        )

        assert res.exit_code == 0, res.output
        assert "nothing to update" in res.output.lower()


class TestModelsApply:
    """`fr models apply --harness opencode` — the verb install.sh's delivery
    step calls instead of reimplementing tier resolution + frontmatter
    rewriting in bash (spec §3.A)."""

    def test_apply_opencode_materializes_the_current_resolved_config(self, tmp_path: Path) -> None:
        agent_dir = _seed_opencode_agents(tmp_path / ".config")
        runner.invoke(
            app,
            ["models", "set", "--harness", "opencode", "--tier", "hard", "--model", "provider/A"],
        )
        # Simulate a rebind that only touched config (as if written by hand,
        # or by a second process) — `apply` alone must still pick it up.
        import yaml

        cfg_path = tmp_path / ".config" / "fr" / "models.yaml"
        cfg = yaml.safe_load(cfg_path.read_text())
        cfg["opencode"]["hard"] = "provider/B"
        cfg_path.write_text(yaml.safe_dump(cfg))

        res = runner.invoke(app, ["models", "apply", "--harness", "opencode"])

        assert res.exit_code == 0, res.output
        content = (agent_dir / "fr-phase-executor-hard.md").read_text()
        assert "model: provider/B" in content
        assert "model: provider/A" not in content

    def test_apply_rejects_an_unknown_harness(self, tmp_path: Path) -> None:
        res = runner.invoke(app, ["models", "apply", "--harness", "bogus-harness"])

        assert res.exit_code != 0, "a typo'd --harness must be refused, not silently no-op"

    def test_apply_reports_no_matching_files_for_empty_directory(self, tmp_path: Path) -> None:
        """Phase 1.T1: when no agent files exist, report the absence plainly."""
        res = runner.invoke(app, ["models", "apply", "--harness", "opencode"])

        assert res.exit_code == 0, res.output
        assert "nothing to update (no opencode agent files found)" in res.output.lower()

    def test_apply_reports_discovered_count_when_files_already_correct(self, tmp_path: Path) -> None:
        """Phase 1.T1: when agent files exist and are already correct, report
        the count as 'already up to date', not the confusing 'nothing to update'
        message that implies there were no files."""
        agent_dir = _seed_opencode_agents(tmp_path / ".config")
        # Ensure all agents are already correct by setting config matching them
        runner.invoke(
            app,
            ["models", "set", "--harness", "opencode", "--tier", "mechanical", "--model", "m"],
        )
        runner.invoke(
            app,
            ["models", "set", "--harness", "opencode", "--tier", "standard", "--model", "s"],
        )
        runner.invoke(
            app,
            ["models", "set", "--harness", "opencode", "--tier", "hard", "--model", "h"],
        )

        # Now apply again — should be idempotent but report the count
        res = runner.invoke(app, ["models", "apply", "--harness", "opencode"])

        assert res.exit_code == 0, res.output
        # Should report the count of agent files found, not "nothing to update"
        assert "agent files already up to date" in res.output.lower(), (
            f"apply must report discovered count for idempotent materialization, got: {res.output!r}"
        )
