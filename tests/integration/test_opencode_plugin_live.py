"""gh#563, live half: the plugin install.sh delivers is one OpenCode loads,
and the delivered copy (not the repo source) refuses a base-clone edit.

Two probes, each against throwaway XDG config/data/state/cache dirs. OpenCode 2
runs every CLI command through a background service on a fixed port, so each
probe gives its isolated service its own free port (`opencode service set
port`) and stops it afterwards — otherwise the CLI would talk to the operator's
own service and its plugins.

1. The REAL binary loads the delivered plugin directory: its server log records
   `loading plugin` for it EXACTLY ONCE, with no error. This is what #568's
   compiled executable would have failed: OpenCode never registers an
   extensionless file. Once, because OpenCode 2 scans plugin DIRECTORIES too,
   so the 1.x top-level loader beside the directory loaded it twice (plan
   finding p1-v2-loads-sources-dir-as-plugin). (`debug config` lists config
   sources, not plugins.)
2. OpenCode's own runtime imports and initialises the delivered loader: a
   sentinel plugin delivered beside it imports its V2 definition, runs its
   `setup` against a context that captures the `tool` `execute.before` hook,
   drives it and records the verdicts. A write into an fr-enabled base clone is
   refused; a write outside any repo is allowed.
3. The status line (spec R12): the real TUI, started under a pseudo-terminal in
   a git repo, loads the delivered `tui/` entrypoint and renders the segment
   script's text for that repo's branch.

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
import time
from collections.abc import Callable, Iterator
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
    return plugins / "fr-opencode-plugin"


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


def _wait_for(predicate: Callable[[], bool], seconds: float = 15.0) -> bool:
    """Bounded wait for the DAEMON's side of a probe.

    OpenCode 2 runs every CLI command through a background service, and
    `plugin list` RETURNS before that service has finished loading the plugins
    it was started for: both the sentinel's verdict file (written from a
    plugin's `setup`) and the service log's `loading plugin` line can arrive
    AFTER the CLI exits. Asserting straight after `plugin list` won the race on
    macOS and on 2.1.x, and lost it on the slower 2.0.32 CI runner — the
    failure reads "OpenCode never initialised the probe" for a probe that was
    simply still loading."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return predicate()


@contextmanager
def _service(opencode: str, project: Path, env: dict[str, str]) -> Iterator[None]:
    """An isolated OpenCode 2 background service, stopped on the way out.

    The service is a DETACHED daemon and inherits the stdio of whichever CLI
    call first started it, so a survivor holds the test runner's stdout pipe
    open after pytest has already printed its summary. Measured: 34s of tests,
    3m19s of wall clock, and `exit 124` from a `timeout` around a run that had
    already reported `3 passed`. So the pid recorded in this environment's
    `service.json` is captured before `service stop` (a successful stop deletes
    the file) and killed if it is still alive afterwards."""
    port = _opencode(opencode, "service", "set", "port", str(_free_port()), cwd=project, env=env)
    assert port.returncode == 0, port.stderr
    try:
        yield
    finally:
        pid = _service_pid(env)
        _opencode(opencode, "service", "stop", cwd=project, env=env)
        _reap_service(pid)


def _service_pid(env: dict[str, str]) -> int | None:
    import json

    path = Path(env["XDG_STATE_HOME"]) / "opencode" / "service.json"
    try:
        return int(json.loads(path.read_text())["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _reap_service(pid: int | None) -> None:
    """Kill a service `service stop` left behind; bounded, and never a stranger's."""
    import signal
    import time

    if pid is None:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.05)


def _project(root: Path) -> Path:
    project = root / "project"
    project.mkdir()
    _git("init", "--quiet", cwd=project)
    return project


def test_opencode_registers_the_delivered_plugin_exactly_once(tmp_path: Path) -> None:
    opencode = _binary("opencode")
    env = _isolated_env(tmp_path)
    loader = _deliver(Path(env["XDG_CONFIG_HOME"]))
    project = _project(tmp_path)

    log = Path(env["XDG_DATA_HOME"]) / "opencode" / "log" / "opencode.log"

    def _lines() -> list[str]:
        return log.read_text().splitlines() if log.is_file() else []

    # Inside the `with`: the service must be ALIVE for the load it started to
    # finish; `_service` stops it on the way out.
    with _service(opencode, project, env):
        result = _opencode(opencode, "plugin", "list", cwd=project, env=env)
        if result.returncode == 0:
            _wait_for(lambda: any('msg="loading plugin"' in line for line in _lines()))
    assert result.returncode == 0, result.stderr

    lines = _lines()
    loaded = [line for line in lines if 'msg="loading plugin"' in line]
    ours = [line for line in loaded if "fr-opencode-plugin" in line]
    assert len(ours) == 1, f"super-fr must load exactly once; its loads: {ours}"
    assert f"id={loader} " in ours[0], f"opencode did not load the delivered directory: {ours}"
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
        # Inside the `with`: the probe runs in the service's own `setup`, and
        # `_service` stops the service on the way out.
        if result.returncode == 0:
            _wait_for(out.is_file)
    assert result.returncode == 0, result.stderr
    assert out.is_file(), (
        "OpenCode never initialised the probe, so it never imported the delivered "
        f"loader; stderr: {result.stderr[-2000:]}"
    )
    verdicts = json.loads(out.read_text())
    assert verdicts["id"] == "super-fr", verdicts
    assert verdicts["base_clone"].startswith("REFUSED fr-isolation"), verdicts
    assert verdicts["outside"] == "ALLOWED", verdicts


def _tui_screen(opencode: str, cwd: Path, env: dict[str, str], seconds: float) -> str:
    """Run the interactive TUI on a pseudo-terminal for `seconds`; return its screen text.

    Its own session and process group, killed as a group on the way out, so
    nothing it started outlives the probe."""
    import fcntl
    import pty
    import re
    import select
    import signal
    import struct
    import termios
    import time

    leader, follower = pty.openpty()
    fcntl.ioctl(follower, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 160, 0, 0))
    proc = subprocess.Popen(
        [opencode],
        cwd=cwd,
        env={**env, "TERM": "xterm-256color"},
        stdin=follower,
        stdout=follower,
        stderr=follower,
        start_new_session=True,
    )
    os.close(follower)
    buf = b""
    end = time.monotonic() + seconds
    try:
        while time.monotonic() < end:
            ready, _, _ = select.select([leader], [], [], 0.5)
            if not ready:
                continue
            try:
                chunk = os.read(leader, 65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
    finally:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                break
            try:
                proc.wait(timeout=5)
                break
            except subprocess.TimeoutExpired:
                continue
        os.close(leader)
    text = re.sub(rb"\x1b\[[0-9;?<>=]*[a-zA-Z]|\x1b\][^\x07]*\x07", b"", buf)
    return text.decode(errors="ignore")


def test_opencode_tui_renders_the_delivered_status_line(tmp_path: Path) -> None:
    opencode = _binary("opencode")
    env = _isolated_env(tmp_path)
    env["HOME"] = str(tmp_path / "home")
    (tmp_path / "home").mkdir()
    _deliver(Path(env["XDG_CONFIG_HOME"]))
    project = tmp_path / "project"
    project.mkdir()
    _git("init", "--quiet", "-b", "frstatusprobe", cwd=project)
    _git(
        "-c",
        "user.email=t@example.com",
        "-c",
        "user.name=T",
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "x",
        cwd=project,
    )

    with _service(opencode, project, env):
        screen = _tui_screen(opencode, project, env, 30)
    flat = " ".join(screen.split())
    assert "frstatusprobe · no fr-isolation" in flat, (
        f"the TUI did not render the status line; screen tail: {flat[-1500:]}"
    )
