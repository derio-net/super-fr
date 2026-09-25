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


def test_wait_required_checks_waits_for_checks_to_appear_after_a_push(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review r2p-f10: right after a push GitHub has registered no check runs
    yet, so `[]` is not yet "no required checks". The wait polls through a
    bounded grace period until checks appear."""
    rounds = iter(
        [
            [],
            [],
            [{"name": "t", "bucket": "pending", "state": "QUEUED"}],
            [{"name": "t", "bucket": "fail", "state": "FAILURE"}],
        ]
    )
    client = RealGhClient()
    monkeypatch.setattr(client, "pr_required_checks", lambda repo, number: next(rounds))
    slept: list[float] = []

    final = client.wait_required_checks(
        REPO, 12, interval=5.0, timeout=60.0, grace=30.0, sleep=slept.append
    )

    assert final == [{"name": "t", "bucket": "fail", "state": "FAILURE"}]
    assert slept == [5.0, 5.0, 5.0]


def test_wait_required_checks_accepts_none_required_once_the_grace_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = RealGhClient()
    monkeypatch.setattr(client, "pr_required_checks", lambda repo, number: [])
    slept: list[float] = []

    final = client.wait_required_checks(
        REPO, 12, interval=10.0, timeout=600.0, grace=25.0, sleep=slept.append
    )

    assert final == []
    assert sum(slept) >= 25.0 - 10.0 and sum(slept) <= 30.0


def test_pr_required_checks_raises_on_a_pending_exit_with_no_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review r2p-f10: exit 8 means "pending"; with no JSON to read, the answer is
    unknown, which must never read as "no required checks" (an empty list)."""
    _fake(monkeypatch, {("pr", "checks"): _gh.GhError("", stdout="", returncode=8)})
    with pytest.raises(_gh.GhError):
        RealGhClient().pr_required_checks(REPO, 12)


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


def test_repo_merge_methods_reads_the_viewer_default_and_the_allowed_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shape captured live 2026-09-26 from `gh repo view derio-net/super-fr`."""
    captured = (
        '{"mergeCommitAllowed":true,"rebaseMergeAllowed":false,'
        '"squashMergeAllowed":true,"viewerDefaultMergeMethod":"SQUASH"}'
    )
    fake = _fake(monkeypatch, {("repo", "view"): captured})

    got = RealGhClient().repo_merge_methods(REPO)

    assert got == {"default": "squash", "allowed": ["merge", "squash"]}
    (call,) = fake.calls
    assert call[:3] == ["repo", "view", REPO]
    fields = set(call[call.index("--json") + 1].split(","))
    assert fields == {
        "viewerDefaultMergeMethod",
        "mergeCommitAllowed",
        "squashMergeAllowed",
        "rebaseMergeAllowed",
    }


def test_repo_merge_methods_maps_an_unknown_default_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake(monkeypatch, {("repo", "view"): '{"squashMergeAllowed":true}'})
    assert RealGhClient().repo_merge_methods(REPO) == {"default": None, "allowed": ["squash"]}


# ------------------------------------------------------- declared refusals

_CALLS: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {
    "list_issue_comments": ((REPO, 1), {}),
    "list_prs_by_head": ((REPO, "feat/batch-x"), {}),
    "pr_view": ((REPO, 1), {}),
    "pr_required_checks": ((REPO, 1), {}),
    "wait_required_checks": ((REPO, 1), {}),
    "pr_merge": ((REPO, 1), {"head_sha": "abc", "method": "merge"}),
    "closing_ref": ((REPO, 1), {}),
    "repo_merge_methods": ((REPO,), {}),
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

# Every batch module, by glob (review r2p-f11): a module added later is covered
# without editing this list. `fr.triage.gitseam` is deliberately NOT matched:
# it is the one place git (and the repo's declared version commands) run, and
# it has its own guard below.
_BATCH_GLOBS = (
    "packages/fr/src/fr/triage/batch*.py",
    "packages/fr/src/fr/commands/triage_batch*.py",
)
_FORGE_CLIS = ("fr.gh", "fr.glab", "fr.tea", "subprocess", "fr.triage.collect")
_GIT_SEAM = "packages/fr/src/fr/triage/gitseam.py"


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _batch_modules() -> list[Path]:
    return sorted(p for g in _BATCH_GLOBS for p in _root().glob(g))


def test_the_batch_globs_find_every_batch_module() -> None:
    names = {p.name for p in _batch_modules()}
    assert {"batch.py", "batch_dispatch.py", "batch_merge.py", "triage_batch_cmd.py"} <= names
    assert "gitseam.py" not in names


@pytest.mark.parametrize("path", _batch_modules(), ids=lambda p: p.name)
def test_no_batch_module_reaches_a_forge_cli_or_triage_forge(path: Path) -> None:
    """Batch verbs go through the GhClient adapter only (spec §3.J, Test Plan 19)."""
    from tests.unit.triage_fixtures import forbidden_imports

    package = ".".join(path.relative_to(_root() / "packages/fr/src").with_suffix("").parts[:-1])
    assert forbidden_imports(path, package, _FORGE_CLIS) == []


def test_the_git_seam_runs_git_and_declared_commands_only() -> None:
    """The seam may use subprocess, but never a forge CLI (review r2p-f11)."""
    import ast

    from tests.unit.triage_fixtures import forbidden_imports

    path = _root() / _GIT_SEAM
    assert (
        forbidden_imports(path, "fr.triage", ("fr.gh", "fr.glab", "fr.tea", "fr.triage.collect"))
        == []
    )
    literals = {
        n.value
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    assert not literals & {"gh", "glab", "tea"}
    # Every process starts from one of the two argv builders.
    source = path.read_text(encoding="utf-8")
    assert source.count("subprocess.run(") == 2


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


# ------------------------------------------------ the git seam's surface (r3-f11)

# What a batch module may take from the git seam: the two classes whose
# methods are the declared git operations, and the error they raise. The
# seam's command runners (`_run`, `git`, `git_ok`, `run_declared`) would let a
# batch module run ANY command through the one module allowed subprocess.
_SEAM = "fr.triage.gitseam"
_SEAM_ALLOWED = frozenset({"Checkout", "Worktree", "GitError"})
_SEAM_RUNNERS = frozenset({"_run", "git", "git_ok", "run_declared"})


def _seam_breaches(source: str) -> list[str]:
    import ast

    out: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == _SEAM:
                out += [f"imports {a.name}" for a in node.names if a.name not in _SEAM_ALLOWED]
            elif module == "fr.triage" and any(a.name == "gitseam" for a in node.names):
                out.append("imports the gitseam module whole")
        elif isinstance(node, ast.Import):
            out += [f"imports {a.name}" for a in node.names if a.name == _SEAM]
        elif isinstance(node, ast.Attribute) and node.attr in _SEAM_RUNNERS:
            out.append(f"reaches .{node.attr}")
        elif isinstance(node, ast.Name) and node.id in _SEAM_RUNNERS:
            out.append(f"names {node.id}")
    return out


@pytest.mark.parametrize("path", _batch_modules(), ids=lambda p: p.name)
def test_batch_modules_reach_git_only_through_the_declared_worktree_methods(path: Path) -> None:
    assert _seam_breaches(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "source",
    [
        "from fr.triage.gitseam import run_declared",
        "from fr.triage.gitseam import _run",
        "from fr.triage.gitseam import git, git_ok",
        "from fr.triage import gitseam",
        "import fr.triage.gitseam",
        "def f(wt):\n    wt.run_declared('rm -rf /', wt.path)",
        "def f(seam):\n    seam._run(['sh', '-c', 'x'], seam.path)",
        "def f(seam):\n    seam.git(['push', '--force'], seam.path)",
    ],
)
def test_the_seam_tripwire_fires_on_each_way_around_it(source: str) -> None:
    assert _seam_breaches(source) != []


def test_the_seam_tripwire_admits_the_declared_surface() -> None:
    source = (
        "from fr.triage.gitseam import Checkout, GitError, Worktree\n"
        "def f(wt):\n    wt.merge('origin/main')\n    wt.run('uv lock')\n"
    )
    assert _seam_breaches(source) == []
