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
    KNOWN_TOOLS,
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
        'exec "$HOME/.claude/plugins/marketplaces/derio-net--super-fr'
        '/scripts/validate-plans.sh" "$@"\n'
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
        'exec "$HOME/.claude/plugins/marketplaces/derio-net--super-fr'
        '/scripts/validate-plans.sh" "$@"\n'
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
    assert any(KNOWN_TOOLS["uv"].feature in k for k in cfg["features"])
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


def test_an_unknown_tool_is_refused_and_writes_nothing(repo: Path, tmp_path: Path) -> None:
    """gh#574: an unknown --tool used to exit 0 with the tool parked in a
    `notes:` line — the profile built without it. Now: exit 2, stderr names the
    sorted known set and --feature, and nothing is written or committed."""
    _initial_commit(repo)
    before = _log_subjects(repo)
    res = scaffold(repo, "--tool", "nosuchtool", "--secret", "GH_TOKEN")
    assert res.exit_code == 2, res.output
    assert "nosuchtool" in res.stderr
    assert ", ".join(sorted(KNOWN_TOOLS)) in res.stderr
    assert "--feature" in res.stderr
    assert not (repo / ".devcontainer" / "dev" / "devcontainer.json").exists()
    assert not (repo / ".devcontainer" / "fr-profiles.yaml").exists()
    assert not (tmp_path / "home" / ".config" / "fr" / "secrets" / "myrepo" / "dev.env").exists()
    assert _log_subjects(repo) == before


def test_an_unknown_tool_is_refused_before_the_exists_check(repo: Path) -> None:
    """p3r-f4: tool resolution runs FIRST — rerunning over an existing profile
    with a bad --tool reports the tool, not "--force", and touches nothing."""
    assert scaffold(repo).exit_code == 0
    profiles = repo / ".devcontainer" / "fr-profiles.yaml"
    before = profiles.read_bytes()
    res = scaffold(repo, "--tool", "nosuchtool")
    assert res.exit_code == 2, res.output
    assert "nosuchtool" in res.stderr
    assert "--force" not in res.stderr
    assert profiles.read_bytes() == before


def test_tool_help_lists_the_known_tools() -> None:
    """p3r-f6: the known set is discoverable from --help, not only from an error."""
    res = runner.invoke(app, ["init", "scaffold", "--help"], env={"COLUMNS": "400"})
    assert res.exit_code == 0, res.output
    assert ", ".join(sorted(KNOWN_TOOLS)) in " ".join(res.output.split())


@pytest.mark.parametrize("reserved", ["host", "external"])
def test_a_reserved_profile_name_is_refused(repo: Path, reserved: str) -> None:
    """spec §3.C: legacy states with no `target` infer the mode from `profile`
    (`host` → worktree, `external` → external), permanently — so a real
    devcontainer profile with either name would be misrouted. Refused at birth."""
    res = runner.invoke(
        app,
        ["init", "scaffold", "--repo", str(repo), "--profile", reserved, "--purpose", "p"],
    )
    assert res.exit_code == 2, res.output
    assert reserved in res.stderr and "reserved" in res.stderr
    assert not (repo / ".devcontainer" / reserved).exists()


def test_java_and_maven_write_one_java_feature_with_maven(repo: Path) -> None:
    res = scaffold(repo, "--no-commit", "--tool", "java", "--tool", "maven")
    assert res.exit_code == 0, res.output
    features = _config(repo)["features"]
    assert features["ghcr.io/devcontainers/features/java:1"] == {"installMaven": True}


JAVA = "ghcr.io/devcontainers/features/java:1"


def _pom_release(repo: Path, version: str) -> None:
    (repo / "pom.xml").write_text(
        '<project xmlns="http://maven.apache.org/POM/4.0.0"><properties>'
        f"<maven.compiler.release>{version}</maven.compiler.release>"
        "</properties></project>\n"
    )


def test_maven_applies_the_detected_java_version_and_reports_it(repo: Path) -> None:
    """gh#574: maven implies java — its version comes from the project's pom."""
    _pom_release(repo, "17")
    res = scaffold(repo, "--no-commit", "--tool", "maven")
    assert res.exit_code == 0, res.output
    assert _config(repo)["features"][JAVA] == {"installMaven": True, "version": "17"}
    assert "java 17 (from pom.xml maven.compiler.release)" in res.stderr


def test_an_explicit_java_version_wins_over_detection(repo: Path) -> None:
    _pom_release(repo, "17")
    res = scaffold(repo, "--no-commit", "--tool", "java@21", "--tool", "maven")
    assert res.exit_code == 0, res.output
    assert _config(repo)["features"][JAVA]["version"] == "21"
    assert "from pom.xml" not in res.stderr
    assert "not detected" not in res.stderr


def test_an_undetected_java_version_warns_and_keeps_the_default(repo: Path) -> None:
    res = scaffold(repo, "--no-commit", "--tool", "java")
    assert res.exit_code == 0, res.output
    assert "version" not in _config(repo)["features"][JAVA]
    assert (
        "java version not detected — the java feature's default (latest) will be used; "
        "pass --tool java@<major> to pin it"
    ) in res.stderr


def test_java_detection_never_runs_without_java(repo: Path) -> None:
    _pom_release(repo, "17")
    res = scaffold(repo, "--no-commit", "--tool", "uv")
    assert res.exit_code == 0, res.output
    assert "java" not in res.stderr
    assert JAVA not in _config(repo)["features"]


def test_a_raw_java_feature_does_not_trigger_detection(repo: Path) -> None:
    """p4r-f4: detection is gated on --tool java/maven, not on the feature ref —
    a bare --feature is taken as written."""
    _pom_release(repo, "17")
    res = scaffold(repo, "--no-commit", "--feature", JAVA)
    assert res.exit_code == 0, res.output
    assert _config(repo)["features"][JAVA] == {}
    assert "java" not in res.stderr


def test_a_raw_feature_lands_in_features(repo: Path) -> None:
    res = scaffold(repo, "--no-commit", "--feature", "ghcr.io/acme/x:1")
    assert res.exit_code == 0, res.output
    assert _config(repo)["features"]["ghcr.io/acme/x:1"] == {}


def test_a_versioned_uv_still_separates_its_environment(repo: Path) -> None:
    from fr.isolation.scaffold import UV_CONTAINER_PROJECT_ENV

    res = scaffold(repo, "--no-commit", "--tool", "uv@0.5.0")
    assert res.exit_code == 0, res.output
    cfg = _config(repo)
    assert cfg["features"][KNOWN_TOOLS["uv"].feature] == {"version": "0.5.0"}
    assert cfg["containerEnv"] == {"UV_PROJECT_ENVIRONMENT": UV_CONTAINER_PROJECT_ENV}


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


def test_scaffold_envfile_is_private(repo: Path, tmp_path: Path) -> None:
    """Host secrets env-file is created private: 0600 file, 0700 dir chain.

    A world-readable secrets store (0644 files under 0755 dirs) once exposed a
    live cluster-admin kube token — the generator must birth these private.
    """
    res = scaffold(repo, "--secret", "GH_TOKEN")
    assert res.exit_code == 0, res.output
    fr_root = tmp_path / "home" / ".config" / "fr"
    secrets_root = fr_root / "secrets"
    env = secrets_root / "myrepo" / "dev.env"
    assert env.is_file()
    assert env.stat().st_mode & 0o777 == 0o600, oct(env.stat().st_mode)
    for d in (env.parent, secrets_root, fr_root):
        assert d.stat().st_mode & 0o777 == 0o700, f"{d}: {oct(d.stat().st_mode)}"


def test_scaffold_tightens_preexisting_loose_envfile(repo: Path, tmp_path: Path) -> None:
    """Re-scaffolding self-heals a legacy world-readable file + dir (the store
    that leaked was already on disk when the fix landed)."""
    scaffold(repo, "--secret", "A_KEY")
    env = tmp_path / "home" / ".config" / "fr" / "secrets" / "myrepo" / "dev.env"
    env.chmod(0o644)
    env.parent.chmod(0o755)
    scaffold(repo, "--force", "--secret", "A_KEY")
    assert env.stat().st_mode & 0o777 == 0o600, oct(env.stat().st_mode)
    assert env.parent.stat().st_mode & 0o777 == 0o700, oct(env.parent.stat().st_mode)


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


# --- a uv project gets its OWN environment inside the container ------------
#
# Found live on PR #508's Test Plan. The worktree is bind-mounted, and uv on
# both sides defaults its project environment to `<project>/.venv` — one path,
# two operating systems. A venv's interpreter link is valid only on the side
# that made it, so host and container each found the other's "broken", deleted
# it and rebuilt (the container re-downloading ~26 MB), on EVERY alternation.
# fr's exec-bridge discipline mandates that alternation, so under fr it is the
# normal case; and a host pytest can be running on the venv while it is deleted.


def _config(repo: Path, profile: str = "dev") -> dict:
    return json.loads((repo / ".devcontainer" / profile / "devcontainer.json").read_text())


def test_a_uv_profile_keeps_uvs_environment_out_of_the_bind_mount(repo: Path) -> None:
    from fr.isolation.scaffold import UV_CONTAINER_PROJECT_ENV

    scaffold_profile(repo, "dev", "day-to-day", tools=["uv"], secrets=[], commit=False)

    env = _config(repo)["containerEnv"]
    assert env == {"UV_PROJECT_ENVIRONMENT": UV_CONTAINER_PROJECT_ENV}


def test_the_container_env_is_relative_so_it_is_per_project() -> None:
    """uv resolves a RELATIVE `UV_PROJECT_ENVIRONMENT` against each project's
    root; an ABSOLUTE one is a single directory every project in the container
    shares. Review of this fix tried the absolute form with two independent
    projects: nothing was destroyed, but project `a` could import a package only
    `b` declared — a consumer's tests passing on a dependency they forgot. So:
    relative, and not the host's own name for it."""
    from pathlib import PurePosixPath

    from fr.isolation.scaffold import UV_CONTAINER_PROJECT_ENV

    path = PurePosixPath(UV_CONTAINER_PROJECT_ENV)
    assert not path.is_absolute()
    assert len(path.parts) == 1, "a bare directory name, resolved per project"
    assert UV_CONTAINER_PROJECT_ENV != ".venv", "the host's — the collision this fixes"
    # Hidden, so pytest's default `norecursedirs` (`.*`) never collects from it;
    # uv writes its own `.gitignore: *` inside, which keeps it out of git and ruff.
    assert UV_CONTAINER_PROJECT_ENV.startswith(".")


def test_a_profile_without_uv_gets_no_container_env(repo: Path) -> None:
    """Nothing is added for tools that did not ask for it — `containerEnv` is
    absent, not empty, so a non-uv profile is byte-identical to before."""
    scaffold_profile(repo, "dev", "day-to-day", tools=["node"], secrets=[], commit=False)

    assert "containerEnv" not in _config(repo)


def test_this_repos_own_uv_profiles_carry_it() -> None:
    """The scaffold fixes the next profile; these are the ones already written.
    Any profile here that installs the uv feature must separate the env too."""
    from fr.isolation.scaffold import UV_CONTAINER_PROJECT_ENV

    root = Path(__file__).resolve().parents[2] / ".devcontainer"
    uv_profiles = [
        p
        for p in sorted(root.glob("*/devcontainer.json"))
        if KNOWN_TOOLS["uv"].feature in json.loads(p.read_text()).get("features", {})
    ]
    assert uv_profiles, "expected at least one uv-enabled profile in this repo"
    for path in uv_profiles:
        env = json.loads(path.read_text()).get("containerEnv", {})
        assert env.get("UV_PROJECT_ENVIRONMENT") == UV_CONTAINER_PROJECT_ENV, path
