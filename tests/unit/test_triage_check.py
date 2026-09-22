"""`fr triage check` — the four sets that make triage debt visible (spec §3.F).

unranked, settled, orphaned and unreachable (review r-p2-check-sets): a
judgement whose issue the forge would not show (`unviewed`) or whose repo was
`skipped` is unreachable, never orphaned. Keys are compared only through
`fr.triage.model.normalize_key`. Every state directory is under tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.triage.check import classify
from fr.triage.model import Facts, Issue, Judgements, PullRequest, Skipped, Unviewed
from typer.testing import CliRunner

REPO = "derio-net/super-fr"


def _issue(number: int, *, title: str = "t", state: str = "open", **kw: Any) -> Issue:
    return Issue.model_validate(
        {
            "repo": kw.pop("repo", REPO),
            "number": number,
            "title": title,
            "state": state,
            "url": f"https://github.com/{REPO}/issues/{number}",
            **kw,
        }
    )


def _merged_pr(number: int) -> PullRequest:
    return PullRequest(
        repo=REPO,
        number=number,
        title="fix",
        state="MERGED",
        is_draft=False,
        merged_at="2026-09-20T10:00:00Z",
        url=f"https://github.com/{REPO}/pull/{number}",
    )


def _facts(issues: list[Issue], **kw: Any) -> Facts:
    return Facts.model_validate(
        {
            "schema": 2,
            "scope": "derio-net--super-fr",
            "kind": "repo",
            "collected_at": "2026-09-21T12:00:00+00:00",
            "repos": kw.pop("repos", [REPO]),
            "issues": [i.model_dump(mode="json") for i in issues],
            **{k: [x.model_dump(mode="json") for x in v] for k, v in kw.items()},
        }
    )


def _judgements(*keys: str) -> Judgements:
    return Judgements.model_validate(
        {
            "schema": 1,
            "tiers": [{"n": 1, "title": "Data loss"}],
            "issues": {k: {"tier": 1} for k in keys},
        }
    )


def test_an_open_issue_with_no_judgement_is_unranked() -> None:
    result = classify(_facts([_issue(1), _issue(2)]), _judgements("super-fr#2"))

    assert [i.key for i in result.unranked] == ["super-fr#1"]
    assert result.settled == [] and result.orphaned == [] and result.unreachable == []


@pytest.mark.parametrize("how", ["closed", "merged"])
def test_a_judged_issue_now_closed_or_merged_is_settled(how: str) -> None:
    issue = (
        _issue(3, state="closed")
        if how == "closed"
        else _issue(3, prs=[_merged_pr(9).model_dump(mode="json")])
    )
    result = classify(_facts([issue]), _judgements("super-fr#3"))

    assert [i.key for i in result.settled] == ["super-fr#3"]
    assert result.unranked == [] and result.orphaned == []


def test_a_judgement_naming_no_collected_repo_is_orphaned() -> None:
    # A typo'd repo name. (This used super-fr#404 as "a deleted issue", but a real
    # collect VIEWS a judged key in a collected repo, so a deleted issue lands in
    # unviewed -> unreachable. The old state could not arise from collect — C1/C2.)
    result = classify(_facts([_issue(1)]), _judgements("super-fr#1", "super-fx#404"))

    assert result.orphaned == ["super-fx#404"]
    assert result.unreachable == []


def test_a_judgement_the_forge_would_not_show_is_unreachable_not_orphaned() -> None:
    facts = _facts([], unviewed=[Unviewed(key="super-fr#7", reason="HTTP 502")])
    result = classify(facts, _judgements("super-fr#7"))

    assert result.orphaned == []
    assert [(u.key, u.reason) for u in result.unreachable] == [("super-fr#7", "HTTP 502")]


def test_a_judgement_in_a_skipped_repo_is_unreachable_not_orphaned() -> None:
    facts = Facts.model_validate(
        {
            **_facts([]).to_json(),
            "scope": "derio-net",
            "kind": "org",
            "repos": ["derio-net/alpha", "derio-net/beta"],
            "skipped": [Skipped(repo="derio-net/beta", reason="issues disabled").model_dump()],
        }
    )
    result = classify(facts, _judgements("beta#4", "gamma#5"))

    # gamma is no repo collect read, so gamma#5 is the one genuine orphan here.
    # (This test used alpha#5 as its orphan, but alpha IS collected: it was
    # asserting the defect the next test pins — phase-4 review C2.)
    assert result.orphaned == ["gamma#5"]
    assert [(u.key, u.reason) for u in result.unreachable] == [("beta#4", "issues disabled")]


def test_a_key_in_a_collected_repo_absent_from_the_facts_is_unreachable_not_orphaned() -> None:
    """Phase-4 review C2: `check` reads the LAST collect's facts.

    A key in a collected repo that collect never viewed was judged AFTER that
    collect, so its absence is evidence about the facts, not about the issue.
    Calling it orphaned invited the agent to prune a live judgement. Orphaned
    now means exactly one thing: the key names no repo collect read.
    """
    result = classify(_facts([_issue(1)]), _judgements("super-fr#1", "super-fr#77", "super-fx#5"))

    assert result.orphaned == ["super-fx#5"]
    assert [u.key for u in result.unreachable] == ["super-fr#77"]
    assert "after the last collect" in result.unreachable[0].reason
    assert "fr triage collect" in result.unreachable[0].reason


def test_keys_compare_through_the_one_normaliser() -> None:
    """A judgement keyed in another case still matches its issue (r-p2-case)."""
    facts = _facts([_issue(1, repo="Derio-Net/Super-FR")], unviewed=[])
    result = classify(facts, _judgements("SUPER-FR#1"))

    assert result.unranked == [] and result.orphaned == []


# ---------------------------------------------------------------- the command


def _write(tmp_path: Path, facts: Facts, judgements: str | None) -> None:
    (tmp_path / "facts.json").write_text(json.dumps(facts.to_json()), encoding="utf-8")
    if judgements is not None:
        (tmp_path / "judgements.yaml").write_text(judgements, encoding="utf-8")


JUDGED = """schema: 1
tiers: [{n: 1, title: Data loss}]
issues:
  "super-fr#3": {tier: 1}
  "super-fx#404": {tier: 1}
  "super-fr#7": {tier: 1}
"""


def _state(tmp_path: Path) -> Facts:
    facts = _facts(
        [_issue(1, title="[manual] x [/red]"), _issue(3, state="closed")],
        unviewed=[Unviewed(key="super-fr#7", reason="HTTP 502")],
    )
    _write(tmp_path, facts, JUDGED)
    return facts


def _check(tmp_path: Path, *extra: str) -> Any:
    return CliRunner().invoke(
        app, ["triage", "check", "--repo", REPO, "--dir", str(tmp_path), *extra]
    )


def test_check_exits_0_with_all_four_sets_present(tmp_path: Path) -> None:
    _state(tmp_path)
    result = _check(tmp_path)

    assert result.exit_code == 0, result.output
    for label in ("unranked", "settled", "orphaned", "unreachable"):
        assert label in result.output


def test_check_json_emits_the_four_sets(tmp_path: Path) -> None:
    _state(tmp_path)
    result = _check(tmp_path, "--json")

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert [i["key"] for i in data["unranked"]] == ["super-fr#1"]
    assert [i["key"] for i in data["settled"]] == ["super-fr#3"]
    assert data["orphaned"] == ["super-fx#404"]
    assert data["unreachable"] == [{"key": "super-fr#7", "reason": "HTTP 502"}]


def test_a_markup_looking_title_prints_verbatim_and_does_not_raise(tmp_path: Path) -> None:
    """Spec-review r7: rich would eat `[manual]` and raise on `[/red]`."""
    _state(tmp_path)
    result = _check(tmp_path)

    assert result.exception is None, result.exception
    assert "[manual] x [/red]" in result.output


def test_check_with_no_judgements_reports_everything_unranked(tmp_path: Path) -> None:
    _write(tmp_path, _facts([_issue(1), _issue(2)]), None)
    result = _check(tmp_path, "--json")

    assert result.exit_code == 0, result.output
    assert [i["key"] for i in json.loads(result.output)["unranked"]] == [
        "super-fr#1",
        "super-fr#2",
    ]


def test_check_with_no_facts_names_collect(tmp_path: Path) -> None:
    result = _check(tmp_path)

    assert result.exit_code == 2
    assert "fr triage collect" in result.output
