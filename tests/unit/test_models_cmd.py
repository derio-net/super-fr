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

    def test_apply_reports_discovered_count_when_files_already_correct(
        self, tmp_path: Path
    ) -> None:
        """Phase 1.T1: when agent files exist and are already correct, report
        the count as 'already up to date', not the confusing 'nothing to update'
        message that implies there were no files."""
        agent_dir = tmp_path / ".config" / "opencode" / "agent"
        agent_dir.mkdir(parents=True)
        agent_files = [
            agent_dir / "fr-phase-executor-mechanical.md",
            agent_dir / "fr-phase-executor-standard.md",
            agent_dir / "fr-phase-executor-hard.md",
        ]
        for path, model in zip(agent_files, ("m", "s", "h"), strict=True):
            path.write_text(
                f'---\ndescription: "test agent"\nmode: subagent\nmodel: {model}\n---\nbody\n'
            )

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
        # Should report the count of matching agent files, not "nothing to update"
        assert "3 agent files already up to date" in res.output.lower(), (
            f"apply must report discovered count for idempotent "
            f"materialization, got: {res.output!r}"
        )


# --- spec 2026-10-06-model-binding-churn §B: probing `set`, and `check` ---------


class _FakeProber:
    """A prober scripted per model: ``states`` maps a model to ``live``,
    ``unknown`` or ``dead[:hint]``; anything unlisted is live."""

    def __init__(self, entries, states=None) -> None:
        self.entries = entries
        self.states = states or {}
        self.probed: list[str] = []

    def probe(self, model: str):
        from fr.bindings.probe import ProbeResult

        self.probed.append(model)
        state = self.states.get(model, "live")
        verdict, _, hint = state.partition(":")
        detail = (
            f"ProviderModelNotFoundError: Model not found: {model}"
            if verdict == "dead"
            else ("server error" if verdict == "unknown" else "")
        )
        return ProbeResult(verdict, detail, hint or None, 0.0)  # type: ignore[arg-type]

    def catalogue(self, provider: str):
        return [e for e in self.entries if e.provider == provider]


def _ent(name: str, family: str, date: str, price: float = 10.0):
    from fr.bindings.catalogue import CatalogueEntry

    return CatalogueEntry(f"prov/{name}", "prov", family, date, price, True)


ENTRIES = [
    _ent("std", "s", "2026-01-01"),
    _ent("std2", "s", "2026-04-01"),
    _ent("orch", "o", "2026-01-01"),
    _ent("orch2", "o", "2026-05-01"),
]


def _patch_prober(monkeypatch: pytest.MonkeyPatch, prober) -> None:
    import fr.bindings

    monkeypatch.setattr(fr.bindings, "prober_for", lambda h: prober if h == "opencode" else None)


def _interactive(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    import fr.artifacts.trigger as trigger

    monkeypatch.setattr(trigger, "is_interactive", lambda **_: value)


def _set(model: str, *extra: str, tier: str = "standard", harness: str = "opencode"):
    return runner.invoke(
        app,
        ["models", "set", "--harness", harness, "--tier", tier, "--model", model, *extra],
        input=None,
    )


def _models_yaml(tmp_path: Path) -> Path:
    return tmp_path / ".config/fr/models.yaml"


class TestSetProbes:
    def test_a_dead_model_off_a_terminal_is_refused_with_the_error_and_the_proposal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_prober(monkeypatch, _FakeProber(ENTRIES, {"prov/std": "dead"}))
        _interactive(monkeypatch, False)
        res = _set("prov/std")
        assert res.exit_code == 2, res.output
        assert "ProviderModelNotFoundError" in res.output
        assert "prov/std2" in res.output and "family" in res.output
        assert not _models_yaml(tmp_path).exists()

    def test_a_dead_model_on_a_terminal_asks_and_a_yes_persists_the_proposal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_prober(monkeypatch, _FakeProber(ENTRIES, {"prov/std": "dead"}))
        _interactive(monkeypatch, True)
        res = runner.invoke(
            app,
            ["models", "set", "--harness", "opencode", "--tier", "standard", "--model", "prov/std"],
            input="y\n",
        )
        assert res.exit_code == 0, res.output
        import yaml

        assert (
            yaml.safe_load(_models_yaml(tmp_path).read_text())["opencode"]["standard"]
            == "prov/std2"
        )
        assert "prov/std → prov/std2" in res.output
        for word in ("retired", "operator", "family"):
            assert word in res.output

    def test_a_no_on_a_terminal_persists_nothing_and_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_prober(monkeypatch, _FakeProber(ENTRIES, {"prov/std": "dead"}))
        _interactive(monkeypatch, True)
        res = runner.invoke(
            app,
            ["models", "set", "--harness", "opencode", "--tier", "standard", "--model", "prov/std"],
            input="n\n",
        )
        assert res.exit_code == 2
        assert not _models_yaml(tmp_path).exists()

    def test_an_unknown_probe_warns_and_persists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_prober(monkeypatch, _FakeProber(ENTRIES, {"prov/std": "unknown"}))
        _interactive(monkeypatch, False)
        res = _set("prov/std")
        assert res.exit_code == 0, res.output
        assert "inconclusive" in res.output
        assert "prov/std" in _models_yaml(tmp_path).read_text()

    def test_no_probe_persists_and_says_it_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prober = _FakeProber(ENTRIES, {"prov/std": "dead"})
        _patch_prober(monkeypatch, prober)
        res = _set("prov/std", "--no-probe")
        assert res.exit_code == 0, res.output
        assert "probe skipped" in res.output
        assert prober.probed == []
        assert "prov/std" in _models_yaml(tmp_path).read_text()

    def test_other_harnesses_persist_unprobed(self, tmp_path: Path) -> None:
        res = _set("claude-sonnet-5", harness="claude-code")
        assert res.exit_code == 0, res.output
        assert "not probed (live probing covers opencode only)" in res.output

    def test_a_live_model_persists_quietly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_prober(monkeypatch, _FakeProber(ENTRIES))
        res = _set("prov/std")
        assert res.exit_code == 0, res.output
        assert "substituted" not in res.output.lower()


def _bind(tmp_path: Path, **tiers: str) -> None:
    import yaml

    path = _models_yaml(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"opencode": tiers}))


class TestCheck:
    def test_one_line_per_binding_with_verdict_proposal_and_offer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _bind(tmp_path, standard="prov/std", orchestrator="prov/orch")
        _patch_prober(monkeypatch, _FakeProber(ENTRIES, {"prov/std": "dead"}))
        _interactive(monkeypatch, False)
        res = runner.invoke(app, ["models", "check"])
        assert res.exit_code == 1, res.output
        lines = {
            ln.split(":")[0].strip(): ln
            for ln in res.output.splitlines()
            if ln.startswith("opencode/")
        }
        assert "dead" in lines["opencode/standard"]
        assert "prov/std2" in lines["opencode/standard"] and "family" in lines["opencode/standard"]
        assert "×1.0" in lines["opencode/standard"]
        assert "live" in lines["opencode/orchestrator"]
        assert (
            "offer" in lines["opencode/orchestrator"]
            and "prov/orch2" in lines["opencode/orchestrator"]
        )
        # Off a terminal it only reports.
        assert "standard: prov/std\n" in _models_yaml(tmp_path).read_text()

    def test_other_harnesses_are_unprobed(self, tmp_path: Path) -> None:
        import yaml

        path = _models_yaml(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"claude-code": {"standard": "claude-sonnet-5"}}))
        res = runner.invoke(app, ["models", "check"])
        assert res.exit_code == 0, res.output
        assert "claude-code/standard" in res.output and "unprobed" in res.output

    def test_an_operator_only_proposal_is_marked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = [_ent("std", "s", "2026-01-01", 10.0), _ent("std2", "s", "2026-04-01", 25.0)]
        _bind(tmp_path, standard="prov/std")
        _patch_prober(monkeypatch, _FakeProber(entries, {"prov/std": "dead"}))
        _interactive(monkeypatch, False)
        res = runner.invoke(app, ["models", "check"])
        assert "operator-only" in res.output and "×2.5" in res.output

    def test_on_a_terminal_a_proposal_defaults_yes_and_an_offer_defaults_no(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _bind(tmp_path, standard="prov/std", orchestrator="prov/orch")
        _patch_prober(monkeypatch, _FakeProber(ENTRIES, {"prov/std": "dead"}))
        _interactive(monkeypatch, True)
        res = runner.invoke(app, ["models", "check"], input="\n\n")
        assert res.exit_code == 0, res.output
        import yaml

        cfg = yaml.safe_load(_models_yaml(tmp_path).read_text())["opencode"]
        assert cfg["standard"] == "prov/std2"  # the proposal, accepted by default
        assert cfg["orchestrator"] == "prov/orch"  # the offer, declined by default
        assert "prov/std → prov/std2" in res.output

    def test_an_offer_is_applied_only_on_an_explicit_yes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _bind(tmp_path, orchestrator="prov/orch")
        _patch_prober(monkeypatch, _FakeProber(ENTRIES))
        _interactive(monkeypatch, True)
        res = runner.invoke(app, ["models", "check"], input="y\n")
        import yaml

        assert (
            yaml.safe_load(_models_yaml(tmp_path).read_text())["opencode"]["orchestrator"]
            == "prov/orch2"
        )
        assert "upgrade" in res.output

    def test_a_repo_layer_dead_binding_is_not_rewritten(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import yaml

        repo = tmp_path / "repo"
        (repo / "docs/superpowers").mkdir(parents=True)
        (repo / "docs/superpowers/models.yaml").write_text(
            yaml.safe_dump({"opencode": {"standard": "prov/std"}})
        )
        monkeypatch.chdir(repo)
        import subprocess

        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        _patch_prober(monkeypatch, _FakeProber(ENTRIES, {"prov/std": "dead"}))
        _interactive(monkeypatch, True)
        res = runner.invoke(app, ["models", "check"], input="y\n")
        assert res.exit_code == 1, res.output
        assert "docs/superpowers/models.yaml" in res.output
        assert not _models_yaml(tmp_path).exists()
