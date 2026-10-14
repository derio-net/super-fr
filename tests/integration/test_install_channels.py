"""Install channels (spec 2026-10-14-exit-gates R22, R23).

install.sh carries the channel marker and its preflight accepts a clean, detached
HEAD at a v* tag; bootstrap.sh --version picks the tag. Everything runs against a
fixture remote in tmp (FR_SRC_REMOTE + FR_SRC_DIR) whose install.sh is a stub that
records argv -- never the network, never the operator's real install.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

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


def _run_install(tmp_path: Path, repo: Path) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True, exist_ok=True)
    uv = home / "bin" / "uv"
    uv.write_text("#!/bin/sh\nexit 0\n")
    uv.chmod(0o755)
    env = {
        "HOME": str(home),
        "PATH": f"{home / 'bin'}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "VK_INSTALL_SKIP_PREFLIGHT": "",
    }
    return subprocess.run(
        ["bash", str(repo / "scripts" / "install.sh")], capture_output=True, text=True, env=env
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
    res = _run_install(tmp_path, repo)
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


def test_no_marked_final_falls_back_to_main_saying_so(tmp_path: Path) -> None:
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
    res, marker = _bootstrap(tmp_path, origin)
    assert res.returncode == 0, res.stderr
    assert marker.exists()
    assert "origin/main" in res.stdout and "No installable release" in res.stdout


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
    res = _run_install(tmp_path, repo)
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
    res = _run_install(tmp_path, clone)
    assert "Channel: main" in res.stdout, res.stdout + res.stderr
