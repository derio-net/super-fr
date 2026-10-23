"""install.sh is serialised and replaces live state atomically (gh#938).

Root cause (journal debug/2026-10-04-post-merge-install-lock): install.sh
mutated everything a running session executes in place, with no mutual
exclusion — the plugin cache's `current` link via `ln -sfn` (unlink, then
create: a hook fired in the gap exits 127, the only route to a Stop hook
*error*), the `fr` tool env via `uv tool install --force` (fr absent while uv
rebuilds it), and fixed `<file>.tmp` sidecars that two concurrent installs
share. A day of releases, each followed by a hand, watcher or `post_merge`
install, overlapped them.

Every test runs install.sh against a fake HOME with a `uv` stub, so nothing
touches the real user directory or the real uv.

**Why one install at a time (gh#1223).** Each sandboxed install rsyncs the whole
tracked tree (~166 MB, 3300 files, `.git`/`.venv` excluded) twice — the
marketplace copy and the per-plugin cache sync — and eight of those running at
once while the rest of the suite saturates the disk pushed the last two tests of
`TestInstallLock` past their 60 s bound under `pytest -n auto` on a 12-core host
(never serially, where the file is 8 passed in ~28 s). The file therefore holds
one cross-process advisory lock across each test, so its installs are the only
ones on the machine: peak load is bounded without weakening an assertion. The
60 s bounds become 180 s for the same reason the issue gives — it is a sandbox,
not a latency assertion — so a genuine hang is still caught, on a much quieter
disk. `fcntl.flock` degrades to no lock on a host-share FUSE mount (see
`tests/conftest.py`'s `native_herdr_cache` note); the raised bound is the
backstop there.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"

INSTALL_BOUND_S = 180
"""A sandbox install's hard bound (gh#1223). Serially the whole file is 8 passed
in ~28 s; on a loaded machine the copy — not the install logic — is what grows,
so this catches a hang without re-creating the 60 s flake."""

# A uv stub that behaves like uv where it matters here: honours UV_TOOL_DIR /
# UV_TOOL_BIN_DIR, and `tool install --force` DELETES the env, takes a while,
# then rebuilds it and links the entry point — so a naive install leaves `fr`
# absent for the rebuild. Every default-dir install appends its start/end to
# $UV_STUB_STATE/installs so a test can see whether two installs overlapped.
_UV_STUB = r"""#!/bin/sh
if [ "$1 $2 $3" = "tool install --help" ]; then echo "      --with-executables-from <X>"; exit 0; fi
tooldir="${UV_TOOL_DIR:-$UV_STUB_TOOLDIR}"
bindir="${UV_TOOL_BIN_DIR:-$UV_STUB_BINDIR}"
case "$1 $2" in
"tool dir")
  if [ "$3" = "--bin" ]; then printf '%s\n' "$bindir"; else printf '%s\n' "$tooldir"; fi
  ;;
"tool install")
  log="$UV_STUB_STATE/installs"
  [ -z "$UV_TOOL_DIR" ] && echo "start $$ $(date +%s.%N)" >> "$log"
  # Like uv: --force first removes the entry point its receipt recorded —
  # whatever that path points at by now — and links the new one at the end.
  [ -f "$tooldir/fr/receipt" ] && rm -f "$(cat "$tooldir/fr/receipt")"
  rm -rf "$tooldir/fr"
  sleep "${UV_STUB_BUILD_SECONDS:-0}"
  mkdir -p "$tooldir/fr/bin" "$bindir"
  printf '#!/bin/sh\necho "fr 9.9.9"\n' > "$tooldir/fr/bin/fr"
  chmod +x "$tooldir/fr/bin/fr"
  printf '%s\n' "$bindir/fr" > "$tooldir/fr/receipt"
  ln -s "$tooldir/fr/bin/fr" "$bindir/.fr.uvtmp.$$"
  mv -f "$bindir/.fr.uvtmp.$$" "$bindir/fr" 2>/dev/null \
    || { rm -f "$bindir/fr"; mv "$bindir/.fr.uvtmp.$$" "$bindir/fr"; }
  [ -z "$UV_TOOL_DIR" ] && echo "end $$ $(date +%s.%N)" >> "$log"
  echo "Installed 1 executable: fr"
  ;;
"tool uninstall")
  [ -f "$tooldir/fr/receipt" ] && rm -f "$(cat "$tooldir/fr/receipt")"
  rm -rf "$tooldir/fr"
  ;;
*)
  exit 0
  ;;
esac
"""


@pytest.fixture()
def sandbox(tmp_path: Path) -> dict[str, Path]:
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    vk = home / "bin" / "vibe-kanban-mcp"
    vk.write_text("#!/bin/sh\necho stub\n")
    vk.chmod(0o755)
    plugins = home / ".claude" / "plugins"
    plugins.mkdir(parents=True)
    (plugins / "installed_plugins.json").write_text(json.dumps({"plugins": {}, "version": 1}))
    (home / ".claude" / "settings.json").write_text("{}")
    uv = home / "bin" / "uv"
    uv.write_text(_UV_STUB)
    uv.chmod(0o755)
    state = tmp_path / "uv-state"
    state.mkdir()
    return {
        "home": home,
        "state": state,
        "tooldir": home / ".local" / "share" / "uv" / "tools",
        "bindir": home / ".local" / "bin",
    }


def _env(sb: dict[str, Path], **extra: str) -> dict[str, str]:
    return {
        "HOME": str(sb["home"]),
        "PATH": f"{sb['home'] / 'bin'}:/usr/bin:/bin:/usr/local/bin",
        "VK_INSTALL_SKIP_PREFLIGHT": "1",
        "UV_STUB_TOOLDIR": str(sb["tooldir"]),
        "UV_STUB_BINDIR": str(sb["bindir"]),
        "UV_STUB_STATE": str(sb["state"]),
        "FR_INSTALL_RETRY_SLEEP": "0",
        "FR_INSTALL_DRAIN_SECONDS": "0",
        **extra,
    }


def _install(sb: dict[str, Path], **extra: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        ["bash", str(INSTALL_SH)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_env(sb, **extra),
    )


_INSTALL_GATE = Path(tempfile.gettempdir()) / "fr-install-atomic-tests.lock"
"""One machine-local advisory lock every worker running this file shares, so the
eight sandboxed installs never overlap (gh#1223, module docstring)."""


@pytest.fixture(autouse=True)
def _one_install_at_a_time() -> Iterator[None]:
    """Hold the cross-process gate for the whole test: the installs inside it are
    what saturate the disk, so waiting for them to start is not enough."""
    with _INSTALL_GATE.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _intervals(state: Path) -> list[tuple[float, float]]:
    starts: dict[str, float] = {}
    out = []
    for line in (state / "installs").read_text().splitlines():
        kind, pid, ts = line.split()
        if kind == "start":
            starts[pid] = float(ts)
        else:
            out.append((starts[pid], float(ts)))
    return sorted(out)


class TestInstallLock:
    def test_overlapping_installs_serialise(self, sandbox: dict[str, Path]) -> None:
        """Two installs started together both succeed, and their fr rebuilds
        never overlap: the second waits for the machine-wide lock."""
        a = _install(sandbox, UV_STUB_BUILD_SECONDS="1")
        time.sleep(0.2)
        b = _install(sandbox, UV_STUB_BUILD_SECONDS="1")
        out_a, err_a = a.communicate(timeout=120)
        out_b, err_b = b.communicate(timeout=120)
        assert a.returncode == 0, err_a
        assert b.returncode == 0, err_b
        (s1, e1), (s2, e2) = _intervals(sandbox["state"])
        assert s2 >= e1, f"installs overlapped: {(s1, e1)} vs {(s2, e2)}"
        assert "Another super-fr install is running" in err_a + err_b
        assert not (sandbox["home"] / ".cache" / "fr" / "install.lock").exists(), (
            "the lock must be released when the install finishes"
        )

    def test_lock_wait_times_out_with_a_clear_message(self, sandbox: dict[str, Path]) -> None:
        lock = sandbox["home"] / ".cache" / "fr" / "install.lock"
        lock.mkdir(parents=True)
        holder = subprocess.Popen(["sleep", "60"])
        try:
            (lock / "pid").write_text(f"{holder.pid}\n")
            p = _install(sandbox, FR_INSTALL_LOCK_TIMEOUT="1")
            _, err = p.communicate(timeout=INSTALL_BOUND_S)
        finally:
            holder.send_signal(signal.SIGKILL)
            holder.wait()
        assert p.returncode != 0
        assert str(lock) in err and str(holder.pid) in err
        assert lock.exists(), "a timed-out waiter must not remove a live holder's lock"
        assert not (sandbox["state"] / "installs").exists(), "nothing may be installed"

    def test_a_lock_whose_holder_died_before_writing_its_pid_is_reclaimed(
        self, sandbox: dict[str, Path]
    ) -> None:
        lock = sandbox["home"] / ".cache" / "fr" / "install.lock"
        lock.mkdir(parents=True)
        os.utime(lock, (1, 1))  # no pid file, long after its mkdir
        p = _install(sandbox, FR_INSTALL_LOCK_TIMEOUT="5")
        _, err = p.communicate(timeout=INSTALL_BOUND_S)
        assert p.returncode == 0, err
        assert "stale" in err

    def test_a_dead_holders_lock_is_reclaimed(self, sandbox: dict[str, Path]) -> None:
        lock = sandbox["home"] / ".cache" / "fr" / "install.lock"
        lock.mkdir(parents=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(f"{dead.pid}\n")
        p = _install(sandbox, FR_INSTALL_LOCK_TIMEOUT="5")
        _, err = p.communicate(timeout=INSTALL_BOUND_S)
        assert p.returncode == 0, err
        assert "stale" in err


def _checkout(tmp_path: Path) -> Path:
    """A copy of the tracked tree, so a test can move the plugin version."""
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"], capture_output=True, check=True
    ).stdout.decode()
    checkout = tmp_path / "checkout"
    for rel in filter(None, tracked.split("\0")):
        src = REPO_ROOT / rel
        if src.is_file() and not rel.startswith(("docs/", "tests/")):
            (checkout / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, checkout / rel)
    return checkout


def _set_version(checkout: Path, version: str) -> None:
    for plugin in ("super-fr", "super-fr-dispatch"):
        pj = checkout / "plugins" / plugin / ".claude-plugin" / "plugin.json"
        data = json.loads(pj.read_text())
        data["version"] = version
        pj.write_text(json.dumps(data))


class TestSessionHeldPluginPath:
    """The error the operator actually hit: Claude Code resolves installPath
    when it loads the plugin and runs that session's hooks from the resolved
    path. Three releases later the prune had deleted it ("Plugin directory
    does not exist" on every hook)."""

    def test_a_sessions_resolved_plugin_path_survives_later_releases(
        self, sandbox: dict[str, Path], tmp_path: Path
    ) -> None:
        checkout = _checkout(tmp_path)
        install_sh = checkout / "scripts" / "install.sh"
        entry_id = "super-fr@derio-net--super-fr"
        installed = sandbox["home"] / ".claude" / "plugins" / "installed_plugins.json"

        def install(version: str) -> None:
            _set_version(checkout, version)
            r = subprocess.run(
                ["bash", str(install_sh)], capture_output=True, text=True, env=_env(sandbox)
            )
            assert r.returncode == 0, r.stderr

        install("1.0.0")
        install_path = json.loads(installed.read_text())["plugins"][entry_id][0]["installPath"]
        held = Path(os.path.realpath(install_path))  # what a session runs hooks from
        hook = held / "hooks" / "fr-run-idle-guard.sh"
        assert hook.is_file()

        for version in ("1.0.1", "1.0.2", "1.0.3"):
            # Releases are hours apart; `rsync -a` copies the source's mtimes,
            # so without this every dir ties and recency is a coin toss.
            os.utime(held, (1, 1))
            install(version)
            assert hook.is_file(), f"the session's hook path vanished after installing {version}"

        assert json.loads((held / ".claude-plugin" / "plugin.json").read_text())["version"] == (
            "1.0.3"
        ), "the held path must carry the newest plugin, not a frozen old one"

    def test_the_move_off_the_versioned_layout_keeps_held_version_dirs(
        self, sandbox: dict[str, Path], tmp_path: Path
    ) -> None:
        """A session started before the upgrade holds some `<version>/`; the
        first new-style install must delete none of them, and a week later
        they go. A dir's mtime is its SOURCE's (rsync -a), so an old mtime says
        nothing about when it was installed or whether a session holds it."""
        cache = sandbox["home"] / ".claude" / "plugins" / "cache" / "derio-net--super-fr"
        for plugin in ("super-fr", "super-fr-dispatch"):
            (cache / plugin / "0.9.0" / "hooks").mkdir(parents=True)
            (cache / plugin / "0.8.0").mkdir()
            os.utime(cache / plugin / "0.9.0", (1, 1))
            os.utime(cache / plugin / "0.8.0", (1, 1))
            (cache / plugin / "current").symlink_to("0.9.0")

        r = _install(sandbox)
        _, err = r.communicate(timeout=120)
        assert r.returncode == 0, err

        live = cache / "super-fr" / "current"
        assert live.is_dir() and not live.is_symlink()
        assert (live / "hooks" / "fr-run-idle-guard.sh").is_file()
        for legacy in ("0.9.0", "0.8.0"):
            assert (cache / "super-fr" / legacy).is_dir(), f"{legacy} must outlive the move"
            os.utime(cache / "super-fr" / legacy, (1, 1))  # a week on
        r = _install(sandbox)
        _, err = r.communicate(timeout=120)
        assert r.returncode == 0, err
        assert not (cache / "super-fr" / "0.9.0").exists()
        assert not (cache / "super-fr" / "0.8.0").exists()
        assert sorted(p.name for p in (cache / "super-fr").iterdir()) == ["current"]


class TestAtomicReplacement:
    def test_a_live_link_is_repointed_by_rename(self, tmp_path: Path) -> None:
        """`ln -sfn` unlinks then creates; `atomic_symlink` (used for the `fr`
        on PATH, a link to a file) is a rename, so a reader resolves it to one
        target or the other. On Linux that is exact. On macOS APFS a lookup can
        still race a rename (measured: 60 misses in 300 os.replace swaps), so
        there only the end state is checked — which is why the plugin path is
        a directory, not a link."""
        commands = [ln.strip() for ln in INSTALL_SH.read_text().splitlines()]
        assert not [c for c in commands if c.startswith("ln -sfn")], (
            "a live link must be swapped with atomic_symlink"
        )
        for v in ("1.0.0", "2.0.0"):
            (tmp_path / v).write_text("#!/bin/sh\n")  # an entry point: a file
        link = tmp_path / "fr"
        link.symlink_to("1.0.0")
        probe = link
        stop = threading.Event()
        misses = []

        def watch() -> None:
            while not stop.is_set():
                if not probe.exists():
                    misses.append(1)

        t = threading.Thread(target=watch)
        t.start()
        try:
            flips = (
                'for i in $(seq 1 200); do atomic_symlink 2.0.0 "$L"; '
                'atomic_symlink 1.0.0 "$L"; done'
            )
            fn = 'eval "$(sed -n \'/^atomic_symlink() {/,/^}/p\' "$S")"'
            subprocess.run(
                ["bash", "-c", f"set -euo pipefail; {fn}; {flips}"],
                env={"S": str(INSTALL_SH), "L": str(link), "PATH": "/usr/bin:/bin"},
                check=True,
            )
        finally:
            stop.set()
            t.join()
        assert link.is_symlink() and os.readlink(link) == "1.0.0"
        if sys.platform != "darwin":
            assert not misses, f"the link was missing at {len(misses)} probe instants"

    def test_fr_stays_runnable_throughout_a_reinstall(self, sandbox: dict[str, Path]) -> None:
        """A `fr` call made while an install rebuilds the tool env finds the
        old or the new fr, never neither (the stub's rebuild takes 1 s)."""
        first = _install(sandbox)
        _, err = first.communicate(timeout=120)
        assert first.returncode == 0, err
        fr = sandbox["bindir"] / "fr"
        assert subprocess.run([str(fr)], capture_output=True).returncode == 0

        stop = threading.Event()
        failures: list[str] = []
        calls = []

        def call_fr() -> None:
            while not stop.is_set():
                try:
                    r = subprocess.run([str(fr)], capture_output=True, text=True)
                except OSError as exc:  # the entry point itself was missing
                    calls.append(-1)
                    failures.append(str(exc)[:120])
                    continue
                calls.append(r.returncode)
                if r.returncode != 0:
                    failures.append(r.stderr.strip()[:120])

        t = threading.Thread(target=call_fr)
        t.start()
        try:
            p = _install(sandbox, UV_STUB_BUILD_SECONDS="1")
            _, err = p.communicate(timeout=120)
        finally:
            stop.set()
            t.join()
        assert p.returncode == 0, err
        assert len(calls) > 20, "the probe must have run across the install"
        assert not failures, (
            f"{len(failures)}/{len(calls)} fr calls failed mid-install: {failures[:3]}"
        )
        assert os.readlink(fr) == str(sandbox["tooldir"] / "fr" / "bin" / "fr"), (
            "after the install, fr must be uv's own env again, not the staged copy"
        )
        # The stage outlives its install (an fr may still be loading from it)
        # and goes at the end of the next one: never more than one is left.
        stages = sandbox["home"] / ".cache" / "fr" / "install-stage"
        assert len(list(stages.iterdir())) <= 1
