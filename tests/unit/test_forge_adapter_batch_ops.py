"""The forge adapter's batch operations (spec 2026-09-25-triage-batches §3.J, Test Plan 19).

`RealGhClient` implements each new `GhClient` method over `fr.gh`, with the
`gh` subprocess faked at `fr.gh._run_gh` (the pattern of
`test_real_ghclient.py`). `RealGlabClient` and `RealTeaClient` declare every
one of them unsupported, one method at a time, with a typed refusal naming
the operation, the backend and gh#611.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr import gh as _gh
from fr.ghclient import UnsupportedForgeOperation
from fr.real_ghclient import RealGhClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient

REPO = "derio-net/super-fr"


class _Gh:
    """A `_run_gh` stand-in: canned stdout by argv prefix, every call recorded."""

    def __init__(self, returns: dict[tuple[str, ...], str | Exception]) -> None:
        self.returns = returns
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> str:
        self.calls.append(list(args))
        for prefix, value in self.returns.items():
            if tuple(args[: len(prefix)]) == prefix:
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError(f"unexpected gh call: {args}")


def _fake(monkeypatch: pytest.MonkeyPatch, returns: dict[tuple[str, ...], Any]) -> _Gh:
    fake = _Gh(returns)
    monkeypatch.setattr(_gh, "_run_gh", fake)
    return fake


# ------------------------------------------------------------ RealGhClient


def test_list_issue_comments_returns_body_author_and_created_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = {
        "comments": [
            {"author": {"login": "a"}, "body": "first", "createdAt": "2026-09-25T10:00:00Z"},
            {"author": {"login": "b"}, "body": "second", "createdAt": "2026-09-26T10:00:00Z"},
        ]
    }
    fake = _fake(monkeypatch, {("issue", "view"): json.dumps(raw)})

    comments = RealGhClient().list_issue_comments(REPO, 577)

    assert comments == [
        {"author": "a", "body": "first", "created_at": "2026-09-25T10:00:00Z"},
        {"author": "b", "body": "second", "created_at": "2026-09-26T10:00:00Z"},
    ]
    assert fake.calls == [["issue", "view", "577", "--repo", REPO, "--json", "comments"]]


def test_list_prs_by_head_lists_every_state_for_the_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [{"number": 9, "state": "MERGED", "headRefName": "feat/batch-x"}]
    fake = _fake(monkeypatch, {("pr", "list"): json.dumps(records)})

    prs = RealGhClient().list_prs_by_head(REPO, "feat/batch-x")

    assert prs == records
    (call,) = fake.calls
    assert call[:4] == ["pr", "list", "--repo", REPO]
    assert call[call.index("--head") + 1] == "feat/batch-x"
    assert call[call.index("--state") + 1] == "all"
    fields = call[call.index("--json") + 1].split(",")
    assert {"number", "state", "headRefName", "closingIssuesReferences"} <= set(fields)


def test_pr_view_shapes_state_draft_head_oid_and_mergeable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = {
        "state": "OPEN",
        "isDraft": True,
        "headRefOid": "abc123",
        "headRefName": "feat/batch-x",
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "BEHIND",
    }
    _fake(monkeypatch, {("pr", "view"): json.dumps(raw)})

    view = RealGhClient().pr_view(REPO, 12)

    assert view == {
        "state": "OPEN",
        "draft": True,
        "head_oid": "abc123",
        "head_ref": "feat/batch-x",
        "mergeable": "MERGEABLE",
        "merge_state": "BEHIND",
    }


def test_pr_required_checks_returns_name_and_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = [{"name": "test", "bucket": "pass", "state": "SUCCESS"}]
    fake = _fake(monkeypatch, {("pr", "checks"): json.dumps(raw)})

    checks = RealGhClient().pr_required_checks(REPO, 12)

    assert checks == [{"name": "test", "bucket": "pass", "state": "SUCCESS"}]
    assert "--required" in fake.calls[0]


def test_pr_required_checks_reads_the_output_of_a_pending_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`gh pr checks` exits 8 while checks are pending; its JSON is still the answer."""
    raw = [{"name": "test", "bucket": "pending", "state": "IN_PROGRESS"}]
    _fake(
        monkeypatch,
        {("pr", "checks"): _gh.GhError("pending", stdout=json.dumps(raw), returncode=8)},
    )

    assert RealGhClient().pr_required_checks(REPO, 12)[0]["bucket"] == "pending"


def test_pr_required_checks_is_empty_when_the_branch_requires_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake(
        monkeypatch,
        {
            ("pr", "checks"): _gh.GhError(
                "no required checks reported on the 'feat/x' branch", returncode=1
            )
        },
    )

    assert RealGhClient().pr_required_checks(REPO, 12) == []


def test_wait_required_checks_polls_until_nothing_is_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rounds = iter(
        [
            [{"name": "t", "bucket": "pending", "state": "IN_PROGRESS"}],
            [{"name": "t", "bucket": "pass", "state": "SUCCESS"}],
        ]
    )
    client = RealGhClient()
    monkeypatch.setattr(client, "pr_required_checks", lambda repo, number: next(rounds))
    slept: list[float] = []

    final = client.wait_required_checks(REPO, 12, interval=5.0, timeout=60.0, sleep=slept.append)

    assert final == [{"name": "t", "bucket": "pass", "state": "SUCCESS"}]
    assert slept == [5.0]


def test_wait_required_checks_gives_up_at_the_timeout_with_the_last_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pending = [{"name": "t", "bucket": "pending", "state": "IN_PROGRESS"}]
    client = RealGhClient()
    monkeypatch.setattr(client, "pr_required_checks", lambda repo, number: pending)
    slept: list[float] = []

    final = client.wait_required_checks(REPO, 12, interval=10.0, timeout=25.0, sleep=slept.append)

    assert final == pending
    assert sum(slept) <= 25.0
    assert len(slept) == 2


def test_pr_merge_matches_the_head_commit_and_never_passes_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake(monkeypatch, {("pr", "merge"): ""})

    RealGhClient().pr_merge(REPO, 12, head_sha="abc123", method="squash")

    (call,) = fake.calls
    assert call[:5] == ["pr", "merge", "12", "--repo", REPO]
    assert "--squash" in call
    assert call[call.index("--match-head-commit") + 1] == "abc123"
    assert "--admin" not in call


def test_pr_merge_refuses_an_unknown_method(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, {})
    with pytest.raises(ValueError, match="method"):
        RealGhClient().pr_merge(REPO, 12, head_sha="abc", method="admin")


def test_pr_merge_propagates_a_protection_refusal_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    msg = "X Pull request derio-net/super-fr#12 is not mergeable: the base branch policy"
    _fake(monkeypatch, {("pr", "merge"): _gh.GhError(msg, returncode=1)})
    with pytest.raises(_gh.GhError, match="base branch policy"):
        RealGhClient().pr_merge(REPO, 12, head_sha="abc", method="merge")


def test_closing_ref_is_githubs_cross_repo_closes_line() -> None:
    assert RealGhClient().closing_ref(REPO, 577) == "Closes derio-net/super-fr#577"


# ------------------------------------------------------- declared refusals

_CALLS: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {
    "list_issue_comments": ((REPO, 1), {}),
    "list_prs_by_head": ((REPO, "feat/batch-x"), {}),
    "pr_view": ((REPO, 1), {}),
    "pr_required_checks": ((REPO, 1), {}),
    "wait_required_checks": ((REPO, 1), {}),
    "pr_merge": ((REPO, 1), {"head_sha": "abc", "method": "merge"}),
    "closing_ref": ((REPO, 1), {}),
}


@pytest.mark.parametrize(
    ("client", "backend"),
    [(RealGlabClient(), "gitlab"), (RealTeaClient(), "gitea")],
    ids=["glab", "tea"],
)
@pytest.mark.parametrize("op", sorted(_CALLS))
def test_glab_and_tea_declare_each_batch_operation_unsupported(
    client: Any, backend: str, op: str
) -> None:
    args, kwargs = _CALLS[op]
    with pytest.raises(UnsupportedForgeOperation) as info:
        getattr(client, op)(*args, **kwargs)
    message = str(info.value)
    assert op in message
    assert backend in message
    assert "gh#611" in message
    assert info.value.op == op
    assert info.value.backend == backend


def test_the_protocol_declares_every_batch_operation() -> None:
    from fr.ghclient import GhClient

    for op in _CALLS:
        assert hasattr(GhClient, op), op


# ------------------------------------------------------------- tripwire (§3.J)

_BATCH_MODULES = {
    "fr.triage": "packages/fr/src/fr/triage/batch.py",
    "fr.commands": "packages/fr/src/fr/commands/triage_batch_cmd.py",
}
_FORGE_CLIS = ("fr.gh", "fr.glab", "fr.tea", "subprocess", "fr.triage.collect")


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(("package", "path"), sorted(_BATCH_MODULES.items()))
def test_no_batch_module_reaches_a_forge_cli_or_triage_forge(package: str, path: str) -> None:
    """Batch verbs go through the GhClient adapter only (spec §3.J, Test Plan 19)."""
    from tests.unit.triage_fixtures import forbidden_imports

    assert forbidden_imports(_root() / path, package, _FORGE_CLIS) == []


@pytest.mark.parametrize(
    "source",
    ["from fr import gh", "import subprocess", "from fr.triage.collect import GhForge",
     "from fr import tea", "import fr.glab"],
)  # fmt: skip
def test_the_batch_tripwire_catches_each_forbidden_import(tmp_path: Path, source: str) -> None:
    from tests.unit.triage_fixtures import forbidden_imports

    plant = tmp_path / "plant.py"
    plant.write_text(source + "\n", encoding="utf-8")
    assert forbidden_imports(plant, "fr.triage", _FORGE_CLIS) != []
