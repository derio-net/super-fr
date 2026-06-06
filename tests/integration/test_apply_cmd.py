"""End-to-end smoke for the apply_cmd -> apply(plan=...) propagation fix.

Regression guard for the 2026-05-17 dispatch incident — broken bodies
referenced old closed Issues (e.g. `Blocked by #1`) instead of the
actual predecessor Issue number, triggering out-of-order dispatch.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

FIXTURE = Path(__file__).parent.parent / "unit" / "fixtures" / "v2_plan_multi_phase"


@pytest.fixture()
def fake_gh_factory(monkeypatch):
    from tests.unit.fakes import FakeGhClient

    fake = FakeGhClient()
    monkeypatch.setattr(
        "fr.commands.apply_cmd._make_gh_client",
        lambda: fake,
    )
    return fake


def _seed_repo(tmp_path: Path) -> Path:
    """Create a bare-origin + work clone, copy the multi-phase fixture into
    the work tree, push to origin so the reachability gate passes, and
    return the path to the in-repo plan copy."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    subprocess.run(["git", "-C", str(work), "config", "user.email", "t@x"], check=True)
    subprocess.run(["git", "-C", str(work), "config", "user.name", "T"], check=True)

    plan_copy = work / "v2_plan_multi_phase"
    shutil.copytree(FIXTURE, plan_copy)

    meta = yaml.safe_load((plan_copy / "_meta.yaml").read_text())
    if meta.get("spec"):
        spec_path = work / meta["spec"]
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text("# stub spec\n")

    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(
        ["git", "-C", str(work), "push", "-q", "-u", "origin", "HEAD"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work), "remote", "set-head", "origin", "--auto"],
        check=True,
        capture_output=True,
    )
    return plan_copy


def test_apply_cmd_produces_correct_dep_refs_for_multi_phase_plan(fake_gh_factory, tmp_path):
    """
    GIVEN a multi-phase plan with phase 2 depending on phase 1,
          neither dispatched
    WHEN  `fr apply --yes <plan>` runs against a FakeGhClient
    THEN  the IssueCreate mutation for phase 2 carries a body that says
          `Blocked by #<phase-1-issue-number>` (NOT `Blocked by #1`,
          which would be the phase-number fallback).
    """
    from fr.cli import app

    plan_copy = _seed_repo(tmp_path)

    runner = CliRunner()
    result = runner.invoke(app, ["apply", str(plan_copy), "--yes"])
    assert result.exit_code == 0, result.output

    # Find the FakeGhClient create_issue calls. The first create_issue is
    # phase 1 (fixture's next_issue_number starts at 1). Phase 2's body
    # MUST reference phase 1's freshly-created issue number, not the
    # phase-number fallback (`#1` here happens to collide — but FakeGh
    # assigns 1 to phase 1's Issue first, so for phase 2's create body
    # it should *also* be #1 only if the renderer correctly resolved it).
    #
    # We assert the harder direction: phase 2's create body must reference
    # the predecessor's freshly-known issue number from the *running*
    # `created_issues` map, which is what `_rerender_dependent_creates`
    # provides. To avoid the #1 == phase-number coincidence, we look at
    # phase 10 (depends_on=[2]) — its create body must say `#2`
    # (the issue number FakeGh assigned to phase 2), not `#10`
    # (the phase-number fallback).
    create_calls = [c for c in fake_gh_factory.calls if c[0] == "create_issue"]
    assert len(create_calls) == 3, f"expected 3 IssueCreate calls, got {len(create_calls)}"

    # The strongest signal: phase 10 depends on phase 2 (issue #2). The
    # phase-number fallback would emit `Blocked by #10`; the correct
    # render emits `Blocked by #2`. Find the create_call for phase 10
    # (its title contains "Tenth").
    phase_10_call = next(
        (c for c in create_calls if "Tenth" in c[1]["title"]),
        None,
    )
    assert phase_10_call is not None, (
        f"could not find phase 10 IssueCreate among titles: {[c[1]['title'] for c in create_calls]}"
    )
    phase_10_body = phase_10_call[1]["body"]
    assert "Blocked by #2" in phase_10_body, (
        f"phase 10 body should reference phase 2's actual issue #2 "
        f"(NOT the phase-number fallback #10), got body:\n{phase_10_body}"
    )
    assert "Blocked by #10" not in phase_10_body, (
        "phase 10 body still uses the phase-number fallback — "
        "apply_cmd is not propagating plan= to apply()"
    )
