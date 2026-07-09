"""fr init scaffold — mechanical devcontainer-profile writer."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from fr.cli import app
from fr.isolation.scaffold import (
    BASE_IMAGE,
    GH_FEATURE,
    HOST_CLI_FEATURE,
    HOST_CLI_POST_CREATE,
    KNOWN_TOOL_FEATURES,
    scaffold_profile,
)
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    r = tmp_path / "myrepo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    # A real repo has a configured identity; scaffold now commits the profile.
    subprocess.run(["git", "-C", str(r), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.name", "t"], check=True)
    return r


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _initial_commit(repo: Path) -> None:
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "seed")


def _log_subjects(repo: Path) -> list[str]:
    out = _git(repo, "log", "--format=%s").stdout
    return out.splitlines()


def _tracked(repo: Path) -> list[str]:
    return _git(repo, "ls-files").stdout.splitlines()


def scaffold(repo: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "init",
            "scaffold",
            "--repo",
            str(repo),
            "--profile",
            "dev",
            "--purpose",
            "day-to-day development",
            *extra,
        ],
    )


# --- super-fr#299 part 2: scaffold commits the profile by default -----------


def test_scaffold_commits_profile_by_default(repo: Path) -> None:
    _initial_commit(repo)
    res = scaffold(repo)
    assert res.exit_code == 0, res.output
    assert "chore(fr): scaffold dev devcontainer profile" in _log_subjects(repo)
    tracked = _tracked(repo)
    assert ".devcontainer/dev/devcontainer.json" in tracked
    assert ".devcontainer/fr-profiles.yaml" in tracked


def test_scaffold_commit_is_scoped(repo: Path) -> None:
    _initial_commit(repo)
    (repo / "UNRELATED.txt").write_text("x\n")
    _git(repo, "add", "UNRELATED.txt")  # staged, unrelated to the profile
    res = scaffold(repo)
    assert res.exit_code == 0, res.output
    head_files = _git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert ".devcontainer/dev/devcontainer.json" in head_files  # profile committed
    assert "UNRELATED.txt" not in head_files  # the operator's change is NOT swept in
    # and it remains staged, untouched by scaffold
    assert "UNRELATED.txt" in _git(repo, "diff", "--cached", "--name-only").stdout


def test_scaffold_plan_repo_installs_validator_wrapper(repo: Path) -> None:
    _initial_commit(repo)
    plans = repo / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / ".gitkeep").write_text("")
    _git(repo, "add", "docs/superpowers/plans/.gitkeep")
    _git(repo, "commit", "-qm", "add plans dir")

    res = scaffold(repo)

    assert res.exit_code == 0, res.output
    wrapper = repo / "scripts" / "validate-plans.sh"
    assert wrapper.exists()
    assert wrapper.stat().st_mode & 0o111
    assert "super-fr plugin" in wrapper.read_text()
    head_files = _git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert "scripts/validate-plans.sh" in head_files
    assert "scripts/validate-plans.sh" in _tracked(repo)


def test_scaffold_without_plans_does_not_install_validator_wrapper(repo: Path) -> None:
    _initial_commit(repo)

    res = scaffold(repo)

    assert res.exit_code == 0, res.output
    assert not (repo / "scripts" / "validate-plans.sh").exists()


def test_scaffold_plan_repo_refuses_custom_validator(repo: Path) -> None:
    _initial_commit(repo)
    (repo / "docs" / "superpowers" / "plans").mkdir(parents=True)
    scripts = repo / "scripts"
    scripts.mkdir()
    custom = scripts / "validate-plans.sh"
    custom.write_text("#!/usr/bin/env bash\nexit 0\n")
    custom.chmod(0o755)

    res = scaffold(repo)

    assert res.exit_code == 2
    assert "already exists" in res.output
    assert "not a super-fr wrapper" in res.output
    assert custom.read_text() == "#!/usr/bin/env bash\nexit 0\n"


def test_scaffold_plan_repo_refuses_custom_validator_that_mentions_super_fr(
    repo: Path,
) -> None:
    _initial_commit(repo)
    (repo / "docs" / "superpowers" / "plans").mkdir(parents=True)
    scripts = repo / "scripts"
    scripts.mkdir()
    custom = scripts / "validate-plans.sh"
    custom.write_text("#!/usr/bin/env bash\n# custom super-fr validator\nexit 0\n")
    custom.chmod(0o755)

    res = scaffold(repo)

    assert res.exit_code == 2
    assert "not a super-fr wrapper" in res.output
    assert custom.read_text() == "#!/usr/bin/env bash\n# custom super-fr validator\nexit 0\n"


def test_scaffold_plan_repo_commits_existing_untracked_wrapper(repo: Path) -> None:
    _initial_commit(repo)
    plans = repo / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / ".gitkeep").write_text("")
    wrapper = repo / "scripts" / "validate-plans.sh"
    wrapper.parent.mkdir()
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "# Thin wrapper — delegates to the canonical validator from the\n"
        "# super-fr plugin installed at the user level.\n"
        'exec "$HOME/.claude/plugins/marketplaces/derio-net/scripts/validate-plans.sh" "$@"\n'
    )
    wrapper.chmod(0o755)
    _git(repo, "add", "docs/superpowers/plans/.gitkeep")
    _git(repo, "commit", "-qm", "plans")

    res = scaffold(repo)

    assert res.exit_code == 0, res.output
    assert "scripts/validate-plans.sh" in _tracked(repo)
    head_files = _git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert "scripts/validate-plans.sh" in head_files


def test_scaffold_plan_repo_commits_existing_wrapper_mode_fix(repo: Path) -> None:
    _initial_commit(repo)
    plans = repo / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / ".gitkeep").write_text("")
    wrapper = repo / "scripts" / "validate-plans.sh"
    wrapper.parent.mkdir()
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "# Thin wrapper — delegates to the canonical validator from the\n"
        "# super-fr plugin installed at the user level.\n"
        'exec "$HOME/.claude/plugins/marketplaces/derio-net/scripts/validate-plans.sh" "$@"\n'
    )
    wrapper.chmod(0o644)
    _git(repo, "add", "docs/superpowers/plans/.gitkeep", "scripts/validate-plans.sh")
    _git(repo, "commit", "-qm", "plans and non-executable wrapper")

    res = scaffold(repo)

    assert res.exit_code == 0, res.output
    mode = _git(repo, "ls-tree", "HEAD", "--", "scripts/validate-plans.sh").stdout.split()[0]
    assert mode == "100755"


def test_scaffold_commit_preserves_partial_staged_file(repo: Path) -> None:
    # Hardest case: a file staged at v1 then dirtied to v2 (AM). The scoped
    # scaffold commit must leave both its index (v1) and worktree (v2) intact.
    _initial_commit(repo)
    (repo / "work.txt").write_text("v1\n")
    _git(repo, "add", "work.txt")  # index = v1
    (repo / "work.txt").write_text("v2\n")  # worktree = v2 (AM state)
    res = scaffold(repo)
    assert res.exit_code == 0, res.output
    head_files = _git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert "work.txt" not in head_files  # not committed by scaffold
    assert _git(repo, "show", ":work.txt").stdout == "v1\n"  # index split preserved
    assert (repo / "work.txt").read_text() == "v2\n"  # worktree split preserved


def test_rescaffold_unchanged_makes_no_new_commit(repo: Path) -> None:
    _initial_commit(repo)
    scaffold(repo)
    after_first = _log_subjects(repo)
    res = scaffold(repo, "--force")  # identical inputs → nothing to stage
    assert res.exit_code == 0, res.output
    assert _log_subjects(repo) == after_first  # no empty re-scaffold commit


def test_scaffold_zero_commit_repo_makes_initial_commit(repo: Path) -> None:
    # `repo` has no commits yet — the scaffold commit becomes the first one.
    res = scaffold(repo)
    assert res.exit_code == 0, res.output
    assert _log_subjects(repo) == ["chore(fr): scaffold dev devcontainer profile"]
    assert ".devcontainer/dev/devcontainer.json" in _tracked(repo)


def test_scaffold_gitignored_devcontainer_warns_and_skips(repo: Path) -> None:
    _initial_commit(repo)
    (repo / ".gitignore").write_text(".devcontainer/\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-qm", "ignore devcontainer")
    before = _log_subjects(repo)
    res = scaffold(repo)
    assert res.exit_code == 0, res.output
    assert _log_subjects(repo) == before  # nothing committed
    assert "git-ignored" in res.output  # but the operator is warned


def test_scaffold_no_commit_writes_only(repo: Path) -> None:
    _initial_commit(repo)
    before = _log_subjects(repo)
    res = scaffold(repo, "--no-commit")
    assert res.exit_code == 0, res.output
    assert _log_subjects(repo) == before  # no commit
    assert (repo / ".devcontainer" / "dev" / "devcontainer.json").exists()  # written
    assert ".devcontainer/dev/devcontainer.json" not in _tracked(repo)  # left untracked


def test_scaffold_writes_profile_yaml_and_envfile(repo: Path, tmp_path: Path) -> None:
    res = scaffold(repo, "--tool", "uv", "--secret", "GH_TOKEN", "--default")
    assert res.exit_code == 0, res.output

    cfg = json.loads((repo / ".devcontainer" / "dev" / "devcontainer.json").read_text())
    assert "image" in cfg
    # super-fr#300: the base image must be a PINNED LTS tag, not the floating
    # `:ubuntu` tag (which now resolves to a release where the docker-in-docker
    # feature fails to install — `moby` packages absent on Ubuntu "resolute").
    assert cfg["image"] == BASE_IMAGE
    assert cfg["image"] == "mcr.microsoft.com/devcontainers/base:ubuntu-24.04", (
        "base image must be pinned to an LTS tag for reproducible isolation (super-fr#300)"
    )
    # baseline: gh feature present; requested tool mapped to its feature
    assert any("github-cli" in k for k in cfg["features"])
    assert any(KNOWN_TOOL_FEATURES["uv"] in k for k in cfg["features"])
    # vk installed in postCreate; secrets env-file wired with localEnv HOME
    assert "super-fr#subdirectory=packages/fr" in cfg["postCreateCommand"]
    # host-path workspace mount — linked-worktree git breaks without it
    assert cfg["workspaceFolder"] == "${localWorkspaceFolder}"
    assert "target=${localWorkspaceFolder}" in cfg["workspaceMount"]
    assert "--env-file" in " ".join(cfg["runArgs"])
    assert "${localEnv:HOME}" in " ".join(cfg["runArgs"])
    # fr spellings on the new-write side (#272): fr secrets mount + fr key
    assert "/.config/fr/secrets/" in " ".join(cfg["runArgs"])
    assert "fr" in cfg["customizations"] and "vk" not in cfg["customizations"]

    profiles = yaml.safe_load((repo / ".devcontainer" / "fr-profiles.yaml").read_text())
    assert profiles["default"] == "dev"
    assert profiles["profiles"]["dev"]["purpose"] == "day-to-day development"
    assert profiles["profiles"]["dev"]["secrets"] == ["GH_TOKEN"]

    env = tmp_path / "home" / ".config" / "fr" / "secrets" / "myrepo" / "dev.env"
    assert env.is_file()
    assert "# GH_TOKEN=" in env.read_text()


def test_scaffold_refuses_overwrite_without_force(repo: Path) -> None:
    assert scaffold(repo).exit_code == 0
    res = scaffold(repo)
    assert res.exit_code == 2
    assert "--force" in res.output
    assert scaffold(repo, "--force").exit_code == 0


def test_scaffold_second_profile_keeps_first(repo: Path) -> None:
    assert scaffold(repo, "--default").exit_code == 0
    res = runner.invoke(
        app,
        [
            "init",
            "scaffold",
            "--repo",
            str(repo),
            "--profile",
            "readonly",
            "--purpose",
            "read-only review",
        ],
    )
    assert res.exit_code == 0, res.output
    profiles = yaml.safe_load((repo / ".devcontainer" / "fr-profiles.yaml").read_text())
    assert profiles["default"] == "dev"  # unchanged
    assert set(profiles["profiles"]) == {"dev", "readonly"}


def test_unknown_tool_recorded_in_notes(repo: Path) -> None:
    res = scaffold(repo, "--tool", "frobnicator9000")
    assert res.exit_code == 0, res.output
    profiles = yaml.safe_load((repo / ".devcontainer" / "fr-profiles.yaml").read_text())
    assert "frobnicator9000" in " ".join(profiles["profiles"]["dev"].get("notes", []))


def test_scaffold_outside_repo_exits_2(tmp_path: Path) -> None:
    res = runner.invoke(
        app, ["init", "scaffold", "--repo", str(tmp_path), "--profile", "x", "--purpose", "p"]
    )
    assert res.exit_code == 2
    assert "git repo" in res.output


def test_envfile_never_overwritten(repo: Path, tmp_path: Path) -> None:
    scaffold(repo, "--secret", "A_KEY")
    env = tmp_path / "home" / ".config" / "fr" / "secrets" / "myrepo" / "dev.env"
    env.write_text("A_KEY=real-secret\n")
    scaffold(repo, "--force", "--secret", "A_KEY", "--secret", "B_KEY")
    text = env.read_text()
    assert "A_KEY=real-secret" in text  # operator's value preserved
    assert "# B_KEY=" in text  # new placeholder appended


def test_scaffold_purpose_non_ascii_written_literally(repo: Path) -> None:
    """Scaffold output keeps UTF-8 literal (same ensure_ascii bug class)."""
    res = runner.invoke(
        app,
        [
            "init",
            "scaffold",
            "--repo",
            str(repo),
            "--profile",
            "dev",
            "--purpose",
            "day-to-day — checks: pytest",
        ],
    )
    assert res.exit_code == 0, res.output
    text = (repo / ".devcontainer" / "dev" / "devcontainer.json").read_text()
    assert "day-to-day — checks: pytest" in text
    assert "\\u2014" not in text


# --- multi-backend: devcontainer CLI-install becomes backend-conditional ----
# (docs/superpowers/specs/2026-07-09-multi-backend-git-host-adapters-design.md §9)


def test_scaffold_profile_github_default_unchanged(repo: Path) -> None:
    """Regression guard: backend="github" (the default) still gets the
    unconditional github-cli feature, no postCreate addition."""
    _initial_commit(repo)
    config_path = scaffold_profile(repo, "dev", "purpose", tools=[], secrets=[])
    config = json.loads(config_path.read_text())
    assert GH_FEATURE in config["features"]
    assert config["postCreateCommand"].count("curl") == 0


def test_scaffold_profile_gitlab_no_github_cli_feature(repo: Path) -> None:
    """backend="gitlab" gets NO github-cli feature and DOES get a
    glab-install postCreateCommand snippet appended."""
    _initial_commit(repo)
    config_path = scaffold_profile(repo, "dev", "purpose", tools=[], secrets=[], backend="gitlab")
    config = json.loads(config_path.read_text())
    assert GH_FEATURE not in config["features"]
    assert "glab" in config["postCreateCommand"]


def test_scaffold_profile_gitea_no_github_cli_feature(repo: Path) -> None:
    """backend="gitea" gets NO github-cli feature and DOES get a
    tea-install postCreateCommand snippet appended."""
    _initial_commit(repo)
    config_path = scaffold_profile(repo, "dev", "purpose", tools=[], secrets=[], backend="gitea")
    config = json.loads(config_path.read_text())
    assert GH_FEATURE not in config["features"]
    assert "tea" in config["postCreateCommand"]


def test_scaffold_profile_still_installs_fr_for_every_backend(repo: Path) -> None:
    """The baseline fr install must survive regardless of backend — the
    CLI-install snippet is ADDED, not a replacement."""
    _initial_commit(repo)
    config_path = scaffold_profile(repo, "dev", "purpose", tools=[], secrets=[], backend="gitlab")
    config = json.loads(config_path.read_text())
    assert "super-fr" in config["postCreateCommand"]


def test_scaffold_profile_writes_backend_and_host_to_profiles_yaml(repo: Path) -> None:
    """A non-default backend (and optional self-hosted host) is recorded
    as a top-level (repo-level, not per-profile) key in
    .devcontainer/fr-profiles.yaml — what fr._hosts.detect_backend reads."""
    _initial_commit(repo)
    scaffold_profile(
        repo, "dev", "purpose", tools=[], secrets=[], backend="gitlab", host="gitlab.mycorp.com"
    )
    data = yaml.safe_load((repo / ".devcontainer" / "fr-profiles.yaml").read_text())
    assert data["backend"] == "gitlab"
    assert data["host"] == "gitlab.mycorp.com"


def test_scaffold_profile_github_default_omits_backend_key(repo: Path) -> None:
    """The default backend ("github") is NOT written explicitly — matches
    fr._hosts.detect_backend's own fallback, so an unmodified
    fr-profiles.yaml (as scaffolded before this feature existed) behaves
    identically."""
    _initial_commit(repo)
    scaffold_profile(repo, "dev", "purpose", tools=[], secrets=[])
    data = yaml.safe_load((repo / ".devcontainer" / "fr-profiles.yaml").read_text())
    assert "backend" not in data
    assert "host" not in data


def test_host_cli_feature_table_shape() -> None:
    assert HOST_CLI_FEATURE["github"] == GH_FEATURE
    assert HOST_CLI_FEATURE["gitlab"] is None
    assert HOST_CLI_FEATURE["gitea"] is None


def test_host_cli_post_create_table_has_gitlab_and_gitea_only() -> None:
    assert set(HOST_CLI_POST_CREATE) == {"gitlab", "gitea"}


def test_cli_backend_flag_reaches_scaffold_profile(repo: Path) -> None:
    """`fr init scaffold --backend gitlab --host ...` reaches scaffold_profile
    and is recorded in fr-profiles.yaml."""
    _initial_commit(repo)
    res = scaffold(repo, "--backend", "gitlab", "--host", "gitlab.mycorp.com")
    assert res.exit_code == 0, res.output
    data = yaml.safe_load((repo / ".devcontainer" / "fr-profiles.yaml").read_text())
    assert data["backend"] == "gitlab"
    assert data["host"] == "gitlab.mycorp.com"
    config = json.loads((repo / ".devcontainer" / "dev" / "devcontainer.json").read_text())
    assert "glab" in config["postCreateCommand"]


def test_cli_backend_flag_rejects_unknown_value(repo: Path) -> None:
    _initial_commit(repo)
    res = scaffold(repo, "--backend", "bitbucket")
    assert res.exit_code == 2
    assert "must be one of github, gitlab, gitea" in res.output
