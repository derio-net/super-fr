"""Sandboxed, copyable fixture templates (spec 2026-11-19-local-suite-cost §3.B, R2)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from fr.isolation.marker import valid_workspace

from tests.conftest import OPERATOR_HOME
from tests.unit import record_support
from tests.unit.record_support import LAST_BRIEF, RUN, fr, git, snapshot, started_run


def _refs(origin: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(origin), "for-each-ref"], check=True, capture_output=True, text=True
    ).stdout


def test_a_copied_started_run_is_a_valid_workspace_with_a_working_run(tmp_path):
    root = started_run(tmp_path)
    assert valid_workspace(root, "feat/rec").ok
    data = json.loads((root / ".fr-isolation").read_text())
    assert data["toplevel"] == str(root.resolve())
    out = fr(root, ["run", "status", RUN])
    assert out.exit_code == 0, out.output
    assert (
        git(root, "rev-parse", "--git-common-dir").strip()
        != git(root, "rev-parse", "--git-dir").strip()
    )


def test_a_push_in_one_copy_leaves_the_other_copys_origin_alone(tmp_path):
    a = started_run(tmp_path / "a")
    b = started_run(tmp_path / "b")
    before_b = _refs(tmp_path / "b" / "origin.git")
    git(a, "push", "-q", "origin", "feat/rec")
    assert "refs/heads/feat/rec" in _refs(tmp_path / "a" / "origin.git")
    assert _refs(tmp_path / "b" / "origin.git") == before_b
    assert "feat/rec" not in before_b
    assert git(b, "config", "remote.origin.url").strip() == str(tmp_path / "b" / "origin.git")


def test_a_write_in_a_copy_leaves_the_template_unchanged(tmp_path, fixture_templates):
    started_run(tmp_path / "first")
    template = fixture_templates.template_path("started_run", record_support._build_started_run)
    before = snapshot(template)
    root = started_run(tmp_path / "second")
    (root / "scratch.txt").write_text("x")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "scribble", "--no-verify")
    assert snapshot(template) == before
    assert "scratch.txt" not in before


def test_the_templates_home_and_git_config_are_the_sandboxs_not_the_operators(
    tmp_path, fixture_templates
):
    seen: dict[str, str] = {}

    def build(directory: Path) -> dict[str, str]:
        seen.update(HOME=os.environ["HOME"], GIT_CONFIG_GLOBAL=os.environ["GIT_CONFIG_GLOBAL"])
        return {}

    fixture_templates.copy("env-probe", build, tmp_path / "c")
    assert Path(seen["HOME"]) != OPERATOR_HOME
    assert not Path(seen["HOME"]).is_relative_to(OPERATOR_HOME / ".config")
    assert Path(seen["GIT_CONFIG_GLOBAL"]).parent == Path(seen["HOME"])
    assert seen["HOME"] != os.environ["HOME"]  # not this test's own sandbox either
    assert fixture_templates.env["HOME"] == seen["HOME"]
    # and building it did not leak into this process
    assert os.environ["HOME"] != seen["HOME"]


def test_last_brief_is_the_templates_brief_in_each_copy(tmp_path):
    started_run(tmp_path / "a")
    first = json.loads(json.dumps(LAST_BRIEF))
    LAST_BRIEF.clear()
    started_run(tmp_path / "b")
    second = json.loads(json.dumps(LAST_BRIEF))
    assert (first["step"], first["item"]) == ("implement-phase", "phase/1")
    assert LAST_BRIEF["record"]["template"]
    # the brief is the template's, with paths that name the copy rather than the template
    assert str(tmp_path / "a") not in json.dumps(second)
    assert json.dumps(first).replace(str((tmp_path / "a").resolve()), "X") == json.dumps(
        second
    ).replace(str((tmp_path / "b").resolve()), "X")


def test_a_run_cli_template_is_keyed_per_branch(tmp_path, fixture_templates):
    from tests.unit.test_run_cli import _repo

    x = _repo(tmp_path / "x", branch="feat/x")
    y = _repo(tmp_path / "y", branch="feat/y")
    again = _repo(tmp_path / "z", branch="feat/x")
    assert git(x, "rev-parse", "--abbrev-ref", "HEAD").strip() == "feat/x"
    assert git(y, "rev-parse", "--abbrev-ref", "HEAD").strip() == "feat/y"
    assert git(again, "rev-parse", "--abbrev-ref", "HEAD").strip() == "feat/x"
    assert json.loads((y / ".fr-isolation").read_text())["branch"] == "feat/y"
    assert valid_workspace(again, "feat/x").ok
