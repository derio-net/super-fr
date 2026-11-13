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
    """When `fr` resolves, FR_PLANS_DIR is the plans directory the placement names."""
    repo = fr_repo(tmp_path, fr_enabled=False)
    plans = tmp_path / "elsewhere" / "plans"
    plans.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "fr"
    stub.write_text(f"#!/bin/bash\necho 'FR_PLACEMENT=repo'\necho 'FR_PLANS_DIR={plans}'\n")
    stub.chmod(0o755)
    assert enabled(repo, {"PATH": f"{bin_dir}:/usr/bin:/bin"}) == 0
