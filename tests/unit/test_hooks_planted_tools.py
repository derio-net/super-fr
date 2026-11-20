"""Every hook runs the RESOLVED jq, python3 and gh, never one PATH happens to reach.

Same class as #1429 (git) and gh#746 (fr), for the hooks' other helpers:

- #1509: the Claude edit gate parsed its payload with a bare `jq` under `set -eu`. With
  no jq on PATH the script died before it printed a decision, which the harness reads as
  "no opinion": an edit to a base clone went through.
- #1484: the decision library found python3/jq with `command -v`, which honours a
  RELATIVE PATH entry (`bin`, `.`, an empty one), i.e. a file in whatever directory the
  hook runs from; and it ran `python3 -c` without `-I`, which puts that directory on
  `sys.path`, so a `json.py` there is the `json` the parser imports.
- #1481: five hooks gated on `command -v jq` and then ran a bare `jq`; the push guard ran
  a bare `gh`.

A planted file in the hook's cwd stands in for one an agent wrote in a base clone (shell
writes are ungated with no live pipeline).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REAL = {name: shutil.which(name) for name in ("jq", "git", "python3")}
pytestmark = pytest.mark.skipif(
    any(v is None for v in REAL.values()), reason="hooks need jq, git and python3"
)

HOOKS_DIR = Path(__file__).resolve().parents[2] / "plugins" / "super-fr" / "hooks"
PLANTED = '#!/bin/sh\nprintf "%s %s\\n" "$0" "$*" >> "$PLANTED_MARK"\nexit 1\n'

# What the hooks run besides jq/python3/git. A missing one makes a hook fail in both
# the broken and the fixed state, so the shim stays generous.
_TOOLS = (
    "bash sh cat dirname basename sed tr grep head tail cut printf env mkdir rm ls stat "
    "realpath readlink date touch awk wc sort uniq mktemp mv cp ln find xargs sleep id "
    "uname timeout"
).split()


def _exe(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


def _shim(dest: Path, *, with_jq: bool) -> Path:
    """An absolute PATH entry holding the tools above, git, python3 and (maybe) jq."""
    dest.mkdir(parents=True)
    names = [*_TOOLS, "git", "python3", *(["jq"] if with_jq else [])]
    for name in names:
        real = REAL.get(name) or shutil.which(name)
        if real:
            (dest / name).symlink_to(real)
    # Several hooks leave before their first jq call when no `fr` resolves. This one
    # answers nothing, so each hook takes its "no answer" path after reading the payload.
    _exe(dest / "fr", "#!/bin/sh\nexit 1\n")
    return dest


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [REAL["git"], "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def world(tmp_path: Path) -> dict:
    repo = tmp_path / "repo"
    (repo / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "plans" / ".keep").write_text("")
    (repo / "src.py").write_text("x = 1\n")
    subprocess.run([REAL["git"], "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "i")
    # Planted where only a relative entry reaches them: `bin`, `.` and "".
    for name in ("jq", "python3", "gh"):
        _exe(repo / "bin" / name, PLANTED)
        _exe(repo / name, PLANTED)
    return {
        "repo": repo.resolve(),
        "tmp": tmp_path,
        "mark": tmp_path / "planted",
        "with_jq": _shim(tmp_path / "shim-jq", with_jq=True),
        "no_jq": _shim(tmp_path / "shim-nojq", with_jq=False),
    }


def _env(world: dict, path: str, **extra: str) -> dict[str, str]:
    return {
        "PATH": path,
        "HOME": str(world["tmp"]),
        "TMPDIR": str(world["tmp"]),
        "PLANTED_MARK": str(world["mark"]),
        "FR_SENTINEL_DIR": str(world["tmp"] / "sentinels"),
        **extra,
    }


def _run(script: str, payload: dict, cwd: Path, env: dict[str, str]):
    return subprocess.run(
        ["/bin/bash", str(HOOKS_DIR / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=60,
    )


def _edit(world: dict) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": str(world["repo"] / "src.py")}}


# --- #1509: the edit gate decides without jq -----------------------------------------


def test_the_edit_gate_denies_a_base_clone_edit_with_no_jq_anywhere(world: dict) -> None:
    env = _env(world, str(world["no_jq"]), FR_JQ_CANDIDATES="/nonexistent/jq")
    res = _run("fr-isolation-required.sh", _edit(world), world["tmp"], env)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny", res.stdout


def test_the_edit_gate_refuses_when_no_json_parser_resolves(world: dict) -> None:
    env = _env(
        world,
        str(world["no_jq"]),
        FR_JQ_CANDIDATES="/nonexistent/jq",
        FR_PYTHON_CANDIDATES="/nonexistent/python3",
    )
    res = _run("fr-isolation-required.sh", _edit(world), world["tmp"], env)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no JSON parser" in out["hookSpecificOutput"]["permissionDecisionReason"]


def _broken_python(world: dict) -> str:
    """A python3 that resolves but cannot run: a pyenv shim with no version, the CLT stub."""
    path = world["tmp"] / "broken" / "python3"
    _exe(path, "#!/bin/sh\nexit 127\n")
    return str(path)


def test_a_python3_that_cannot_run_and_no_jq_still_denies(world: dict) -> None:
    env = _env(
        world,
        str(world["no_jq"]),
        FR_JQ_CANDIDATES="/nonexistent/jq",
        FR_PYTHON_CANDIDATES=_broken_python(world),
    )
    res = _run("fr-isolation-required.sh", _edit(world), world["tmp"], env)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_python3_that_cannot_run_falls_through_to_jq(world: dict) -> None:
    # Not a lockout: with jq present the gate still decides, and allows what it allows.
    env = _env(world, str(world["with_jq"]), FR_PYTHON_CANDIDATES=_broken_python(world))
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(world["tmp"] / "x.txt")}}
    res = _run("fr-isolation-required.sh", payload, world["tmp"], env)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == ""
    res = _run("fr-isolation-required.sh", _edit(world), world["tmp"], env)
    assert json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_the_edit_gate_still_allows_an_edit_outside_any_repo_without_jq(world: dict) -> None:
    env = _env(world, str(world["no_jq"]), FR_JQ_CANDIDATES="/nonexistent/jq")
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(world["tmp"] / "x.txt")}}
    res = _run("fr-isolation-required.sh", payload, world["tmp"], env)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == ""


# --- #1484 / #1481: nothing a relative PATH entry reaches is ever run ------------------


def _hook_cases(world: dict) -> list[tuple[str, dict]]:
    repo = str(world["repo"])
    bash = {"tool_name": "Bash", "session_id": "s1", "cwd": repo}
    sentinels = world["tmp"] / "sentinels"
    sentinels.mkdir(exist_ok=True)
    (sentinels / "s1.json").write_text(json.dumps({"repo_root": repo, "skill": "fr-goal"}))
    return [
        ("fr-isolation-required.sh", _edit(world)),
        ("fr-isolation-guard.sh", bash | {"tool_input": {"command": "ls"}}),
        ("fr-merged-pr-push-guard.sh", bash | {"tool_input": {"command": "git push"}}),
        ("fr-phase-executor-guard.sh", {"tool_name": "Agent", "tool_input": {}}),
        ("fr-pipeline-sentinel.sh", {"tool_name": "Skill", "tool_input": {"skill": "x"}}),
        ("fr-acceptance-nag.sh", {"hook_event_name": "SessionStart", "cwd": repo}),
        ("fr-run-idle-guard.sh", {"session_id": "s1", "cwd": repo}),
        ("fr-session-bind.sh", bash | {"tool_input": {"command": "ls"}}),
        ("fr-session-unbind.sh", {"session_id": "s1", "reason": "exit"}),
        ("fr-worktree-create.sh", {"session_id": "s1", "cwd": repo, "name": "plain"}),
        ("fr-worktree-remove.sh", {"worktree_path": str(world["tmp"] / "nowhere")}),
        ("hermes/fr-isolation-required.sh", {"tool_name": "write_file", "tool_input": {}}),
    ]


@pytest.mark.parametrize("index", range(12))
def test_a_planted_tool_on_a_relative_path_entry_is_never_run(world: dict, index: int) -> None:
    script, payload = _hook_cases(world)[index]
    path = os.pathsep.join(["bin", ".", "", str(world["with_jq"]), "/usr/bin", "/bin"])
    res = _run(script, payload, world["repo"], _env(world, path))
    planted = world["mark"].read_text() if world["mark"].exists() else ""
    assert planted == "", f"{script} ran a planted tool:\n{planted}\nstderr: {res.stderr}"


@pytest.mark.parametrize("script", ["fr-isolation-required.sh", "hermes/fr-isolation-required.sh"])
def test_the_json_parser_never_imports_from_the_hook_cwd(world: dict, script: str) -> None:
    # `python3 -c` puts the cwd on sys.path; `-I` does not. A json.py there is the
    # `json` an un-isolated parser imports.
    (world["repo"] / "json.py").write_text(
        f"open({str(world['mark'])!r}, 'a').write('json.py imported\\n')\nraise SystemExit(0)\n"
    )
    tool = "write_file" if script.startswith("hermes") else "Edit"
    key = "path" if script.startswith("hermes") else "file_path"
    payload = {"tool_name": tool, "tool_input": {key: str(world["repo"] / "src.py")}}
    env = _env(world, str(world["no_jq"]), FR_JQ_CANDIDATES="/nonexistent/jq")
    _run(script, payload, world["repo"], env)
    assert not world["mark"].exists(), world["mark"].read_text()


# --- tripwire --------------------------------------------------------------------------

_BARE = re.compile(r"(?:^|[;&|(]|\$\(|\b(?:if|then|do|!|&&|\|\|))\s*(jq|gh)(?:\s|$)")
_COMMAND_V = re.compile(r"command\s+-v\s+(jq|gh|python3)\b")


def _scripts() -> list[Path]:
    return sorted([*HOOKS_DIR.glob("*.sh"), *HOOKS_DIR.glob("hermes/*.sh")])


def test_no_hook_script_runs_a_bare_jq_or_gh() -> None:
    offenders = []
    for script in _scripts():
        for n, line in enumerate(script.read_text().splitlines(), 1):
            code = "" if line.lstrip().startswith("#") else re.sub(r"\s#.*$", "", line)
            if _BARE.search(code) or _COMMAND_V.search(code):
                offenders.append(f"{script.relative_to(HOOKS_DIR)}:{n}: {line.strip()}")
    assert offenders == [], "run fr_jq / fr_gh, never a bare name:\n" + "\n".join(offenders)


def test_the_library_resolves_no_tool_with_command_v() -> None:
    lib = (HOOKS_DIR / "lib" / "fr-isolation-decision.sh").read_text()
    code = "\n".join(line.split("#", 1)[0] for line in lib.splitlines())
    assert "command -v" not in code


def test_the_library_runs_python_isolated() -> None:
    lib = (HOOKS_DIR / "lib" / "fr-isolation-decision.sh").read_text()
    assert '"$FR_JSON_BIN" -c' not in lib
    assert '"$FR_JSON_BIN" -I -c' in lib
