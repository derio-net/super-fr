"""fr-acceptance-nag.sh — SessionStart hook injects open acceptance debt.

Spec §6.1: fr-enabled repos surface open unwired/not-implemented rows into
every agent session (capped — counts + top-3 oldest). The hook must NEVER
break session start: any missing precondition is a silent exit 0.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit.acceptance_helpers import make_repo, row, write_fragments, write_matrix_fragments

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="hook scripts require jq")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "fr-acceptance-nag.sh"


def run_hook(
    cwd: Path, event: str = "SessionStart", *, is_first_turn: bool | None = None
) -> subprocess.CompletedProcess[str]:
    payload: dict[str, object] = {
        "session_id": "sess-1",
        "cwd": str(cwd),
        "hook_event_name": event,
    }
    if is_first_turn is not None:
        payload["extra"] = {"is_first_turn": is_first_turn}
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ},
    )


def _git(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)


def test_nag_emits_capped_debt(tmp_path: Path) -> None:
    rows = row(id="green") + "".join(row(id=f"debt-{i}", status="unwired") for i in range(5))
    root = make_repo(tmp_path, rows, git=False)
    _git(root)
    result = run_hook(root)
    assert result.returncode == 0, result.stderr
    assert "acceptance" in result.stdout
    assert "debt-0" in result.stdout
    assert "debt-2" in result.stdout
    assert "debt-4" not in result.stdout  # capped at 3
    assert "+2 more" in result.stdout


def test_nag_emits_hermes_json_context_on_first_llm_call(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(id="debt", status="unwired"), git=False)
    _git(root)

    result = run_hook(root, event="pre_llm_call", is_first_turn=True)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "Acceptance debt" in payload["context"]
    assert "debt" in payload["context"]


def test_nag_is_silent_after_hermes_first_turn(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(id="debt", status="unwired"), git=False)
    _git(root)

    result = run_hook(root, event="pre_llm_call", is_first_turn=False)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_nag_silent_on_zero_debt(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(id="green"), git=False)
    _git(root)
    result = run_hook(root)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_nag_silent_without_matrix(tmp_path: Path) -> None:
    root = tmp_path / "bare"
    root.mkdir()
    _git(root)
    result = run_hook(root)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_nag_silent_outside_git(tmp_path: Path) -> None:
    result = run_hook(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_hook_registered_for_session_start() -> None:
    hooks = json.loads((REPO_ROOT / "plugins" / "super-fr" / "hooks" / "hooks.json").read_text())
    session_start = hooks["hooks"].get("SessionStart", [])
    commands = [h["command"] for entry in session_start for h in entry.get("hooks", [])]
    assert any("fr-acceptance-nag.sh" in c for c in commands)


def test_a_stale_artifact_refusal_is_reported_not_swallowed(tmp_path, monkeypatch):
    """review r5-c5: `|| exit 0` swallowed EVERY failure, so the nag simply
    vanished when `fr` refused over stale artifacts — silence at the exact
    moment the operator most needed to know why."""
    import json
    import subprocess

    repo = tmp_path / "repo"
    (repo / "docs" / "acceptance").mkdir(parents=True)
    write_fragments(repo, [], feature="legacy")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_fr = bin_dir / "fr"
    fake_fr.write_text(
        "#!/bin/sh\n"
        "echo 'fr: artifacts in . were written for a different fr and must be "
        "migrated before this command can run.' >&2\n"
        "exit 2\n"
    )
    fake_fr.chmod(0o755)

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }
    done = subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps({"cwd": str(repo)}),
        capture_output=True,
        text=True,
        env=env,
    )

    assert done.returncode == 0, done.stderr
    assert "acceptance nag skipped: artifacts stale" in done.stdout


def _run_with_fake_fr(tmp_path: Path, script: str) -> subprocess.CompletedProcess[str]:
    repo = tmp_path / "repo"
    (repo / "docs" / "acceptance").mkdir(parents=True)
    write_fragments(repo, [], feature="legacy")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_fr = bin_dir / "fr"
    fake_fr.write_text("#!/bin/sh\n" + script)
    fake_fr.chmod(0o755)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps({"cwd": str(repo)}),
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
    )


NOTICE = (
    "fr: migrated and committed 2 artifact(s): chore(fr): migrate 2 plans to fr 9.9.9 (abc1234)"
)


def test_the_gates_commit_notice_is_relayed_first(tmp_path: Path) -> None:
    """Spec 2026-11-01-auto-migrate-own-commit R11: a session's first gated
    command is often this nag, so a migration it committed is said here."""
    done = _run_with_fake_fr(
        tmp_path,
        "echo 'fr: artifacts in . are out of date — migrating before running the command.' >&2\n"
        f"echo '{NOTICE}' >&2\n"
        "echo '1 row owes a walk: debt-0'\n"
        "exit 0\n",
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith(NOTICE + "\n"), done.stdout
    assert "debt-0" in done.stdout


def test_the_commit_notice_is_relayed_even_with_no_debt(tmp_path: Path) -> None:
    done = _run_with_fake_fr(tmp_path, f"echo '{NOTICE}' >&2\necho 'no acceptance debt'\nexit 0\n")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == NOTICE


def test_a_partial_migration_still_relays_its_commit(tmp_path: Path) -> None:
    """Review p1-r4: a partial migration commits what it could and then exits
    2. The commit has landed, so the session is told about it."""
    done = _run_with_fake_fr(
        tmp_path,
        f"echo '{NOTICE}' >&2\n"
        "echo 'fr: 2 artifact(s) migrated and committed; 1 left unmodified.' >&2\n"
        "exit 2\n",
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith(NOTICE + "\n") or done.stdout.strip() == NOTICE, done.stdout


def test_a_stale_refusal_names_the_workspace_way_to_carry_it(tmp_path: Path) -> None:
    done = _run_with_fake_fr(
        tmp_path,
        "echo 'fr: artifacts in . were written for a different fr and must be migrated' >&2\n"
        "exit 2\n",
    )
    assert done.returncode == 0, done.stderr
    assert "acceptance nag skipped: artifacts stale" in done.stdout
    assert "fr-isolation workspace" in done.stdout
    assert "fr isolation up --branch" in done.stdout
    assert "fr migrate artifacts --yes" in done.stdout


def test_nag_says_acceptance_is_disabled_when_the_repo_setting_is_off(tmp_path: Path) -> None:
    from tests.unit.settings_repo import land_on_main, make_repo

    root = make_repo(tmp_path)
    land_on_main(root, "artifacts:\n  acceptance: off\n")
    assert run_hook(root).stdout == ""  # no matrix: the cheap early exit (p2-r6)
    (root / "docs" / "acceptance").mkdir(parents=True)
    write_matrix_fragments(root, "org: o\nrepo: r\nrows: []\n")
    result = run_hook(root)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "acceptance disabled by repo setting"


def test_p2_r6_no_matrix_exits_before_spawning_fr(tmp_path: Path) -> None:
    """The cheap early exit: a repo with no matrix never starts an `fr` process."""
    root = tmp_path / "plain"
    root.mkdir()
    _git(root)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls"
    fake = bin_dir / "fr"
    fake.write_text(f'#!/bin/bash\necho "$@" >> {calls}\n')
    fake.chmod(0o755)
    payload = json.dumps({"session_id": "s", "cwd": str(root), "hook_event_name": "SessionStart"})
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert not calls.exists(), calls.read_text()


def test_nag_reads_the_acceptance_dir_the_placement_names(tmp_path: Path) -> None:
    """R1/R26: under quiet or stealth the fragments are not in the checkout; the nag asks
    `fr settings paths --shell` for FR_ACCEPTANCE_DIR instead of assuming docs/acceptance."""
    repo = tmp_path / "plain"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for args in (
        ["remote", "add", "origin", "https://example.com/org/repo.git"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"],
    ):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    settings = subprocess.run(
        ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
        input="placement: quiet\n",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "-C", str(repo), "mktree"],
        input=f"100644 blob {settings}\tsettings.yaml\n",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    commit = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit-tree",
            tree,
            "-m",
            "s",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(repo), "update-ref", "refs/remotes/origin/fr", commit], check=True
    )
    elsewhere = tmp_path / "space" / "acceptance"
    (elsewhere / "features").mkdir(parents=True)
    (elsewhere / "features" / "x.yaml").write_text("rows: []\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "fr"
    stub.write_text(
        "#!/bin/bash\n"
        'case "$*" in\n'
        f'  "settings paths --shell --no-create") echo "FR_ACCEPTANCE_DIR={elsewhere}" ;;\n'
        '  "settings show --json") echo "{}" ;;\n'
        '  "acceptance status --brief") echo "1 row unwired: stub-row" ;;\n'
        "esac\n"
    )
    stub.chmod(0o755)
    payload = json.dumps({"session_id": "s", "cwd": str(repo), "hook_event_name": "SessionStart"})
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
    )
    assert result.returncode == 0, result.stderr
    assert "stub-row" in result.stdout


def test_a_relative_path_entry_holding_an_fr_is_never_run(tmp_path: Path) -> None:
    """Review p6-r2: the nag spawns only an `fr` found in an ABSOLUTE PATH entry; a
    repo-planted `bin/fr` reached through `bin` or `.` is never executed."""
    rows = row(id="debt-0", status="unwired")
    root = make_repo(tmp_path, rows, git=False)
    _git(root)
    ran = tmp_path / "planted-ran"
    for where in (root / "bin", root):
        where.mkdir(exist_ok=True)
        planted = where / "fr"
        planted.write_text(f'#!/bin/bash\ntouch "{ran}"\necho planted-debt\n')
        planted.chmod(0o755)
    tools = sorted({str(Path(shutil.which(t) or "/usr/bin/x").parent) for t in ("jq", "git")})
    path = ":".join(["bin", ".", "", *tools, "/usr/bin", "/bin"])
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps({"session_id": "s", "cwd": str(root), "hook_event_name": "SessionStart"}),
        capture_output=True,
        text=True,
        cwd=root,
        env={**os.environ, "PATH": path},
    )
    assert result.returncode == 0, result.stderr
    assert "planted-debt" not in result.stdout
    assert not ran.exists()


def test_a_plain_repo_with_fragments_never_asks_for_paths(tmp_path: Path) -> None:
    """Review p6-r8: with no `origin/fr` ref and no marker on the filesystem, the nag
    asks `fr` only for the nag itself, never `fr settings paths`."""
    rows = row(id="debt-0", status="unwired")
    root = make_repo(tmp_path, rows, git=False)
    _git(root)
    subprocess.run(
        ["git", "-C", str(root), "remote", "add", "origin", "https://example.com/o/r.git"],
        check=True,
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls"
    fake = bin_dir / "fr"
    fake.write_text(f'#!/bin/bash\necho "$@" >> {calls}\n')
    fake.chmod(0o755)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps({"session_id": "s", "cwd": str(root), "hook_event_name": "SessionStart"}),
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
    )
    assert result.returncode == 0, result.stderr
    assert "settings paths" not in (calls.read_text() if calls.exists() else "")
