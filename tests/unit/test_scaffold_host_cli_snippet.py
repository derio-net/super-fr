"""The rendered glab/tea install snippet, EXECUTED under `sh` (gh#576, spec §3.B).

devcontainer runs `postCreateCommand` with `/bin/sh -c` — dash on the Ubuntu
base image — so the snippet is exercised as a real POSIX-sh program with stub
`dpkg`/`uname`/`curl`/`sha256sum`/`tar`/`sudo` first on PATH, not asserted on
as a string. Every stub appends one line to $LOG, so the log is the record of
what the snippet actually ran, in order.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from fr.isolation.scaffold import (
    HOST_CLI_PINS,
    POST_CREATE,
    HostCliPin,
    render_host_cli_post_create,
    scaffold_profile,
)

_STUBS = {
    "dpkg": (
        '[ "$STUB_DPKG" = absent ] && exit 1\n'
        'echo "dpkg $*" >> "$LOG"\n'
        'printf "%s\\n" "$STUB_ARCH"\n'
    ),
    "uname": 'echo "uname $*" >> "$LOG"\nprintf "%s\\n" "$STUB_UNAME"\n',
    "curl": 'echo "curl $*" >> "$LOG"\nexit "${STUB_CURL_RC:-0}"\n',
    "sha256sum": (
        'printf "sha256sum %s | " "$*" >> "$LOG"\ncat >> "$LOG"\nexit "${STUB_SHA_RC:-0}"\n'
    ),
    "tar": 'echo "tar $*" >> "$LOG"\n',
    "sudo": 'echo "sudo $*" >> "$LOG"\n',
    # Stubbed so the tarball recipe's scratch dir never touches the host's real /tmp.
    "rm": 'echo "rm $*" >> "$LOG"\n',
    "mkdir": 'echo "mkdir $*" >> "$LOG"\n',
    "find": 'echo "find $*" >> "$LOG"\n',
    # POST_CREATE's own commands, for executing the whole postCreateCommand.
    "pipx": 'echo "pipx $*" >> "$LOG"\n',
    "uv": 'echo "uv $*" >> "$LOG"\n',
}


@pytest.fixture
def stubdir(tmp_path: Path) -> Path:
    d = tmp_path / "stubs"
    d.mkdir()
    for name, body in _STUBS.items():
        p = d / name
        p.write_text("#!/bin/sh\n" + body)
        p.chmod(0o755)
    return d


def _run(
    snippet: str, stubdir: Path, tmp_path: Path, **stub_env: str
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    log = tmp_path / "log"
    log.write_text("")
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)  # POST_CREATE runs a real `git config --global`; never the real ~
    env = {"PATH": f"{stubdir}:/usr/bin:/bin", "LOG": str(log), "HOME": str(home), **stub_env}
    res = subprocess.run(["sh", "-c", snippet], env=env, capture_output=True, text=True, timeout=30)
    return res, log.read_text().splitlines()


def _curl_lines(log: list[str]) -> list[str]:
    return [line for line in log if line.startswith("curl ")]


BACKENDS = sorted(HOST_CLI_PINS)


def test_the_pins_carry_exactly_amd64_and_arm64_for_gitlab_and_gitea() -> None:
    assert set(HOST_CLI_PINS) == {"gitlab", "gitea"}
    for pin in HOST_CLI_PINS.values():
        assert set(pin.assets) == {"amd64", "arm64"}
        for url, sha in pin.assets.values():
            assert url.startswith("https://")
            assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize(
    ("arch_env", "expect"),
    [
        ({"STUB_ARCH": "amd64"}, "amd64"),
        ({"STUB_ARCH": "arm64"}, "arm64"),
        ({"STUB_DPKG": "absent", "STUB_UNAME": "x86_64"}, "amd64"),
        ({"STUB_DPKG": "absent", "STUB_UNAME": "aarch64"}, "arm64"),
    ],
)
def test_each_arch_selects_its_own_asset_and_checksum(
    backend: str,
    arch_env: dict[str, str],
    expect: str,
    stubdir: Path,
    tmp_path: Path,
) -> None:
    pin = HOST_CLI_PINS[backend]
    url, sha = pin.assets[expect]
    other = "arm64" if expect == "amd64" else "amd64"
    other_url, other_sha = pin.assets[other]

    res, log = _run(render_host_cli_post_create(pin), stubdir, tmp_path, **arch_env)

    assert res.returncode == 0, res.stderr
    curls = _curl_lines(log)
    assert len(curls) == 1 and url in curls[0], log
    assert other_url not in "\n".join(log)
    sums = [line for line in log if line.startswith("sha256sum ")]
    assert len(sums) == 1 and sha in sums[0], log
    assert other_sha not in "\n".join(log)
    sudo = [line for line in log if line.startswith("sudo ")]
    assert len(sudo) == 1 and sudo[0].endswith(f"/usr/local/bin/{pin.name}"), log


@pytest.mark.parametrize("backend", BACKENDS)
def test_an_unsupported_arch_names_itself_and_never_downloads(
    backend: str, stubdir: Path, tmp_path: Path
) -> None:
    pin = HOST_CLI_PINS[backend]
    res, log = _run(render_host_cli_post_create(pin), stubdir, tmp_path, STUB_ARCH="s390x")

    assert res.returncode != 0
    assert "s390x" in res.stderr
    assert "supported: amd64 arm64" in res.stderr
    assert f"{pin.name} {pin.version}" in res.stderr
    assert _curl_lines(log) == [], log


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_failing_checksum_fails_the_snippet_and_installs_nothing(
    backend: str, stubdir: Path, tmp_path: Path
) -> None:
    pin = HOST_CLI_PINS[backend]
    res, log = _run(
        render_host_cli_post_create(pin), stubdir, tmp_path, STUB_ARCH="arm64", STUB_SHA_RC="1"
    )

    assert res.returncode != 0
    assert len(_curl_lines(log)) == 1
    assert not [line for line in log if line.startswith(("sudo ", "tar "))], log


@pytest.mark.parametrize("backend", BACKENDS)
def test_the_snippet_is_the_last_command_of_post_create(
    backend: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Its exit status is the postCreateCommand's status — nothing runs after it."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))  # the secrets env file lands under it
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    scaffold_profile(repo, "dev", "purpose", tools=[], secrets=[], backend=backend, commit=False)  # type: ignore[arg-type]
    config = json.loads((repo / ".devcontainer" / "dev" / "devcontainer.json").read_text())
    snippet = render_host_cli_post_create(HOST_CLI_PINS[backend])
    assert config["postCreateCommand"] == f"{POST_CREATE}; {snippet}"


def test_the_amd64_pins_are_unchanged_from_the_previous_release() -> None:
    """The amd64 sums predate this change; carrying them over must not move them."""
    assert HOST_CLI_PINS["gitlab"].assets["amd64"][1] == (
        "eb42f56eb1a789cf4f22aa5960ff0ef60cf1e7fc1295327501f9f59030d5ae2c"
    )
    assert HOST_CLI_PINS["gitea"].assets["amd64"][1] == (
        "be4ab135752825ab223cfa87d30e7f328312a24120b70176b67c1bd4aba19cc3"
    )
    assert os.path.basename(HOST_CLI_PINS["gitea"].assets["arm64"][0]) == "tea-0.14.2-linux-arm64"


def test_the_glab_tarball_installs_its_exact_path_from_a_dedicated_dir(
    stubdir: Path, tmp_path: Path
) -> None:
    """The release tarball carries `bin/glab` (checked 2026-09-23 with `tar -tzf`).

    Extracting into a fresh dedicated dir and installing that exact path means a
    stray `glab` elsewhere in a shared /tmp can never be the one installed (p5r-f2).
    """
    res, log = _run(
        render_host_cli_post_create(HOST_CLI_PINS["gitlab"]), stubdir, tmp_path, STUB_ARCH="arm64"
    )
    assert res.returncode == 0, res.stderr
    assert not [line for line in log if line.startswith("find ")], log
    tail = log[log.index(next(line for line in log if line.startswith("sha256sum "))) + 1 :]
    assert tail == [
        "rm -rf /tmp/glab-x",
        "mkdir -p /tmp/glab-x",
        "tar -xzf /tmp/glab.dl -C /tmp/glab-x",
        "sudo install -m 755 /tmp/glab-x/bin/glab /usr/local/bin/glab",
    ], log


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_failing_download_fails_the_snippet_before_verify_or_install(
    backend: str, stubdir: Path, tmp_path: Path
) -> None:
    res, log = _run(
        render_host_cli_post_create(HOST_CLI_PINS[backend]),
        stubdir,
        tmp_path,
        STUB_ARCH="amd64",
        STUB_CURL_RC="22",
    )
    assert res.returncode != 0
    assert len(_curl_lines(log)) == 1
    assert not [line for line in log if line.startswith(("sha256sum ", "sudo ", "tar "))], log


@pytest.mark.parametrize(("arch", "ok"), [("s390x", False), ("arm64", True)])
def test_the_whole_post_create_command_carries_the_snippets_status(
    arch: str,
    ok: bool,
    stubdir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Executed, not string-compared: POST_CREATE's `|| true`s must not swallow it (p5r-f3)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    scaffold_profile(repo, "dev", "purpose", tools=[], secrets=[], backend="gitlab", commit=False)
    command = json.loads((repo / ".devcontainer" / "dev" / "devcontainer.json").read_text())[
        "postCreateCommand"
    ]

    res, log = _run(command, stubdir, tmp_path, STUB_ARCH=arch)

    assert [line.split()[0] for line in log][:2] == ["pipx", "uv"], log
    if ok:
        assert res.returncode == 0, res.stderr
    else:
        assert res.returncode != 0
        assert "glab 1.107.0: unsupported architecture 's390x'" in res.stderr
        assert _curl_lines(log) == [], log


@pytest.mark.parametrize(("kind", "member"), [("tarball", ""), ("binary", "bin/x")])
def test_a_tarball_pin_must_name_its_member_and_only_a_tarball_may(kind: str, member: str) -> None:
    with pytest.raises(ValueError, match="tarball_member"):
        HostCliPin(name="x", version="1", assets={}, kind=kind, tarball_member=member)  # type: ignore[arg-type]
