"""gh#563: install.sh must deliver fr-opencode-plugin to consumers.

`fr harness parity` credits OpenCode's edit gate and idle adapter from the
plugin's SOURCE (`super-fr-parity:` markers), but until this fix nothing ever
copied that source to a consumer's `~/.config/opencode/plugins/` — every
OpenCode user outside this repo ran with neither surface while parity said
both were wired.

OpenCode (verified live on 1.18.32, isolated XDG_CONFIG_HOME) registers and
imports only TOP-LEVEL `*.ts`/`*.js` files in its global plugins directory;
subdirectories are not scanned. So the delivered shape is one top-level
loader plus the sources in a sibling directory the scan skips.

These are behavioural tests of `scripts/deliver-opencode-plugin.sh`, plus
drift guards that install.sh actually calls it. The live half — the real
`opencode` binary registering the delivered loader — is
`tests/integration/test_opencode_plugin_live.py`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "deliver-opencode-plugin.sh"
PLUGIN_SRC = REPO_ROOT / "packages" / "fr-opencode-plugin" / "src"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, check=False)


def test_install_writes_a_top_level_loader_and_every_source(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    result = _run("install", str(plugins))
    assert result.returncode == 0, result.stderr

    loader = plugins / "fr-opencode-plugin.ts"
    assert loader.is_file(), "the loader must sit at the TOP level — OpenCode scans nothing deeper"
    assert 'from "./fr-opencode-plugin/index"' in loader.read_text()
    assert "export {" in loader.read_text() and "as default" in loader.read_text()

    sources = sorted(p.name for p in PLUGIN_SRC.glob("*.ts"))
    assert sources, "no plugin sources found — did packages/fr-opencode-plugin/src move?"
    delivered = sorted(p.name for p in (plugins / "fr-opencode-plugin").glob("*.ts"))
    assert delivered == sources
    for name in sources:
        assert (plugins / "fr-opencode-plugin" / name).read_bytes() == (
            PLUGIN_SRC / name
        ).read_bytes()


def test_only_the_loader_is_a_top_level_module(tmp_path: Path) -> None:
    """A support module at the top level would be loaded as a plugin of its own."""
    plugins = tmp_path / "plugins"
    assert _run("install", str(plugins)).returncode == 0
    top_level = sorted(p.name for p in plugins.iterdir() if p.is_file())
    assert top_level == ["fr-opencode-plugin.ts"]


def test_reinstall_replaces_the_source_dir_wholesale(tmp_path: Path) -> None:
    """A source file removed upstream must not linger on the consumer."""
    plugins = tmp_path / "plugins"
    assert _run("install", str(plugins)).returncode == 0
    stale = plugins / "fr-opencode-plugin" / "removed-upstream.ts"
    stale.write_text("export const x = 1;\n")
    assert _run("install", str(plugins)).returncode == 0
    assert not stale.exists()


def test_uninstall_removes_only_what_install_wrote(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    foreign = plugins / "someone-elses-plugin.js"
    foreign.write_text("export default async () => ({});\n")
    assert _run("install", str(plugins)).returncode == 0
    result = _run("uninstall", str(plugins))
    assert result.returncode == 0, result.stderr
    assert not (plugins / "fr-opencode-plugin.ts").exists()
    assert not (plugins / "fr-opencode-plugin").exists()
    assert foreign.read_text() == "export default async () => ({});\n"


def test_uninstall_with_nothing_installed_is_a_no_op(tmp_path: Path) -> None:
    assert _run("uninstall", str(tmp_path / "absent")).returncode == 0


def test_a_bad_invocation_fails_loudly(tmp_path: Path) -> None:
    assert _run().returncode != 0
    assert _run("frobnicate", str(tmp_path)).returncode != 0


def test_install_sh_delivers_the_plugin_inside_the_opencode_opt_in_gate() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    gate = 'if [ "${OPENCODE_SKILLS_INSTALL:-}" = "1" ] || [ -d "$HOME/.config/opencode" ]; then'
    assert gate in install
    block = install.split(gate, 1)[1].split("\nfi\n", 1)[0]
    assert "deliver-opencode-plugin.sh" in block and " install " in block, (
        "install.sh must call deliver-opencode-plugin.sh install inside the "
        "OpenCode opt-in block — parity credits the plugin to OpenCode users"
    )
    assert ".config/opencode/plugins" in install


def test_install_sh_uninstall_removes_the_plugin() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    uninstall_block = install.split('"${1:-}" == "--uninstall"', 1)[1].split("\nfi\n", 1)[0]
    assert "deliver-opencode-plugin.sh" in uninstall_block
    assert " uninstall " in uninstall_block
