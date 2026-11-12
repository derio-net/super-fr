"""The `lens-review` step in both shipped manifests and its brief (spec
2026-11-12-review-lenses R8, R11, §3.C)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fr.lenses.review import lens_review_rule
from fr.workflow.model import parse_manifest

from tests.unit.lens_review_support import at_lens_review
from tests.unit.test_run_cli import _invoke

REPO = Path(__file__).parents[2]
SHIPPED = REPO / "plugins" / "super-fr" / "workflows"
WHEEL = REPO / "packages" / "fr" / "src" / "fr" / "workflows"


@pytest.mark.parametrize("name", ["fr-goal", "fr-goal-light"])
def test_both_shipped_manifests_run_lens_review_between_journal_check_and_deliver(
    name: str,
) -> None:
    from fr.workflow.check import check_workflow

    manifest = parse_manifest((SHIPPED / f"{name}.yaml").read_text())
    ids = [s.id for s in manifest.steps]
    assert ids.index("lens-review") == ids.index("journal-check") + 1
    assert ids.index("deliver") == ids.index("lens-review") + 1
    step = next(s for s in manifest.steps if s.id == "lens-review")
    assert step.kind == "agent"
    assert step.tier == "standard"
    # `journal:plan` in `needs` would be a cycle with `review-phase`, which needs
    # and emits it too (the spec's snippet; see the plan-journal discovery).
    assert list(step.needs) == ["spec", "plan"]
    assert list(step.emits) == ["journal:plan"]
    assert list(step.evidence) == ["lenses", "review", "reviewer", "findings"]
    assert list(step.skill or ()) == [
        "superpowers:requesting-code-review",
        "superpowers:receiving-code-review",
    ]
    assert check_workflow(manifest, REPO) == []
    assert (WHEEL / f"{name}.yaml").read_text() == (SHIPPED / f"{name}.yaml").read_text()


def _brief(output: str) -> dict[str, object]:
    line = next(ln for ln in reversed(output.splitlines()) if ln.startswith("{"))
    return json.loads(line)


def test_the_brief_lists_each_lens_with_its_text_reasons_and_return_rule(
    tmp_path: Path,
) -> None:
    from fr.lenses.resolve import effective_lenses

    repo, shipped, _ = at_lens_review(tmp_path, lenses=("security",))
    out = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])
    assert out.exit_code == 0, out.output

    brief = _brief(out.output)
    review = brief["lens_review"]
    assert isinstance(review, dict)
    assert isinstance(review["merge_base"], str) and len(review["merge_base"]) == 40
    (entry,) = review["set"]
    security = effective_lenses(repo)["security"]
    assert entry["lens"] == "security"
    assert entry["title"] == security.title
    assert entry["brief"] == security.brief
    assert entry["reasons"] == [
        {"text": "why it matters", "step": None, "entry": "lens-security-1"}
    ]
    assert entry["rule"] is None and entry["file"] is None
    assert entry["return_rule"] == lens_review_rule("security")
    assert "lenses" not in brief["evidence"]
    template = brief["record"]["template"]  # type: ignore[index]
    assert "#   owed: review: <id>, reviewer: <id>\n" in template
    assert "lenses:" not in template


def test_a_rule_lens_carries_its_rule_and_file(tmp_path: Path) -> None:
    config = "require:\n  - paths: [src/auth/**]\n    lenses: [security]\n"
    repo, shipped, _ = at_lens_review(tmp_path, config=config)
    out = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    (entry,) = _brief(out.output)["lens_review"]["set"]  # type: ignore[index]
    assert entry["lens"] == "security"
    assert entry["reasons"] == []
    assert entry["rule"] == ["src/auth/**"]
    assert entry["file"] == "src/auth/token.py"


def test_an_empty_set_says_so_and_owes_no_reviewer(tmp_path: Path) -> None:
    repo, shipped, _ = at_lens_review(tmp_path)
    out = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])
    assert out.exit_code == 0, out.output

    brief = _brief(out.output)
    review = brief["lens_review"]
    assert set(review) == {"set", "note"}  # type: ignore[arg-type]
    assert review["set"] == []  # type: ignore[index]
    assert "resolve" in review["note"]  # type: ignore[index]
    template = brief["record"]["template"]  # type: ignore[index]
    assert "review: <id>" not in template and "reviewer: <id>" not in template
    assert "lenses:" not in template


def test_an_unreadable_lens_set_refuses_the_brief(tmp_path: Path) -> None:
    """`lens_set` fails closed (a rule requires a lens that is not effective):
    the brief refuses, exit 2, never an empty set."""
    config = "disable: [security]\nrequire:\n  - paths: [src/**]\n    lenses: [security]\n"
    repo, shipped, _ = at_lens_review(tmp_path, lenses=("tests",))
    (repo / ".fr" / "lenses.yaml").parent.mkdir(exist_ok=True)
    (repo / ".fr" / "lenses.yaml").write_text(config)

    out = _invoke(repo, shipped, ["run", "advance", "r1", "--redispatch"])

    assert out.exit_code == 2, out.output
    assert "requires lens security" in out.output
    assert "lens_review" not in out.output


@pytest.mark.parametrize("name", ["fr-goal", "fr-goal-light"])
def test_the_review_phase_brief_carries_no_lens_text(name: str) -> None:
    from fr.commands.run_cmd import _build_member_brief

    manifest = parse_manifest((SHIPPED / f"{name}.yaml").read_text())
    group = next(s for s in manifest.steps if any(m.id == "review-phase" for m in s.steps))
    member = next(m for m in group.steps if m.id == "review-phase")
    state = SimpleNamespace(run="r1", workflow=name, issue=None)

    brief = _build_member_brief(member, group, "phase/3", state, None)  # type: ignore[arg-type]

    assert "lens_review" not in brief
    # The record template's journal comment teaches that ANY step may add a
    # lens (R4); the rest of the brief carries no lens text.
    rest = {k: v for k, v in brief.items() if k != "record"}
    assert "lens" not in json.dumps(rest, sort_keys=True)
