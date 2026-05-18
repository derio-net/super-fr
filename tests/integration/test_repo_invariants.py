import re
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


def test_claude_md_has_bridge_audit_rule():
    """
    GIVEN CLAUDE.md in the repo root
    WHEN  searching its content
    THEN  it contains a section/paragraph mentioning 'bridge audit rule'
          AND references vk.bridge.* as the canonical read-target post-rebuild
    """
    body = Path("CLAUDE.md").read_text()
    assert re.search(r"bridge audit rule", body, re.IGNORECASE), (
        "CLAUDE.md is missing a 'bridge audit rule' section"
    )
    assert "vk.bridge" in body, (
        "CLAUDE.md's bridge audit rule must reference `vk.bridge.*` as the canonical "
        "read-target after the v2 rebuild"
    )


def test_v2_bridge_rebuild_spec_has_architectural_ownership_section():
    """
    GIVEN this spec doc on disk
    WHEN  searching for the '## Architectural ownership' section
    THEN  the section exists
    AND   contains a table mapping every contract-level invariant to one
          owner module + the signature that lets it enforce
    (Regression guard so the pattern isn't dropped from future specs that
    copy this one as a template.)
    """
    spec = Path("docs/superpowers/specs/2026-05-17-v2-bridge-rebuild-design.md").read_text()
    # Heading present (case-insensitive on "ownership" because the section
    # header in the spec is "## Architectural ownership ...").
    assert re.search(r"^##\s+Architectural ownership", spec, re.MULTILINE), (
        "spec is missing the '## Architectural ownership' section"
    )
    # The section must contain a markdown table with an "Invariant" header
    # column — that's the load-bearing structure the pattern relies on.
    section_start = spec.index("## Architectural ownership")
    section = spec[section_start:]
    # Cut at the next top-level heading.
    next_h = re.search(r"\n##\s+", section[2:])
    if next_h:
        section = section[: 2 + next_h.start()]
    assert re.search(r"^\|\s*Invariant\s*\|", section, re.MULTILINE), (
        "Architectural ownership section must contain a markdown table with an "
        "'Invariant' header column"
    )
    # The table must have at least one body row (a line starting with "| ...").
    body_rows = [
        line
        for line in section.splitlines()
        if line.startswith("| ") and "---" not in line and "Invariant" not in line
    ]
    assert body_rows, "Architectural ownership table must contain at least one invariant row"
