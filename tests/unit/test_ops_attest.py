"""`fr ops attest` (spec 2026-10-22-fr-ops R8)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

runner = CliRunner()
PLAN_REL = "docs/superpowers/plans/p"
OPS = """schema_version: 1
ops:
  - id: click-ui
    summary: Enable the toggle in the UI
    phase: post-merge
    commands: [open the settings page]
  - id: checked
    summary: has a check
    phase: post-merge
    check: 'true'
"""


class Prompt:
    def __init__(self, terminal: bool = True, answer: bool = True) -> None:
        self.terminal, self.answer = terminal, answer

    def has_terminal(self) -> bool:
        return self.terminal

    def confirm(self, text: str) -> bool:
        return self.answer


def _journal(repo: Path) -> str:
    return "".join(p.read_text() for p in (repo / "docs/superpowers/journals").rglob("*.md"))


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("FR_OPS_TRUST_DIR", str(tmp_path / "trust"))
    root = tmp_path / "r"
    (root / PLAN_REL).mkdir(parents=True)
    (root / PLAN_REL / "ops.yaml").write_text(OPS)
    _git(root, "init", "-q", "-b", "feat/x")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed")
    from fr.ops.load import load_ops, load_ops_config
    from fr.ops.trust import fingerprint, grant_trust, head_tree, tree_digest

    tree = head_tree(root)
    fp = fingerprint(
        load_ops(root / PLAN_REL, root).ops,
        load_ops_config(root),
        root,
        code_tree=tree_digest(tree),
    )
    grant_trust(root, "p", fp, tree=tree)
    monkeypatch.chdir(root)
    monkeypatch.setattr("fr.ops.profile.in_ops_profile", lambda *a, **k: True)
    monkeypatch.setattr("fr.commands.ops_cmd._prompt", lambda: Prompt())
    return root


def _attest(*args: str):
    return runner.invoke(app, ["ops", "attest", *args, "--plan", PLAN_REL])


def test_attest_closes_an_unverifiable_op_as_attested(repo: Path) -> None:
    res = _attest("click-ui", "--note", "toggled it, saw the banner")
    assert res.exit_code == 0, res.output
    assert "DONE (attested)" in res.output
    body = next((repo / "docs/superpowers/journals").rglob("*.md")).read_text()
    assert "attested_by: operator" in body and "toggled it, saw the banner" in body
    st = runner.invoke(app, ["ops", "status", "--plan", PLAN_REL])
    assert "DONE (attested)" in st.output and "DONE (checked)" in st.output


def test_attest_is_refused_for_an_op_with_a_check(repo: Path) -> None:
    res = _attest("checked", "--note", "x")
    assert res.exit_code == 2 and "has a check" in res.output


def test_attest_is_refused_without_a_terminal(repo: Path, monkeypatch) -> None:
    monkeypatch.setattr("fr.commands.ops_cmd._prompt", lambda: Prompt(terminal=False))
    res = _attest("click-ui", "--note", "x")
    assert res.exit_code == 2 and "terminal" in res.output
    assert "op click-ui" not in _journal(repo)


def test_attest_declined_writes_nothing(repo: Path, monkeypatch) -> None:
    monkeypatch.setattr("fr.commands.ops_cmd._prompt", lambda: Prompt(answer=False))
    res = _attest("click-ui", "--note", "x")
    assert res.exit_code == 2
    assert "op click-ui" not in _journal(repo)


def test_attest_is_refused_outside_an_ops_profile(repo: Path, monkeypatch) -> None:
    monkeypatch.setattr("fr.ops.profile.in_ops_profile", lambda *a, **k: False)
    res = _attest("click-ui", "--note", "x")
    assert res.exit_code == 2 and "fr isolation up --profile" in res.output


def test_attest_of_a_runbook_op_needs_plan(repo: Path) -> None:
    (repo / ".fr").mkdir()
    (repo / ".fr/ops.yaml").write_text("runbook: book.yaml\n")
    (repo / "book.yaml").write_text(
        "- id: rb\n  summary: rb op\n  phase: post-merge\n  commands: [do it]\n"
    )
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "book")
    res = runner.invoke(app, ["ops", "attest", "rb", "--note", "x"])
    assert res.exit_code == 2
