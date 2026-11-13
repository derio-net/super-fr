"""Placement drift and `fr placement migrate-branch`, hardened by the phase-7 review (spec
2026-11-04-repo-feature-settings R28, R24; plan 2026-11-12-placement-resolver, findings
p7-r2, r3, r5, r6, r7).

- p7-r2: migrate-branch killed after its commits and before its push completes on re-run,
  and records `repo` only once nothing is left unpushed.
- p7-r3: a deletion is never drift, and the move's own copy back into the repo is
  recognised by structure, never by a marker.
- p7-r5: only fr artifacts reach the product branch; a planted file refuses.
- p7-r6: migrate-branch never writes fr artifacts into a stealth-bound repo's branch.
- p7-r7: in CI a checkout that cannot see the refs refuses; elsewhere it warns.

Every repo is a local sandbox with a bare origin; nothing reaches a network or a forge.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.artifacts.commit import commit_paths
from fr.artifacts.paths import artifact_root
from fr.cli import app
from fr.git_policy import push as git_push
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.marker import marker_at
from fr.placement import drift, move, quiet
from fr.settings import SettingsError
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_drift import (  # noqa: F401  (_home is an autouse fixture)
    FRAG,
    FRAG_TEXT,
    _home,
    _switch_to,
    drifted,
)
from tests.unit.test_placement_quiet import QUIET

REPO_SWITCH = QUIET.replace("placement: quiet", "placement: repo")


def _origin(root: Path) -> Path:
    return Path(git(root, "remote", "get-url", "origin").strip())


def quiet_branch(tmp_path: Path, branch: str = "feat/q") -> tuple[Path, Path]:
    """(base clone, workspace): *branch* was set up under quiet, its fragment pushed on
    `fr`; then the repo went back to repo."""
    root = make_repo(tmp_path)
    _switch_to(root, QUIET)
    ws = HostWorktreeTarget(root).up(profile=None, branch=branch).worktree
    path = artifact_root(ws) / FRAG
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(FRAG_TEXT)
    assert commit_paths(ws, [path], "chore(fr): row").committed
    git_push.atomic_push(ws, quiet.worktree_path(ws), "origin", branch, code=True)
    _switch_to(root, REPO_SWITCH)
    return root, ws


# --- p7-r2: killed between the commits and the push ---------------------------------------


def test_migrate_into_quiet_killed_before_its_push_pushes_on_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.git_policy import product

    root, ws = drifted(tmp_path)
    head = git(ws, "rev-parse", "HEAD").strip()
    real = product.push_product_branch

    def killed(*a: object, **k: object) -> list[str]:
        raise KeyboardInterrupt("killed before the push")

    monkeypatch.setattr(product, "push_product_branch", killed)
    with pytest.raises(KeyboardInterrupt):
        drift.migrate_branch(ws, emit=lambda _: None)
    monkeypatch.setattr(product, "push_product_branch", real)

    lines: list[str] = []
    drift.migrate_branch(ws, emit=lines.append)

    origin = _origin(root)
    assert git(origin, "rev-parse", "feat/live").strip() == git(ws, "rev-parse", "HEAD").strip()
    assert f"features/feat__live/{FRAG}" in git(origin, "ls-tree", "-r", "--name-only", "fr")
    assert git(ws, "rev-list", "--count", f"{head}..HEAD").strip() == "1"
    assert "earlier run" in "\n".join(lines)


@pytest.mark.parametrize("killed_at", ["push_product_branch", "atomic_push"])
def test_migrate_into_repo_killed_before_its_push_pushes_on_rerun_and_records_last(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, killed_at: str
) -> None:
    from fr.git_policy import product

    module = product if killed_at == "push_product_branch" else git_push
    root, ws = quiet_branch(tmp_path)
    real = getattr(module, killed_at)

    def killed(*a: object, **k: object) -> object:
        raise KeyboardInterrupt(f"killed in {killed_at}")

    monkeypatch.setattr(module, killed_at, killed)
    with pytest.raises(KeyboardInterrupt):
        drift.migrate_branch(ws, emit=lambda _: None)
    assert (marker_at(ws) or {}).get("placement") == "quiet"  # not recorded while unpushed
    monkeypatch.setattr(module, killed_at, real)

    drift.migrate_branch(ws, emit=lambda _: None)

    origin = _origin(root)
    assert FRAG in git(origin, "ls-tree", "-r", "--name-only", "feat/q")
    assert "features/feat__q/" not in git(origin, "ls-tree", "-r", "--name-only", "fr")
    assert git(origin, "rev-parse", "feat/q").strip() == git(ws, "rev-parse", "HEAD").strip()
    assert (marker_at(ws) or {}).get("placement") == "repo"
    assert drift.detect(ws) is None


# --- p7-r3: deletions, and the move's own branches -----------------------------------------


def test_a_deletion_is_never_drift(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / FRAG).parent.mkdir(parents=True, exist_ok=True)
    (root / FRAG).write_text(FRAG_TEXT)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "chore(fr): row")
    git(root, "push", "-q", "origin", "main")
    git(root, "fetch", "-q", "origin")
    _switch_to(root, QUIET)
    git(root, "checkout", "-q", "-b", "chore/drop")
    git(root, "rm", "-q", "--", FRAG)
    git(root, "commit", "-qm", "chore: drop the row")
    assert drift.branch_drift(root) is None


def _validate_in_ci(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, str]:
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    result = CliRunner().invoke(app, ["validate", "artifacts"], env={"CI": "true"})
    return result.exit_code, result.output


def test_the_moves_own_branches_pass_validate_in_ci(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit import test_placement_move as tm

    monkeypatch.setenv("GIT_COMMITTER_DATE", f"{tm.EPOCH} +0000")
    monkeypatch.setenv("GIT_AUTHOR_DATE", f"{tm.EPOCH} +0000")
    root = tm.repo_with_artifacts(tmp_path)
    tm._run(root, "quiet")
    git(root, "fetch", "-q", "origin")
    git(root, "switch", "-q", "chore/fr-placement-move-to-quiet")
    assert drift.branch_drift(root) is None  # deletion only
    assert _validate_in_ci(root, monkeypatch)[0] == 0

    git(root, "switch", "-q", "main")
    tm._land(root, "chore/fr-placement-move-to-quiet")
    tm._run(root, "repo")  # paused: the copy back waits for its PR
    git(root, "fetch", "-q", "origin")
    git(root, "switch", "-q", move.COPY_BRANCH)
    assert drift.branch_drift(root) is None  # exactly fr's merged features
    code, out = _validate_in_ci(root, monkeypatch)
    assert code == 0, out

    # The same branch carrying one fr file more than `fr` holds as merged is drift.
    extra = f"{Path(FRAG).parent}/2026-03-01-extra.yaml"
    (root / extra).write_text(FRAG_TEXT.replace("2026-02-01-live", "2026-03-01-extra"))
    git(root, "add", "-A")
    git(root, "commit", "-qm", "chore: smuggle")
    found = drift.branch_drift(root)
    assert found is not None and extra in found.files


# --- p7-r5: only fr artifacts reach the product branch -----------------------------------


def test_migrate_branch_refuses_a_planted_workflow_and_writes_nothing(tmp_path: Path) -> None:
    root, ws = quiet_branch(tmp_path)
    frwt = quiet.worktree_path(ws)
    planted = frwt / "features" / "feat__q" / ".github" / "workflows" / "x.yml"
    planted.parent.mkdir(parents=True)
    planted.write_text("on: push\n")
    git(frwt, "add", "-A")
    git(frwt, "commit", "-qm", "plant")
    head = git(ws, "rev-parse", "HEAD").strip()

    with pytest.raises(SettingsError, match=r"\.github/workflows/x\.yml"):
        drift.migrate_branch(ws, emit=lambda _: None)

    assert not (ws / ".github").exists()
    assert not (ws / FRAG).exists()
    assert git(ws, "rev-parse", "HEAD").strip() == head
    assert (frwt / "features" / "feat__q" / FRAG).is_file()  # nothing moved off `fr`


# --- p7-r6: never into a stealth-bound repo's branch ---------------------------------------


def test_migrate_into_repo_refuses_while_a_move_to_stealth_is_in_progress(
    tmp_path: Path,
) -> None:
    _, ws = quiet_branch(tmp_path)
    move.state_path(ws).write_text(json.dumps({"to": "stealth", "done": ["copy"]}))
    head = git(ws, "rev-parse", "HEAD").strip()
    with pytest.raises(SettingsError, match="stealth"):
        drift.migrate_branch(ws, emit=lambda _: None)
    assert not (ws / FRAG).exists()
    assert git(ws, "rev-parse", "HEAD").strip() == head


# --- p7-r7: a checkout that cannot see the refs --------------------------------------------


def _shallow(tmp_path: Path) -> Path:
    root, _ = drifted(tmp_path)
    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{_origin(root)}", str(clone)],
        check=True, capture_output=True,
    )  # fmt: skip
    return clone


def test_in_ci_a_shallow_checkout_refuses_naming_fetch_depth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = _shallow(tmp_path)
    monkeypatch.setenv("CI", "true")
    with pytest.raises(drift.DriftError, match="fetch-depth: 0"):
        drift.branch_drift(clone)
    monkeypatch.delenv("CI")
    code, out = _validate_in_ci(clone, monkeypatch)
    assert code == 2 and "fetch-depth: 0" in out and "shallow" in out


def test_in_ci_a_checkout_without_the_default_ref_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path)
    for ref in git(root, "for-each-ref", "--format=%(refname)", "refs/remotes/").split():
        git(root, "update-ref", "-d", ref)
    monkeypatch.setenv("CI", "true")
    with pytest.raises(drift.DriftError, match="fetch-depth: 0"):
        drift.branch_drift(root)


def test_outside_ci_a_shallow_checkout_warns_and_goes_on(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clone = _shallow(tmp_path)
    assert drift.branch_drift(clone) is None
    err = capsys.readouterr().err
    assert "warning: placement drift cannot be checked" in err and "fetch-depth: 0" in err


def test_a_repo_with_no_remote_has_nothing_to_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    plain = tmp_path / "plain"
    git(tmp_path, "init", "-q", "-b", "main", str(plain))
    monkeypatch.setenv("CI", "true")
    assert drift.branch_drift(plain) is None
    assert capsys.readouterr().err == ""
