"""fr-worktree-create.sh (WorktreeCreate) and fr-worktree-remove.sh (WorktreeRemove).

Spec 2026-09-04 §5.B.3 / §5.B.4: a native Claude session worktree in an
fr-enabled repo becomes an fr workspace (``fr isolation up --print-path``);
subagent worktrees (``agent-*``) and non-fr repos keep Claude's default shape
(``<repo>/.claude/worktrees/<name>``, detached). The hooks are exercised via
subprocess with hook-protocol JSON on stdin and a stub ``fr`` on PATH that
records its argv (and the FR_ISOLATION_TARGET it saw) and fakes a worktree
path, so no real fr state is ever touched. git runs for real.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="hook scripts require jq")

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "plugins" / "super-fr" / "hooks"
CREATE = HOOKS_DIR / "fr-worktree-create.sh"
REMOVE = HOOKS_DIR / "fr-worktree-remove.sh"

STUB = r"""#!/bin/bash
printf '%s\n' "$*" >> "$FR_STUB_LOG"
printf '%s\n' "${FR_ISOLATION_TARGET:-}" >> "$FR_STUB_LOG.env"
b=""
for ((i=1;i<=$#;i++)); do [ "${!i}" = "--branch" ] && j=$((i+1)) && b="${!j}"; done
d="$HOME/.cache/fr/worktrees/stub/${b//\//__}"
mkdir -p "$d"
echo "stdout noise"
echo "isolation up: worktree=$d" >&2
echo "$d"
"""


@pytest.fixture
def stub_fr(tmp_path: Path) -> dict[str, str]:
    """Recording ``fr`` stub first on PATH; returns the env to run hooks with.

    The stub CREATES the path it is asked for and prints it as its last stdout
    line (after some noise), mirroring ``fr isolation up --print-path``."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "fr"
    stub.write_text(STUB)
    stub.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "FR_STUB_LOG": str(tmp_path / "fr.log"),
        "HOME": str(tmp_path),
    }
    env.pop("FR_ISOLATION_TARGET", None)  # case (f) depends on it being unset
    return env


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """An fr-enabled repo: one commit, docs/superpowers/plans/ committed."""
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    (r / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (r / "docs" / "superpowers" / "plans" / ".keep").write_text("")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "init")
    return r.resolve()


@pytest.fixture
def plain_repo(tmp_path: Path) -> Path:
    """A git repo that is NOT fr-enabled (no plans dir, no devcontainer)."""
    r = tmp_path / "plain"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    (r / "x").write_text("x")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "init")
    return r.resolve()


def run_hook(script: Path, payload: dict, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def create_payload(name: str, cwd: Path | str) -> dict:
    return {
        "session_id": "sess-1",
        "cwd": str(cwd),
        "hook_event_name": "WorktreeCreate",
        "name": name,
    }


def remove_payload(cwd: Path | str, **fields: object) -> dict:
    return {
        "session_id": "sess-1",
        "cwd": str(cwd),
        "hook_event_name": "WorktreeRemove",
        **fields,
    }


def logged(env: dict[str, str]) -> list[str]:
    log = Path(env["FR_STUB_LOG"])
    if not log.exists():
        return []
    return log.read_text().splitlines()


def logged_env(env: dict[str, str]) -> list[str]:
    log = Path(env["FR_STUB_LOG"] + ".env")
    if not log.exists():
        return []
    return log.read_text().splitlines()


def agent_dir(env: dict[str, str], name: str, key: str = "repo") -> Path:
    """Where the hook puts an `agent-*` worktree (gh#1270)."""
    return Path(env["HOME"]) / ".cache" / "fr" / "agent-worktrees" / key / name


def last_line(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def worktrees(repo: Path) -> list[str]:
    out = _git(repo, "worktree", "list", "--porcelain")
    return [ln.split(" ", 1)[1] for ln in out.splitlines() if ln.startswith("worktree ")]


class TestWorktreeCreate:
    # (a) session worktree in an fr-enabled repo -> fr isolation up --print-path
    def test_session_worktree_becomes_fr_workspace(
        self, tmp_path: Path, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        result = run_hook(CREATE, create_payload("feature-auth", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        assert last_line(result.stdout) == str(
            tmp_path / ".cache" / "fr" / "worktrees" / "stub" / "wt__feature-auth"
        )
        assert logged(stub_fr) == [
            f"isolation up --repo {repo} --branch wt/feature-auth "
            "--session sess-1 --harness claude --print-path"
        ]

    # (b) a name that already contains a slash is used as the branch verbatim
    def test_name_with_slash_is_branch_verbatim(
        self, tmp_path: Path, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        result = run_hook(CREATE, create_payload("feat/x", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        assert last_line(result.stdout) == str(
            tmp_path / ".cache" / "fr" / "worktrees" / "stub" / "feat__x"
        )
        assert "--branch feat/x " in logged(stub_fr)[0]

    # (c) agent-* -> OUTSIDE the repo, under the fr agent cache (gh#1270): a real
    # linked worktree of the repo, idempotent, never routed through fr.
    def test_agent_worktree_lands_outside_the_repo(
        self, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        result = run_hook(CREATE, create_payload("agent-abc123", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        expected = agent_dir(stub_fr, "agent-abc123")
        assert last_line(result.stdout) == str(expected)
        assert expected.is_dir()
        assert str(expected) in worktrees(repo)
        assert not (repo / ".claude" / "worktrees").exists()
        again = run_hook(CREATE, create_payload("agent-abc123", repo), stub_fr)
        assert again.returncode == 0, again.stderr
        assert last_line(again.stdout) == str(expected)

    def test_agent_worktree_is_locked_with_the_session_pid(
        self, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        """Claude's native path locks a running subagent's worktree; a hook-made
        one has no lock unless the hook takes it. The reason names the hook's
        parent (the Claude process, measured live) so gc can tell running from
        finished (gh#1270)."""
        result = run_hook(CREATE, create_payload("agent-lck1", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        porcelain = _git(repo, "worktree", "list", "--porcelain")
        block = porcelain.split(f"worktree {agent_dir(stub_fr, 'agent-lck1')}\n", 1)[1]
        block = block.split("\n\n", 1)[0]
        assert f"locked fr-agent pid={os.getpid()} session=sess-1" in block

    def test_nested_agent_worktree_is_a_sibling_not_a_child(
        self, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        """A subagent inside its worktree dispatching another isolated subagent
        nested `agent-Y` inside `agent-X` (frank: 4 of 31). Out of the repo, both
        are siblings under the MAIN checkout's key."""
        outer = run_hook(CREATE, create_payload("agent-outer", repo), stub_fr)
        assert outer.returncode == 0, outer.stderr
        inner = run_hook(CREATE, create_payload("agent-inner", last_line(outer.stdout)), stub_fr)
        assert inner.returncode == 0, inner.stderr
        assert last_line(inner.stdout) == str(agent_dir(stub_fr, "agent-inner"))
        assert str(agent_dir(stub_fr, "agent-inner")) in worktrees(repo)

    def test_agent_worktree_creation_fires_a_detached_agent_sweep(
        self, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        """Claude never fires WorktreeRemove for a subagent, and non-fr repos never
        run `fr isolation up/down`, so every agent dispatch starts the reaper."""
        result = run_hook(CREATE, create_payload("agent-sw1", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        for _ in range(50):
            if logged(stub_fr):
                break
            time.sleep(0.1)
        assert logged(stub_fr) == [f"isolation gc --agent-worktrees --repo {repo}"]

    def test_agent_dir_owned_by_another_repo_fails_closed(
        self, tmp_path: Path, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        """Two repos with one basename share a cache key. A name collision must
        not hand a subagent the OTHER repo's checkout."""
        other = tmp_path / "elsewhere" / "repo"
        other.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(other)], check=True)
        (other / "y").write_text("y")
        _git(other, "add", "-A")
        _git(other, "commit", "-qm", "init")
        first = run_hook(CREATE, create_payload("agent-same", other), stub_fr)
        assert first.returncode == 0, first.stderr
        result = run_hook(CREATE, create_payload("agent-same", repo), stub_fr)
        assert result.returncode == 1
        assert "belongs to another repository" in result.stderr

    # (c2) super-fr#455: agent-* also copies `.worktreeinclude` matches — the
    # files that are BOTH git-ignored and named by an include pattern, as
    # Claude's native path does (spec 2026-09-04 §5.B.3).
    def test_agent_worktree_copies_worktreeinclude_matches(
        self, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        (repo / ".gitignore").write_text(".env\nbuild/\nsecrets/\n")
        (repo / ".worktreeinclude").write_text(".env\nsecrets/\nnotes.txt\n")
        _git(repo, "add", ".gitignore", ".worktreeinclude")
        _git(repo, "commit", "-qm", "include")
        (repo / ".env").write_text("TOKEN=x\n")  # ignored + included -> copied
        (repo / "secrets").mkdir()
        (repo / "secrets" / "k.pem").write_text("k\n")  # nested, ignored + included
        (repo / "build").mkdir()
        (repo / "build" / "out.o").write_text("o\n")  # ignored, not included
        (repo / "notes.txt").write_text("n\n")  # included, NOT ignored -> not copied

        result = run_hook(CREATE, create_payload("agent-inc1", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        wt = agent_dir(stub_fr, "agent-inc1")
        assert last_line(result.stdout) == str(wt)
        assert (wt / ".env").read_text() == "TOKEN=x\n"
        assert (wt / "secrets" / "k.pem").read_text() == "k\n"
        assert not (wt / "build").exists()
        assert not (wt / "notes.txt").exists()

    def test_agent_worktree_include_copy_never_writes_through_a_symlink(
        self, tmp_path: Path, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        """The agent worktree is cut from the COMMITTED tree, which may hold a
        symlink where the base checkout has a real directory. The copy must not
        follow it out of the worktree (security review of super-fr#455)."""
        outside = tmp_path / "outside"
        outside.mkdir()
        (repo / ".gitignore").write_text(".env\n")
        (repo / ".worktreeinclude").write_text(".env\n")
        (repo / "cfg").symlink_to(outside)
        _git(repo, "add", ".gitignore", ".worktreeinclude", "cfg")
        _git(repo, "commit", "-qm", "cfg is a symlink in the committed tree")
        (repo / "cfg").unlink()
        (repo / "cfg").mkdir()  # ...but a real directory in the base checkout
        (repo / "cfg" / ".env").write_text("TOKEN=x\n")
        (repo / ".env").symlink_to(outside / "secret")  # an ignored symlink source
        (outside / "secret").write_text("s\n")

        result = run_hook(CREATE, create_payload("agent-inc3", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        wt = agent_dir(stub_fr, "agent-inc3")
        assert not (outside / ".env").exists(), "copied through the committed symlink"
        assert (wt / ".env").is_symlink()  # copied as a link, not its target's bytes

    def test_agent_worktree_without_worktreeinclude_copies_nothing(
        self, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        (repo / ".gitignore").write_text(".env\n")
        _git(repo, "add", ".gitignore")
        _git(repo, "commit", "-qm", "ignore")
        (repo / ".env").write_text("TOKEN=x\n")
        result = run_hook(CREATE, create_payload("agent-inc2", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        assert not (agent_dir(stub_fr, "agent-inc2") / ".env").exists()

    # (d) non-fr repo -> default shape even for a session worktree name
    def test_non_fr_repo_mimics_default(self, plain_repo: Path, stub_fr: dict[str, str]) -> None:
        result = run_hook(CREATE, create_payload("feature-auth", plain_repo), stub_fr)
        assert result.returncode == 0, result.stderr
        expected = plain_repo / ".claude" / "worktrees" / "feature-auth"
        assert last_line(result.stdout) == str(expected)
        assert expected.is_dir()
        assert logged(stub_fr) == []

    # (e) cwd not a git repo -> exit 1 (a registered hook cannot decline)
    def test_non_git_cwd_exits_1(self, tmp_path: Path, stub_fr: dict[str, str]) -> None:
        d = tmp_path / "nogit"
        d.mkdir()
        result = run_hook(CREATE, create_payload("feature-auth", d), stub_fr)
        assert result.returncode == 1
        assert "not a git repo" in result.stderr
        assert logged(stub_fr) == []

    # (f) fr-enabled via plans dir, no profile, FR_ISOLATION_TARGET unset ->
    #     the hook exports host-worktree mode for this call
    def test_no_profile_exports_host_worktree_mode(
        self, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        assert "FR_ISOLATION_TARGET" not in stub_fr
        result = run_hook(CREATE, create_payload("feature-auth", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        assert len(logged(stub_fr)) == 1
        assert logged_env(stub_fr) == ["worktree"]
        assert "host-worktree mode" in result.stderr

    def test_profile_present_leaves_target_alone(self, repo: Path, stub_fr: dict[str, str]) -> None:
        (repo / ".devcontainer" / "dev").mkdir(parents=True)
        result = run_hook(CREATE, create_payload("feature-auth", repo), stub_fr)
        assert result.returncode == 0, result.stderr
        assert logged_env(stub_fr) == [""]

    def test_preset_target_is_respected(self, repo: Path, stub_fr: dict[str, str]) -> None:
        env = {**stub_fr, "FR_ISOLATION_TARGET": "devcontainer"}
        result = run_hook(CREATE, create_payload("feature-auth", repo), env)
        assert result.returncode == 0, result.stderr
        assert logged_env(env) == ["devcontainer"]


class TestWorktreeRemove:
    # (g) agent-* path -> plain git worktree removal, fr never called. Both the
    # legacy in-repo shape and the gh#1270 cache shape, the latter locked.
    def test_legacy_in_repo_agent_worktree_removed_with_git(
        self, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        wt = repo / ".claude" / "worktrees" / "agent-abc123"
        wt.parent.mkdir(parents=True)
        _git(repo, "worktree", "add", "--detach", str(wt), "HEAD")
        assert str(wt) in worktrees(repo)
        result = run_hook(REMOVE, remove_payload(repo, worktree_path=str(wt)), stub_fr)
        assert result.returncode == 0, result.stderr
        assert not wt.exists()
        assert str(wt) not in worktrees(repo)
        assert logged(stub_fr) == []

    def test_locked_cache_agent_worktree_removed_with_git(
        self, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        made = run_hook(CREATE, create_payload("agent-rm1", repo), stub_fr)
        assert made.returncode == 0, made.stderr
        wt = agent_dir(stub_fr, "agent-rm1")
        result = run_hook(REMOVE, remove_payload(repo, worktree_path=str(wt)), stub_fr)
        assert result.returncode == 0, result.stderr
        assert not wt.exists()
        assert str(wt) not in worktrees(repo)
        assert [
            ln for ln in logged(stub_fr) if "--agent-worktrees" not in ln
        ] == []  # create's sweep only

    # (h) any other path -> fr isolation down --worktree <path>
    def test_other_path_delegates_to_fr_down(
        self, tmp_path: Path, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        p = tmp_path / "cache" / "wt"
        result = run_hook(REMOVE, remove_payload(repo, worktree_path=str(p)), stub_fr)
        assert result.returncode == 0, result.stderr
        assert logged(stub_fr) == [f"isolation down --worktree {p}"]

    # (i) missing worktree_path -> exit 0, nothing happens
    def test_missing_worktree_path_is_noop(self, repo: Path, stub_fr: dict[str, str]) -> None:
        result = run_hook(REMOVE, remove_payload(repo), stub_fr)
        assert result.returncode == 0, result.stderr
        assert logged(stub_fr) == []

    def test_fr_refusal_is_reported_but_exit_0(
        self, tmp_path: Path, repo: Path, stub_fr: dict[str, str]
    ) -> None:
        """A refused down (open PR) keeps the workspace: the hook says so on
        stderr and still exits 0 (spec §5.B.4)."""
        stub = Path(stub_fr["PATH"].split(":")[0]) / "fr"
        stub.write_text(STUB + "exit 2\n")
        p = tmp_path / "cache" / "wt"
        result = run_hook(REMOVE, remove_payload(repo, worktree_path=str(p)), stub_fr)
        assert result.returncode == 0
        assert "refused" in result.stderr and str(p) in result.stderr
        assert logged(stub_fr) == [f"isolation down --worktree {p}"]


# --- The hook may be registered twice (plugin hooks.json + ~/.claude/settings.json) ---
#
# Claude Code 2.1.281 does not invoke a PLUGIN-registered WorktreeCreate for
# `claude --worktree` (live, 2026-09-24), so install.sh also registers the same
# script in settings.json. Where Claude Code DOES invoke both, the two copies
# run concurrently and would race on the same `git worktree add` — a nonzero
# exit fails the worktree creation outright. The hook serializes `fr isolation
# up` per repo+branch so a double registration is harmless.

SLOW_STUB = (
    r"""#!/bin/bash
mkdir "$HOME/in-flight" 2>/dev/null || echo OVERLAP >> "$FR_STUB_LOG"
sleep 1
"""
    + STUB.split("\n", 1)[1]
    + r"""
rmdir "$HOME/in-flight" 2>/dev/null
"""
)


def test_two_concurrent_invocations_do_not_overlap(repo: Path, stub_fr: dict[str, str]) -> None:
    stub = Path(stub_fr["PATH"].split(":")[0]) / "fr"
    stub.write_text(SLOW_STUB)
    # stdin from a file, not a pipe: with pipes, communicate() on the first
    # process blocks the second on `input=$(cat)` until the first finishes,
    # so the two never actually overlap and the test proves nothing.
    payload = Path(stub_fr["HOME"]) / "payload.json"
    payload.write_text(json.dumps(create_payload("twice", repo)))
    procs = []
    for _ in range(2):
        with payload.open() as stdin:
            procs.append(
                subprocess.Popen(
                    ["bash", str(CREATE)],
                    stdin=stdin,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=stub_fr,
                )
            )
    outs = [p.communicate(timeout=60) for p in procs]
    assert all(p.returncode == 0 for p in procs), [o[1] for o in outs]
    assert "OVERLAP" not in logged(stub_fr), "two fr isolation up runs overlapped"
    paths = {o[0].strip().splitlines()[-1] for o in outs}
    assert len(paths) == 1, f"the two invocations disagree on the worktree: {paths}"


SLOW_DOWN_STUB = r"""#!/bin/bash
printf '%s\n' "$*" >> "$FR_STUB_LOG"
mkdir "$HOME/down-in-flight" 2>/dev/null || echo OVERLAP >> "$FR_STUB_LOG"
sleep 1
rmdir "$HOME/down-in-flight" 2>/dev/null
"""


def test_two_concurrent_removals_do_not_overlap(
    tmp_path: Path, repo: Path, stub_fr: dict[str, str]
) -> None:
    """Same double registration, WorktreeRemove side: two `fr isolation down`
    runs on one workspace must not tear it down concurrently."""
    stub = Path(stub_fr["PATH"].split(":")[0]) / "fr"
    stub.write_text(SLOW_DOWN_STUB)
    target = tmp_path / "cache" / "wt"
    payload = tmp_path / "remove.json"
    payload.write_text(json.dumps(remove_payload(repo, worktree_path=str(target))))
    procs = []
    for _ in range(2):
        with payload.open() as stdin:
            procs.append(
                subprocess.Popen(
                    ["bash", str(REMOVE)],
                    stdin=stdin,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=stub_fr,
                )
            )
    for p in procs:
        p.communicate(timeout=60)
    assert all(p.returncode == 0 for p in procs)
    assert "OVERLAP" not in logged(stub_fr), "two fr isolation down runs overlapped"


# gh#1124: the lock above covered only the `fr isolation up` path. `agent-*`
# worktrees (every `isolation: "worktree"` Agent dispatch) took `mimic_default`
# BEFORE the lock, so the two registered copies both ran `git worktree add` on
# one path: the loser hit `.git/worktrees/agent-<id>/index.lock` and the
# dispatch failed. A slow `git worktree add` shim makes the overlap certain.
SLOW_GIT = r"""#!/bin/bash
if [ "${3:-}" = "worktree" ] && [ "${4:-}" = "add" ]; then sleep 1; fi
exec "$REAL_GIT" "$@"
"""


def test_two_concurrent_agent_worktree_creations_both_succeed(
    repo: Path, stub_fr: dict[str, str]
) -> None:
    bin_dir = Path(stub_fr["PATH"].split(":")[0])
    git = bin_dir / "git"
    git.write_text(SLOW_GIT)
    git.chmod(0o755)
    env = {**stub_fr, "REAL_GIT": shutil.which("git") or "git"}
    payload = Path(stub_fr["HOME"]) / "agent-payload.json"
    payload.write_text(json.dumps(create_payload("agent-twice", repo)))
    procs = []
    for _ in range(2):
        with payload.open() as stdin:
            procs.append(
                subprocess.Popen(
                    ["bash", str(CREATE)],
                    stdin=stdin,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                )
            )
    outs = [p.communicate(timeout=60) for p in procs]
    assert all(p.returncode == 0 for p in procs), [o[1] for o in outs]
    expected = str(agent_dir(stub_fr, "agent-twice"))
    assert {last_line(o[0]) for o in outs} == {expected}
    assert worktrees(repo).count(expected) == 1


def test_agent_worktree_of_a_bare_repo_is_removed_and_unlocked(
    tmp_path: Path, stub_fr: dict[str, str]
) -> None:
    """A bare repo's common dir has no parent checkout; the remove hook must
    still unlock and remove, or its `rm -rf` fallback leaves a locked entry."""
    bare = tmp_path / "b.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", "-q", str(bare), str(seed)], check=True, capture_output=True)
    (seed / "x").write_text("x")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-qm", "init")
    _git(seed, "push", "-q", "origin", "main")
    wt = agent_dir(stub_fr, "agent-bare1", key="b")
    wt.parent.mkdir(parents=True)
    subprocess.run(
        ["git", "--git-dir", str(bare), "worktree", "add", "--detach", str(wt), "main"],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "--git-dir", str(bare), "worktree", "lock", str(wt)], check=True)
    result = run_hook(REMOVE, remove_payload(tmp_path, worktree_path=str(wt)), stub_fr)
    assert result.returncode == 0, result.stderr
    listed = subprocess.run(
        ["git", "--git-dir", str(bare), "worktree", "list"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert str(wt) not in listed
