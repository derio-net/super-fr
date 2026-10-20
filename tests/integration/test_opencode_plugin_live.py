"""gh#563, live half: the plugin install.sh delivers is one OpenCode loads,
and the delivered copy (not the repo source) refuses a base-clone edit.

Two probes, each against throwaway XDG config/data/state/cache dirs. OpenCode 2
runs every CLI command through a background service on a fixed port, so each
probe gives its isolated service its own free port (`opencode service set
port`) and stops it afterwards — otherwise the CLI would talk to the operator's
own service and its plugins.

1. The REAL binary loads the delivered loader: its server log records
   `loading plugin` for it, with no error. This is what #568's compiled
   executable would have failed: OpenCode never registers an extensionless
   file. (OpenCode 2's `debug config` lists config sources, not plugins.)
2. OpenCode's own runtime imports and initialises the delivered loader: a
   sentinel plugin delivered beside it imports its V2 definition, runs its
   `setup` against a context that captures the `tool` `execute.before` hook,
   drives it and records the verdicts. A write into an fr-enabled base clone is
   refused; a write outside any repo is allowed.

What this does NOT prove, stated so a green run is not over-read: that a
model-driven OpenCode session routes its tool calls through the hook. That
needs a paid model call. It was shown live through the project-local copy
(acceptance row `opencode-isolation-enforcement`); for the delivered copy it
is the operator's post-merge Test Plan.

Skips when `opencode` is absent — EXCEPT under
`FR_REQUIRE_OPENCODE=1` (set by CI's `opencode-plugin-test` job), where a
missing binary fails, so the probe cannot silently stop running.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from tests.conftest import subprocess_timeout

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "deliver-opencode-plugin.sh"
REQUIRED = os.environ.get("FR_REQUIRE_OPENCODE") == "1"


def _binary(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        if REQUIRED:
            pytest.fail(f"FR_REQUIRE_OPENCODE=1 but `{name}` is not on PATH")
        pytest.skip(f"`{name}` not on PATH")
    return path


def _deliver(config_home: Path) -> Path:
    plugins = config_home / "opencode" / "plugins"
    result = subprocess.run(
        ["bash", str(SCRIPT), "install", str(plugins)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return plugins / "fr-opencode-plugin.ts"


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _fr_enabled_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    _git("init", "--quiet", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    (repo / ".devcontainer" / "dev").mkdir(parents=True)
    (repo / ".devcontainer" / "dev" / "devcontainer.json").write_text("{}\n")
    (repo / "README.md").write_text("placeholder\n")
    _git("add", ".", cwd=repo)
    _git("commit", "--quiet", "-m", "init", cwd=repo)
    return repo


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _isolated_env(root: Path) -> dict[str, str]:
    env = {
        k: v for k, v in os.environ.items() if k != "FR_BASE_OK" and not k.startswith("OPENCODE")
    }
    for name in ("CONFIG", "DATA", "STATE", "CACHE"):
        env[f"XDG_{name}_HOME"] = str(root / name.lower())
    return env


def _opencode(opencode: str, *args: str, cwd: Path, env: dict[str, str]):
    return subprocess.run(
        [opencode, *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=subprocess_timeout(120),
        check=False,
    )


@contextmanager
def _service(opencode: str, project: Path, env: dict[str, str]) -> Iterator[None]:
    """An isolated OpenCode 2 background service, stopped on the way out."""
    port = _opencode(opencode, "service", "set", "port", str(_free_port()), cwd=project, env=env)
    assert port.returncode == 0, port.stderr
    try:
        yield
    finally:
        _opencode(opencode, "service", "stop", cwd=project, env=env)


def _project(root: Path) -> Path:
    project = root / "project"
    project.mkdir()
    _git("init", "--quiet", cwd=project)
    return project


def test_opencode_registers_the_delivered_loader(tmp_path: Path) -> None:
    opencode = _binary("opencode")
    env = _isolated_env(tmp_path)
    loader = _deliver(Path(env["XDG_CONFIG_HOME"]))
    project = _project(tmp_path)

    with _service(opencode, project, env):
        result = _opencode(opencode, "plugin", "list", cwd=project, env=env)
    assert result.returncode == 0, result.stderr

    log = Path(env["XDG_DATA_HOME"]) / "opencode" / "log" / "opencode.log"
    lines = log.read_text().splitlines() if log.is_file() else []
    loaded = [line for line in lines if 'msg="loading plugin"' in line]
    assert any(f"id={loader}" in line for line in loaded), (
        f"opencode did not load the delivered loader; its loads: {loaded}"
    )
    # A load that fails is logged as a WARN `failed to load plugin`, not an error.
    failed = [
        line
        for line in lines
        if "failed to load plugin" in line or ("level=ERROR" in line and "plugin" in line.lower())
    ]
    assert not failed, failed


# A sentinel plugin OpenCode itself loads beside the delivered one. It imports
# the delivered loader through OpenCode's OWN runtime (the resolver that must
# handle the extensionless `./fr-opencode-plugin/index` import), runs its V2
# `setup` against a context that captures the hooks it registers, drives the
# `execute.before` gate on both cases, and records the verdicts in a file —
# the evidence that the delivered code, not just its registration, works.
_SENTINEL = """
import {{ writeFileSync }} from "node:fs";
import fr from "./fr-opencode-plugin";

async function verdict(directory, target) {{
  const hooks = {{}};
  const register = (domain) => async (name, cb) => {{ hooks[domain + ":" + name] = cb; }};
  const cleanup = await fr.setup({{
    location: {{ directory }},
    // setup registers the nag on session.hook (2.x) and the claim/bind/idle
    // handlers read session.get/prompt when events fire; the fake must carry
    // every domain setup touches or the plugin fails to load for the wrong
    // reason (2026-10-20: this probe caught exactly that).
    session: {{
      hook: register("session"),
      get: async () => undefined,
      prompt: async () => ({{}}),
    }},
    tool: {{ hook: register("tool") }},
    shell: {{ hook: register("shell") }},
    event: undefined,
  }});
  try {{
    const gate = hooks["tool:execute.before"];
    await gate({{ tool: "edit", sessionID: "", input: {{ filePath: target }} }});
    return "ALLOWED";
  }} catch (e) {{
    return "REFUSED " + String(e.message).split("\\n")[0];
  }} finally {{
    if (typeof cleanup === "function") cleanup();
  }}
}}

export default {{
  id: "fr-delivery-probe",
  async setup() {{
    writeFileSync({out}, JSON.stringify({{
      id: fr.id,
      base_clone: await verdict({repo}, {repo_target}),
      outside: await verdict({outside}, {outside_target}),
    }}));
  }},
}};
"""


def test_opencode_runs_the_delivered_gate(tmp_path: Path) -> None:
    opencode = _binary("opencode")
    env = _isolated_env(tmp_path)
    loader = _deliver(Path(env["XDG_CONFIG_HOME"]))
    repo = _fr_enabled_repo(tmp_path)
    outside = tmp_path / "scratch"
    outside.mkdir()
    out = tmp_path / "verdicts.json"
    (loader.parent / "zz-delivery-probe.ts").write_text(
        _SENTINEL.format(
            out=json.dumps(str(out)),
            repo=json.dumps(str(repo)),
            repo_target=json.dumps(str(repo / "README.md")),
            outside=json.dumps(str(outside)),
            outside_target=json.dumps(str(outside / "notes.md")),
        )
    )
    project = _project(tmp_path)

    with _service(opencode, project, env):
        result = _opencode(opencode, "plugin", "list", cwd=project, env=env)
    assert result.returncode == 0, result.stderr
    assert out.is_file(), (
        "OpenCode never initialised the probe, so it never imported the delivered "
        f"loader; stderr: {result.stderr[-2000:]}"
    )
    verdicts = json.loads(out.read_text())
    assert verdicts["id"] == "super-fr", verdicts
    assert verdicts["base_clone"].startswith("REFUSED fr-isolation"), verdicts
    assert verdicts["outside"] == "ALLOWED", verdicts
