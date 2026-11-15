"""fr-binary-pin.sh — SessionStart pins the hooks' `fr` for the shell (super-fr#746).

Claude Code sources `$CLAUDE_ENV_FILE` before every Bash command, and
`~/.zshenv` rebuilds PATH but leaves other variables alone — so an exported
`FR_HARNESS_FR` is the one channel the hooks and the shell both see. The hook
must never break session start: every missing precondition is a silent exit 0.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "fr-binary-pin.sh"

# A path with a space and a single quote: the export line must survive both.
IDENTITY = "9.9.9 /tmp/it's here/site-packages/fr"


def _fake_fr(bin_dir: Path, body: str) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    fake = bin_dir / "fr"
    fake.write_text(f"#!/bin/sh\n{body}\n")
    fake.chmod(0o755)


def run_hook(path: str, env_file: Path | None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_ENV_FILE"}
    env["PATH"] = path
    if env_file is not None:
        env["CLAUDE_ENV_FILE"] = str(env_file)
    return subprocess.run(
        ["/bin/bash", str(SCRIPT)],
        input='{"hook_event_name":"SessionStart"}',
        capture_output=True,
        text=True,
        env=env,
    )


def _sourced_pin(env_file: Path) -> str:
    out = subprocess.run(
        ["/bin/bash", "-c", f'. "{env_file}"; printf %s "$FR_HARNESS_FR"'],
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    return out.stdout


def test_the_hook_exports_the_fr_it_resolved(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    _fake_fr(bin_dir, f'[ "$1" = --identity ] && printf \'%s\\n\' "{IDENTITY}"')
    env_file = tmp_path / "env.sh"
    result = run_hook(f"{bin_dir}:/usr/bin:/bin", env_file)
    assert result.returncode == 0, result.stderr
    assert _sourced_pin(env_file) == IDENTITY


def test_the_hook_appends_and_leaves_earlier_exports_alone(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    _fake_fr(bin_dir, f"printf '%s\\n' \"{IDENTITY}\"")
    env_file = tmp_path / "env.sh"
    env_file.write_text("export SOMETHING_ELSE=1\n")
    assert run_hook(f"{bin_dir}:/usr/bin:/bin", env_file).returncode == 0
    assert env_file.read_text().startswith("export SOMETHING_ELSE=1\n")


def test_no_env_file_is_a_silent_no_op(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    _fake_fr(bin_dir, f"printf '%s\\n' \"{IDENTITY}\"")
    result = run_hook(f"{bin_dir}:/usr/bin:/bin", None)
    assert result.returncode == 0
    assert result.stdout == ""


def test_no_fr_writes_nothing(tmp_path: Path) -> None:
    env_file = tmp_path / "env.sh"
    result = run_hook("/usr/bin:/bin", env_file)
    assert result.returncode == 0
    assert not env_file.exists() or env_file.read_text() == ""


def test_an_fr_too_old_to_know_identity_writes_nothing(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    _fake_fr(bin_dir, "echo 'No such option: --identity' >&2; exit 2")
    env_file = tmp_path / "env.sh"
    result = run_hook(f"{bin_dir}:/usr/bin:/bin", env_file)
    assert result.returncode == 0
    assert not env_file.exists() or env_file.read_text() == ""


def test_the_pin_reaches_every_pinned_sibling_hook_file(tmp_path: Path) -> None:
    """R7 (#1259): Claude Code sources every sessionstart-hook-*.sh in the session-env
    dir; a later hook's old pin must not outlive the new one. Only plain files that
    already hold a pin are touched, and nothing new is created."""
    bin_dir = tmp_path / "bin"
    _fake_fr(bin_dir, f"printf '%s\\n' \"{IDENTITY}\"")
    session = tmp_path / "session-env"
    session.mkdir()
    old = "export FR_HARNESS_FR='old 1.0.0 /x'\n"
    (session / "sessionstart-hook-8.sh").write_text(old)
    other = "export A=1\n" + old + "export B=2\n"
    (session / "sessionstart-hook-3.sh").write_text(other)
    plain = "export C=3\n"
    (session / "sessionstart-hook-4.sh").write_text(plain)
    outside = tmp_path / "outside.sh"
    outside.write_text(old)
    (session / "sessionstart-hook-9.sh").symlink_to(outside)
    env_file = session / "sessionstart-hook-5.sh"
    before = sorted(p.name for p in session.iterdir())

    result = run_hook(f"{bin_dir}:/usr/bin:/bin", env_file)
    assert result.returncode == 0, result.stderr
    for name in ("sessionstart-hook-8.sh", "sessionstart-hook-3.sh", "sessionstart-hook-5.sh"):
        assert _sourced_pin(session / name) == IDENTITY
    assert (session / "sessionstart-hook-3.sh").read_text().startswith(other)
    assert (session / "sessionstart-hook-4.sh").read_text() == plain
    assert outside.read_text() == old
    assert sorted(p.name for p in session.iterdir()) == sorted([*before, env_file.name])


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the read-only mode (review p3-r3)")
def test_an_unwritable_sibling_is_skipped_and_the_hook_still_exits_zero(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    _fake_fr(bin_dir, f"printf '%s\\n' \"{IDENTITY}\"")
    session = tmp_path / "session-env"
    session.mkdir()
    locked = session / "sessionstart-hook-1.sh"
    locked.write_text("export FR_HARNESS_FR='old 1.0.0 /x'\n")
    locked.chmod(0o444)
    env_file = session / "sessionstart-hook-2.sh"
    try:
        result = run_hook(f"{bin_dir}:/usr/bin:/bin", env_file)
    finally:
        locked.chmod(0o644)
    assert result.returncode == 0, result.stderr
    assert _sourced_pin(env_file) == IDENTITY


def test_our_own_already_pinned_file_gets_the_pin_once(tmp_path: Path) -> None:
    """review p3-r1: the loop skips $CLAUDE_ENV_FILE, so a resume at the same hook
    position appends one line, not two."""
    bin_dir = tmp_path / "bin"
    _fake_fr(bin_dir, f"printf '%s\\n' \"{IDENTITY}\"")
    session = tmp_path / "session-env"
    session.mkdir()
    env_file = session / "sessionstart-hook-5.sh"
    env_file.write_text("export FR_HARNESS_FR='old 1.0.0 /x'\n")
    assert run_hook(f"{bin_dir}:/usr/bin:/bin", env_file).returncode == 0
    lines = env_file.read_text().splitlines()
    assert len(lines) == 2 and _sourced_pin(env_file) == IDENTITY


def test_only_a_line_starting_with_the_exact_export_counts_as_a_pin(tmp_path: Path) -> None:
    """review p3-r3: a lookalike variable or an indented line is not fr's pin."""
    bin_dir = tmp_path / "bin"
    _fake_fr(bin_dir, f"printf '%s\\n' \"{IDENTITY}\"")
    session = tmp_path / "session-env"
    session.mkdir()
    lookalike = "export FR_HARNESS_FRX='1'\n  export FR_HARNESS_FR='indented'\n"
    (session / "sessionstart-hook-1.sh").write_text(lookalike)
    assert run_hook(f"{bin_dir}:/usr/bin:/bin", session / "sessionstart-hook-2.sh").returncode == 0
    assert (session / "sessionstart-hook-1.sh").read_text() == lookalike
