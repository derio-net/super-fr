"""The OpenCode plugin delivery carries install.sh's shipped rules (consumer-delivery R1, R3).

OpenCode never reads `~/.claude/rules/`, so the plugin directory carries the
rules itself, copied from the generated `.opencode/instructions/` mirror. The
rule list lives once, in install.sh's CLAUDE_RULES.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "deliver-opencode-plugin.sh"
INSTRUCTIONS = REPO_ROOT / ".opencode" / "instructions"
LOCAL_ONLY = {
    "acceptance-matrix.md",
    "artifact-versioning.md",
    "explainers-currency.md",
    "third-party-privacy.md",
}


def _claude_rules() -> list[str]:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    match = re.search(r"CLAUDE_RULES=\(([^)]+)\)", install, re.DOTALL)
    assert match, "CLAUDE_RULES array not found in install.sh"
    return re.findall(r"([\w.-]+\.md)", match.group(1))


def _run(*args: str, env_rules: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    import os

    env = dict(os.environ)
    if env_rules is not None:
        env["FR_OPENCODE_RULES"] = " ".join(env_rules)
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, check=False, env=env
    )


def test_install_delivers_exactly_the_claude_rules(tmp_path: Path) -> None:
    rules = _claude_rules()
    plugins = tmp_path / "plugins"
    result = _run("install", str(plugins), env_rules=rules)
    assert result.returncode == 0, result.stderr
    delivered = plugins / "fr-opencode-plugin" / "rules"
    assert sorted(p.name for p in delivered.iterdir()) == sorted(rules)
    for name in rules:
        assert (delivered / name).read_bytes() == (INSTRUCTIONS / name).read_bytes()
    assert not LOCAL_ONLY & {p.name for p in delivered.iterdir()}


def test_uninstall_removes_the_rules_with_the_directory(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    assert _run("install", str(plugins), env_rules=_claude_rules()).returncode == 0
    assert _run("uninstall", str(plugins)).returncode == 0
    assert not (plugins / "fr-opencode-plugin").exists()


def test_a_missing_rule_file_refuses_and_writes_nothing(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    result = _run("install", str(plugins), env_rules=["no-such-rule.md"])
    assert result.returncode != 0
    assert not (plugins / "fr-opencode-plugin").exists()


@pytest.mark.parametrize("bad", ["*.md", "../escape.md", "sub/x.md", ".hidden.md", "no-suffix"])
def test_a_malformed_rule_name_refuses_and_writes_nothing(tmp_path: Path, bad: str) -> None:
    plugins = tmp_path / "plugins"
    result = _run("install", str(plugins), env_rules=[bad])
    assert result.returncode != 0
    assert "refusing rule name" in result.stderr
    assert not (plugins / "fr-opencode-plugin").exists()


def test_install_sh_names_a_neutral_remedy_on_refusal() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    assert "fix what that message names" in install


def test_install_sh_passes_claude_rules_to_the_delivery() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    call = [
        ln for ln in install.splitlines() if "deliver-opencode-plugin.sh" in ln and "install" in ln
    ]
    assert any("FR_OPENCODE_RULES" in ln and "CLAUDE_RULES[*]" in ln for ln in call), call
