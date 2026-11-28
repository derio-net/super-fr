"""Install channels (spec 2026-10-14-exit-gates R22, R23).

install.sh carries the channel marker and its preflight accepts a clean, detached
HEAD at a v* tag; bootstrap.sh --version picks the tag. Everything runs against a
fixture remote in tmp (FR_SRC_REMOTE + FR_SRC_DIR) whose install.sh is a stub that
records argv -- never the network, never the operator's real install.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.own_artifacts

REPO_ROOT = Path(__file__).parent.parent.parent
BOOTSTRAP_SH = REPO_ROOT / "scripts" / "bootstrap.sh"
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
MARKER = "# fr-install-channels: 1"


def _git(cwd: Path, *args: str) -> str:
    res = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return res.stdout.strip()


# ── R23: install.sh ───────────────────────────────────────────────────


def test_install_sh_carries_the_channel_marker() -> None:
    assert MARKER in INSTALL_SH.read_text().splitlines()


def _install_checkout(tmp_path: Path) -> Path:
    repo = tmp_path / "checkout"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "install.sh").write_text(INSTALL_SH.read_text())
    _git(repo, "-c", "init.defaultBranch=main", "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _run_install(tmp_path: Path, repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True, exist_ok=True)
    uv = home / "bin" / "uv"
    uv.write_text("#!/bin/sh\nexit 0\n")
    uv.chmod(0o755)
    env = {
        "HOME": str(home),
        "PATH": f"{home / 'bin'}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "FR_INSTALL_SKIP_PREFLIGHT": "",
    }
    return subprocess.run(
        ["bash", str(repo / "scripts" / "install.sh"), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_preflight_passes_on_a_clean_detached_tag(tmp_path: Path) -> None:
    repo = _install_checkout(tmp_path)
    _git(repo, "tag", "v1.0.0")
    _git(repo, "checkout", "-q", "--detach", "v1.0.0")
    res = _run_install(tmp_path, repo)
    assert "Channel: v1.0.0" in res.stdout, res.stdout + res.stderr
    assert "Preflight failed" not in res.stderr


def test_preflight_refuses_a_dirty_tag_checkout(tmp_path: Path) -> None:
    repo = _install_checkout(tmp_path)
    _git(repo, "tag", "v1.0.0")
    _git(repo, "checkout", "-q", "--detach", "v1.0.0")
    (repo / "stray").write_text("x\n")
    res = _run_install(tmp_path, repo)
    assert res.returncode != 0
    assert "Preflight failed" in res.stderr
    assert "Channel:" not in res.stdout


def test_preflight_refuses_a_detached_head_that_is_not_a_tag(tmp_path: Path) -> None:
    repo = _install_checkout(tmp_path)
    _git(repo, "tag", "rc/some-branch/abc1234")  # per-branch pre-merge tag: not a channel
    _git(repo, "checkout", "-q", "--detach", "HEAD")
    res = _run_install(tmp_path, repo, "--version", "main")  # the preflight is main's
    assert res.returncode != 0
    assert "Preflight failed" in res.stderr
    assert "Channel:" not in res.stdout


# ── R22: bootstrap.sh --version ───────────────────────────────────────

_STUB = """\
#!/usr/bin/env bash
{marker}
printf '%s\\n' "$@" > "$BOOTSTRAP_TEST_MARKER"
root="$(dirname "$0")/.."
echo "stub install tag=$(git -C "$root" describe --tags --exact-match 2>/dev/null || echo none)"
"""


def _fixture_remote(tmp_path: Path) -> Path:
    origin = tmp_path / "origin"
    (origin / "scripts").mkdir(parents=True)
    (origin / "scripts" / "bootstrap.sh").write_text(BOOTSTRAP_SH.read_text())
    _git(origin, "-c", "init.defaultBranch=main", "init", "-q")
    _git(origin, "config", "user.email", "t@t")
    _git(origin, "config", "user.name", "t")

    def commit(tag: str | None, marked: bool) -> None:
        body = _STUB.format(marker=MARKER if marked else "# old")
        (origin / "scripts" / "install.sh").write_text(body)
        (origin / "scripts" / "install.sh").chmod(0o755)
        _git(origin, "add", "-A")
        _git(origin, "commit", "-q", "--allow-empty", "-m", tag or "main")
        if tag:
            _git(origin, "tag", tag)

    commit("v1.0.0", marked=False)
    commit("v1.1.0", marked=True)
    commit("v1.2.0-rc.1", marked=True)
    commit("v1.2.0-rc.2", marked=True)
    commit("v1.2.0-rc.10", marked=True)
    commit("v1.2.0-rc.9", marked=True)
    # Unmarked and lexically last, as this repo's real v5.9.4 is (p8-r1).
    commit("v1.9.0", marked=False)
    commit("v0.9.0", marked=False)
    # A tag whose commit has no scripts/install.sh at all: skipped without a message.
    (origin / "scripts" / "install.sh").unlink()
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "v0.8.0")
    _git(origin, "tag", "v0.8.0")
    commit("v1.2.0", marked=True)
    commit("rc/some-branch/abc1234", marked=True)  # per-branch tag, never a channel
    commit(None, marked=True)  # main moves past every tag
    return origin


def _bootstrap(
    tmp_path: Path, origin: Path, *args: str, piped: bool = False
) -> tuple[subprocess.CompletedProcess[str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name in ("uv", "jq"):
        stub = bin_dir / name
        if not stub.exists():
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)
    (tmp_path / "home").mkdir(exist_ok=True)
    marker = tmp_path / "marker.txt"
    env = {
        "HOME": str(tmp_path / "home"),
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "FR_SRC_DIR": str(tmp_path / "src"),
        "FR_SRC_REMOTE": f"file://{origin}",
        "BOOTSTRAP_TEST_MARKER": str(marker),
    }
    if piped:
        res = subprocess.run(
            ["bash", "-s", "--", *args],
            input=BOOTSTRAP_SH.read_text(),
            capture_output=True,
            text=True,
            env=env,
        )
    else:
        res = subprocess.run(
            ["bash", str(BOOTSTRAP_SH), *args], capture_output=True, text=True, env=env
        )
    return res, marker


def _installed(res: subprocess.CompletedProcess[str]) -> str | None:
    for line in res.stdout.splitlines():
        if line.startswith("stub install tag="):
            return line.removeprefix("stub install tag=")
    return None


def test_no_argument_installs_the_newest_installable_final(tmp_path: Path) -> None:
    res, _ = _bootstrap(tmp_path, _fixture_remote(tmp_path))
    assert res.returncode == 0, res.stderr
    assert _installed(res) == "v1.2.0"


def test_rc_installs_the_newest_rc_numerically(tmp_path: Path) -> None:
    res, _ = _bootstrap(tmp_path, _fixture_remote(tmp_path), "--version", "RC")
    assert res.returncode == 0, res.stderr
    assert _installed(res) == "v1.2.0-rc.10"


def test_x_y_z_rc_installs_the_newest_rc_of_that_release(tmp_path: Path) -> None:
    res, _ = _bootstrap(tmp_path, _fixture_remote(tmp_path), "--version", "1.2.0-RC")
    assert res.returncode == 0, res.stderr
    assert _installed(res) == "v1.2.0-rc.10"


def test_exact_rc_and_exact_release(tmp_path: Path) -> None:
    origin = _fixture_remote(tmp_path)
    res, _ = _bootstrap(tmp_path, origin, "--version", "1.2.0-rc.1")
    assert _installed(res) == "v1.2.0-rc.1", res.stderr
    res, _ = _bootstrap(tmp_path, origin, "--version", "1.1.0")
    assert _installed(res) == "v1.1.0", res.stderr
    res, _ = _bootstrap(tmp_path, origin, "--version", "1.2.0")
    assert _installed(res) == "v1.2.0", res.stderr


def test_an_unmarked_tag_is_refused_listing_the_installable_ones(tmp_path: Path) -> None:
    res, marker = _bootstrap(tmp_path, _fixture_remote(tmp_path), "--version", "1.0.0")
    assert res.returncode != 0
    assert not marker.exists()
    assert "v1.1.0" in res.stderr and "v1.2.0-rc.2" in res.stderr
    assert "v1.0.0" not in res.stderr.replace("1.0.0 is not installable", "")
    assert "v1.9.0" not in res.stderr and "v0.9.0" not in res.stderr


def test_the_refusal_lists_installable_tags_in_version_order(tmp_path: Path) -> None:
    res, _ = _bootstrap(tmp_path, _fixture_remote(tmp_path), "--version", "9.9.9")
    listed = [ln.strip() for ln in res.stderr.splitlines() if ln.strip().startswith("v")]
    assert listed == [
        "v1.1.0",
        "v1.2.0-rc.1",
        "v1.2.0-rc.2",
        "v1.2.0-rc.9",
        "v1.2.0-rc.10",
        "v1.2.0",
    ], res.stderr


# ── 2026-11-28-batch-silent-failures R3, R4: no tag is dropped without a message ──

_REAL_GIT = shutil.which("git") or "/usr/bin/git"
_RC10_SHOW = "show refs/tags/v1.2.0-rc.10:scripts/install.sh"


def _git_stub(tmp_path: Path, match: str, stderr: str, code: int = 128) -> None:
    """A `git` first on PATH that fails one invocation and delegates the rest to the real one."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "git"
    stub.write_text(
        "#!/bin/sh\n"
        f'case "$*" in *"{match}"*) echo "{stderr}" >&2; exit {code};; esac\n'
        f'exec "{_REAL_GIT}" "$@"\n'
    )
    stub.chmod(0o755)


@pytest.mark.parametrize(
    "args",
    [(), ("--version", "RC"), ("--version", "1.2.0"), ("--version", "9.9.9")],
    ids=["default", "rc", "exact", "refusal"],
)
def test_a_tag_whose_install_sh_cannot_be_read_stops_bootstrap(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    origin = _fixture_remote(tmp_path)
    _git_stub(tmp_path, _RC10_SHOW, "fatal: simulated read failure")
    res, marker = _bootstrap(tmp_path, origin, *args)
    assert res.returncode == 1, res.stdout + res.stderr
    assert (
        "ERROR: could not read scripts/install.sh at v1.2.0-rc.10: fatal: simulated read failure"
        in res.stderr
    )
    assert not marker.exists()
    assert "No installable versions" not in res.stderr


def test_an_unreadable_tag_never_blocks_the_main_channel(tmp_path: Path) -> None:
    origin = _fixture_remote(tmp_path)
    _git_stub(tmp_path, _RC10_SHOW, "fatal: simulated read failure")
    res, marker = _bootstrap(tmp_path, origin, "--version", "main")
    assert res.returncode == 0, res.stderr
    assert marker.exists()


def test_a_failing_tag_listing_is_named_never_read_as_no_versions(tmp_path: Path) -> None:
    origin = _fixture_remote(tmp_path)
    _git_stub(tmp_path, "ls-remote --tags", "fatal: simulated network failure")
    for args in ((), ("--version", "9.9.9")):
        res, marker = _bootstrap(tmp_path, origin, *args)
        assert res.returncode == 1, res.stdout + res.stderr
        assert "ERROR: could not list release tags: fatal: simulated network failure" in res.stderr
        assert "No installable versions" not in res.stderr
        assert not marker.exists()


def test_a_tag_without_an_install_sh_is_skipped_without_a_message(tmp_path: Path) -> None:
    res, _ = _bootstrap(tmp_path, _fixture_remote(tmp_path), "--version", "9.9.9")
    assert "v0.8.0" not in res.stderr
    assert "could not" not in res.stderr


def test_an_unknown_version_installs_nothing(tmp_path: Path) -> None:
    res, marker = _bootstrap(tmp_path, _fixture_remote(tmp_path), "--version", "9.9.9")
    assert res.returncode != 0
    assert not marker.exists()
    assert "v1.1.0" in res.stderr


def test_a_missing_version_value_installs_nothing(tmp_path: Path) -> None:
    res, marker = _bootstrap(tmp_path, _fixture_remote(tmp_path), "--version")
    assert res.returncode != 0
    assert not marker.exists()


def test_main_checks_out_origin_main(tmp_path: Path) -> None:
    origin = _fixture_remote(tmp_path)
    res, _ = _bootstrap(tmp_path, origin, "--version", "v1.1.0")  # leave a tag checkout first
    assert _installed(res) == "v1.1.0", res.stderr
    res, _ = _bootstrap(tmp_path, origin, "--version", "main")
    assert res.returncode == 0, res.stderr
    src = tmp_path / "src"
    assert _git(src, "symbolic-ref", "--short", "HEAD") == "main"
    assert _git(src, "rev-parse", "HEAD") == _git(origin, "rev-parse", "main")


def test_a_channel_switch_removes_untracked_files_from_the_managed_cache(tmp_path: Path) -> None:
    """gh#1202: `checkout -f` kept untracked files, and install.sh's preflight then
    refused the tag checkout until the operator cleaned the cache by hand."""
    origin = _fixture_remote(tmp_path)
    res, _ = _bootstrap(tmp_path, origin, "--version", "v1.1.0")
    assert _installed(res) == "v1.1.0", res.stderr
    src = tmp_path / "src"
    (src / "stray.txt").write_text("left by an older channel\n")
    (src / "leftover" / "nested").mkdir(parents=True)
    (src / "leftover" / "nested" / "f").write_text("x\n")
    res, _ = _bootstrap(tmp_path, origin, "--version", "1.2.0")
    assert _installed(res) == "v1.2.0", res.stderr
    assert not (src / "stray.txt").exists()
    assert not (src / "leftover").exists()
    assert _git(src, "status", "--porcelain") == ""


def test_a_channel_switch_keeps_ignored_files_in_the_managed_cache(tmp_path: Path) -> None:
    """Only what the preflight refuses goes: ignored files (a venv, caches) stay."""
    origin = _fixture_remote(tmp_path)
    res, _ = _bootstrap(tmp_path, origin, "--version", "v1.1.0")
    assert _installed(res) == "v1.1.0", res.stderr
    src = tmp_path / "src"
    (src / ".git" / "info" / "exclude").write_text(".venv/\n")
    (src / ".venv").mkdir()
    (src / ".venv" / "keep").write_text("x\n")
    res, _ = _bootstrap(tmp_path, origin, "--version", "1.2.0")
    assert _installed(res) == "v1.2.0", res.stderr
    assert (src / ".venv" / "keep").exists()


def test_no_marked_final_installs_nothing_and_names_the_explicit_channels(tmp_path: Path) -> None:
    """gh: the default is the newest stable release, never main or an RC by accident.
    With no installable final, bootstrap refuses and names `--version main` / `RC`."""
    origin = tmp_path / "origin"
    (origin / "scripts").mkdir(parents=True)
    (origin / "scripts" / "bootstrap.sh").write_text(BOOTSTRAP_SH.read_text())
    (origin / "scripts" / "install.sh").write_text(_STUB.format(marker=MARKER))
    (origin / "scripts" / "install.sh").chmod(0o755)
    _git(origin, "-c", "init.defaultBranch=main", "init", "-q")
    _git(origin, "config", "user.email", "t@t")
    _git(origin, "config", "user.name", "t")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "init")
    _git(origin, "tag", "v1.0.0-rc.1")
    res, marker = _bootstrap(tmp_path, origin)
    assert res.returncode != 0
    assert not marker.exists()
    assert "no installable release" in res.stderr.lower()
    assert "--version main" in res.stderr and "--version RC" in res.stderr
    assert "v1.0.0-rc.1" in res.stderr


def test_main_channel_tells_install_sh_to_install_its_checkout(tmp_path: Path) -> None:
    """main's install.sh delegates to the stable channel unless told `--version main`,
    so bootstrap's main channel must say it (else the two would loop)."""
    res, marker = _bootstrap(tmp_path, _fixture_remote(tmp_path), "--version", "main", "--x")
    assert res.returncode == 0, res.stderr
    assert marker.read_text().split() == ["--version", "main", "--x"]


def test_other_flags_reach_install_sh(tmp_path: Path) -> None:
    res, marker = _bootstrap(
        tmp_path, _fixture_remote(tmp_path), "--uninstall", "--version", "1.1.0", "--x"
    )
    assert res.returncode == 0, res.stderr
    assert marker.read_text().split() == ["--uninstall", "--x"]


def test_works_piped_from_curl(tmp_path: Path) -> None:
    res, _ = _bootstrap(tmp_path, _fixture_remote(tmp_path), "--version", "RC", piped=True)
    assert res.returncode == 0, res.stderr
    assert _installed(res) == "v1.2.0-rc.10"


def test_a_forwarded_argument_with_spaces_stays_one_argument(tmp_path: Path) -> None:
    origin = _fixture_remote(tmp_path)
    for piped in (False, True):
        res, marker = _bootstrap(
            tmp_path, origin, "--note", "a b  c", "--version", "1.1.0", piped=piped
        )
        assert res.returncode == 0, res.stderr
        assert marker.read_text().splitlines() == ["--note", "a b  c"]


# ── install.sh preflight edges (p8-r4, p8-r5) ─────────────────────────


def test_preflight_refuses_a_loose_v_tag(tmp_path: Path) -> None:
    repo = _install_checkout(tmp_path)
    _git(repo, "tag", "v5-hotfix")
    _git(repo, "checkout", "-q", "--detach", "v5-hotfix")
    res = _run_install(tmp_path, repo, "--version", "main")  # the preflight is main's
    assert res.returncode != 0
    assert "Preflight failed" in res.stderr
    assert "Channel:" not in res.stdout


def test_preflight_accepts_an_rc_tag(tmp_path: Path) -> None:
    repo = _install_checkout(tmp_path)
    _git(repo, "tag", "v1.2.0-rc.3")
    _git(repo, "checkout", "-q", "--detach", "v1.2.0-rc.3")
    res = _run_install(tmp_path, repo)
    assert "Channel: v1.2.0-rc.3" in res.stdout, res.stdout + res.stderr


def test_preflight_on_main_in_sync_prints_channel_main(tmp_path: Path) -> None:
    upstream = _install_checkout(tmp_path)
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--branch", "main", f"file://{upstream}", str(clone))
    res = _run_install(tmp_path, clone, "--version", "main")
    assert "Channel: main" in res.stdout, res.stdout + res.stderr


# ── install.sh from a clone: stable by default (amends R23) ───────────


def _clone_with_real_scripts(tmp_path: Path) -> tuple[Path, Path]:
    """The fixture remote, with main moved to a commit carrying the REAL install.sh
    and bootstrap.sh, cloned on main: what an operator's base clone looks like."""
    origin = _fixture_remote(tmp_path)
    (origin / "scripts" / "install.sh").write_text(INSTALL_SH.read_text())
    (origin / "scripts" / "bootstrap.sh").write_text(BOOTSTRAP_SH.read_text())
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "release: v1.3.0-rc.1")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--branch", "main", f"file://{origin}", str(clone))
    return origin, clone


def _run_clone_install(
    tmp_path: Path, clone: Path, *args: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name in ("uv", "jq"):
        stub = bin_dir / name
        if not stub.exists():
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)
    (tmp_path / "home").mkdir(exist_ok=True)
    env = {
        "HOME": str(tmp_path / "home"),
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "FR_SRC_DIR": str(tmp_path / "src"),
        "BOOTSTRAP_TEST_MARKER": str(tmp_path / "marker.txt"),
        **(extra_env or {}),
    }
    return subprocess.run(
        ["bash", str(clone / "scripts" / "install.sh"), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_install_sh_on_main_installs_the_newest_stable_release(tmp_path: Path) -> None:
    """The operator's report: install.sh in a clone on main installed main's HEAD, which
    the release bot makes an RC while a gate is pending. No --version means stable."""
    _, clone = _clone_with_real_scripts(tmp_path)
    res = _run_clone_install(tmp_path, clone)
    assert res.returncode == 0, res.stdout + res.stderr
    assert _installed(res) == "v1.2.0", res.stdout + res.stderr
    assert "--version main" in res.stdout  # says how to install the checkout instead
    assert _git(clone, "symbolic-ref", "--short", "HEAD") == "main"  # clone untouched


def test_install_sh_version_rc_installs_the_newest_rc(tmp_path: Path) -> None:
    _, clone = _clone_with_real_scripts(tmp_path)
    res = _run_clone_install(tmp_path, clone, "--version", "RC")
    assert res.returncode == 0, res.stdout + res.stderr
    assert _installed(res) == "v1.2.0-rc.10"


def test_install_sh_forwards_other_flags_through_the_delegation(tmp_path: Path) -> None:
    _, clone = _clone_with_real_scripts(tmp_path)
    res = _run_clone_install(tmp_path, clone, "--x", "--version=1.1.0", "a b")
    assert res.returncode == 0, res.stdout + res.stderr
    assert _installed(res) == "v1.1.0"
    assert (tmp_path / "marker.txt").read_text().splitlines() == ["--x", "a b"]


def test_install_sh_refuses_to_delegate_twice(tmp_path: Path) -> None:
    """A bootstrap whose main channel forgot `--version main` must not loop forever."""
    _, clone = _clone_with_real_scripts(tmp_path)
    res = _run_clone_install(tmp_path, clone, extra_env={"FR_INSTALL_DELEGATED": "1"})
    assert res.returncode != 0
    assert "--version main" in res.stderr
    assert not (tmp_path / "marker.txt").exists()


def test_the_cloud_setup_script_installs_the_newest_stable_release(tmp_path: Path) -> None:
    from fr import cloud

    origin, _ = _clone_with_real_scripts(tmp_path)
    script = cloud.setup_script().replace(cloud.SOURCE_URL, f"file://{origin}")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name in ("uv", "jq", "rsync"):
        stub = bin_dir / name
        stub.write_text("#!/bin/sh\nexit 0\n")
        stub.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    env = {
        "HOME": str(home),
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "BOOTSTRAP_TEST_MARKER": str(tmp_path / "marker.txt"),
    }
    res = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)
    assert res.returncode == 0, res.stdout + res.stderr
    assert _installed(res) == "v1.2.0", res.stdout + res.stderr


def test_the_wave_drivers_post_merge_installs_main_explicitly() -> None:
    import yaml

    config = yaml.safe_load((REPO_ROOT / ".fr" / "triage.yaml").read_text())
    assert config["post_merge"] == ["./scripts/install.sh", "--version", "main"]


def test_uninstall_never_delegates(tmp_path: Path) -> None:
    """--uninstall chooses no version: it runs from the clone, wherever its flag sits."""
    _, clone = _clone_with_real_scripts(tmp_path)
    res = _run_clone_install(tmp_path, clone, "--uninstall")
    assert "newest stable release" not in res.stdout + res.stderr
    assert _installed(res) is None
    assert not (tmp_path / "src").exists()  # bootstrap's managed clone never made
