"""`facts.json` schema 3 (spec 2026-09-25-triage-batches §3.F Facts, §3.I, Test Plan 15).

The forge is faked (`tests.unit.triage_fixtures.FakeForge`). Schema 3 adds:
`PullRequest.files`/`head_oid`, filled on a LINKED open PR by joining the
open-PR record with the same (repo, number); `Issue.dispatch_marker_at` from
the fr-batch marker comment of an `fr:in-progress` issue; `Facts.batch_prs`
from one head-branch lookup per dispatched batch; `Facts.config` from
`.fr/triage.yaml` read at the default branch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr.triage.collect import CONFIG_PATH, collect_facts
from fr.triage.errors import ForgeError, TriageError
from fr.triage.model import FACTS_SCHEMA, Scope, batch_marker, load_facts

from tests.unit.triage_fixtures import NOW, FakeForge

REPO = "example-org/alpha"
SCOPE = Scope(kind="repo", target=REPO)


def _ref(number: int) -> dict[str, Any]:
    return {"repository": {"owner": {"login": "example-org"}, "name": "alpha"}, "number": number}


def _pr(number: int, *, state: str = "OPEN", head: str = "topic", refs: list[int] = ()) -> dict:
    return {
        "number": number,
        "title": f"PR {number}",
        "state": state,
        "isDraft": False,
        "mergedAt": "2026-09-24T00:00:00Z" if state == "MERGED" else None,
        "url": f"https://github.com/{REPO}/pull/{number}",
        "headRefName": head,
        "closingIssuesReferences": [_ref(n) for n in refs],
    }


def _open_record(number: int, *, head: str = "topic", refs: list[int] = ()) -> dict:
    return {
        **_pr(number, head=head, refs=refs),
        "headRefOid": "0123abcd",
        "files": [{"path": "packages/fr/src/fr/isolation/local.py"}, {"path": "README.md"}],
        "statusCheckRollup": [{"conclusion": "SUCCESS"}, {"conclusion": "FAILURE"}],
        "mergeable": "CONFLICTING",
        "mergeStateStatus": "DIRTY",
        "reviewDecision": None,
    }


def _issue(number: int, labels: tuple[str, ...] = ()) -> dict:
    return {
        "number": number,
        "title": f"issue {number}",
        "labels": [{"name": n} for n in labels],
        "url": f"https://github.com/{REPO}/issues/{number}",
    }


class _Forge(FakeForge):
    """FakeForge whose open-PR list is its own record set (with files and head oid)."""

    def __init__(self, *, open_prs: list[dict], **kw: Any) -> None:
        super().__init__(**kw)
        self.open_prs = open_prs

    def list_open_prs(self, *, repo: str, limit: int) -> list[dict[str, Any]]:
        self.calls.append(("list_open_prs", {"repo": repo, "limit": limit}))
        return self.open_prs


def test_facts_are_written_at_schema_3() -> None:
    forge = _Forge(issues={REPO: []}, prs={REPO: []}, open_prs=[])
    assert FACTS_SCHEMA == 3
    assert collect_facts(forge, SCOPE, now=NOW).to_json()["schema"] == 3


def test_a_linked_open_pr_gains_files_head_oid_checks_and_merge_state_from_the_join() -> None:
    forge = _Forge(
        issues={REPO: [_issue(7)]},
        prs={REPO: [_pr(12, refs=[7])]},
        open_prs=[_open_record(12, refs=[7])],
    )

    (issue,) = collect_facts(forge, SCOPE, now=NOW).issues
    (pr,) = issue.prs

    assert pr.files == ["packages/fr/src/fr/isolation/local.py", "README.md"]
    assert pr.head_oid == "0123abcd"
    assert pr.checks == {"pass": 1, "fail": 1, "pending": 0}
    assert pr.mergeable == "CONFLICTING"
    assert pr.merge_state == "DIRTY"


def test_a_closed_linked_pr_keeps_its_defaults() -> None:
    forge = _Forge(
        issues={REPO: [_issue(7)]}, prs={REPO: [_pr(3, state="MERGED", refs=[7])]}, open_prs=[]
    )

    (pr,) = collect_facts(forge, SCOPE, now=NOW).issues[0].prs

    assert (pr.files, pr.head_oid, pr.merge_state) == ([], "", "UNKNOWN")


def test_an_in_progress_issue_gets_the_age_of_its_latest_fr_batch_marker() -> None:
    item = f"{REPO}/run/batch-lifecycle"
    comments = [
        {"author": "a", "body": "unrelated", "created_at": "2026-09-20T00:00:00Z"},
        {
            "author": "a",
            "body": batch_marker(item) + "\nDispatched",
            "created_at": "2026-09-22T09:00:00Z",
        },
        {"author": "a", "body": "later chatter", "created_at": "2026-09-23T00:00:00Z"},
    ]
    forge = _Forge(
        issues={REPO: [_issue(7, ("fr:in-progress",)), _issue(8)]},
        prs={REPO: []},
        open_prs=[],
        comments={(REPO, 7): comments},
    )

    facts = collect_facts(forge, SCOPE, now=NOW)

    by_number = {i.number: i for i in facts.issues}
    assert by_number[7].dispatch_marker_at == "2026-09-22T09:00:00Z"
    assert by_number[8].dispatch_marker_at is None
    # One comment read per fr:in-progress issue, none for the rest.
    assert forge.called("list_issue_comments") == [{"repo": REPO, "number": 7}]


def test_a_marker_with_no_created_at_gives_no_dispatch_time() -> None:
    """Review r2p-f13: an empty stamp is not a time; it never reaches check."""
    item = f"{REPO}/run/batch-lifecycle"
    comments = [{"author": "a", "body": batch_marker(item), "created_at": ""}]
    forge = _Forge(
        issues={REPO: [_issue(7, ("fr:in-progress",))]},
        prs={REPO: []},
        open_prs=[],
        comments={(REPO, 7): comments},
    )

    assert collect_facts(forge, SCOPE, now=NOW).issues[0].dispatch_marker_at is None


def test_a_withdrawn_marker_is_not_a_dispatch_marker() -> None:
    comments = [
        {
            "author": "a",
            "body": f"<!-- fr-batch-withdrawn:{REPO}/run/batch-x -->",
            "created_at": "t",
        }
    ]
    forge = _Forge(
        issues={REPO: [_issue(7, ("fr:in-progress",))]},
        prs={REPO: []},
        open_prs=[],
        comments={(REPO, 7): comments},
    )

    assert collect_facts(forge, SCOPE, now=NOW).issues[0].dispatch_marker_at is None


def test_a_dispatched_batch_branch_lands_its_prs_in_batch_prs() -> None:
    """A merged PR whose body lost every Closes line links to no member; the
    head-branch lookup is how the batch still finds it (spec §3.A)."""
    lost = {**_pr(40, state="MERGED", head="feat/batch-x"), "headRefOid": "feedbeef"}
    forge = _Forge(
        issues={REPO: [_issue(7)]},
        prs={REPO: []},
        open_prs=[],
        head_prs={(REPO, "feat/batch-x"): [lost]},
    )

    facts = collect_facts(forge, SCOPE, now=NOW, batch_branches=[("alpha", "feat/batch-x")])

    assert [(p.number, p.state, p.head_ref, p.head_oid) for p in facts.batch_prs] == [
        (40, "MERGED", "feat/batch-x", "feedbeef")
    ]
    assert forge.called("list_prs_by_head") == [{"repo": REPO, "branch": "feat/batch-x"}]


def test_a_branch_already_on_a_linked_pr_costs_no_lookup() -> None:
    forge = _Forge(
        issues={REPO: [_issue(7)]},
        prs={REPO: [_pr(12, head="feat/batch-x", refs=[7])]},
        open_prs=[_open_record(12, head="feat/batch-x", refs=[7])],
    )

    facts = collect_facts(forge, SCOPE, now=NOW, batch_branches=[("alpha", "feat/batch-x")])

    assert forge.called("list_prs_by_head") == []
    assert facts.batch_prs == []


def test_a_batch_in_a_repo_outside_the_scope_is_not_looked_up() -> None:
    forge = _Forge(issues={REPO: []}, prs={REPO: []}, open_prs=[])

    collect_facts(forge, SCOPE, now=NOW, batch_branches=[("beta", "feat/batch-x")])

    assert forge.called("list_prs_by_head") == []


_CONFIG = """\
defaults:
  launch: {runner: herdr, harness: claude, model: claude-opus-5-5}
version:
  source: {file: pyproject.toml, key: project.version}
  files: ["pyproject.toml", "uv.lock"]
  set: "uv run --no-project python scripts/bump-version.py {version}"
stale_dispatch_days: 5
"""


def test_the_repo_config_is_read_once_at_the_default_branch_into_facts() -> None:
    forge = _Forge(
        issues={REPO: []},
        prs={REPO: []},
        open_prs=[],
        file_bodies={(REPO, CONFIG_PATH, "HEAD"): _CONFIG},
    )

    facts = collect_facts(forge, SCOPE, now=NOW)

    config = facts.config[REPO]
    assert config.defaults.launch.runner == "herdr"
    assert config.defaults.launch.model == "claude-opus-5-5"
    assert config.version is not None
    assert config.version.source.key == "project.version"
    assert config.version.set_ == "uv run --no-project python scripts/bump-version.py {version}"
    assert config.version.relock is None
    assert config.stale_dispatch_days == 5
    assert forge.called("read_file_at_ref") == [{"repo": REPO, "path": CONFIG_PATH, "ref": "HEAD"}]


def test_an_absent_config_is_no_entry_and_the_defaults_apply() -> None:
    forge = _Forge(issues={REPO: []}, prs={REPO: []}, open_prs=[])

    facts = collect_facts(forge, SCOPE, now=NOW)

    assert facts.config == {}
    assert facts.config_for(REPO).stale_dispatch_days == 3
    assert facts.config_for(REPO).version is None


def test_a_malformed_config_is_refused_naming_the_repo_and_file() -> None:
    forge = _Forge(
        issues={REPO: []},
        prs={REPO: []},
        open_prs=[],
        file_bodies={(REPO, CONFIG_PATH, "HEAD"): "stale_dispatch_days: soon\n"},
    )

    with pytest.raises(TriageError, match=r"example-org/alpha.*\.fr/triage\.yaml"):
        collect_facts(forge, SCOPE, now=NOW)


ORG = Scope(kind="org", target="example-org")
_NAMES = ("alpha", "beta", "gamma")


def _org_forge(**kw: Any) -> _Forge:
    """example-org: three repos, one fr:in-progress issue each, no PRs."""
    return _Forge(
        repos=[{"name": n, "isArchived": False} for n in _NAMES],
        issues={f"example-org/{n}": [_issue(1, ("fr:in-progress",))] for n in _NAMES},
        prs={f"example-org/{n}": [] for n in _NAMES},
        open_prs=[],
        **kw,
    )


def test_org_scope_skips_a_repo_whose_config_is_invalid() -> None:
    """Review r2p-f4: one repo's bad .fr/triage.yaml does not abort an org collect."""
    forge = _org_forge(
        file_bodies={("example-org/beta", CONFIG_PATH, "HEAD"): "stale_dispatch_days: soon\n"}
    )

    facts = collect_facts(forge, ORG, now=NOW)

    ((repo, reason),) = [(s.repo, s.reason) for s in facts.skipped]
    assert repo == "example-org/beta"
    assert ".fr/triage.yaml" in reason
    assert sorted({i.repo for i in facts.issues}) == ["example-org/alpha", "example-org/gamma"]


def _failing_comments(forge: _Forge, repo: str) -> None:
    real = forge.list_issue_comments

    def comments(*, repo: str = repo, number: int, _bad: str = repo) -> list[dict[str, Any]]:
        if repo == _bad:
            raise ForgeError("HTTP 502")
        return real(repo=repo, number=number)

    forge.list_issue_comments = comments  # type: ignore[method-assign]


def test_org_scope_skips_a_repo_whose_comment_read_fails() -> None:
    forge = _org_forge()
    _failing_comments(forge, "example-org/gamma")

    facts = collect_facts(forge, ORG, now=NOW)

    assert [(s.repo, s.reason) for s in facts.skipped] == [("example-org/gamma", "HTTP 502")]
    assert sorted({i.repo for i in facts.issues}) == ["example-org/alpha", "example-org/beta"]


def test_repo_scope_still_fails_loudly_on_a_comment_read() -> None:
    forge = _Forge(issues={REPO: [_issue(7, ("fr:in-progress",))]}, prs={REPO: []}, open_prs=[])
    _failing_comments(forge, REPO)

    with pytest.raises(ForgeError, match="HTTP 502"):
        collect_facts(forge, SCOPE, now=NOW)


def test_schema_3_facts_round_trip_through_the_loader(tmp_path: Path) -> None:
    forge = _Forge(
        issues={REPO: [_issue(7)]},
        prs={REPO: [_pr(12, refs=[7])]},
        open_prs=[_open_record(12, refs=[7])],
        file_bodies={(REPO, CONFIG_PATH, "HEAD"): _CONFIG},
    )
    facts = collect_facts(forge, SCOPE, now=NOW)
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(facts.to_json()), encoding="utf-8")

    assert load_facts(path) == facts


def test_schema_2_facts_are_refused_with_the_recollect_message(tmp_path: Path) -> None:
    path = tmp_path / "facts.json"
    doc = {
        "schema": 2,
        "scope": "example-org--alpha",
        "kind": "repo",
        "collected_at": "2026-09-21T00:00:00+00:00",
        "repos": [REPO],
        "issues": [],
    }
    path.write_text(json.dumps(doc), encoding="utf-8")

    with pytest.raises(TriageError, match=r"facts\.json.*schema 2.*re-run collect"):
        load_facts(path)


def test_the_collect_command_looks_up_the_branch_of_each_batch_last_dispatched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a batch whose LAST event is a dispatch is looked up (spec §3.A)."""
    from fr.cli import app
    from fr.commands import triage_cmd
    from typer.testing import CliRunner

    (tmp_path / "judgements.yaml").write_text(
        "schema: 2\n"
        "tiers: [{n: 1, title: Now}]\n"
        "issues: {alpha#7: {tier: 1}, alpha#8: {tier: 1}, alpha#9: {tier: 1}}\n"
        "batches:\n"
        "  - {id: live, title: t, ids: [alpha#7], events: [{kind: dispatch, "
        "at: '2026-09-25T00:00:00Z', runner: herdr, handle: h, branch: feat/batch-live}]}\n"
        "  - {id: gone, title: t, ids: [alpha#8], events: [{kind: dispatch, "
        "at: '2026-09-25T00:00:00Z', runner: herdr, handle: h, branch: feat/batch-gone}, "
        "{kind: cancel, at: '2026-09-26T00:00:00Z'}]}\n"
        "  - {id: idea, title: t, ids: [alpha#9]}\n",
        encoding="utf-8",
    )
    forge = _Forge(issues={REPO: [_issue(7), _issue(8), _issue(9)]}, prs={REPO: []}, open_prs=[])
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)

    result = CliRunner().invoke(app, ["triage", "collect", "--repo", REPO, "--dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert forge.called("list_prs_by_head") == [{"repo": REPO, "branch": "feat/batch-live"}]
