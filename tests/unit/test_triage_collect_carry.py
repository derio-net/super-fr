"""`collect_facts_counted`: known-closed issues are carried over, not re-viewed (gh#911).

Spec 2026-10-04-drive-scoped-collect §A-§B. The forge is `FakeForge`; carried
issues are built by hand, since a closed issue's identity is all the carry needs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr.commands import triage_cmd
from fr.triage.collect import CollectStats, collect_facts, collect_facts_counted
from fr.triage.errors import ForgeError
from fr.triage.model import Issue, Scope

from tests.unit.triage_fixtures import NOW, FakeForge, _issue, _pr_closing

REPO = "o/repo"
SCOPE = Scope(kind="repo", target=REPO)


def _carried(number: int, *, repo: str = REPO, state: str = "closed") -> Issue:
    return Issue(
        repo=repo,
        number=number,
        title="old",
        state=state,  # type: ignore[arg-type]
        url=f"https://github.com/{repo}/issues/{number}",
    )


def _view(number: int, *, repo: str = REPO) -> dict[str, Any]:
    return {
        "number": number,
        "title": f"fresh #{number}",
        "body": "",
        "labels": [],
        "state": "CLOSED",
        "url": f"https://github.com/{repo}/issues/{number}",
        "closedAt": "2026-09-20T10:00:00Z",
    }


def _forge(**kw: Any) -> FakeForge:
    kw.setdefault("issues", {REPO: []})
    kw.setdefault("prs", {REPO: []})
    return FakeForge(**kw)


def _viewed(forge: FakeForge) -> list[dict[str, Any]]:
    return forge.called("view_issue")


def test_a_carried_closed_key_is_not_viewed() -> None:
    forge = _forge(closed={(REPO, 5): _view(5)})

    facts, stats = collect_facts_counted(
        forge, SCOPE, now=NOW, judged=["repo#5"], carried=[_carried(5)]
    )

    assert _viewed(forge) == []
    [issue] = facts.issues
    assert (issue.state, issue.title) == ("closed", "old")
    assert stats == CollectStats(viewed=0, carried=1)


def test_a_carried_issues_prs_are_recomputed_from_this_pass() -> None:
    first = _forge(
        prs={REPO: [_pr_closing(owner="o", name="repo", number=5, pr_number=77)]},
        closed={(REPO, 5): _view(5)},
    )
    seen, _ = collect_facts_counted(first, SCOPE, now=NOW, judged=["repo#5"])
    assert [p.number for p in seen.issues[0].prs] == [77]  # the stale link to replace

    second = _forge(prs={REPO: [_pr_closing(owner="o", name="repo", number=5, pr_number=88)]})
    facts, stats = collect_facts_counted(
        second, SCOPE, now=NOW, judged=["repo#5"], carried=seen.issues
    )

    assert stats.carried == 1
    assert [p.number for p in facts.issues[0].prs] == [88]


def test_a_carried_key_that_reads_open_is_the_open_one_and_not_counted() -> None:
    forge = _forge(issues={REPO: [_issue(5, title="reopened")]})

    facts, stats = collect_facts_counted(
        forge, SCOPE, now=NOW, judged=["repo#5"], carried=[_carried(5)]
    )

    assert [(i.state, i.title) for i in facts.issues] == [("open", "reopened")]
    assert stats == CollectStats(viewed=0, carried=0)


def test_an_unseen_key_and_a_carried_open_issue_are_viewed() -> None:
    forge = _forge(closed={(REPO, 6): _view(6), (REPO, 7): _view(7)})

    facts, stats = collect_facts_counted(
        forge,
        SCOPE,
        now=NOW,
        judged=["repo#6", "repo#7"],
        carried=[_carried(7, state="open")],
    )

    assert sorted(kw["number"] for kw in _viewed(forge)) == [6, 7]
    assert stats == CollectStats(viewed=2, carried=0)
    assert all(i.state == "closed" and i.title.startswith("fresh") for i in facts.issues)


def test_a_truncated_open_list_carries_nothing() -> None:
    forge = _forge(issues={REPO: [_issue(9)]}, closed={(REPO, 5): _view(5)})

    facts, stats = collect_facts_counted(
        forge, SCOPE, now=NOW, judged=["repo#5"], carried=[_carried(5)], issue_limit=1
    )

    assert [kw["number"] for kw in _viewed(forge)] == [5]
    assert stats == CollectStats(viewed=1, carried=0)
    assert next(i for i in facts.issues if i.number == 5).title == "fresh #5"


def test_viewed_counts_failed_views_and_pr_past_limit() -> None:
    pull = {**_view(8), "url": f"https://github.com/{REPO}/pull/8", "state": "OPEN"}
    forge = _forge(closed={(REPO, 8): pull})
    # #6 has no entry: FakeForge raises KeyError, so wrap it as a ForgeError.
    real = forge.view_issue

    def view(*, repo: str, number: int) -> dict[str, Any]:
        if number == 6:
            forge.calls.append(("view_issue", {"repo": repo, "number": number}))
            raise ForgeError("HTTP 502")
        return real(repo=repo, number=number)

    forge.view_issue = view  # type: ignore[method-assign]

    facts, stats = collect_facts_counted(forge, SCOPE, now=NOW, judged=["repo#6", "repo#8"])

    assert stats == CollectStats(viewed=2, carried=0)
    assert len(facts.unviewed) == 2


def test_a_carried_issue_of_another_owner_is_not_carried_into_this_repo() -> None:
    scope = Scope.group(["a/x", "b/x"])
    forge = FakeForge(
        issues={"a/x": [], "b/x": []},
        prs={"a/x": [], "b/x": []},
        closed={("a/x", 5): _view(5, repo="a/x"), ("b/x", 5): _view(5, repo="b/x")},
    )

    # The bare key `x#5` resolves to one repo (b/x); a carry under a/x is not it.
    facts, stats = collect_facts_counted(
        forge, scope, now=NOW, judged=["x#5"], carried=[_carried(5, repo="a/x")]
    )

    assert stats == CollectStats(viewed=1, carried=0)
    assert [i.title for i in facts.issues] == ["fresh #5"]


def test_a_carried_issue_in_a_skipped_repo_is_not_emitted() -> None:
    scope = Scope(kind="org", target="example-org")
    forge = FakeForge(
        repos=[{"name": n, "isArchived": False} for n in ("alpha", "beta")],
        issues={"example-org/alpha": [], "example-org/beta": []},
        prs={"example-org/alpha": [], "example-org/beta": []},
        failing={"example-org/beta": "HTTP 403"},
    )

    facts, stats = collect_facts_counted(
        forge, scope, now=NOW, judged=["beta#5"], carried=[_carried(5, repo="example-org/beta")]
    )

    assert [s.repo for s in facts.skipped] == ["example-org/beta"]
    assert facts.issues == []
    assert stats == CollectStats(viewed=0, carried=0)


def test_collect_facts_without_carried_equals_the_counted_facts_and_views_all() -> None:
    def mk() -> FakeForge:
        return _forge(closed={(REPO, 5): _view(5)})

    plain = collect_facts(mk(), SCOPE, now=NOW, judged=["repo#5"])
    forge = mk()
    counted, stats = collect_facts_counted(forge, SCOPE, now=NOW, judged=["repo#5"])

    assert plain == counted
    assert stats == CollectStats(viewed=1, carried=0)


# ---------------------------------------------------------------- command layer


def _write_judgements(target: Path, key: str = "repo#5") -> None:
    (target / "judgements.yaml").write_text(
        f'schema: 1\ntiers: [{{n: 1, title: T}}]\nissues:\n  "{key}": {{tier: 1}}\n',
        encoding="utf-8",
    )


@pytest.fixture
def forge(monkeypatch: pytest.MonkeyPatch) -> FakeForge:
    fake = _forge(closed={(REPO, 5): _view(5)})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: fake)
    return fake


def test_collect_into_with_carry_views_nothing_on_the_second_pass(
    tmp_path: Path, forge: FakeForge
) -> None:
    _write_judgements(tmp_path)
    triage_cmd.collect_into(SCOPE, tmp_path, carry=True)
    forge.calls.clear()

    _, _, stats = triage_cmd.collect_into(SCOPE, tmp_path, carry=True)

    assert _viewed(forge) == []
    assert stats == CollectStats(viewed=0, carried=1)


@pytest.mark.parametrize("previous", ["missing", "corrupt", "other-scope"])
def test_collect_into_with_carry_views_when_the_previous_facts_are_no_use(
    tmp_path: Path, forge: FakeForge, previous: str
) -> None:
    _write_judgements(tmp_path)
    if previous == "corrupt":
        (tmp_path / "facts.json").write_text("{", encoding="utf-8")
    elif previous == "other-scope":
        triage_cmd.collect_into(SCOPE, tmp_path)  # a valid facts.json ...
        path = tmp_path / "facts.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["scope"] = "o--other"  # ... that belongs to another scope
        path.write_text(json.dumps(data), encoding="utf-8")

    _, _, stats = triage_cmd.collect_into(SCOPE, tmp_path, carry=True)

    assert stats == CollectStats(viewed=1, carried=0)


def test_collect_into_with_carry_views_a_key_the_previous_pass_could_not_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_judgements(tmp_path)
    failing = _forge()

    def view_fails(*, repo: str, number: int) -> dict[str, Any]:
        raise ForgeError("HTTP 502")  # the read fails: #5 is recorded unviewed

    failing.view_issue = view_fails  # type: ignore[method-assign]
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: failing)
    facts, _, _ = triage_cmd.collect_into(SCOPE, tmp_path, carry=True)
    assert [u.key for u in facts.unviewed] == ["repo#5"]

    answering = _forge(closed={(REPO, 5): _view(5)})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: answering)
    facts, _, stats = triage_cmd.collect_into(SCOPE, tmp_path, carry=True)

    assert len(_viewed(answering)) == 1
    assert stats == CollectStats(viewed=1, carried=0)
    assert [i.state for i in facts.issues] == ["closed"]


def test_collect_into_without_carry_views_every_time(tmp_path: Path, forge: FakeForge) -> None:
    _write_judgements(tmp_path)
    triage_cmd.collect_into(SCOPE, tmp_path)
    forge.calls.clear()

    _, _, stats = triage_cmd.collect_into(SCOPE, tmp_path)

    assert len(_viewed(forge)) == 1
    assert stats == CollectStats(viewed=1, carried=0)


def test_the_collect_command_views_on_a_second_run_too(tmp_path: Path, forge: FakeForge) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    _write_judgements(tmp_path)
    args = ["triage", "collect", "--repo", REPO, "--dir", str(tmp_path)]
    assert CliRunner().invoke(app, args).exit_code == 0
    forge.calls.clear()
    assert CliRunner().invoke(app, args).exit_code == 0

    assert len(_viewed(forge)) == 1


def test_a_duplicate_of_target_in_a_collected_repo_is_viewed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _forge(closed={(REPO, 8): _view(8)})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: fake)
    (tmp_path / "judgements.yaml").write_text(
        "schema: 3\ntiers: [{n: 1, title: T}]\nissues:\n"
        '  "repo#5": {tier: 1, duplicate_of: "Repo#8"}\n',
        encoding="utf-8",
    )

    triage_cmd.collect_into(SCOPE, tmp_path)

    assert sorted(kw["number"] for kw in _viewed(fake)) == [5, 8]
