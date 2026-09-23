"""gh#563, live half: the plugin install.sh delivers is one OpenCode loads,
and the delivered copy (not the repo source) refuses a base-clone edit.

Two probes, each against a throwaway config dir via `XDG_CONFIG_HOME`:

1. `opencode debug config` — the REAL binary resolves its plugin list. The
   delivered loader must be in it. This is what #568's compiled executable
   would have failed: OpenCode never registers an extensionless file.
2. OpenCode's own runtime imports and initialises the delivered loader: a
   sentinel plugin delivered beside it imports it, drives its
   `tool.execute.before` hook and records the verdicts. A write into an
   fr-enabled base clone is refused; a write outside any repo is allowed.

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
import subprocess
from pathlib import Path

import pytest

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


def test_opencode_registers_the_delivered_loader(tmp_path: Path) -> None:
    opencode = _binary("opencode")
    config_home = tmp_path / "config"
    loader = _deliver(config_home)
    project = tmp_path / "project"
    project.mkdir()
    _git("init", "--quiet", cwd=project)

    env = {**os.environ, "XDG_CONFIG_HOME": str(config_home)}
    result = subprocess.run(
        [opencode, "debug", "config"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    plugins = json.loads(result.stdout).get("plugin") or []
    resolved = {Path(p.removeprefix("file://")).resolve() for p in plugins}
    assert loader.resolve() in resolved, (
        f"opencode did not register the delivered loader; its plugin list: {plugins}"
    )
    assert not any("fr-opencode-plugin/" in p for p in plugins), (
        "a support module was registered as a plugin of its own"
    )


# A sentinel plugin OpenCode itself loads beside the delivered one. It imports
# the delivered loader through OpenCode's OWN runtime (the resolver that must
# handle the extensionless `./fr-opencode-plugin/index` import), initialises
# it, drives its hook on both cases, and records the verdicts in a file —
# OpenCode's logs do not record plugin loads, so this file is the evidence.
_SENTINEL = """
import {{ writeFileSync }} from "node:fs";
import fr from "./fr-opencode-plugin";

async function verdict(directory, target) {{
  const hook = (await fr({{
    project: undefined, client: undefined, $: undefined, directory, worktree: directory,
  }}))["tool.execute.before"];
  try {{
    await hook({{ tool: "edit" }}, {{ args: {{ filePath: target }} }});
    return "ALLOWED";
  }} catch (e) {{
    return "REFUSED " + String(e.message).split("\\n")[0];
  }}
}}

export const FrDeliveryProbe = async () => {{
  writeFileSync({out}, JSON.stringify({{
    base_clone: await verdict({repo}, {repo_target}),
    outside: await verdict({outside}, {outside_target}),
  }}));
  return {{}};
}};
"""


def test_opencode_runs_the_delivered_gate(tmp_path: Path) -> None:
    opencode = _binary("opencode")
    config_home = tmp_path / "config"
    loader = _deliver(config_home)
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
    project = tmp_path / "project"
    project.mkdir()
    _git("init", "--quiet", cwd=project)

    env = {k: v for k, v in os.environ.items() if k != "FR_BASE_OK"}
    env["XDG_CONFIG_HOME"] = str(config_home)
    result = subprocess.run(
        [opencode, "debug", "config"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert out.is_file(), (
        "OpenCode never initialised the probe, so it never imported the delivered "
        f"loader; stderr: {result.stderr[-2000:]}"
    )
    verdicts = json.loads(out.read_text())
    assert verdicts["base_clone"].startswith("REFUSED fr-isolation"), verdicts
    assert verdicts["outside"] == "ALLOWED", verdicts
