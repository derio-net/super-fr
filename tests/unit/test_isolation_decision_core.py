"""lib/fr-isolation-decision.sh — the pure fr-isolation edit decision.

The marker/allowlist/fr-enabled logic is shared by the Claude Code PreToolUse
hook and the Hermes pre_tool_call hook, so it lives in one sourced shell library
with no stdin/stdout protocol and no harness-specific deny shape. This test
drives the function directly: `. lib; fr_isolation_decide_edit <abs-path>` and
asserts the return code — 0 ALLOW, 1 BLOCK.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "lib" / "fr-isolation-decision.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="decision core needs git",
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def fr_repo(tmp_path: Path, name: str = "repo", fr_enabled: bool = True) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "README.md").write_text("x\n")
    if fr_enabled:
        d = repo / ".devcontainer" / "dev"
        d.mkdir(parents=True)
        (d / "devcontainer.json").write_text('{"image": "x"}\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def linked_worktree(repo: Path, branch: str = "feat/x") -> Path:
    wt = repo.parent / f"{repo.name}-wt"
    _git(repo, "worktree", "add", "-q", str(wt), "-b", branch)
    return wt


def write_marker(root: Path, toplevel: Path, mode: str = "worktree") -> None:
    (root / ".fr-isolation").write_text(
        f'{{"toplevel": "{toplevel.resolve()}", "branch": "feat/x", "mode": "{mode}"}}'
    )


def decide(file: Path, env: dict[str, str] | None = None) -> int:
    """Return code of fr_isolation_decide_edit for `file` (0 allow, 1 block)."""
    script = f'. "{LIB}"; fr_isolation_decide_edit "{file}"'
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    return result.returncode


def test_blocks_edit_outside_worktree_in_fr_repo(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert decide(repo / "src.py") == 1


def test_allows_non_fr_repo(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path, fr_enabled=False)
    assert decide(repo / "src.py") == 0


def test_fr_base_ok_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert decide(repo / "src.py", env={"FR_BASE_OK": "1"}) == 0


def test_allowlist_glob_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    (repo / ".fr-isolation-allow").write_text("projects/**\n")
    assert decide(repo / "projects" / "deep" / "x.md") == 0
    assert decide(repo / "src.py") == 1


def test_valid_linked_worktree_marker_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    write_marker(wt, wt)
    assert decide(wt / "src.py") == 0


def test_stale_marker_in_primary_tree_still_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    write_marker(repo, repo)  # marker copied into the primary tree — not a linked worktree
    assert decide(repo / "src.py") == 1


# --- mode "external": toplevel match + container evidence ------------------
#
# An external marker is a preparer's claim ("this checkout is contained"). It
# validates only with a matching recorded toplevel AND live container evidence
# (/.dockerenv, /run/.containerenv, or $KUBERNETES_SERVICE_HOST). Tests inject
# evidence via $KUBERNETES_SERVICE_HOST — the two file probes can't be created
# on the test host. The negative-evidence case is skipped when /.dockerenv
# actually exists (CI containers), where the file probe would fire regardless.


def test_external_marker_with_container_evidence_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    write_marker(repo, repo, mode="external")  # preparer's checkout == primary tree
    assert decide(repo / "src.py", env={"KUBERNETES_SERVICE_HOST": "1"}) == 0


def test_external_marker_without_evidence_blocks(tmp_path: Path) -> None:
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        pytest.skip("container evidence file present on host — file probe fires unconditionally")
    repo = fr_repo(tmp_path)
    write_marker(repo, repo, mode="external")
    assert decide(repo / "src.py", env={"KUBERNETES_SERVICE_HOST": ""}) == 1


def test_external_marker_toplevel_mismatch_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    bogus = tmp_path / "elsewhere"
    bogus.mkdir()
    write_marker(repo, bogus, mode="external")  # recorded toplevel != actual
    assert decide(repo / "src.py", env={"KUBERNETES_SERVICE_HOST": "1"}) == 1


def test_bogus_mode_marker_fails_closed(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    write_marker(repo, repo, mode="bogus")  # unknown mode → never valid
    assert decide(repo / "src.py", env={"KUBERNETES_SERVICE_HOST": "1"}) == 1


def test_worktree_mode_unchanged_by_external_branch(tmp_path: Path) -> None:
    # Existing worktree-mode behavior stays byte-identical: linked worktree +
    # worktree marker still ALLOW with no container-evidence env.
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    write_marker(wt, wt, mode="worktree")
    assert decide(wt / "src.py", env={"KUBERNETES_SERVICE_HOST": ""}) == 0


# ---------- super-fr#553: the marker's branch is checked against HEAD ----------


def test_worktree_marker_blocks_when_checkout_drifted_to_another_branch(tmp_path: Path) -> None:
    # The marker records `feat/x`; a `git checkout -b` moved the worktree to
    # another branch, so fr's state no longer describes what is being edited.
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)  # on feat/x
    write_marker(wt, wt)
    _git(wt, "checkout", "-q", "-b", "chore/elsewhere")
    assert decide(wt / "src.py") == 1


def test_worktree_marker_allows_detached_head(tmp_path: Path) -> None:
    # A rebase or bisect detaches HEAD without moving to another branch; the
    # gate must not block conflict resolution mid-rebase.
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    write_marker(wt, wt)
    _git(wt, "checkout", "-q", "--detach")
    assert decide(wt / "src.py") == 0


def test_drift_reason_names_both_branches(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    write_marker(wt, wt)
    _git(wt, "checkout", "-q", "-b", "chore/elsewhere")
    out = subprocess.run(
        ["bash", "-c", f'. "{LIB}"; fr_isolation_drift_reason "{wt / "src.py"}"'],
        capture_output=True,
        text=True,
    ).stdout
    assert "feat/x" in out and "chore/elsewhere" in out
    assert "git switch feat/x" in out and "fr isolation up --branch chore/elsewhere" in out


def test_drifted_worktree_is_still_an_allowed_shell_context(tmp_path: Path) -> None:
    # Review finding: the Bash guards ask decide_cwd, and treating a drifted
    # worktree as a base clone blocked `git switch <registered>`, the very
    # recovery the deny names. Drift is refused by the EDIT decision only.
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    write_marker(wt, wt)
    _git(wt, "checkout", "-q", "-b", "chore/elsewhere")
    rc = subprocess.run(
        ["bash", "-c", f'. "{LIB}"; fr_isolation_decide_cwd "{wt}"'],
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 0
    assert decide(wt / "src.py") == 1  # ...while edits stay refused


def test_switching_back_to_the_marker_branch_restores_edits(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    write_marker(wt, wt)
    _git(wt, "checkout", "-q", "-b", "chore/elsewhere")
    _git(wt, "switch", "-q", "feat/x")
    assert decide(wt / "src.py") == 0


# --- R26: quiet and stealth are fr-enabled -----------------------------------
#
# A repo whose `refs/remotes/origin/fr:settings.yaml` says `placement: quiet`, or a
# workspace whose marker records `placement: stealth`, keeps no devcontainer profile and
# no plans dir in its checkout, so the legacy two-part test called it "not fr-enabled".


def quiet_repo(
    tmp_path: Path, settings: str | None = "placement: quiet\n", origin: bool = True
) -> Path:
    """A plain repo (no profile, no plans dir) whose last fetched `origin/fr` carries
    *settings* (None: no `fr` branch at all)."""
    repo = fr_repo(tmp_path, fr_enabled=False)
    if origin:
        _git(repo, "remote", "add", "origin", "https://example.com/org/repo.git")
    if settings is not None:
        _git(repo, "checkout", "-q", "--orphan", "fr")
        _git(repo, "rm", "-rqf", ".")
        (repo / "settings.yaml").write_text(settings)
        _git(repo, "add", "settings.yaml")
        _git(repo, "commit", "-qm", "switch")
        _git(repo, "update-ref", "refs/remotes/origin/fr", "fr")
        _git(repo, "checkout", "-q", "main")
        _git(repo, "branch", "-qD", "fr")
    return repo


def enabled(repo: Path, env: dict[str, str] | None = None) -> int:
    script = f'. "{LIB}"; _fr_is_enabled "{repo.resolve()}"'
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    ).returncode


NO_FR = {"PATH": "/usr/bin:/bin"}  # no `fr` on the path: the direct checks alone decide


@pytest.mark.parametrize("env", [None, NO_FR], ids=["fr-resolves", "fr-absent"])
def test_a_quiet_repo_is_fr_enabled(tmp_path: Path, env: dict[str, str] | None) -> None:
    repo = quiet_repo(tmp_path)
    assert enabled(repo, env) == 0
    assert decide(repo / "src.py", env=env) == 1


@pytest.mark.parametrize("env", [None, NO_FR], ids=["fr-resolves", "fr-absent"])
def test_an_fr_branch_without_the_switch_is_not_fr_enabled(
    tmp_path: Path, env: dict[str, str] | None
) -> None:
    repo = quiet_repo(tmp_path, settings="placement: repo\n")
    assert enabled(repo, env) == 1
    assert decide(repo / "src.py", env=env) == 0


def test_the_switch_needs_an_origin_remote(tmp_path: Path) -> None:
    """R23: no origin is `repo`; a stale tracking ref speaks for nobody."""
    repo = quiet_repo(tmp_path, origin=False)
    assert enabled(repo, NO_FR) == 1


def test_no_fr_branch_at_all_is_not_fr_enabled(tmp_path: Path) -> None:
    repo = quiet_repo(tmp_path, settings=None)
    assert enabled(repo, NO_FR) == 1


@pytest.mark.parametrize("env", [None, NO_FR], ids=["fr-resolves", "fr-absent"])
def test_a_stealth_marker_makes_the_workspace_fr_enabled(
    tmp_path: Path, env: dict[str, str] | None
) -> None:
    repo = fr_repo(tmp_path, fr_enabled=False)
    wt = linked_worktree(repo)
    (wt / ".fr-isolation").write_text(
        f'{{"toplevel": "{wt.resolve()}", "branch": "feat/x", "mode": "worktree", '
        '"placement": "stealth", "tracking": {"ref": "x", "target": "y"}}'
    )
    assert enabled(wt, env) == 0
    # and the same marker, forged on the base clone, is fr-enabled AND not valid: a deny
    (repo / ".fr-isolation").write_text(
        f'{{"toplevel": "{repo.resolve()}", "branch": "main", "mode": "worktree", '
        '"placement": "stealth"}'
    )
    assert decide(repo / "src.py", env=env) == 1


def test_a_valid_stealth_workspace_allows_its_edits(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path, fr_enabled=False)
    wt = linked_worktree(repo)
    (wt / ".fr-isolation").write_text(
        f'{{"toplevel": "{wt.resolve()}", "branch": "feat/x", "mode": "worktree", '
        '"placement": "stealth"}'
    )
    assert decide(wt / "src.py", env=NO_FR) == 0


def test_a_garbled_fr_answer_never_turns_a_direct_yes_into_no(tmp_path: Path) -> None:
    """A failing or garbled `fr settings paths` falls back to the direct checks."""
    repo = quiet_repo(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "fr"
    stub.write_text("#!/bin/bash\necho 'FR_PLANS_DIR=\\\\\\garbled'\nexit 3\n")
    stub.chmod(0o755)
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin"}
    assert enabled(repo, env) == 0
    plain = fr_repo(tmp_path, name="plain", fr_enabled=False)
    assert enabled(plain, env) == 1


def test_fr_paths_name_a_plans_dir_the_direct_test_cannot_see(tmp_path: Path) -> None:
    """When `fr` resolves and an `origin/fr` ref exists (the cheap precondition, review
    p6-r1), FR_PLANS_DIR is the plans directory the placement names. It is asked with
    `--no-create` (review p6-r4): a hook never creates the `fr` branch or worktree."""
    repo = quiet_repo(tmp_path, settings="placement: repo\n")
    plans = tmp_path / "elsewhere" / "plans"
    plans.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "fr"
    stub.write_text(
        '#!/bin/bash\n[ "$*" = "settings paths --shell --no-create" ] || exit 9\n'
        f"echo 'FR_PLACEMENT=repo'\necho 'FR_PLANS_DIR={plans}'\n"
    )
    stub.chmod(0o755)
    assert enabled(repo, {"PATH": f"{bin_dir}:/usr/bin:/bin"}) == 0


# --- review p6-r1: no `fr` spawn on a plain repo; a bounded one otherwise -----------


def recording_fr(bin_dir: Path, body: str = "") -> Path:
    """A PATH stub `fr` that appends its argv to a log, then runs *body*."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    log = bin_dir.parent / f"{bin_dir.name}-calls.log"
    stub = bin_dir / "fr"
    stub.write_text(f'#!/bin/bash\nprintf "%s\\n" "$*" >> "{log}"\n{body}\n')
    stub.chmod(0o755)
    return log


def test_a_plain_repos_decision_spawns_no_fr(tmp_path: Path) -> None:
    log = recording_fr(tmp_path / "bin")
    env = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin"}
    plain = fr_repo(tmp_path, name="plain", fr_enabled=False)
    with_origin = fr_repo(tmp_path, name="with-origin", fr_enabled=False)
    _git(with_origin, "remote", "add", "origin", "https://example.com/org/repo.git")
    for repo in (plain, with_origin):
        assert enabled(repo, env) == 1
        assert decide(repo / "src.py", env=env) == 0
    assert not log.exists(), log.read_text()


def test_a_slow_fr_is_bounded_and_falls_back_to_the_direct_checks(tmp_path: Path) -> None:
    import time

    repo = quiet_repo(tmp_path, settings="placement: repo\n")
    log = recording_fr(tmp_path / "bin", "sleep 30")
    env = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin", "FR_PATHS_TIMEOUT": "1"}
    started = time.monotonic()
    assert enabled(repo, env) == 1
    assert time.monotonic() - started < 10
    assert log.read_text().splitlines() == ["settings paths --shell --no-create"]


# --- review p6-r2: only an absolute PATH entry's `fr` is ever run --------------------


def test_a_relative_path_entry_holding_an_fr_is_never_run(tmp_path: Path) -> None:
    """A repo-planted `bin/fr` reached through a relative PATH entry is never executed
    (the TS `resolveFr` relative-PATH test, mirrored)."""
    repo = quiet_repo(tmp_path, settings="placement: repo\n")
    planted = repo / "bin" / "fr"
    planted.parent.mkdir()
    ran = tmp_path / "planted-ran"
    planted.write_text(f'#!/bin/bash\ntouch "{ran}"\necho FR_PLACEMENT=quiet\n')
    planted.chmod(0o755)
    for relative in ("bin", "./bin", "", "."):
        entry = f"{relative}:/usr/bin:/bin"
        cwd = repo / "bin" if relative == "." else repo
        script = f'cd "{cwd}"; . "{LIB}"; _fr_is_enabled "{repo.resolve()}"'
        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            env={**os.environ, "PATH": entry},
        )
        assert result.returncode == 1, (relative, result.stderr)
    assert not ran.exists()


def test_an_absolute_fr_harness_pin_is_preferred_over_path(tmp_path: Path) -> None:
    repo = quiet_repo(tmp_path, settings="placement: repo\n")
    on_path = recording_fr(tmp_path / "path-bin", "echo FR_PLACEMENT=repo")
    pinned = recording_fr(tmp_path / "pin-bin", "echo FR_PLACEMENT=quiet")
    env = {
        "PATH": f"{tmp_path / 'path-bin'}:/usr/bin:/bin",
        "FR_HARNESS_FR": str(tmp_path / "pin-bin" / "fr"),
    }
    assert enabled(repo, env) == 0
    assert pinned.exists() and not on_path.exists()
    # an identity string (what the pin normally holds) is not a path: PATH decides
    env["FR_HARNESS_FR"] = f"7.0.0 {tmp_path}"
    assert enabled(repo, env) == 1
    assert on_path.exists()


# --- review p6-r3(b): a switch the hooks cannot positively read as repo is fr-enabled ---

NON_CANONICAL_QUIET = {
    "double-quoted": 'placement: "quiet"\n',
    "single-quoted": "placement: 'quiet'\n",
    "trailing-comment": "placement: quiet # c\n",
    "flow-mapping": "{placement: quiet}\n",
    "indented": "  placement: quiet\n",
    "quoted-key": '"placement": quiet\n',
    "crlf-canonical": "placement: quiet\r\n",
    "two-lines": "placement: repo\nplacement: quiet\n",
    "quoted-repo": 'placement: "repo"\n',
}


@pytest.mark.parametrize("text", NON_CANONICAL_QUIET.values(), ids=NON_CANONICAL_QUIET)
def test_every_spelling_of_a_placement_is_fr_enabled_without_fr(tmp_path: Path, text: str) -> None:
    repo = quiet_repo(tmp_path, settings=text)
    assert enabled(repo, NO_FR) == 0
    assert decide(repo / "src.py", env=NO_FR) == 1


def test_a_switch_naming_no_placement_is_the_repo_default(tmp_path: Path) -> None:
    repo = quiet_repo(tmp_path, settings="schema: 1\n## placement: quiet is prose here\n")
    assert enabled(repo, NO_FR) == 1


# --- review pr1431-n6: the placement question spawns no git in a plain repo ---------


def recording_git(tmp_path: Path) -> tuple[Path, Path]:
    """A git that logs its argv, then runs the real git: FR_GIT_CANDIDATES names it."""
    real = shutil.which("git")
    assert real is not None
    log = tmp_path / "git-calls.log"
    stub = tmp_path / "git-stub" / "git"
    stub.parent.mkdir()
    stub.write_text(f'#!/bin/bash\nprintf "%s\\n" "$*" >> "{log}"\nexec "{real}" "$@"\n')
    stub.chmod(0o755)
    return stub, log


def test_a_plain_repos_placement_question_spawns_no_git(tmp_path: Path) -> None:
    """The marker and the filesystem switch-ref precondition come first: a repo with no
    `refs/remotes/origin/fr` never runs `git config` or `git cat-file` for placement."""
    stub, log = recording_git(tmp_path)
    plain = fr_repo(tmp_path, name="plain", fr_enabled=False)
    _git(plain, "remote", "add", "origin", "https://example.com/org/repo.git")
    env = {**NO_FR, "FR_GIT_CANDIDATES": str(stub)}
    assert enabled(plain, env) == 1
    assert decide(plain / "src.py", env=env) == 0
    calls = log.read_text().splitlines() if log.exists() else []
    assert not [c for c in calls if "config" in c or "cat-file" in c], calls
    # and a quiet repo still asks, and is still fr-enabled
    (tmp_path / "q").mkdir()
    quiet = quiet_repo(tmp_path / "q")
    assert enabled(quiet, env) == 0
    assert any("cat-file" in c for c in log.read_text().splitlines())


# --- review pr1431-r6: the placement's own write targets ----------------------------
#
# Under quiet fr writes artifacts in the repo's `fr` worktree, and under stealth in the
# tracking clone; neither carries a marker. The gate allows them by STRUCTURE: the path
# `fr.placement.quiet.worktree_path` computes, HEAD on `fr`, the switch saying quiet; or a
# clone recorded by a valid stealth workspace's marker. Never anything else.


def quiet_fr_worktree(tmp_path: Path, home: Path, settings: str = "placement: quiet\n") -> Path:
    """A quiet repo named `prod` and its `fr` worktree where fr puts it under *home*."""
    (tmp_path / "q").mkdir(exist_ok=True)
    repo = quiet_repo(tmp_path / "q", settings=settings)
    repo = repo.rename(repo.parent / "prod")
    wt = home / ".cache" / "fr" / "worktrees" / "prod" / "fr"
    wt.parent.mkdir(parents=True)
    _git(repo, "worktree", "add", "-q", "-b", "fr", str(wt), "refs/remotes/origin/fr")
    return wt


def spec_in(root: Path) -> Path:
    return root / "features" / "feat__x" / "docs" / "superpowers" / "specs" / "x-design.md"


@pytest.mark.parametrize("env", [None, NO_FR], ids=["fr-resolves", "fr-absent"])
def test_the_repos_own_quiet_fr_worktree_is_editable(
    tmp_path: Path, env: dict[str, str] | None
) -> None:
    home = tmp_path / "home"
    wt = quiet_fr_worktree(tmp_path, home)
    assert decide(spec_in(wt), env={**(env or {}), "HOME": str(home)}) == 0


def test_the_quiet_fr_worktree_is_editable_only_while_the_repo_is_quiet(tmp_path: Path) -> None:
    """A `fr` worktree whose switch reads anything but canonical quiet is not allowed;
    a non-canonical spelling stays fr-enabled (fail closed) and so is blocked."""
    home = tmp_path / "home"
    wt = quiet_fr_worktree(tmp_path, home, settings='placement: "quiet"\n')
    assert decide(spec_in(wt), env={**NO_FR, "HOME": str(home)}) == 1


def test_an_fr_worktree_at_another_repos_path_is_refused(tmp_path: Path) -> None:
    """A worktree on branch `fr` of repo `other`, placed where `prod`'s fr worktree goes."""
    home = tmp_path / "home"
    (tmp_path / "o").mkdir()
    other = quiet_repo(tmp_path / "o")
    other = other.rename(other.parent / "other")
    wt = home / ".cache" / "fr" / "worktrees" / "prod" / "fr"
    wt.parent.mkdir(parents=True)
    _git(other, "worktree", "add", "-q", "-b", "fr", str(wt), "refs/remotes/origin/fr")
    assert decide(spec_in(wt), env={**NO_FR, "HOME": str(home)}) == 1


def test_an_fr_worktree_somewhere_else_is_refused(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (tmp_path / "q").mkdir()
    repo = quiet_repo(tmp_path / "q")
    wt = tmp_path / "elsewhere" / "fr"
    _git(repo, "worktree", "add", "-q", "-b", "fr", str(wt), "refs/remotes/origin/fr")
    assert decide(spec_in(wt), env={**NO_FR, "HOME": str(home)}) == 1


def test_a_worktree_at_the_fr_path_on_another_branch_is_refused(tmp_path: Path) -> None:
    home = tmp_path / "home"
    wt = quiet_fr_worktree(tmp_path, home)
    _git(wt, "checkout", "-q", "-b", "not-fr")
    assert decide(spec_in(wt), env={**NO_FR, "HOME": str(home)}) == 1


def test_the_quiet_repos_primary_checkout_is_still_refused(tmp_path: Path) -> None:
    home = tmp_path / "home"
    wt = quiet_fr_worktree(tmp_path, home)
    prod = tmp_path / "q" / "prod"
    assert decide(prod / "src.py", env={**NO_FR, "HOME": str(home)}) == 1
    # even when the primary checkout itself sits on branch `fr`
    _git(prod, "worktree", "remove", "--force", str(wt))
    _git(prod, "checkout", "-q", "fr")
    assert decide(prod / "x.md", env={**NO_FR, "HOME": str(home)}) == 1


def stealth_setup(tmp_path: Path, home: Path) -> tuple[Path, Path, Path]:
    """A target workspace with a valid stealth marker, and its tracking clone beside it.
    The tracking repo has a devcontainer profile, so the clone is fr-enabled on its own."""
    tracking = fr_repo(tmp_path, name="tracking")  # fr-enabled: it has a profile
    bare = tmp_path / "tracking.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(tracking), str(bare)], check=True)
    target = fr_repo(tmp_path, name="target", fr_enabled=False)
    parent = home / ".cache" / "fr" / "worktrees" / "target"
    parent.mkdir(parents=True)
    ws = parent / "feat__x"
    _git(target, "worktree", "add", "-q", str(ws), "-b", "feat/x")
    (ws / ".fr-isolation").write_text(
        f'{{"toplevel": "{ws.resolve()}", "branch": "feat/x", "mode": "worktree", '
        f'"placement": "stealth", "tracking": {{"ref": "{bare}@main", "target": "target"}}}}'
    )
    clone = parent / "stealth--local--tracking--main"
    subprocess.run(
        ["git", "clone", "-q", "--branch", "main", str(bare), str(clone)], check=True
    )
    return ws, clone, bare


@pytest.mark.parametrize("env", [None, NO_FR], ids=["fr-resolves", "fr-absent"])
def test_the_stealth_tracking_clone_is_editable(
    tmp_path: Path, env: dict[str, str] | None
) -> None:
    home = tmp_path / "home"
    _ws, clone, _bare = stealth_setup(tmp_path, home)
    assert decide(spec_in(clone / "target"), env={**(env or {}), "HOME": str(home)}) == 0


def test_a_tracking_clone_without_a_valid_stealth_workspace_is_refused(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ws, clone, _bare = stealth_setup(tmp_path, home)
    env = {**NO_FR, "HOME": str(home)}
    # the marker copied into a primary checkout is not a valid workspace
    marker = (ws / ".fr-isolation").read_text()
    (ws / ".fr-isolation").write_text(marker.replace('"placement": "stealth"', '"placement": "repo"'))
    assert decide(spec_in(clone / "target"), env=env) == 1
    (ws / ".fr-isolation").write_text(marker.replace(str(ws.resolve()), "/elsewhere.invalid"))
    assert decide(spec_in(clone / "target"), env=env) == 1


def test_a_clone_of_another_repo_or_branch_is_refused(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _ws, clone, _bare = stealth_setup(tmp_path, home)
    env = {**NO_FR, "HOME": str(home)}
    _git(clone, "checkout", "-q", "-b", "other")
    assert decide(spec_in(clone / "target"), env=env) == 1
    _git(clone, "checkout", "-q", "main")
    _git(clone, "remote", "set-url", "origin", "https://example.com/org/other.git")
    assert decide(spec_in(clone / "target"), env=env) == 1
