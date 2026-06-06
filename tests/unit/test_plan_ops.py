"""Tests for `vk.plan_ops.set_tracking_issue`.

Each test copies the minimal v2 plan fixture into a tmp_path under a
git repo and exercises the writer. The helper must:

  - write the URL into <plan_dir>/<NN>.yaml,
  - stage the file via `git add`,
  - be idempotent on a same-url re-call (no file rewrite),
  - overwrite a different existing URL silently,
  - raise `PlanEditError` if the phase yaml is missing,
  - re-parse after the write and translate any `PlanSchemaError` into a
    `PlanEditError`,
  - behave identically for `tag: manual` phases.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _setup_plan(tmp_path: Path) -> Path:
    """Copy the minimal fixture into a fresh git repo under tmp_path.

    Returns the plan dir (`tmp_path / "docs/superpowers/plans/v2_plan_minimal"`).
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    plan_dir = tmp_path / "docs" / "superpowers" / "plans" / "v2_plan_minimal"
    plan_dir.parent.mkdir(parents=True)
    shutil.copytree(FIXTURE, plan_dir)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "init"], check=True)
    return plan_dir


def _staged_files(repo_root: Path) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout


URL = "https://github.com/derio-net/test/issues/42"
URL_B = "https://github.com/derio-net/test/issues/99"


def test_set_tracking_issue_writes_url_and_stages(tmp_path):
    from fr import plan_ops

    plan_dir = _setup_plan(tmp_path)

    plan_ops.set_tracking_issue(plan_dir, 1, URL)

    raw = yaml.safe_load((plan_dir / "01.yaml").read_text())
    assert raw["phase"]["tracking_issue"] == URL

    staged = _staged_files(tmp_path)
    # Relative path from repo_root to 01.yaml
    rel = (plan_dir / "01.yaml").relative_to(tmp_path)
    assert str(rel) in staged


def test_set_tracking_issue_idempotent_on_same_url(tmp_path):
    from fr import plan_ops

    plan_dir = _setup_plan(tmp_path)
    plan_ops.set_tracking_issue(plan_dir, 1, URL)

    phase_path = plan_dir / "01.yaml"
    before = phase_path.read_bytes()

    plan_ops.set_tracking_issue(plan_dir, 1, URL)  # second call

    after = phase_path.read_bytes()
    assert before == after


def test_set_tracking_issue_overwrites_different_non_null_url(tmp_path):
    from fr import plan_ops

    plan_dir = _setup_plan(tmp_path)
    plan_ops.set_tracking_issue(plan_dir, 1, URL)

    # Replacement: no exception, yaml carries URL_B
    plan_ops.set_tracking_issue(plan_dir, 1, URL_B)

    raw = yaml.safe_load((plan_dir / "01.yaml").read_text())
    assert raw["phase"]["tracking_issue"] == URL_B


def test_set_tracking_issue_raises_when_phase_yaml_missing(tmp_path):
    from fr import plan_ops
    from fr.plan_ops import PlanEditError

    plan_dir = _setup_plan(tmp_path)

    with pytest.raises(PlanEditError) as ei:
        plan_ops.set_tracking_issue(plan_dir, 99, URL)

    msg = str(ei.value)
    assert "99" in msg
    assert "99.yaml" in msg


def test_set_tracking_issue_works_for_manual_phase(tmp_path):
    from fr import plan_ops

    plan_dir = _setup_plan(tmp_path)

    # Flip the fixture's phase to tag: manual before the call
    phase_path = plan_dir / "01.yaml"
    raw = yaml.safe_load(phase_path.read_text())
    raw["phase"]["tag"] = "manual"
    phase_path.write_text(yaml.safe_dump(raw, sort_keys=False))
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "flip"], check=True)

    plan_ops.set_tracking_issue(plan_dir, 1, URL)

    raw_after = yaml.safe_load(phase_path.read_text())
    assert raw_after["phase"]["tracking_issue"] == URL
    assert raw_after["phase"]["tag"] == "manual"

    staged = _staged_files(tmp_path)
    rel = phase_path.relative_to(tmp_path)
    assert str(rel) in staged


def test_set_tracking_issue_raises_on_post_write_schema_invalid(tmp_path):
    """If the post-write re-parse fails schema validation, the writer must
    translate the PlanSchemaError into a PlanEditError so callers see a
    single exception type from the writer surface.
    """
    from fr import plan_ops
    from fr.parser import PlanSchemaError
    from fr.plan_ops import PlanEditError

    plan_dir = _setup_plan(tmp_path)

    # Pre-write parse must succeed; post-write parse must raise. side_effect
    # consumed once for the pre-write call, once for the post-write call.
    real_parse = plan_ops.parse

    def fake_parse(dir_: Path):
        if not fake_parse.called:  # type: ignore[attr-defined]
            fake_parse.called = True  # type: ignore[attr-defined]
            return real_parse(dir_)
        raise PlanSchemaError("synthetic post-write schema failure")

    fake_parse.called = False  # type: ignore[attr-defined]

    with patch.object(plan_ops, "parse", side_effect=fake_parse):
        with pytest.raises(PlanEditError) as ei:
            plan_ops.set_tracking_issue(plan_dir, 1, URL)

    assert "schema" in str(ei.value).lower() or "synthetic" in str(ei.value)
