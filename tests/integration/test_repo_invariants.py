from pathlib import Path

import yaml


def test_v2_plan_cross_repo_fixture_exists():
    """
    GIVEN the repo
    THEN  tests/unit/fixtures/v2_plan_cross_repo/_meta.yaml exists
    AND   at least one phase yaml has tracking_issue pointing at a
          repo different from _meta.target_repo
    AND   at least one phase yaml has tracking_issue=null (undispatched)
    """
    fx = Path("tests/unit/fixtures/v2_plan_cross_repo")
    meta = yaml.safe_load((fx / "_meta.yaml").read_text())
    assert meta["target_repo"] == "derio-net/repo-a"
    phases = [yaml.safe_load(p.read_text()) for p in sorted(fx.glob("0*.yaml"))]
    foreign = [
        p
        for p in phases
        if (p["phase"].get("tracking_issue") or "").startswith(
            "https://github.com/derio-net/repo-b"
        )
    ]
    undispatched = [p for p in phases if p["phase"].get("tracking_issue") is None]
    assert foreign, "no foreign-repo phase in fixture"
    assert undispatched, "no undispatched phase in fixture"
