"""install.sh installs the dependency set the release was tested with (super-fr#1508).

`uv tool install packages/fr` resolves `fr`'s lower-bound requirements afresh on every
install, so one release could install a different dependency set on a later day than
the one its CI ran against. The workspace's `uv.lock` IS that tested set: install.sh
exports it as a constraints file, passes it to every `uv tool install`, and keeps it as
the record of what it asked for. The devcontainer CLI it installs with npm is pinned too.

Executed against a `uv` stub that records its argv and hands `export` to the real uv,
so the constraints are the ones the real lock yields.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
REAL_UV = shutil.which("uv")
pytestmark = pytest.mark.skipif(REAL_UV is None, reason="needs uv")

_UV_STUB = r"""#!/bin/sh
case "$1 $2" in
"tool dir")
  printf '%s\n' "$UV_STUB_TOOLDIR"
  ;;
"tool install")
  [ "${3:-}" != "--help" ] || exit 0
  printf '%s\n' '--- install' >> "$UV_STUB_LOG"
  for a in "$@"; do printf '%s\n' "$a" >> "$UV_STUB_LOG"; done
  mkdir -p "$UV_STUB_TOOLDIR/fr/bin"
  printf '#!/bin/sh\necho "fr 9.9.9"\n' > "$UV_STUB_TOOLDIR/fr/bin/fr"
  chmod +x "$UV_STUB_TOOLDIR/fr/bin/fr"
  ;;
export*)
  [ -z "${UV_STUB_EXPORT_FAILS:-}" ] || exit 1
  exec "$REAL_UV" "$@"
  ;;
*)
  exit 0
  ;;
esac
"""

_NPM_STUB = '#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a" >> "$NPM_STUB_LOG"; done\nexit 0\n'


@pytest.fixture()
def env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    bin_dir = home / "bin"
    bin_dir.mkdir(parents=True)
    (home / ".claude" / "plugins").mkdir(parents=True)
    (home / ".claude" / "plugins" / "installed_plugins.json").write_text(
        '{"version": 2, "plugins": {}}'
    )
    (home / ".claude" / "settings.json").write_text("{}")
    for name, text in (("uv", _UV_STUB), ("npm", _NPM_STUB)):
        (bin_dir / name).write_text(text)
        (bin_dir / name).chmod(0o755)
    return {
        "HOME": str(home),
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin",
        "FR_INSTALL_SKIP_PREFLIGHT": "1",
        "FR_INSTALL_RETRY_SLEEP": "0",
        "REAL_UV": str(REAL_UV),
        "UV_STUB_TOOLDIR": str(tmp_path / "uv-tools"),
        "UV_STUB_LOG": str(tmp_path / "uv-argv"),
        "NPM_STUB_LOG": str(tmp_path / "npm-argv"),
        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR", str(tmp_path / "uv-cache")),
    }


def _installs(env: dict[str, str]) -> list[list[str]]:
    calls: list[list[str]] = []
    for line in Path(env["UV_STUB_LOG"]).read_text().splitlines():
        if line == "--- install":
            calls.append([])
        else:
            calls[-1].append(line)
    return calls


def _locked() -> dict[str, str]:
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text())
    return {p["name"]: p["version"] for p in lock["package"] if "version" in p}


def _run(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALL_SH)], capture_output=True, text=True, env=env, timeout=600
    )


def test_every_fr_install_is_constrained_to_the_lock(env: dict[str, str]) -> None:
    res = _run(env)
    assert res.returncode == 0, f"stdout: {res.stdout}\nstderr: {res.stderr}"
    calls = _installs(env)
    assert calls, "install.sh ran no `uv tool install`"
    locked = _locked()
    for argv in calls:
        assert "--constraints" in argv, argv
        constraints = Path(argv[argv.index("--constraints") + 1])
        pins = dict(
            m.groups()
            for m in re.finditer(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", constraints.read_text(), re.M)
        )
        # fr's own runtime requirements, at exactly the locked versions.
        for name in ("typer", "pydantic", "pyyaml"):
            assert pins.get(name) == locked[name], (name, pins.get(name), locked[name])
        # Workspace members are installed from the checkout, never pinned.
        assert not {"fr", "fr-dispatch", "fr-herdr"} & set(pins), sorted(pins)


def test_the_constraints_are_kept_as_the_install_record(env: dict[str, str]) -> None:
    assert _run(env).returncode == 0
    record = Path(env["HOME"]) / ".local" / "share" / "fr" / "install-constraints.txt"
    assert record.is_file()
    assert f"typer=={_locked()['typer']}" in record.read_text()


def test_an_unexportable_lock_installs_unconstrained_and_says_so(env: dict[str, str]) -> None:
    env["UV_STUB_EXPORT_FAILS"] = "1"
    res = _run(env)
    assert res.returncode == 0, res.stderr
    assert all("--constraints" not in argv for argv in _installs(env))
    assert "not constrained to the release's uv.lock" in res.stderr


def test_the_devcontainer_cli_is_installed_at_a_pinned_version(env: dict[str, str]) -> None:
    if shutil.which("devcontainer", path=env["PATH"]):
        pytest.skip("a devcontainer CLI on the stub PATH skips the npm install")
    assert _run(env).returncode == 0
    argv = Path(env["NPM_STUB_LOG"]).read_text().splitlines()
    specs = [a for a in argv if a.startswith("@devcontainers/cli")]
    assert len(specs) == 1 and re.fullmatch(r"@devcontainers/cli@\d+\.\d+\.\d+", specs[0]), argv
