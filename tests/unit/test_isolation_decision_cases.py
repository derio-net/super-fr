"""The shared behavioural table of the edit gate (review p2-r6).

`tests/fixtures/isolation-decision-cases.json` holds cases both engines must decide
identically: the switch's fallback order and blob compare, which file wins, the stealth
`-config` naming, the configuration-tree shape and the allowlist's self-protection. This
file drives the bash library with them; `packages/fr-opencode-plugin/test/
decision-cases.test.ts` drives marker.ts with the same file. A logic edit to one engine
alone fails one of the two suites, where a test pinning strings alone would stay green.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "lib" / "fr-isolation-decision.sh"
CASES: dict[str, Any] = json.loads(
    (REPO_ROOT / "tests" / "fixtures" / "isolation-decision-cases.json").read_text()
)
NO_FR = {"PATH": "/usr/bin:/bin"}

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="needs git"),
    pytest.mark.own_artifacts,
]


def _bash(script: str) -> str:
    done = subprocess.run(
        ["bash", "-c", f'. "{LIB}"; {script}'],
        capture_output=True,
        text=True,
        env={**os.environ, **NO_FR},
        check=False,
    )
    return done.stdout


def _git(cwd: Path, *args: str, stdin: str | None = None) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _switch_ref(repo: Path, ref: str, path: list[str], settings: str | None) -> None:
    """*ref* -> an orphan commit whose tree holds *settings* at *path* (nothing when None)."""
    if settings is None:
        blob = _git(repo, "hash-object", "-w", "--stdin", stdin="other\n")
        tree = _git(repo, "mktree", stdin=f"100644 blob {blob}\tnotes.md\n")
    else:
        blob = _git(repo, "hash-object", "-w", "--stdin", stdin=settings)
        tree = _git(repo, "mktree", stdin=f"100644 blob {blob}\t{path[-1]}\n")
        for name in reversed(path[:-1]):
            tree = _git(repo, "mktree", stdin=f"040000 tree {tree}\t{name}\n")
    commit = _git(repo, "commit-tree", tree, "-m", "switch")
    _git(repo, "update-ref", ref, commit)


@pytest.mark.parametrize("case", CASES["switch"], ids=lambda c: c["id"])
def test_switch(tmp_path: Path, case: dict[str, Any]) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "remote", "add", "origin", "https://example.com/org/repo.git")
    if case["new"] is not None:
        _switch_ref(
            repo, "refs/remotes/origin/fr-config", [".fr", "settings.yaml"], case["new"]["settings"]
        )
    if case["old"] is not None:
        _switch_ref(repo, "refs/remotes/origin/fr", ["settings.yaml"], case["old"]["settings"])
    top = shlex.quote(str(repo))
    out = _bash(
        f"fr_git_resolve; r=0; e=0; q=0; "
        f"if _fr_read_switch {top}; then r=1; "
        f'_fr_switch_enabled "$_fr_switch" && [ "$_fr_live" -eq 1 ] '
        f'&& [ "$_fr_canon" = "placement: quiet" ] && q=1; fi; '
        f'_fr_placement_enabled {top} && e=1; echo "$r $e $q"'
    ).split()
    assert out == [str(int(case[k])) for k in ("read", "enabled", "quiet")], case["id"]


@pytest.mark.parametrize("case", CASES["allowlist"], ids=lambda c: c["id"])
def test_allowlist(tmp_path: Path, case: dict[str, Any]) -> None:
    top = tmp_path.resolve()
    file = shlex.quote(f"{top}/{case['rel']}")
    out = _bash(
        f"_fr_allowlist_protected {shlex.quote(str(top))} {file} {shlex.quote(case['rel'])} "
        "&& echo 1 || echo 0"
    )
    assert out.strip() == str(int(case["protected"])), case["id"]


@pytest.mark.parametrize("case", CASES["config_tree"], ids=lambda c: c["id"])
def test_config_tree(case: dict[str, Any]) -> None:
    names = "\\n".join(n.replace("\\", "\\\\") for n in case["names"])
    out = _bash(f"printf '{names}\\n' | _fr_config_tree_ok {case['depth']} && echo 1 || echo 0")
    assert out.strip() == str(int(case["ok"])), case["id"]


@pytest.mark.parametrize("case", CASES["stealth_head"], ids=lambda c: c["id"])
def test_stealth_head(case: dict[str, Any]) -> None:
    args = " ".join(shlex.quote(case[k]) for k in ("clone", "branch", "head"))
    out = _bash(f"_fr_stealth_head_ok {args} && echo 1 || echo 0")
    assert out.strip() == str(int(case["ok"])), case["id"]


def test_every_category_has_cases() -> None:
    assert {"switch", "allowlist", "config_tree", "stealth_head"} <= set(CASES)
    assert all(CASES[k] for k in ("switch", "allowlist", "config_tree", "stealth_head"))
