"""Safety helpers: seal / secret / clip / scratch (spec 2026-10-22-fr-ops R10, §F)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fr.ops import helpers
from fr.ops.helpers import HelperError

PLAIN = b"PLAINTEXT-\xff\x00-bytes"


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    monkeypatch.setenv("TMPDIR", str(tmp))
    monkeypatch.setattr("tempfile.tempdir", None)
    return root


def _plaintext_anywhere(root: Path, needle: bytes) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and needle in p.read_bytes()]


def test_seal_success_replaces_the_target_with_out_bytes(repo: Path) -> None:
    target = repo / "secrets.enc"
    target.write_bytes(b"old")
    cipher = "python3 -c \"import sys; open(sys.argv[1],'wb').write(b'CIPHER-\\xff\\x00')\" {out}"
    rc = helpers.seal(cipher, target, PLAIN, repo_root=repo)
    assert rc == 0
    assert target.read_bytes() == b"CIPHER-\xff\x00"
    assert not _plaintext_anywhere(repo, PLAIN)
    assert [p.name for p in repo.iterdir() if p.name.startswith(".seal")] == []


def test_a_failing_encrypt_leaves_the_target_byte_identical_and_no_plaintext(repo: Path) -> None:
    target = repo / "secrets.enc"
    target.write_bytes(b"old-bytes")
    rc = helpers.seal(
        "cat {in} > /dev/null; echo half > {out}; exit 3", target, PLAIN, repo_root=repo
    )
    assert rc != 0
    assert target.read_bytes() == b"old-bytes"
    assert not _plaintext_anywhere(repo, PLAIN)
    assert not any(p.name.startswith(".seal") for p in repo.iterdir())


def test_a_missing_target_stays_missing_on_failure(repo: Path) -> None:
    target = repo / "new.enc"
    assert helpers.seal("exit 1", target, PLAIN, repo_root=repo) != 0
    assert not target.exists()


def test_an_empty_out_is_a_failure(repo: Path) -> None:
    target = repo / "secrets.enc"
    target.write_bytes(b"old")
    rc = helpers.seal("true", target, PLAIN, repo_root=repo)
    assert rc != 0 and target.read_bytes() == b"old"


def test_in_is_a_0600_file_outside_the_repo_holding_stdin(repo: Path, tmp_path: Path) -> None:
    target = repo / "t.enc"
    probe = (
        'test "$(stat -f %Lp {in} 2>/dev/null || stat -c %a {in})" = 600 && '
        "cmp -s {in} " + str(tmp_path / "expected") + " && echo C > {out}"
    )
    (tmp_path / "expected").write_bytes(PLAIN)
    assert helpers.seal(probe, target, PLAIN, repo_root=repo) == 0


def test_in_is_refused_when_tmpdir_is_inside_the_repo(repo: Path, monkeypatch) -> None:
    inside = repo / "scratch"
    inside.mkdir()
    monkeypatch.setenv("TMPDIR", str(inside))
    monkeypatch.setattr("tempfile.tempdir", None)
    with pytest.raises(HelperError, match="TMPDIR"):
        helpers.seal("echo x > {out}", repo / "t.enc", PLAIN, repo_root=repo)
    assert not _plaintext_anywhere(repo, PLAIN)


def test_substitutions_are_shell_quoted(repo: Path) -> None:
    target = repo / "a b; touch pwned.enc"
    rc = helpers.seal("echo {target} > {out}", target, PLAIN, repo_root=repo)
    assert rc == 0
    assert not (repo / "pwned.enc").exists()
    assert target.read_text().strip() == str(target)


def test_a_symlinked_target_is_refused_and_nothing_is_touched(repo: Path, tmp_path: Path) -> None:
    victim = tmp_path / "authorized_keys"
    victim.write_bytes(b"victim")
    link = repo / "t.enc"
    link.symlink_to(victim)
    with pytest.raises(HelperError, match="symlink"):
        helpers.seal("echo x > {out}", link, PLAIN, repo_root=repo)
    assert victim.read_bytes() == b"victim" and link.is_symlink()
    assert not _plaintext_anywhere(repo, PLAIN)


def test_a_symlinked_parent_dir_is_refused(repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "t.enc").write_bytes(b"victim")
    (repo / "d").symlink_to(outside)
    with pytest.raises(HelperError, match="symlink"):
        helpers.seal("echo x > {out}", repo / "d" / "t.enc", PLAIN, repo_root=repo)
    assert (outside / "t.enc").read_bytes() == b"victim"
    assert [p.name for p in outside.iterdir()] == ["t.enc"]


def test_an_absolute_target_outside_the_repo_is_refused(repo: Path, tmp_path: Path) -> None:
    victim = tmp_path / "elsewhere.enc"
    victim.write_bytes(b"victim")
    with pytest.raises(HelperError, match="outside the repo"):
        helpers.seal("echo x > {out}", victim, PLAIN, repo_root=repo)
    assert victim.read_bytes() == b"victim"


def test_a_dotdot_escape_is_refused(repo: Path, tmp_path: Path) -> None:
    victim = tmp_path / "elsewhere.enc"
    victim.write_bytes(b"victim")
    with pytest.raises(HelperError, match="outside the repo"):
        helpers.seal("echo x > {out}", repo / ".." / "elsewhere.enc", PLAIN, repo_root=repo)
    assert victim.read_bytes() == b"victim"


def test_sigterm_during_the_encrypt_command_removes_both_temps(repo: Path, tmp_path: Path) -> None:
    target = repo / "secrets.enc"
    target.write_bytes(b"old")
    env = {**os.environ, "TMPDIR": str(tmp_path / "tmp")}
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; from pathlib import Path; from fr.ops import helpers; "
         "sys.exit(helpers.seal('echo ready > ' + sys.argv[2] + '; sleep 30', "
         "Path(sys.argv[1]), b'SECRET', repo_root=Path(sys.argv[3])))",
         str(target), str(tmp_path / "ready"), str(repo)],
        env=env,
    )  # fmt: skip
    for _ in range(100):
        if (tmp_path / "ready").exists():
            break
        time.sleep(0.1)
    assert (tmp_path / "ready").exists()
    assert list((tmp_path / "tmp").iterdir()) and any(
        p.name.startswith(".seal") for p in repo.iterdir()
    )
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=15)
    assert proc.returncode != 0
    assert list((tmp_path / "tmp").iterdir()) == []
    assert not any(p.name.startswith(".seal") for p in repo.iterdir())
    assert target.read_bytes() == b"old"


def test_secret_passes_the_value_on_stdin_and_never_to_stdout(repo: Path, capfd) -> None:
    out = repo / "got"
    rc = helpers.secret("printf 's3cr3t-value\\n'", ["sh", "-c", f"cat > {out}"], repo_root=repo)
    assert rc == 0
    assert out.read_text() == "s3cr3t-value"
    captured = capfd.readouterr()
    assert "s3cr3t-value" not in captured.out + captured.err


def test_secret_with_a_failing_source_runs_nothing(repo: Path) -> None:
    out = repo / "ran"
    with pytest.raises(HelperError, match="could not be read"):
        helpers.secret("exit 4", ["sh", "-c", f"touch {out}"], repo_root=repo)
    assert not out.exists()


def test_clip_refuses_listing_the_tools_when_none_is_on_path(repo: Path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", str(repo))
    with pytest.raises(HelperError) as e:
        helpers.clip("echo v", repo_root=repo)
    for tool in ("pbcopy", "wl-copy", "xclip", "clip.exe"):
        assert tool in str(e.value)


def test_clip_sends_the_value_to_the_first_tool(repo: Path, monkeypatch, tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "pbcopy"
    fake.write_text(f"#!/bin/sh\ncat > {tmp_path}/clipped\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    assert helpers.clip("printf val", repo_root=repo) == 0
    assert (tmp_path / "clipped").read_text() == "val"


def test_scratch_runs_cleanup_on_success_and_failure(repo: Path) -> None:
    mark = repo / "cleaned"
    assert helpers.scratch(f"echo x >> {mark}", ["true"]) == 0
    assert mark.read_text() == "x\n"
    assert helpers.scratch(f"echo y >> {mark}", ["sh", "-c", "exit 5"]) == 5
    assert mark.read_text() == "x\ny\n"


def test_scratch_runs_cleanup_on_sigint(repo: Path, tmp_path: Path) -> None:
    mark = tmp_path / "cleaned"
    ready = tmp_path / "ready"
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; from fr.ops import helpers; "
         "sys.exit(helpers.scratch('touch ' + sys.argv[1], "
         "['sh', '-c', 'touch ' + sys.argv[2] + '; sleep 30']))",
         str(mark), str(ready)],
    )  # fmt: skip
    for _ in range(100):
        if ready.exists():
            break
        time.sleep(0.1)
    assert ready.exists()
    proc.send_signal(signal.SIGINT)
    proc.wait(timeout=15)
    assert mark.exists() and proc.returncode != 0


def test_helpers_name_no_tool() -> None:
    src = Path(helpers.__file__).read_text().lower()
    for name in ("sops", "kubectl", "kubeseal", "helm", "age-keygen", "gpg", "glab", "terraform"):
        assert name not in src, name


# --- the CLI ------------------------------------------------------------------


def test_cli_seal_refuses_outside_an_ops_profile(repo: Path, monkeypatch) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    monkeypatch.chdir(repo)
    res = CliRunner().invoke(
        app, ["ops", "seal", "--encrypt", "echo c > {out}", "--target", "t.enc"], input=b"x"
    )
    assert res.exit_code == 2 and "fr isolation up --profile" in res.output
    assert not (repo / "t.enc").exists()


def test_cli_seal_in_an_ops_profile(repo: Path, monkeypatch) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    monkeypatch.chdir(repo)
    monkeypatch.setattr("fr.ops.profile.in_ops_profile", lambda *a, **k: True)
    ok = CliRunner().invoke(
        app,
        ["ops", "seal", "--encrypt", "cat {in} | tr a-z A-Z > {out}", "--target", "t.enc"],
        input=b"abc",
    )
    assert ok.exit_code == 0, ok.output
    assert (repo / "t.enc").read_bytes() == b"ABC"
    bad = CliRunner().invoke(
        app, ["ops", "seal", "--encrypt", "exit 7", "--target", "t.enc"], input=b"abc"
    )
    assert bad.exit_code == 7 and (repo / "t.enc").read_bytes() == b"ABC"


def test_cli_scratch_and_secret(repo: Path, monkeypatch) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    monkeypatch.chdir(repo)
    res = CliRunner().invoke(
        app, ["ops", "scratch", "--cleanup", "touch gone", "--", "sh", "-c", "exit 4"]
    )
    assert res.exit_code == 4 and (repo / "gone").exists()
    res = CliRunner().invoke(
        app, ["ops", "secret", "--from", "echo v", "--", "sh", "-c", "cat > got"]
    )
    assert res.exit_code == 0 and (repo / "got").read_text() == "v"
