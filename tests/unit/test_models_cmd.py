"""Phase 4: `fr models` CLI — set / get / resolve + persistence.

Spec §B.2: the runtime fallback persists the operator's tier→model choice to
~/.config/fr/models.yaml so it is chosen once per harness, not once per run.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

runner = CliRunner()


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
