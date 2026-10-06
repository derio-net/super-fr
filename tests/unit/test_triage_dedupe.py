"""`fr.triage.dedupe.candidates` — duplicate-candidate groups (spec triage-dedupe §3.B).

The calibration fixture `tests/fixtures/triage/dedupe-calibration.json` is a capture,
never a construction: taken 2026-10-06 with
`gh issue view N --repo derio-net/super-fr --json number,title,body,state` for
594 607 631 640 647 724 725 868 869 454 458, each body cut to 2,000 characters
(collect's BODY_LIMIT). The captured states vary; the test loads every one as open.
"""

from __future__ import annotations

import json
from pathlib import Path

from fr.triage.dedupe import CandidateGroup, candidates
from fr.triage.model import Facts, Issue, Judgements

REPO = "derio-net/super-fr"
FIXTURE = Path(__file__).parent.parent / "fixtures" / "triage" / "dedupe-calibration.json"


def _issue(number: int, title: str, body: str = "", state: str = "open") -> Issue:
    return Issue(
        repo=REPO,
        number=number,
        title=title,
        state=state,  # type: ignore[arg-type]
        url=f"https://github.com/{REPO}/issues/{number}",
        body=body,
    )


def _facts(issues: list[Issue]) -> Facts:
    return Facts.model_validate(
        {
            "schema": 4,
            "scope": "derio-net--super-fr",
            "kind": "repo",
            "collected_at": "2026-10-06T12:00:00+00:00",
            "repos": [REPO],
            "issues": [i.model_dump(mode="json") for i in issues],
        }
    )


NONE = Judgements.model_validate({"schema": 3, "tiers": [{"n": 1, "title": "T"}]})


def _run(*issues: Issue, judgements: Judgements = NONE) -> list[CandidateGroup]:
    return candidates(_facts(list(issues)), judgements)


def _reasons(groups: list[CandidateGroup]) -> list[str]:
    return [r for g in groups for p in g.pairs for r in p.reasons]


# --------------------------------------------------------------- calibration


def test_the_calibration_fixture_groups_the_known_duplicates() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    issues = [_issue(d["number"], d["title"], d["body"] or "") for d in raw]

    groups = {g.keys: g for g in _run(*issues)}

    for known in (
        (594, 607, 631),
        (640, 647),
        (724, 725),
        (868, 869),
    ):
        keys = tuple(f"super-fr#{n}" for n in known)
        assert keys in groups, f"{keys} not grouped; got {sorted(groups)}"
        assert all(p.reasons for p in groups[keys].pairs)


# ------------------------------------------------------------------ signals


def test_close_titles_flag_a_pair_with_the_ratio() -> None:
    groups = _run(_issue(1, "deliver gate refuses X"), _issue(2, "deliver gate refuses X again"))

    assert [g.keys for g in groups] == [("super-fr#1", "super-fr#2")]
    assert groups[0].pairs[0].reasons == ("title 0.75",)


def test_phase_titles_differing_only_by_number_are_not_a_title_match() -> None:
    assert _run(_issue(1, "x-0-agentic"), _issue(2, "x-1-agentic")) == []


def test_two_shared_rare_identifiers_flag_a_pair() -> None:
    a = _issue(1, "alpha one", "see `verify_tests_log` and `plan_phase_state`")
    b = _issue(2, "beta two", "also `plan_phase_state` then `verify_tests_log`")

    groups = _run(a, b)

    assert _reasons(groups) == ["identifiers plan_phase_state, verify_tests_log"]


def test_one_shared_identifier_needs_a_nearby_title() -> None:
    a = _issue(1, "alpha one", "`verify_tests_log` breaks")
    b = _issue(2, "beta two", "`verify_tests_log` too")
    assert _run(a, b) == []

    c = _issue(3, "tests log broken now", "`verify_tests_log` breaks")
    d = _issue(4, "tests log slow lately", "`verify_tests_log` too")
    assert _reasons(_run(c, d)) == ["identifiers verify_tests_log"]


def test_a_shared_module_or_file_name_never_counts() -> None:
    a = _issue(1, "alpha", "`fr/triage_cmd_pkg/batch_drive.py` and `batch_drive` and `own_thing_a`")
    b = _issue(
        2, "beta", "batch_drive.py, `triage_cmd_pkg::run` and `batch_drive` plus `own_thing_b`"
    )

    assert _run(a, b) == []


def test_a_dotted_path_is_reduced_to_its_leaf() -> None:
    a = _issue(1, "alpha", "`fr.run.telemetry.step_budget_cap` and `other_leaf_one`")
    b = _issue(2, "beta", "`fr.run.telemetry.step_budget_cap` and `other_leaf_one()`")

    assert _reasons(_run(a, b)) == ["identifiers other_leaf_one, step_budget_cap"]


def test_an_identifier_named_by_four_open_issues_is_not_rare() -> None:
    body = "`common_thing_a` and `common_thing_b`"
    issues = [_issue(n, f"title{n}", body) for n in (1, 2, 3, 4)]
    assert _run(*issues) == []
    assert len(_run(*issues[:3])) == 1  # three still count as rare


def test_a_finding_id_with_a_shared_reference_flags_a_pair() -> None:
    a = _issue(1, "alpha", "from finding r2-2 in #723")
    b = _issue(2, "beta", "journal finding r2-2, see #723 and #5")

    assert _reasons(_run(a, b)) == ["finding r2-2 (#723)"]


def test_a_finding_id_without_a_shared_reference_flags_nothing() -> None:
    a = _issue(1, "alpha", "finding r2-2 in #723")
    b = _issue(2, "beta", "finding r2-2 in #724")
    assert _run(a, b) == []


def test_the_word_after_finding_must_look_like_an_id() -> None:
    a = _issue(1, "alpha", "a finding from #723")
    b = _issue(2, "beta", "another finding from #723")
    assert _run(a, b) == []


def test_the_same_theme_with_fairly_close_titles_flags_a_pair() -> None:
    a = _issue(1, "aaa bbb ccc ddd eee fff ggg")
    b = _issue(2, "aaa bbb ccc hhh iii jjj kkk")
    judged = Judgements.model_validate(
        {
            "schema": 3,
            "tiers": [{"n": 1, "title": "T"}],
            "issues": {
                "super-fr#1": {"tier": 1, "theme": "Docs "},
                "super-fr#2": {"tier": 1, "theme": "docs"},
            },
        }
    )

    assert _reasons(_run(a, b, judgements=judged)) == ["theme docs, title 0.27"]


# --------------------------------------------------------------- exclusions


def _dupe_pair() -> tuple[Issue, Issue]:
    return _issue(1, "deliver gate refuses X"), _issue(2, "deliver gate refuses X again")


def test_an_issue_judged_a_duplicate_is_in_no_group() -> None:
    a, b = _dupe_pair()
    judged = Judgements.model_validate(
        {
            "schema": 3,
            "tiers": [{"n": 1, "title": "T"}],
            "issues": {"super-fr#2": {"tier": 1, "duplicate_of": "super-fr#1"}},
        }
    )
    assert _run(a, b, judgements=judged) == []


def test_distinct_from_on_either_side_silences_the_pair() -> None:
    a, b = _dupe_pair()
    for key, other in (("super-fr#1", "super-fr#2"), ("super-fr#2", "super-fr#1")):
        judged = Judgements.model_validate(
            {
                "schema": 3,
                "tiers": [{"n": 1, "title": "T"}],
                "issues": {key: {"tier": 1, "distinct_from": [other]}},
            }
        )
        assert _run(a, b, judgements=judged) == []


def test_closed_issues_and_prs_are_never_candidates() -> None:
    a, b = _dupe_pair()
    closed = _issue(2, b.title, state="closed")
    assert _run(a, closed) == []


# ------------------------------------------------------------ determinism


def test_groups_join_by_connectivity_and_are_sorted() -> None:
    issues = [
        _issue(30, "deliver gate refuses X"),
        _issue(10, "deliver gate refuses X again"),
        _issue(20, "deliver gate refuses X later"),
        _issue(5, "wholly different matter about caches"),
        _issue(7, "wholly different matter about caches again"),
    ]

    groups = _run(*issues)

    assert [g.keys for g in groups] == [
        ("super-fr#10", "super-fr#20", "super-fr#30"),
        ("super-fr#5", "super-fr#7"),
    ]
    assert groups == _run(*reversed(issues))
    for g in groups:
        assert list(g.pairs) == sorted(g.pairs, key=lambda p: (p.a, p.b))
        assert all(p.a < p.b for p in g.pairs)
