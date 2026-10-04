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
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"

# A uv stub that behaves like uv where it matters here: honours UV_TOOL_DIR /
# UV_TOOL_BIN_DIR, and `tool install --force` DELETES the env, takes a while,
# then rebuilds it and links the entry point — so a naive install leaves `fr`
# absent for the rebuild. Every default-dir install appends its start/end to
# $UV_STUB_STATE/installs so a test can see whether two installs overlapped.
_UV_STUB = r"""#!/bin/sh
tooldir="${UV_TOOL_DIR:-$UV_STUB_TOOLDIR}"
bindir="${UV_TOOL_BIN_DIR:-$UV_STUB_BINDIR}"
case "$1 $2" in
"tool dir")
  if [ "$3" = "--bin" ]; then printf '%s\n' "$bindir"; else printf '%s\n' "$tooldir"; fi
  ;;
"tool install")
  [ -z "$UV_TOOL_DIR" ] && echo "start $$ $(date +%s.%N 2>/dev/null || date +%s)" >> "$UV_STUB_STATE/installs"
  rm -rf "$tooldir/fr"
  sleep "${UV_STUB_BUILD_SECONDS:-0}"
  mkdir -p "$tooldir/fr/bin" "$bindir"
  printf '#!/bin/sh\necho "fr 9.9.9"\n' > "$tooldir/fr/bin/fr"
  chmod +x "$tooldir/fr/bin/fr"
  ln -s "$tooldir/fr/bin/fr" "$bindir/.fr.uvtmp.$$"
  mv -f "$bindir/.fr.uvtmp.$$" "$bindir/fr" 2>/dev/null \
    || { rm -f "$bindir/fr"; mv "$bindir/.fr.uvtmp.$$" "$bindir/fr"; }
  [ -z "$UV_TOOL_DIR" ] && echo "end $$ $(date +%s.%N 2>/dev/null || date +%s)" >> "$UV_STUB_STATE/installs"
  echo "Installed 1 executable: fr"
  ;;
"tool uninstall")
  rm -rf "$tooldir/fr" "$bindir/fr"
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
            _, err = p.communicate(timeout=60)
        finally:
            holder.send_signal(signal.SIGKILL)
            holder.wait()
        assert p.returncode != 0
        assert str(lock) in err and str(holder.pid) in err
        assert lock.exists(), "a timed-out waiter must not remove a live holder's lock"
        assert not (sandbox["state"] / "installs").exists(), "nothing may be installed"

    def test_a_dead_holders_lock_is_reclaimed(self, sandbox: dict[str, Path]) -> None:
        lock = sandbox["home"] / ".cache" / "fr" / "install.lock"
        lock.mkdir(parents=True)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(f"{dead.pid}\n")
        p = _install(sandbox, FR_INSTALL_LOCK_TIMEOUT="5")
        _, err = p.communicate(timeout=60)
        assert p.returncode == 0, err
        assert "stale" in err


class TestAtomicReplacement:
    def test_current_link_is_never_missing_while_it_is_repointed(self, tmp_path: Path) -> None:
        """`ln -sfn` unlinks then creates; the swap must be a rename, so a
        concurrent reader always resolves `current` to some version."""
        script = INSTALL_SH.read_text()
        assert "ln -sfn" not in script, "a live link must be swapped with atomic_symlink"
        for v in ("1.0.0", "2.0.0"):
            (tmp_path / v / "hooks").mkdir(parents=True)
            (tmp_path / v / "hooks" / "h.sh").write_text("exit 0\n")
        link = tmp_path / "current"
        link.symlink_to("1.0.0")
        probe = link / "hooks" / "h.sh"
        stop = threading.Event()
        misses = []

        def watch() -> None:
            while not stop.is_set():
                if not probe.exists():
                    misses.append(1)

        t = threading.Thread(target=watch)
        t.start()
        try:
            flips = "for i in $(seq 1 200); do atomic_symlink 2.0.0 \"$L\"; atomic_symlink 1.0.0 \"$L\"; done"
            fn = "eval \"$(sed -n '/^atomic_symlink() {/,/^}/p' \"$S\")\""
            subprocess.run(
                ["bash", "-c", f"set -euo pipefail; {fn}; {flips}"],
                env={"S": str(INSTALL_SH), "L": str(link), "PATH": "/usr/bin:/bin"},
                check=True,
            )
        finally:
            stop.set()
            t.join()
        assert link.is_symlink() and os.readlink(link) == "1.0.0"
        assert not misses, f"`current` was missing at {len(misses)} probe instants"

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
        assert not failures, f"{len(failures)}/{len(calls)} fr calls failed mid-install: {failures[:3]}"
        assert os.readlink(fr) == str(sandbox["tooldir"] / "fr" / "bin" / "fr"), (
            "after the install, fr must be uv's own env again, not the staged copy"
        )
        assert not (sandbox["home"] / ".cache" / "fr" / "install-stage").exists()
