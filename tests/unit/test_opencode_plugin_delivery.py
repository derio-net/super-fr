"""gh#563: install.sh must deliver fr-opencode-plugin to consumers.

`fr harness parity` credits OpenCode's edit gate and idle adapter from the
plugin's SOURCE (`super-fr-parity:` markers), but until this fix nothing ever
copied that source to a consumer's `~/.config/opencode/plugins/` — every
OpenCode user outside this repo ran with neither surface while parity said
both were wired.

OpenCode 2 (measured on 2.1.0, isolated XDG dirs) treats each DIRECTORY in its
plugins directory as one plugin: the server loads `<dir>/index`, the TUI loads
`<dir>/tui`. So the delivered shape is ONE directory and nothing at the top
level — the 1.x top-level loader beside it made 2.x load the plugin twice
(plan finding p1-v2-loads-sources-dir-as-plugin). The directory is also listed
in `<config>/cli.json`'s `plugins` for the status line (spec R12).

These are behavioural tests of `scripts/deliver-opencode-plugin.sh`, plus
drift guards that install.sh actually calls it. The live half — the real
`opencode` binary registering the delivered loader — is
`tests/integration/test_opencode_plugin_live.py`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "deliver-opencode-plugin.sh"
PLUGIN_SRC = REPO_ROOT / "packages" / "fr-opencode-plugin" / "src"
SEGMENT = REPO_ROOT / "plugins" / "super-fr" / "scripts" / "fr-statusline-segment.sh"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, check=False)


def test_install_writes_one_plugin_directory_with_every_source(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    result = _run("install", str(plugins))
    assert result.returncode == 0, result.stderr

    plugin = plugins / "fr-opencode-plugin"
    sources = sorted(p.name for p in PLUGIN_SRC.glob("*.ts"))
    assert "index.ts" in sources, (
        "no plugin sources found — did packages/fr-opencode-plugin/src move?"
    )
    assert sorted(p.name for p in plugin.glob("*.ts")) == sources
    for name in sources:
        assert (plugin / name).read_bytes() == (PLUGIN_SRC / name).read_bytes()

    tui = sorted(p.name for p in (plugin / "tui").iterdir())
    assert tui == ["fr-statusline-segment.sh", "index.tsx", "segment.ts"]
    assert (plugin / "tui" / "fr-statusline-segment.sh").read_bytes() == SEGMENT.read_bytes()


def test_nothing_is_delivered_at_the_top_level(tmp_path: Path) -> None:
    """OpenCode 2 loads the directory; any top-level module is a second load."""
    plugins = tmp_path / "plugins"
    assert _run("install", str(plugins)).returncode == 0
    assert sorted(p.name for p in plugins.iterdir()) == ["fr-opencode-plugin"]


def test_install_deletes_a_stale_1x_loader(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    stale = plugins / "fr-opencode-plugin.ts"
    stale.write_text('export { default } from "./fr-opencode-plugin/index";\n')
    assert _run("install", str(plugins)).returncode == 0
    assert not stale.exists()


def test_the_server_entrypoint_never_imports_the_tui(tmp_path: Path) -> None:
    """The server loads `<dir>/index`; nothing it imports may reach `tui/`."""
    for source in PLUGIN_SRC.glob("*.ts"):
        assert "./tui" not in source.read_text(), source.name


def test_reinstall_replaces_the_source_dir_wholesale(tmp_path: Path) -> None:
    """A source file removed upstream must not linger on the consumer."""
    plugins = tmp_path / "plugins"
    assert _run("install", str(plugins)).returncode == 0
    stale = plugins / "fr-opencode-plugin" / "tui" / "removed-upstream.ts"
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
    assert sorted(p.name for p in plugins.iterdir()) == ["someone-elses-plugin.js"]
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


# --- cli.json: the status line's enablement directive (spec R12) -------------


def _cli(tmp_path: Path) -> tuple[Path, Path]:
    config = tmp_path / "opencode"
    return config / "plugins", config / "cli.json"


def _entry(plugins: Path) -> str:
    return str(plugins.resolve() / "fr-opencode-plugin")


def test_install_creates_cli_json_with_the_plugin_directory(tmp_path: Path) -> None:
    plugins, cli = _cli(tmp_path)
    assert _run("install", str(plugins)).returncode == 0
    assert json.loads(cli.read_text()) == {"plugins": [_entry(plugins)]}


def test_install_appends_only_its_own_entry_and_keeps_the_rest(tmp_path: Path) -> None:
    plugins, cli = _cli(tmp_path)
    cli.parent.mkdir(parents=True)
    cli.write_text(json.dumps({"theme": {"name": "x"}, "plugins": ["their-plugin"]}))
    assert _run("install", str(plugins)).returncode == 0
    assert json.loads(cli.read_text()) == {
        "theme": {"name": "x"},
        "plugins": ["their-plugin", _entry(plugins)],
    }


def test_reinstall_is_idempotent_by_exact_path(tmp_path: Path) -> None:
    plugins, cli = _cli(tmp_path)
    assert _run("install", str(plugins)).returncode == 0
    assert _run("install", str(plugins)).returncode == 0
    assert json.loads(cli.read_text())["plugins"] == [_entry(plugins)]


def test_an_unparsable_cli_json_is_refused_and_left_untouched(tmp_path: Path) -> None:
    plugins, cli = _cli(tmp_path)
    cli.parent.mkdir(parents=True)
    cli.write_text("{ not json\n")
    result = _run("install", str(plugins))
    assert result.returncode != 0
    assert str(cli) in result.stderr
    assert cli.read_text() == "{ not json\n"


def test_uninstall_removes_only_its_own_entry(tmp_path: Path) -> None:
    plugins, cli = _cli(tmp_path)
    cli.parent.mkdir(parents=True)
    cli.write_text(json.dumps({"plugins": ["their-plugin"]}))
    assert _run("install", str(plugins)).returncode == 0
    assert _run("uninstall", str(plugins)).returncode == 0
    assert json.loads(cli.read_text()) == {"plugins": ["their-plugin"]}


# --- review findings p3-r2..r5 ------------------------------------------------


def test_a_refused_cli_json_moves_no_byte(tmp_path: Path) -> None:
    """p3-r2: the refusal fires before the plugin directory is written."""
    plugins, cli = _cli(tmp_path)
    cli.parent.mkdir(parents=True)
    cli.write_text('{ // jsonc\n "plugins": [] }\n')
    result = _run("install", str(plugins))
    assert result.returncode != 0
    assert str(cli) in result.stderr and "Nothing was written" in result.stderr
    assert not plugins.exists()
    assert sorted(p.name for p in cli.parent.iterdir()) == ["cli.json"]


def test_install_sh_fails_loudly_when_delivery_refuses() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    assert 'if ! bash "$PLUGIN_ROOT/scripts/deliver-opencode-plugin.sh" install' in install
    assert "fr-opencode-plugin was NOT installed" in install


def test_uninstall_drops_the_entry_after_the_plugins_dir_is_gone(tmp_path: Path) -> None:
    """p3-r3(a)."""
    import shutil

    plugins, cli = _cli(tmp_path)
    assert _run("install", str(plugins)).returncode == 0
    shutil.rmtree(plugins)
    assert _run("uninstall", str(plugins)).returncode == 0
    assert json.loads(cli.read_text()) == {"plugins": []}


def test_install_sh_uninstall_calls_delivery_unconditionally() -> None:
    """p3-r3(b): no existence guard in front of the uninstall call."""
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    uninstall_block = install.split('"${1:-}" == "--uninstall"', 1)[1].split("\nfi\n", 1)[0]
    line = next(ln for ln in uninstall_block.splitlines() if "deliver-opencode-plugin.sh" in ln)
    idx = uninstall_block.splitlines().index(line)
    assert "fr-opencode-plugin" not in uninstall_block.splitlines()[idx - 1].split("#")[0]
    assert line.startswith('  bash "$PLUGIN_ROOT/scripts/deliver-opencode-plugin.sh" uninstall')


def test_a_symlinked_cli_json_stays_a_symlink(tmp_path: Path) -> None:
    """p3-r4: dotfiles managers symlink cli.json; a relative link is followed."""
    plugins, cli = _cli(tmp_path)
    cli.parent.mkdir(parents=True)
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()
    target = dotfiles / "cli.json"
    target.write_text(json.dumps({"plugins": ["theirs"]}))
    cli.symlink_to(Path("..") / "dotfiles" / "cli.json")
    assert _run("install", str(plugins)).returncode == 0
    assert cli.is_symlink()
    assert json.loads(target.read_text())["plugins"] == ["theirs", _entry(plugins)]
    assert _run("uninstall", str(plugins)).returncode == 0
    assert cli.is_symlink()
    assert json.loads(target.read_text())["plugins"] == ["theirs"]


def test_a_0600_cli_json_keeps_its_mode(tmp_path: Path) -> None:
    plugins, cli = _cli(tmp_path)
    cli.parent.mkdir(parents=True)
    cli.write_text("{}")
    cli.chmod(0o600)
    assert _run("install", str(plugins)).returncode == 0
    assert cli.stat().st_mode & 0o777 == 0o600
    assert _run("uninstall", str(plugins)).returncode == 0
    assert cli.stat().st_mode & 0o777 == 0o600


def test_register_drops_duplicates_then_appends_and_keeps_non_strings(tmp_path: Path) -> None:
    """p3-r5: spec §E — drop ours, then append ours."""
    plugins, cli = _cli(tmp_path)
    cli.parent.mkdir(parents=True)
    plugins.mkdir()
    ours = _entry(plugins)
    cli.write_text(json.dumps({"plugins": [ours, {"package": "x"}, 3, None, ours, "b"]}))
    assert _run("install", str(plugins)).returncode == 0
    assert json.loads(cli.read_text())["plugins"] == [{"package": "x"}, 3, None, "b", ours]
