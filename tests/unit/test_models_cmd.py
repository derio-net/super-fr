"""Phase 4: `fr models` CLI — set / get / resolve + persistence.

Spec §B.2: the runtime fallback persists the operator's tier→model choice to
~/.config/fr/models.yaml so it is chosen once per harness, not once per run.
"""

from __future__ import annotations

from pathlib import Path

from fr.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _env(home: Path) -> dict[str, str]:
    return {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")}


class TestModelsCmd:
    def test_set_persists_to_models_yaml(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
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

    def test_set_then_resolve(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
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

    def test_resolve_unknown_prints_nothing_exit_zero(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        res = runner.invoke(
            app, ["models", "resolve", "--harness", "claude-code", "--tier", "hard"]
        )
        assert res.exit_code == 0
        assert res.output.strip() == ""
