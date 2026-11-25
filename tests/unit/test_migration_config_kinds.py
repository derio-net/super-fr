"""The moved configuration kinds and their migration (spec 2026-11-19-event-driven-a-la-carte
S1 §D, R8 to R12; plan 2026-11-24-s1-configuration-homes P4.T1.S3, P4.T2.S1).

Under `repo` each file moves with a rename in the product checkout, in one
`chore(fr): migrate` commit. Under quiet and stealth the destination is committed and
pushed on the configuration branch first, and the product file leaves in the product's
migrate commit; a refused push removes nothing. Origins are LOCAL bare repos.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.artifacts import ARTIFACT_KINDS, MIGRATIONS, is_stale, run_migrations
from fr.artifacts.commit import commit_migration
from fr.config import change

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import QUIET, push_fr_branch

REPO = Path(__file__).resolve().parents[2]

WORKFLOW = (REPO / "plugins/super-fr/workflows/fr-goal-light.yaml").read_text()
STRATEGY = (REPO / "plugins/super-fr/verifications/candidate.yaml").read_text()
PROFILES_V2 = (
    "schema_version: 2\nprofiles:\n  dev:\n    purpose: dev\n    secrets: []\ndefault: dev\n"
    "forge:\n  type: github\nci:\n  type: github-actions\ntracking:\n  type: github\n"
)

# kind -> (old path, new path below the space root, text)
FILES: dict[str, tuple[str, str, str]] = {
    "workflow-config": (
        "docs/superpowers/workflows/mine.yaml",
        ".fr/workflows/mine.yaml",
        WORKFLOW,
    ),
    "verification-config": (
        "docs/superpowers/verifications/mine.yaml",
        ".fr/verifications/mine.yaml",
        STRATEGY,
    ),
    "models-config": ("docs/superpowers/models.yaml", ".fr/models.yaml", "opencode:\n  hard: m\n"),
    "trackers-config": ("docs/superpowers/trackers.yaml", ".fr/trackers.yaml", "{}\n"),
    "plan-config": ("docs/superpowers/plan-config.yaml", ".fr/plan-config.yaml", "plan: {}\n"),
}


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def prs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    opened: list[tuple[str, str, str]] = []

    def fake(remote: str, head: str, base: str, title: str, body: str) -> str:
        opened.append((remote, head, base))
        return f"https://example.com/pr/{len(opened)}"

    monkeypatch.setattr(change, "open_pr", fake)
    return opened


def _put(root: Path, rel: str, text: str, *, commit: bool = True) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if commit:
        git(root, "add", "-A")
        git(root, "commit", "-qm", f"add {rel}")
    return path


def _feature(root: Path) -> None:
    git(root, "checkout", "-q", "-b", "feat/move")


def _migrate(root: Path):
    report = run_migrations(root, dry_run=False)
    assert report.ok, report.failed
    outcome = commit_migration(root, report, fr_version="9.9.9")
    return report, outcome


# --- repo: a rename in one checkout --------------------------------------------------


@pytest.mark.parametrize("kind", sorted(FILES))
def test_under_repo_each_kind_is_renamed_in_one_migrate_commit(tmp_path: Path, kind: str) -> None:
    old, new, text = FILES[kind]
    root = make_repo(tmp_path)
    _feature(root)
    _put(root, old, text)
    assert ARTIFACT_KINDS[kind].read_version(root / old) == 1

    _report, outcome = _migrate(root)
    assert outcome.committed, outcome.reason
    assert not (root / old).exists() and (root / new).read_text() == text
    assert git(root, "log", "-1", "--format=%s").startswith("chore(fr): migrate 1 artifact")
    status = git(root, "show", "--name-status", "-M", "--format=", "HEAD").split()
    assert status[0].startswith("R") and status[1:] == [old, new]
    assert not is_stale(root)


def test_under_repo_profiles_moves_to_fr_profiles_yaml_at_version_3(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _feature(root)
    _put(root, ".devcontainer/fr-profiles.yaml", PROFILES_V2)
    report, outcome = _migrate(root)
    assert outcome.committed, outcome.reason
    assert [(a.from_version, a.to_version) for a in report.applied] == [(2, 3)]
    moved = (root / ".fr/profiles.yaml").read_text()
    assert moved == PROFILES_V2.replace("schema_version: 2", "schema_version: 3")
    assert not (root / ".devcontainer/fr-profiles.yaml").exists()
    assert git(root, "show", "--name-status", "-M", "--format=", "HEAD").startswith("R")
    assert ARTIFACT_KINDS["profiles"].validate(root / ".fr/profiles.yaml") == []


def test_a_version_1_profiles_file_goes_1_2_3_hop_by_hop(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _feature(root)
    _put(
        root,
        ".devcontainer/fr-profiles.yaml",
        "profiles:\n  dev:\n    purpose: dev\n    secrets: []\nbackend: github\n",
    )
    report, _ = _migrate(root)
    assert [(a.from_version, a.to_version) for a in report.applied] == [(1, 2), (2, 3)]
    assert ARTIFACT_KINDS["profiles"].read_version(root / ".fr/profiles.yaml") == 3


def test_the_profiles_chain_reaches_three_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("profiles", 1)
    assert [(m.from_version, m.to_version) for m in chain] == [(1, 2), (2, 3)]
    assert [m.relocates for m in chain] == [False, True]
    assert ARTIFACT_KINDS["profiles"].current_version == 3


def test_the_profiles_crash_window_is_finished_in_place(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _feature(root)
    _put(root, ".fr/profiles.yaml", PROFILES_V2)  # moved, stamp not landed
    report, outcome = _migrate(root)
    assert outcome.committed and [a.moved_to for a in report.applied] == [None]
    assert "schema_version: 3" in (root / ".fr/profiles.yaml").read_text()


def test_profiles_at_both_paths_is_refused_naming_both(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _put(root, ".devcontainer/fr-profiles.yaml", PROFILES_V2)
    _put(root, ".fr/profiles.yaml", PROFILES_V2.replace("dev\n", "other\n", 1))
    report = run_migrations(root, dry_run=False)
    assert report.failed and all("R12" in f.error for f in report.failed)
    assert (root / ".devcontainer/fr-profiles.yaml").exists()


def test_a_tracked_allowlist_is_git_moved_and_an_untracked_one_renamed_without_a_commit(
    tmp_path: Path,
) -> None:
    root = make_repo(tmp_path)
    _feature(root)
    _put(root, ".fr-isolation-allow", "data/**\n")
    _report, outcome = _migrate(root)
    assert outcome.committed
    assert git(root, "show", "--name-status", "-M", "--format=", "HEAD").startswith("R")

    (tmp_path / "b").mkdir()
    other = make_repo(tmp_path / "b")
    _feature(other)
    _put(other, ".fr-isolation-allow", "data/**\n", commit=False)
    head = git(other, "rev-parse", "HEAD")
    _report, outcome = _migrate(other)
    assert not outcome.committed and git(other, "rev-parse", "HEAD") == head
    assert (other / ".fr/isolation-allow").read_text() == "data/**\n"
    assert not (other / ".fr-isolation-allow").exists()


def test_a_file_at_both_its_old_and_new_path_is_refused_and_the_rest_migrate(
    tmp_path: Path,
) -> None:
    root = make_repo(tmp_path)
    _feature(root)
    _put(root, "docs/superpowers/models.yaml", "opencode:\n  hard: a\n")
    _put(root, ".fr/models.yaml", "opencode:\n  hard: b\n")
    _put(root, "docs/superpowers/trackers.yaml", "{}\n")
    report = run_migrations(root, dry_run=False)
    (failure,) = report.failed
    assert failure.kind == "models-config" and "R12" in failure.error
    assert "docs/superpowers/models.yaml" in failure.error and ".fr/models.yaml" in failure.error
    assert (root / ".fr/trackers.yaml").exists()


# --- quiet: fr-config first, then the product ----------------------------------------


def _quiet(tmp_path: Path) -> Path:
    """A product clone whose switch is only the old root settings.yaml on `fr`."""
    root = make_repo(tmp_path)
    push_fr_branch(root, QUIET)
    git(root, "fetch", "-q", "origin", "+refs/heads/fr:refs/remotes/origin/fr")
    _feature(root)
    return root


def _origin(tmp_path: Path) -> Path:
    return tmp_path / "origin.git"


@pytest.mark.parametrize("kind", sorted(FILES))
def test_under_quiet_fr_config_is_created_first_and_the_product_file_leaves_after(
    tmp_path: Path, kind: str
) -> None:
    old, new, text = FILES[kind]
    root = _quiet(tmp_path)
    _put(root, old, text)

    _report, outcome = _migrate(root)
    origin = _origin(tmp_path)
    assert git(origin, "show", f"fr-config:{new}") == text
    assert git(origin, "show", "fr-config:.fr/settings.yaml") == QUIET
    assert git(origin, "show", "fr:settings.yaml") == QUIET  # R6's legacy copy stays
    assert outcome.committed, outcome.reason
    assert git(root, "show", "--name-status", "--format=", "HEAD").split() == ["D", old]
    assert not (root / old).exists()


def test_under_quiet_one_creation_carries_every_moved_file(tmp_path: Path) -> None:
    root = _quiet(tmp_path)
    for kind in ("models-config", "trackers-config"):
        old, _new, text = FILES[kind]
        _put(root, old, text)
    _put(root, ".fr/ci.yaml", "tests: ci\n")
    _put(root, ".fr/isolation-allow", "data/**\n")
    report, outcome = _migrate(root)
    assert outcome.committed, outcome.reason
    origin = _origin(tmp_path)
    assert git(origin, "rev-list", "--count", "fr-config").strip() == "1"
    tree = sorted(git(origin, "ls-tree", "-r", "--name-only", "fr-config").split())
    assert tree == [".fr/ci.yaml", ".fr/models.yaml", ".fr/settings.yaml", ".fr/trackers.yaml"]
    assert (root / ".fr/isolation-allow").exists()  # R8: stays in the product
    assert {a.kind for a in report.applied} == {"models-config", "trackers-config", "quiet-config"}


def test_under_quiet_a_refused_push_removes_nothing(tmp_path: Path) -> None:
    old, _new, text = FILES["models-config"]
    root = _quiet(tmp_path)
    _put(root, old, text)
    hook = _origin(tmp_path) / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'fr-config is protected' >&2\nexit 1\n")
    hook.chmod(0o755)
    report = run_migrations(root, dry_run=False)
    failure = next(f for f in report.failed if f.kind == "models-config")
    assert "refused" in failure.error
    assert (root / old).read_text() == text
    assert git(root, "status", "--porcelain") == ""
    assert (
        subprocess.run(
            ["git", "-C", str(_origin(tmp_path)), "rev-parse", "--verify", "-q", "fr-config"],
            capture_output=True,
            check=False,
        ).returncode
        != 0
    )


def test_under_quiet_an_existing_fr_config_without_the_file_gets_a_pull_request(
    tmp_path: Path, prs: list[tuple[str, str, str]]
) -> None:
    old, new, text = FILES["models-config"]
    root = _quiet(tmp_path)
    from fr.config.migrate import ensure_space

    assert ensure_space(root)  # fr settings init / an earlier migration made fr-config
    _put(root, old, text)
    report = run_migrations(root, dry_run=False)
    (failure,) = report.failed
    assert "https://example.com/pr/1" in failure.error and (root / old).read_text() == text
    (_remote, head, base) = prs[0]
    assert base == "fr-config" and head.startswith("fr-config-change/")
    assert git(_origin(tmp_path), "show", f"{head}:{new}") == text

    # the forge merges it; the next migration removes the product file
    origin = _origin(tmp_path)
    git(origin, "update-ref", "refs/heads/fr-config", git(origin, "rev-parse", head).strip())
    _report, outcome = _migrate(root)
    assert outcome.committed and not (root / old).exists()


def test_under_quiet_differing_bytes_on_fr_config_is_r12(tmp_path: Path) -> None:
    root = _quiet(tmp_path)
    _put(root, "docs/superpowers/models.yaml", "opencode:\n  hard: a\n")
    from fr.config.migrate import ensure_space

    ensure_space(root)  # carries models.yaml as it is now
    _put(root, "docs/superpowers/models.yaml", "opencode:\n  hard: b\n")
    report = run_migrations(root, dry_run=False)
    (failure,) = report.failed
    assert "R12" in failure.error and (root / "docs/superpowers/models.yaml").exists()


def test_under_quiet_settings_location_creates_fr_config_from_the_old_switch(
    tmp_path: Path,
) -> None:
    root = _quiet(tmp_path)
    from fr.placement.quiet import ensure_worktree

    ensure_worktree(root)  # the `fr` worktree, holding the old switch
    assert is_stale(root)
    report = run_migrations(root, dry_run=False)
    assert report.ok, report.failed
    assert [a.kind for a in report.applied] == ["settings-location"]
    assert git(_origin(tmp_path), "show", "fr-config:.fr/settings.yaml") == QUIET
    assert not is_stale(root)
    assert commit_migration(root, report, fr_version="9.9.9").committed is False


def test_an_fr_config_holding_identical_settings_reads_as_migrated(tmp_path: Path) -> None:
    root = _quiet(tmp_path)
    from fr.config.migrate import ensure_space
    from fr.placement.quiet import ensure_worktree

    ensure_worktree(root)
    ensure_space(root)  # `fr settings init --quiet` ran first
    assert not is_stale(root)


def test_the_cli_entry_veto_holds_a_product_file_being_edited(tmp_path: Path) -> None:
    from fr.artifacts.commit import uncommitted_veto

    old, _new, text = FILES["models-config"]
    root = _quiet(tmp_path)
    _put(root, old, text)
    (root / old).write_text(text + "# editing\n")
    report = run_migrations(root, dry_run=False, veto=uncommitted_veto(root))
    held = next(f for f in report.failed if f.kind == "models-config")
    assert "held back" in held.summary
    assert (root / old).read_text() == text + "# editing\n"
    # the uncommitted edit never rides along in the configuration branch's creation
    tree = git(_origin(tmp_path), "ls-tree", "-r", "--name-only", "fr-config").split()
    assert ".fr/models.yaml" not in tree


# --- stealth: <branch>-config on the tracking repo -----------------------------------


def test_under_stealth_the_file_lands_on_the_tracking_repos_config_branch_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.isolation.hostworktree import HostWorktreeTarget
    from fr.placement import stealth

    from tests.unit.stealth_repo import make_tracking

    stealth.reset_caches()
    target = make_repo(tmp_path)
    track = make_tracking(tmp_path)
    clone = tmp_path / "push-clone"
    git(tmp_path, "clone", "-q", str(track), str(clone))
    git(clone, "config", "user.name", "t")
    git(clone, "config", "user.email", "t@example.invalid")
    (clone / "local--origin").mkdir()
    (clone / "local--origin/settings.yaml").write_text("placement: stealth\n")
    git(clone, "add", "-A")
    git(clone, "commit", "-qm", "target settings")
    git(clone, "push", "-q", "origin", "main")
    old, new, text = FILES["models-config"]
    _put(target, old, text)
    git(target, "push", "-q", "origin", "main")
    ref = stealth.parse_ref(f"{track}@main")
    state = HostWorktreeTarget(target).up(profile=None, branch="feat/s", stealth=ref)
    work = Path(state.worktree)
    assert (work / old).exists()

    report = run_migrations(work, dry_run=False)
    assert report.ok, report.failed
    assert git(track, "show", f"main-config:local--origin/{new}") == text
    assert git(track, "show", "main-config:local--origin/.fr/settings.yaml") == (
        "placement: stealth\n"
    )
    assert not (work / old).exists()
    stealth.reset_caches()


# --- security review: what a cross-space hop may push ---------------------------------


@pytest.mark.parametrize("kind", ["models-config", "profiles"])
def test_under_quiet_a_symlinked_old_path_is_refused_and_nothing_is_pushed(
    tmp_path: Path, kind: str
) -> None:
    """A symlink at an old path (to ~/.ssh/..., say) must never be read and pushed onto
    the configuration branch: it is refused, naming it (review p4-sec-symlink)."""
    old = FILES[kind][0] if kind in FILES else ".devcontainer/fr-profiles.yaml"
    root = _quiet(tmp_path)
    secret = tmp_path / "secret"
    secret.write_text("PRIVATE KEY\n")
    (root / old).parent.mkdir(parents=True, exist_ok=True)
    (root / old).symlink_to(secret)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "a symlink")
    report = run_migrations(root, dry_run=False)
    failure = next(f for f in report.failed if f.kind == kind)
    assert "symlink" in failure.error and old in failure.error
    assert (root / old).is_symlink()
    probe = subprocess.run(
        ["git", "-C", str(_origin(tmp_path)), "grep", "-q", "PRIVATE KEY", "fr-config"],
        capture_output=True,
        check=False,
    )
    assert probe.returncode != 0  # no fr-config, or one without the secret


def test_a_symlink_among_the_pending_files_refuses_the_creation(tmp_path: Path) -> None:
    root = _quiet(tmp_path)
    _put(root, "docs/superpowers/models.yaml", "opencode:\n  hard: m\n")
    secret = tmp_path / "secret"
    secret.write_text("PRIVATE KEY\n")
    (root / ".fr").mkdir(exist_ok=True)
    (root / ".fr/ci.yaml").symlink_to(secret)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "a symlink")
    report = run_migrations(root, dry_run=False)
    assert any("symlink" in f.error and ".fr/ci.yaml" in f.error for f in report.failed)
    assert (root / "docs/superpowers/models.yaml").exists()
    assert (
        subprocess.run(
            ["git", "-C", str(_origin(tmp_path)), "rev-parse", "--verify", "-q", "fr-config"],
            capture_output=True,
            check=False,
        ).returncode
        != 0
    )


def test_a_cross_space_hop_pushes_the_committed_bytes_and_refuses_a_dirty_file(
    tmp_path: Path,
) -> None:
    from fr.config.migrate import move_across

    root = _quiet(tmp_path)
    src = _put(root, "docs/superpowers/models.yaml", "opencode:\n  hard: m\n")
    src.write_text("opencode:\n  hard: edited\n")
    from fr.settings import SettingsError

    with pytest.raises(SettingsError, match="uncommitted"):
        move_across(root, src, "models.yaml")
    assert src.read_text() == "opencode:\n  hard: edited\n"
