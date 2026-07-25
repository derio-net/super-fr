"""fr.hermes — install/uninstall core, plus a `fr hermes` CLI smoke.

Every mutation must be idempotent and fully reversible, and must never touch the
user's own cli-config.yaml keys or SOUL.md content outside the managed markers.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from fr import hermes
from fr.cli import app
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# hooks: merge


def test_merge_hooks_idempotent_and_preserves_unrelated_keys(tmp_path: Path) -> None:
    cfg = tmp_path / "cli-config.yaml"
    cfg.write_text(
        yaml.safe_dump({"model": "hermes-4", "hooks": {"pre_llm_call": [{"command": "user.sh"}]}})
    )
    entries = [{"event": "pre_tool_call", "matcher": "write_file", "command": "/h/edit.sh"}]

    hermes.merge_hooks(cfg, entries)
    hermes.merge_hooks(cfg, entries)  # idempotent

    data = yaml.safe_load(cfg.read_text())
    assert data["model"] == "hermes-4"  # unrelated key preserved
    assert data["hooks"]["pre_llm_call"] == [{"command": "user.sh"}]  # user hook preserved
    assert data["hooks"]["pre_tool_call"] == [{"command": "/h/edit.sh", "matcher": "write_file"}]


def test_unmerge_removes_only_ours(tmp_path: Path) -> None:
    cfg = tmp_path / "cli-config.yaml"
    entries = [{"event": "pre_tool_call", "matcher": "write_file", "command": "/h/edit.sh"}]
    cfg.write_text(yaml.safe_dump({"hooks": {"pre_tool_call": [{"command": "user.sh"}]}}))
    hermes.merge_hooks(cfg, entries)
    hermes.unmerge_hooks(cfg, entries)
    data = yaml.safe_load(cfg.read_text())
    assert data["hooks"]["pre_tool_call"] == [{"command": "user.sh"}]


def test_merge_into_non_mapping_config_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "cli-config.yaml"
    cfg.write_text("- just\n- a\n- list\n")
    original = cfg.read_text()
    try:
        hermes.merge_hooks(cfg, [{"event": "pre_tool_call", "command": "/h/x.sh"}])
        raised = False
    except hermes.HermesError:
        raised = True
    assert raised
    assert cfg.read_text() == original  # untouched — no clobber


def test_merge_malformed_yaml_raises_hermes_error_without_clobber(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("hooks: [unterminated\n")
    original = cfg.read_text()

    try:
        hermes.merge_hooks(cfg, [{"event": "pre_tool_call", "command": "/h/x.sh"}])
        raised = False
    except hermes.HermesError:
        raised = True

    assert raised
    assert cfg.read_text() == original


# ---------------------------------------------------------------------------
# allowlist


def test_allowlist_add_idempotent_and_remove(tmp_path: Path) -> None:
    path = tmp_path / "shell-hooks-allowlist.json"
    pairs = [("pre_tool_call", "/h/edit.sh")]
    hermes.add_allowlist(path, pairs)
    hermes.add_allowlist(path, pairs)
    data = json.loads(path.read_text())
    assert data["approvals"] == [{"event": "pre_tool_call", "command": "/h/edit.sh"}]
    hermes.remove_allowlist(path, pairs)
    assert json.loads(path.read_text())["approvals"] == []


# ---------------------------------------------------------------------------
# SOUL.md managed block


def test_soul_block_applies_preserves_and_strips(tmp_path: Path) -> None:
    soul = tmp_path / "SOUL.md"
    soul.write_text("# My identity\nBe helpful.\n")
    block = f"{hermes.SOUL_BLOCK_START}\nrules here\n{hermes.SOUL_BLOCK_END}\n"

    hermes.apply_soul_block(soul, block)
    once = soul.read_text()
    assert "# My identity" in once
    assert hermes.SOUL_BLOCK_START in once and hermes.SOUL_BLOCK_END in once

    hermes.apply_soul_block(soul, block)  # idempotent
    assert soul.read_text() == once

    hermes.strip_soul_block(soul)
    after = soul.read_text()
    assert "# My identity" in after and "Be helpful." in after
    assert hermes.SOUL_BLOCK_START not in after


def test_soul_block_apply_to_missing_file(tmp_path: Path) -> None:
    soul = tmp_path / "SOUL.md"
    block = f"{hermes.SOUL_BLOCK_START}\nrules\n{hermes.SOUL_BLOCK_END}\n"
    hermes.apply_soul_block(soul, block)
    assert soul.read_text().strip().startswith(hermes.SOUL_BLOCK_START)


# ---------------------------------------------------------------------------
# full install/uninstall roundtrip against the real repo sources


def test_install_uninstall_roundtrip(tmp_path: Path) -> None:
    home = tmp_path / "hermes-home"
    (home).mkdir()
    (home / "SOUL.md").write_text("# user soul\n")

    hermes.install(REPO_ROOT, home)

    # hook tree copied (with lib/ for the guards' ../lib sourcing)
    assert (home / hermes.HOOKS_SUBDIR / "hermes" / "fr-isolation-required.sh").is_file()
    assert (home / hermes.HOOKS_SUBDIR / "lib" / "fr-isolation-decision.sh").is_file()
    # Hooks must land in Hermes's actual main config. A prior implementation
    # wrote cli-config.yaml, which Hermes never reads, so install looked healthy
    # while every enforcement hook was inert.
    cfg = yaml.safe_load((home / "config.yaml").read_text())
    cmds = [e["command"] for lst in cfg["hooks"].values() for e in lst]
    assert any(c.endswith("hermes/fr-isolation-required.sh") for c in cmds)
    assert all(c.startswith(str(home)) for c in cmds)
    assert all(e["timeout"] == 30 for entries in cfg["hooks"].values() for e in entries)
    assert not (home / "cli-config.yaml").exists()
    # allowlisted
    approvals = json.loads((home / "shell-hooks-allowlist.json").read_text())["approvals"]
    assert len(approvals) >= 4
    # SOUL block applied, user content preserved
    soul = (home / "SOUL.md").read_text()
    assert "# user soul" in soul and hermes.SOUL_BLOCK_START in soul

    hermes.uninstall(REPO_ROOT, home)

    assert not (home / hermes.HOOKS_SUBDIR).exists()
    cfg2 = yaml.safe_load((home / "config.yaml").read_text()) or {}
    assert not cfg2.get("hooks")
    assert json.loads((home / "shell-hooks-allowlist.json").read_text())["approvals"] == []
    soul2 = (home / "SOUL.md").read_text()
    assert "# user soul" in soul2 and hermes.SOUL_BLOCK_START not in soul2


def test_install_migrates_legacy_cli_config_hooks(tmp_path: Path) -> None:
    home = tmp_path / "hermes-home"
    home.mkdir()
    hooks_dir = home / hermes.HOOKS_SUBDIR
    entries = hermes.snippet_entries(REPO_ROOT, hooks_dir)
    legacy = home / "cli-config.yaml"
    legacy.write_text(
        yaml.safe_dump(
            {
                "legacy_user_key": "preserved",
                "hooks": {"pre_llm_call": [{"command": "/user/hook.sh"}]},
            }
        )
    )
    hermes.merge_hooks(legacy, entries)

    hermes.install(REPO_ROOT, home)

    migrated = yaml.safe_load((home / "config.yaml").read_text())
    migrated_commands = [e["command"] for event in migrated["hooks"].values() for e in event]
    assert any(command.endswith("hermes/fr-isolation-required.sh") for command in migrated_commands)

    legacy_after = yaml.safe_load(legacy.read_text())
    assert legacy_after["legacy_user_key"] == "preserved"
    assert legacy_after["hooks"] == {"pre_llm_call": [{"command": "/user/hook.sh"}]}


def test_install_replaces_stale_owned_hook_registration(tmp_path: Path) -> None:
    home = tmp_path / "hermes-home"
    home.mkdir()
    hooks_dir = home / hermes.HOOKS_SUBDIR
    config_path = home / hermes.CONFIG_FILENAME
    hermes.merge_hooks(
        config_path,
        [
            {
                "event": "on_session_start",
                "command": str(hooks_dir / "fr-acceptance-nag.sh"),
                "timeout": 30,
            }
        ],
    )

    hermes.install(REPO_ROOT, home)

    data = yaml.safe_load(config_path.read_text())
    assert "on_session_start" not in data["hooks"]
    commands = [
        item["command"]
        for items in data["hooks"].values()
        for item in items
        if isinstance(item, dict)
    ]
    assert commands.count(str(hooks_dir / "fr-acceptance-nag.sh")) == 1


def test_install_malformed_config_is_atomic(tmp_path: Path) -> None:
    home = tmp_path / "hermes-home"
    home.mkdir()
    config = home / "config.yaml"
    config.write_text("hooks: [unterminated\n")
    legacy = home / "cli-config.yaml"
    legacy.write_text("legacy_user_key: preserved\n")
    soul = home / "SOUL.md"
    soul.write_text("# user soul\n")
    before = {path.name: path.read_bytes() for path in home.iterdir()}

    try:
        hermes.install(REPO_ROOT, home)
        raised = False
    except hermes.HermesError:
        raised = True

    assert raised
    assert {path.name: path.read_bytes() for path in home.iterdir()} == before
    assert not (home / hermes.HOOKS_SUBDIR).exists()
    assert not (home / hermes.ALLOWLIST_FILENAME).exists()


def test_cli_smoke(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    result = CliRunner().invoke(
        app, ["hermes", "install", "--source", str(REPO_ROOT), "--home", str(home)]
    )
    assert result.exit_code == 0, result.output
    assert (home / hermes.HOOKS_SUBDIR).is_dir()
    # and the uninstall command is wired too
    result = CliRunner().invoke(
        app, ["hermes", "uninstall", "--source", str(REPO_ROOT), "--home", str(home)]
    )
    assert result.exit_code == 0, result.output
    assert not (home / hermes.HOOKS_SUBDIR).exists()
