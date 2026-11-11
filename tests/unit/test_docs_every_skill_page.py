"""Every shipped skill is covered by a published page (spec 2026-11-11-docs-currency R19)."""

from __future__ import annotations

from pathlib import Path

from fr.docs.check import check
from fr.docs.gate import evaluate
from fr.docs.load import load_config
from fr.docs.model import Page

ROOT = Path(__file__).resolve().parents[2]


def test_this_repos_config_requires_a_page_for_every_skill() -> None:
    config = load_config(ROOT)
    assert config is not None
    assert "plugins/*/skills/*/SKILL.md" in config.must_cover


def test_every_shipped_skill_has_a_page() -> None:
    config = load_config(ROOT)
    assert config is not None
    outcome = evaluate(ROOT, config, None)
    assert [f.message for f in outcome.findings if f.kind == "uncovered"] == []
    skills = sorted(p.parent.name for p in ROOT.glob("plugins/*/skills/*/SKILL.md"))
    assert len(skills) >= 15


def test_a_skill_with_no_page_fails_the_check() -> None:
    page = Page("docs/a.md", ("plugins/p/skills/old/SKILL.md",), "2026-11-11 x")
    tracked = ["docs/a.md", "plugins/p/skills/old/SKILL.md", "plugins/p/skills/new/SKILL.md"]
    got = check([page], [], tracked, None, ["plugins/*/skills/*/SKILL.md"])
    assert [(f.kind, f.paths) for f in got] == [("uncovered", ("plugins/p/skills/new/SKILL.md",))]
