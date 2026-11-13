"""Every product-branch push goes through one function, and stealth's guard holds on all
of them (review pr1431-r1).

The reviewer's reproduction: in a stealth workspace an agent commits a spec on the
product branch with `git add -A`; `fr push` refused naming `fr placement migrate-branch`,
which then committed a removal ("chore(placement): move fr artifacts off ...") and pushed
both commits around the stealth scan, so the target's history held the spec and a
subject naming fr. Now `fr push` names the rewrite instead, and migrate-branch under
stealth only copies to the tracking repo: it never commits on, or pushes, the product
branch.

Target and tracking repos are LOCAL bare repos; nothing reaches a network or a forge.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.git_policy.product import push_product_branch
from fr.git_policy.push import PushRefusedError
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.placement import stealth
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.stealth_repo import make_tracking, stealth_home, tracked_files

__all__ = ["stealth_home"]

SPEC = "docs/superpowers/specs/2026-01-01-y-design.md"
FR_PATH = (
    "docs/superpowers/", "docs/acceptance/", ".fr/", ".fr-isolation", ".claude/agents/fr-",
    "scripts/validate-plans.sh", ".devcontainer/fr-profiles.yaml",
)  # fmt: skip
NAMING = ("chore(fr)", "chore(placement)", "placement stealth", "placement quiet", "fr push",
          "fr placement", "Fr-Commit", "super-fr")  # fmt: skip


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")


def _ws(tmp_path: Path) -> tuple[Path, Path, Path]:
    """(stealth workspace on feat/y, target bare origin, tracking bare repo)."""
    target = make_repo(tmp_path)
    track = make_tracking(tmp_path)
    ws = (
        HostWorktreeTarget(target)
        .up(profile=None, branch="feat/y", stealth=stealth.parse_ref(f"{track}@main"))
        .worktree
    )
    return ws, tmp_path / "origin.git", track


def _fr(ws: Path, *argv: str):  # type: ignore[no-untyped-def]
    return CliRunner().invoke(app, list(argv), env={**os.environ, "FR_REPO_ROOT": str(ws)})


def _commit_spec(ws: Path) -> None:
    (ws / SPEC).parent.mkdir(parents=True, exist_ok=True)
    (ws / SPEC).write_text("# y\n")
    (ws / "code.txt").write_text("code\n")
    git(ws, "add", "-A")
    git(ws, "commit", "-qm", "feat: y")


def _target_is_clean(origin: Path) -> None:
    """No fr path anywhere in the target's history, and no commit message naming fr."""
    for ref in git(origin, "for-each-ref", "--format=%(refname)").split():
        names = git(origin, "log", "--format=", "--name-only", ref).split()
        assert not [n for n in names if n.startswith(FR_PATH)], (ref, names)
        bodies = git(origin, "log", "--format=%B", ref)
        assert not [w for w in NAMING if w in bodies], (ref, bodies)


def test_the_reviewers_reproduction_leaks_nothing_to_the_target(tmp_path: Path) -> None:
    ws, origin, track = _ws(tmp_path)
    _commit_spec(ws)
    head = git(ws, "rev-parse", "HEAD").strip()

    pushed = _fr(ws, "push")
    assert pushed.exit_code == 2
    assert "migrate-branch" not in pushed.output
    migrated = _fr(ws, "placement", "migrate-branch")
    assert migrated.exit_code == 2, migrated.output
    text = " ".join(migrated.output.split())
    assert head[:12] in text and "feat: y" in text
    assert "git filter-branch" in text

    assert git(ws, "rev-parse", "HEAD").strip() == head  # nothing committed on the branch
    assert git(origin, "for-each-ref", "refs/heads/feat").strip() == ""  # nothing pushed
    assert any(p.endswith(f"features/feat__y/{SPEC}") for p in tracked_files(track))
    _target_is_clean(origin)


def test_rewriting_as_told_then_fr_push_lands_only_the_code(tmp_path: Path) -> None:
    ws, origin, _track = _ws(tmp_path)
    _commit_spec(ws)
    migrated = _fr(ws, "placement", "migrate-branch")
    assert migrated.exit_code == 2
    line = next(x for x in migrated.output.splitlines() if "git filter-branch" in x)
    command = line[line.index("FILTER_BRANCH_SQUELCH_WARNING") :].strip().rstrip("`")
    subprocess.run(["bash", "-c", command], cwd=ws, check=True, capture_output=True)
    pushed = _fr(ws, "push")
    assert pushed.exit_code == 0, pushed.output
    assert git(origin, "show", "feat/y:code.txt") == "code\n"
    _target_is_clean(origin)


def test_fr_paths_already_pushed_are_named_as_already_on_the_target(tmp_path: Path) -> None:
    ws, origin, _track = _ws(tmp_path)
    _commit_spec(ws)
    git(ws, "push", "-q", "origin", "feat/y")  # a leak that happened before this guard
    head = git(ws, "rev-parse", "HEAD").strip()
    migrated = _fr(ws, "placement", "migrate-branch")
    assert migrated.exit_code == 2
    assert "already reached the target" in " ".join(migrated.output.split())
    assert git(ws, "rev-parse", "HEAD").strip() == head
    assert git(origin, "rev-parse", "feat/y").strip() == head


def test_the_one_pusher_refuses_a_commit_naming_fr_under_stealth(tmp_path: Path) -> None:
    ws, origin, _track = _ws(tmp_path)
    (ws / "code.txt").write_text("x\n")
    git(ws, "add", "code.txt")
    git(ws, "commit", "-qm", "chore(fr): record something")
    with pytest.raises(PushRefusedError, match=r"chore\(fr\)"):
        push_product_branch(ws, "origin", "feat/y")
    assert git(origin, "for-each-ref", "refs/heads/feat").strip() == ""


def test_the_one_pusher_refuses_an_fr_path_on_a_side_branch(tmp_path: Path) -> None:
    ws, origin, _track = _ws(tmp_path)
    git(ws, "switch", "-q", "-c", "side")
    _commit_spec(ws)
    git(ws, "switch", "-q", "feat/y")
    with pytest.raises(PushRefusedError, match="fr file"):
        push_product_branch(ws, "origin", "side", rev="refs/heads/side")
    assert git(origin, "for-each-ref", "refs/heads/side").strip() == ""


def test_a_plain_code_push_passes(tmp_path: Path) -> None:
    ws, origin, _track = _ws(tmp_path)
    (ws / "code.txt").write_text("x\n")
    git(ws, "add", "code.txt")
    git(ws, "commit", "-qm", "feat: code")
    assert push_product_branch(ws, "origin", "feat/y") == ["feat/y"]
    assert git(origin, "rev-parse", "feat/y").strip() == git(ws, "rev-parse", "HEAD").strip()
    _target_is_clean(origin)


def test_the_rewrite_advice_quotes_every_path() -> None:
    from fr.placement.drift import rewrite_command

    paths = ["docs/a b.md", "docs/c'd.md"]
    tokens = shlex.split(rewrite_command(paths, "abc123"))
    inner = tokens[tokens.index("--index-filter") + 1]
    assert shlex.split(inner)[-2:] == paths
    assert tokens[-1] == "abc123..HEAD"
