"""The installed `fr` carries every runner the workspace declares (#650, #645).

Tests run `uv run fr`, which sees every workspace member, so a runner package
an installer forgets is invisible to CI while the installed `fr` cannot load
it: `fr triage batch dispatch --to herdr` failed on every installed `fr`, and
the devcontainer's `fr` could not import `fr_vk.bridge`. Both installers —
`scripts/install.sh` on a host and the scaffold's POST_CREATE in a
devcontainer — are executed here against a `uv` stub that records its argv,
and must pass `--with` for every package `runner_packages()` derives from the
`fr.runners` entry points.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.isolation import scaffold

from tests.conftest import REPO_ROOT, runner_packages

INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
SUPER_FR_GIT = "git+https://github.com/derio-net/super-fr"

# `tool install` logs its argv one per line; `tool dir` names a tool dir whose
# `fr` runs (install.sh's smoke check) and whose python cannot import anything
# (so `--install-bridge` reaches its refusal and prints the recovery hint).
_UV_STUB = r"""#!/bin/sh
case "$1 $2" in
"tool dir")
  printf '%s\n' "$UV_STUB_TOOLDIR"
  ;;
"tool install")
  for a in "$@"; do printf '%s\n' "$a" >> "$UV_STUB_LOG"; done
  mkdir -p "$UV_STUB_TOOLDIR/fr/bin"
  printf '#!/bin/sh\necho "fr 9.9.9"\n' > "$UV_STUB_TOOLDIR/fr/bin/fr"
  printf '#!/bin/sh\nexit 1\n' > "$UV_STUB_TOOLDIR/fr/bin/python"
  chmod +x "$UV_STUB_TOOLDIR/fr/bin/fr" "$UV_STUB_TOOLDIR/fr/bin/python"
  ;;
*)
  exit 0
  ;;
esac
"""


@pytest.fixture()
def stub_env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    bin_dir = home / "bin"
    bin_dir.mkdir(parents=True)
    (home / ".claude" / "plugins").mkdir(parents=True)
    (home / ".claude" / "plugins" / "installed_plugins.json").write_text(
        '{"version": 2, "plugins": {}}'
    )
    (home / ".claude" / "settings.json").write_text("{}")
    vk_mcp = bin_dir / "vibe-kanban-mcp"
    vk_mcp.write_text("#!/bin/sh\necho stub\n")
    vk_mcp.chmod(0o755)
    uv = bin_dir / "uv"
    uv.write_text(_UV_STUB)
    uv.chmod(0o755)
    return {
        "HOME": str(home),
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin",
        "VK_INSTALL_SKIP_PREFLIGHT": "1",
        "FR_INSTALL_RETRY_SLEEP": "0",
        "UV_STUB_TOOLDIR": str(tmp_path / "uv-tools"),
        "UV_STUB_LOG": str(tmp_path / "uv-argv"),
    }


def _with_args(env: dict[str, str]) -> list[str]:
    """The values passed to `--with` across every recorded `uv tool install`."""
    argv = Path(env["UV_STUB_LOG"]).read_text().splitlines()
    return [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--with"]


def test_the_workspace_declares_the_runners_the_issues_name() -> None:
    """The derivation finds something: an empty list would pass every check below."""
    assert {"fr-vk", "fr-cncd", "fr-herdr", "fr-claude-cloud"} <= set(runner_packages())


def test_install_sh_installs_fr_with_every_runner_package(stub_env: dict[str, str]) -> None:
    result = subprocess.run(["bash", str(INSTALL_SH)], capture_output=True, text=True, env=stub_env)
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    withs = _with_args(stub_env)
    expected = [str(REPO_ROOT / "packages" / p) for p in runner_packages()]
    assert sorted(withs) == sorted(expected)


def test_install_bridge_hint_names_every_runner_package(stub_env: dict[str, str]) -> None:
    """The refusal's recovery command is the install command, not a smaller one."""
    Path(stub_env["UV_STUB_LOG"]).write_text("")
    subprocess.run(["uv", "tool", "install"], env=stub_env, check=True)  # seeds the tool dir

    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--install-bridge"],
        capture_output=True,
        text=True,
        env={**stub_env, "VK_BRIDGE_WRAPPER_PATH": str(Path(stub_env["HOME"]) / "run.sh")},
    )
    assert result.returncode != 0
    for pkg in runner_packages():
        assert f"--with {REPO_ROOT / 'packages' / pkg} " in result.stderr, result.stderr


def test_scaffold_runner_packages_are_the_workspace_runners() -> None:
    """The scaffold ships in the `fr` wheel, where `packages/` does not exist, so
    it keeps a literal; this is what keeps that literal honest."""
    assert sorted(scaffold.RUNNER_PACKAGES) == runner_packages()


def test_the_scaffold_installs_the_cloud_runner() -> None:
    """Cloud-triage §F: the POST_CREATE literal names packages/fr-claude-cloud."""
    assert "subdirectory=packages/fr-claude-cloud" in scaffold.POST_CREATE


def test_post_create_installs_fr_with_every_runner_package(
    stub_env: dict[str, str], tmp_path: Path
) -> None:
    """Executed, not string-matched: the devcontainer's `fr` is what `sh` runs."""
    for tool in ("pipx", "git"):
        stub = Path(stub_env["HOME"]) / "bin" / tool
        stub.write_text("#!/bin/sh\nexit 0\n")
        stub.chmod(0o755)
    result = subprocess.run(
        ["sh", "-c", scaffold.POST_CREATE],
        capture_output=True,
        text=True,
        env=stub_env,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr

    withs = _with_args(stub_env)
    expected = [f"{SUPER_FR_GIT}#subdirectory=packages/{p}" for p in runner_packages()]
    assert sorted(withs) == sorted(expected)
