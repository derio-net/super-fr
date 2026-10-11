"""`fr triage batch adopt --list` (spec 2026-10-11-batch-adopt-safety-2 §D; R11–R17).

The pure parts (`parse_refs`, `resolve_ref`, `session_state`), the git seam's
`Checkout.facts`, the forge's `ref_kind`, and the listing over real throwaway
checkouts with a fake runner and a fake forge.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.ghclient import UnsupportedForgeOperation
from fr.real_ghclient import RealGhClient
from fr.real_ghrestclient import RealGhRestClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient
from fr.triage.batch import LabelRef, parse_refs, resolve_ref, session_state
from fr.triage.gitseam import Checkout
from fr_dispatch.protocols import AdoptTarget
from typer.testing import CliRunner

REPO = "acme/widgets"
URL = "https://example.com/acme/widgets.git"


# ---------------------------------------------------------------- pure parts


def test_parse_refs_reads_each_form_once_in_order() -> None:
    got = parse_refs("acme/widgets#314 then widgets#12 and #97")
    assert got == [
        LabelRef(owner="acme", name="widgets", number=314),
        LabelRef(owner=None, name="widgets", number=12),
        LabelRef(owner=None, name=None, number=97),
    ]


def test_an_owner_name_ref_never_also_yields_a_bare_ref() -> None:
    assert parse_refs("acme/widgets#314") == [LabelRef("acme", "widgets", 314)]


def test_parse_refs_reads_a_hyphen_prefixed_number_as_bare() -> None:
    """Review p3-r1: `feat-#12` is a bare `#12` after a hyphen, never a repo `feat-`."""
    assert parse_refs("fix feat-#12 and a/b#3") == [
        LabelRef(None, None, 12),
        LabelRef("a", "b", 3),
    ]


def test_parse_refs_finds_nothing_in_a_plain_label() -> None:
    assert parse_refs("fr-goal finish") == []


def test_resolve_ref_matches_the_repo_name_and_leaves_a_different_one() -> None:
    assert resolve_ref(LabelRef("acme", "widgets", 1), REPO) == "acme/widgets"
    assert resolve_ref(LabelRef("other", "gadgets", 1), REPO) == "other/gadgets"
    assert resolve_ref(LabelRef(None, "widgets", 1), REPO) == REPO
    assert resolve_ref(LabelRef(None, "gadgets", 1), REPO) is None
    assert resolve_ref(LabelRef(None, None, 1), REPO) == REPO
    assert resolve_ref(LabelRef(None, None, 1), None) is None
    assert resolve_ref(LabelRef(None, "widgets", 1), None) is None


def _state(**over: Any) -> str:
    args: dict[str, Any] = {
        "has_agent": True,
        "label": "widgets#1",
        "toplevel": "/x",
        "branch": "feat/x",
        "default": "main",
    }
    return session_state(**{**args, **over})


@pytest.mark.parametrize(
    ("over", "state"),
    [
        ({"has_agent": False}, "no agent"),
        ({"label": "3 · /run/batch-7"}, "batch"),
        ({"toplevel": None}, "unknown"),
        ({"default": None}, "unknown"),
        ({"branch": "main"}, "on default branch"),
        ({"branch": None}, "detached"),
        ({}, "adoptable"),
    ],
)
def test_session_state_precedence(over: dict[str, Any], state: str) -> None:
    assert _state(**over) == state


def test_no_agent_wins_over_a_batch_label_and_batch_over_unknown() -> None:
    assert _state(has_agent=False, label="/run/batch-1") == "no agent"
    assert _state(label="/run/batch-1", toplevel=None) == "batch"
    assert _state(toplevel=None, branch="main") == "unknown"
    assert _state(branch=None, default=None) == "unknown"


# ------------------------------------------------------------ Checkout.facts


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _clone(tmp_path: Path, name: str = "clone", *, origin_head: bool = True) -> Path:
    path = tmp_path / name
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(path, "config", k, v)
    (path / "a.txt").write_text("a\n")
    _git(path, "add", ".")
    _git(path, "commit", "-qm", "seed")
    _git(path, "remote", "add", "origin", URL)
    if origin_head:
        _git(path, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    return path


def test_facts_reads_the_checkout(tmp_path: Path) -> None:
    path = _clone(tmp_path)
    _git(path, "checkout", "-qb", "feat/x")
    facts = Checkout.facts(path)
    assert facts is not None
    assert facts.toplevel == path.resolve()
    assert facts.origin_url == URL
    assert facts.repo == REPO
    assert facts.branch == "feat/x"
    assert facts.default == "main"
    assert facts.main_worktree == path.resolve()


def test_facts_has_no_branch_when_detached_and_no_default_when_origin_head_is_unset(
    tmp_path: Path,
) -> None:
    path = _clone(tmp_path, origin_head=False)
    _git(path, "checkout", "-q", "--detach")
    facts = Checkout.facts(path)
    assert facts is not None
    assert facts.branch is None
    assert facts.default is None


def test_facts_of_a_subdirectory_and_a_linked_worktree(tmp_path: Path) -> None:
    path = _clone(tmp_path)
    (path / "sub").mkdir()
    sub = Checkout.facts(path / "sub")
    assert sub is not None and sub.toplevel == path.resolve()
    linked = tmp_path / "linked"
    _git(path, "worktree", "add", "-q", "-b", "feat/y", str(linked))
    facts = Checkout.facts(linked)
    assert facts is not None
    assert facts.branch == "feat/y"
    assert facts.main_worktree == path.resolve()


def test_facts_is_none_for_a_non_repo_directory(tmp_path: Path) -> None:
    bare = tmp_path / "plain"
    bare.mkdir()
    assert Checkout.facts(bare) is None
    assert Checkout.facts(tmp_path / "missing") is None


# ------------------------------------------------------------------ ref_kind


class _Api:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(list(argv))
        return json.dumps(self.payload)


def test_rest_ref_kind_reads_the_issues_route() -> None:
    pr = _Api({"number": 5, "pull_request": {"url": "u"}})
    assert RealGhRestClient(run=pr).ref_kind(REPO, 5) == "pr"
    assert any(f"repos/{REPO}/issues/5" in a for a in pr.calls[0])
    issue = _Api({"number": 6})
    assert RealGhRestClient(run=issue).ref_kind(REPO, 6) == "issue"


def test_gh_ref_kind_maps_the_issues_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    from fr import gh as _gh

    seen: list[list[str]] = []

    def run(argv: list[str]) -> str:
        seen.append(argv)
        return json.dumps({"pull_request": {}}) if argv[-1].endswith("/5") else "{}"

    monkeypatch.setattr(_gh, "_run_gh", run)
    client = RealGhClient()
    assert client.ref_kind(REPO, 5) == "pr"
    assert client.ref_kind(REPO, 6) == "issue"
    assert seen[0][:2] == ["api", f"repos/{REPO}/issues/5"]


def test_the_gh_ref_kind_is_hosted() -> None:
    assert getattr(RealGhClient.ref_kind, "__fr_hosted__", False)


@pytest.mark.parametrize("client", [RealGlabClient(), RealTeaClient()])
def test_glab_and_tea_cannot_classify_a_ref(client: Any) -> None:
    with pytest.raises(UnsupportedForgeOperation):
        client.ref_kind(REPO, 1)


# ------------------------------------------------------------------ listing


class ListGh:
    """A forge answering PR lists and ref kinds, counting each read."""

    def __init__(self) -> None:
        self.prs: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.kinds: dict[tuple[str, int], str] = {}
        self.pr_reads: list[tuple[str, str]] = []
        self.kind_reads: list[tuple[str, int]] = []
        self.fail_prs: set[str] = set()
        self.fail_kinds: set[int] = set()

    def list_prs_by_head(self, repo: str, branch: str) -> list[dict[str, Any]]:
        self.pr_reads.append((repo, branch))
        if branch in self.fail_prs:
            raise RuntimeError("forge down")
        return self.prs.get((repo, branch), [])

    def ref_kind(self, repo: str, number: int) -> str | None:
        self.kind_reads.append((repo, number))
        if number in self.fail_kinds:
            raise RuntimeError("forge down")
        return self.kinds.get((repo, number))


def _pr(number: int, *closes: tuple[str, int], state: str = "OPEN", cross: bool = False,
        created: str = "2026-10-01T00:00:00Z") -> dict[str, Any]:  # fmt: skip
    return {
        "number": number,
        "state": state,
        "isCrossRepository": cross,
        "createdAt": created,
        "closingIssuesReferences": [
            {"number": n, "repository": {"name": name, "owner": {"login": "acme"}}}
            for name, n in closes
        ],
    }


class ListRunner:
    def __init__(self, targets: list[AdoptTarget]) -> None:
        self.targets = targets
        self.fail: Exception | None = None

    def list_sessions(self) -> list[AdoptTarget]:
        if self.fail is not None:
            raise self.fail
        return list(self.targets)

    def describe(self, tab: str) -> AdoptTarget | None:  # makes it a SessionAdopter
        return None

    def adopt(self, item: Any, tab: str) -> str:
        return tab


@pytest.fixture
def forge(monkeypatch: pytest.MonkeyPatch) -> ListGh:
    gh = ListGh()
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: gh)
    return gh


@pytest.fixture
def workspaces(monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    bound: dict[str, Path] = {}
    monkeypatch.setattr(triage_batch_cmd, "session_worktree", lambda sid: bound.get(sid))
    monkeypatch.setattr(triage_batch_cmd, "workspace_containing", lambda root, path: None)
    return bound


def _target(tab: str, cwd: Path | None, label: str, **kw: Any) -> AdoptTarget:
    fields: dict[str, Any] = {
        "tab": tab,
        "label": label,
        "group": "widgets",
        "agent": f"{tab}-p",
        "status": "idle",
        "cwd": str(cwd) if cwd else None,
        "session": f"s-{tab}",
        "harness": "claude",
    }
    return AdoptTarget(**{**fields, **kw})


def _install(monkeypatch: pytest.MonkeyPatch, runner: ListRunner) -> None:
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: runner)


def _list() -> tuple[int, str]:
    result = CliRunner().invoke(app, ["triage", "batch", "adopt", "--list"])
    return result.exit_code, result.output


HEADER = "TAB\tWORKSPACE\tSTATUS\tSTATE\tREPO\tBRANCH\tFR WORKSPACE\tPR\tREFS\tLABEL"


def _rows(out: str) -> dict[str, list[str]]:
    lines = out.splitlines()
    assert lines[0] == HEADER
    return {line.split("\t")[0]: line.split("\t") for line in lines[1:]}


def test_the_listing_has_one_row_per_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forge: ListGh, workspaces: dict[str, Path]
) -> None:
    feat = _clone(tmp_path, "feat")
    _git(feat, "checkout", "-qb", "feat/x")
    main = _clone(tmp_path, "main")
    det = _clone(tmp_path, "det")
    _git(det, "checkout", "-q", "--detach")
    nodef = _clone(tmp_path, "nodef", origin_head=False)
    forge.prs[(REPO, "feat/x")] = [_pr(40, ("widgets", 7), ("gadgets", 8))]
    forge.kinds[(REPO, 7)] = "issue"
    forge.kinds[(REPO, 40)] = "pr"
    workspaces["s-t1"] = tmp_path / "ws"
    runner = ListRunner(
        [
            _target("t1", feat, "widgets#7 and acme/widgets#40 and #99"),
            _target("t2", main, "widgets#7"),
            _target("t3", det, "plain"),
            _target("t4", nodef, "plain"),
            _target("t5", None, "plain", agent=None, session=None, harness=None),
            _target("t6", feat, "x /run/batch-3"),
            _target("t7", tmp_path, "plain"),
        ]
    )
    _install(monkeypatch, runner)
    code, out = _list()
    assert code == 0, out
    rows = _rows(out)
    assert [rows[t][3] for t in ("t1", "t2", "t3", "t4", "t5", "t6", "t7")] == [
        "adoptable", "on default branch", "detached", "unknown", "no agent", "batch", "unknown",
    ]  # fmt: skip
    t1 = rows["t1"]
    assert t1[4:7] == [REPO, "feat/x", str(tmp_path / "ws").replace(str(Path.home()), "~")]
    assert t1[7] == "#40 closes widgets#7,gadgets#8"
    assert t1[8] == "widgets#7 (issue), acme/widgets#40 (pr), #99 (?)"
    assert rows["t2"][7] == "-"
    assert rows["t2"][8] == "widgets#7 (issue)"
    assert rows["t3"][4:6] == [REPO, "-"]
    assert rows["t5"][4:8] == ["-", "-", "-", "-"]
    assert rows["t7"][4:6] == ["-", "-"]


def test_the_workspace_comes_from_the_session_index_else_the_containing_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forge: ListGh, workspaces: dict[str, Path]
) -> None:
    feat = _clone(tmp_path, "feat")
    _git(feat, "checkout", "-qb", "feat/x")
    contained = tmp_path / "contained"
    monkeypatch.setattr(triage_batch_cmd, "workspace_containing", lambda root, path: contained)
    workspaces["s-t1"] = tmp_path / "bound"
    _install(
        monkeypatch,
        ListRunner([_target("t1", feat, "x"), _target("t2", feat, "y", session="other")]),
    )
    code, out = _list()
    assert code == 0, out
    rows = _rows(out)
    assert rows["t1"][6].endswith("bound")
    assert rows["t2"][6].endswith("contained")


def test_the_pr_column_is_the_newest_open_same_repo_pr_and_skips_default_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forge: ListGh, workspaces: dict[str, Path]
) -> None:
    feat = _clone(tmp_path, "feat")
    _git(feat, "checkout", "-qb", "feat/x")
    main = _clone(tmp_path, "main")
    forge.prs[(REPO, "feat/x")] = [
        _pr(1, created="2026-10-01T00:00:00Z"),
        _pr(3, created="2026-10-03T00:00:00Z"),
        _pr(4, state="CLOSED", created="2026-10-09T00:00:00Z"),
        _pr(5, cross=True, created="2026-10-08T00:00:00Z"),
        _pr(2, ("widgets", 9), created="2026-10-02T00:00:00Z"),
    ]
    forge.prs[(REPO, "main")] = [_pr(77)]
    _install(monkeypatch, ListRunner([_target("t1", feat, "x"), _target("t2", main, "y")]))
    code, out = _list()
    assert code == 0, out
    rows = _rows(out)
    assert rows["t1"][7] == "#3"
    assert rows["t2"][7] == "-"
    assert (REPO, "main") not in forge.pr_reads


def test_each_distinct_ref_and_branch_is_read_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forge: ListGh, workspaces: dict[str, Path]
) -> None:
    feat = _clone(tmp_path, "feat")
    _git(feat, "checkout", "-qb", "feat/x")
    other = _clone(tmp_path, "other")
    _git(other, "checkout", "-qb", "feat/x")
    forge.kinds[(REPO, 7)] = "issue"
    _install(
        monkeypatch,
        ListRunner(
            [
                _target("t1", feat, "widgets#7 #7"),
                _target("t2", other, "#7 acme/widgets#7"),
            ]
        ),
    )
    code, out = _list()
    assert code == 0, out
    assert forge.pr_reads == [(REPO, "feat/x")]
    assert forge.kind_reads == [(REPO, 7)]


def test_one_rows_failures_degrade_only_that_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forge: ListGh, workspaces: dict[str, Path]
) -> None:
    good = _clone(tmp_path, "good")
    _git(good, "checkout", "-qb", "feat/good")
    bad = _clone(tmp_path, "bad")
    _git(bad, "checkout", "-qb", "feat/bad")
    forge.prs[(REPO, "feat/good")] = [_pr(11)]
    forge.kinds[(REPO, 7)] = "issue"
    forge.fail_prs.add("feat/bad")
    forge.fail_kinds.add(8)
    _install(
        monkeypatch,
        ListRunner([_target("t1", good, "widgets#7"), _target("t2", bad, "widgets#8")]),
    )
    code, out = _list()
    assert code == 0, out
    rows = _rows(out)
    assert rows["t1"][7] == "#11" and rows["t1"][8] == "widgets#7 (issue)"
    assert rows["t2"][3] == "adoptable" and rows["t2"][7] == "-"
    assert rows["t2"][8] == "widgets#8 (?)"


def test_a_git_a_client_and_a_session_index_failure_degrade_one_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forge: ListGh, workspaces: dict[str, Path]
) -> None:
    good = _clone(tmp_path, "good")
    _git(good, "checkout", "-qb", "feat/good")
    boom = _clone(tmp_path, "boom")
    _git(boom, "checkout", "-qb", "feat/boom")
    real = Checkout.facts

    def facts(cwd: Path) -> Any:
        if Path(cwd) == boom:
            raise RuntimeError("git exploded")
        return real(cwd)

    monkeypatch.setattr(Checkout, "facts", staticmethod(facts))
    _install(
        monkeypatch,
        ListRunner([_target("t1", good, "plain"), _target("t2", boom, "widgets#7")]),
    )
    code, out = _list()
    assert code == 0, out
    rows = _rows(out)
    assert rows["t1"][3] == "adoptable"
    assert rows["t2"][3] == "unknown" and rows["t2"][4] == "-"
    assert rows["t2"][8] == "widgets#7 (?)"


def test_a_client_that_cannot_be_made_degrades_the_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, workspaces: dict[str, Path]
) -> None:
    feat = _clone(tmp_path, "feat")
    _git(feat, "checkout", "-qb", "feat/x")

    def refuse(url: str) -> Any:
        raise RuntimeError("no such forge")

    monkeypatch.setattr(triage_batch_cmd, "make_client", refuse)
    _install(monkeypatch, ListRunner([_target("t1", feat, "widgets#7")]))
    code, out = _list()
    assert code == 0, out
    row = _rows(out)["t1"]
    assert row[3] == "adoptable" and row[7] == "-" and row[8] == "widgets#7 (?)"


def test_an_unsupported_forge_prints_unknown_kinds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forge: ListGh, workspaces: dict[str, Path]
) -> None:
    feat = _clone(tmp_path, "feat")
    _git(feat, "checkout", "-qb", "feat/x")

    def unsupported(repo: str, number: int) -> str:
        raise UnsupportedForgeOperation("ref_kind", "glab")

    monkeypatch.setattr(forge, "ref_kind", unsupported)
    _install(monkeypatch, ListRunner([_target("t1", feat, "widgets#7")]))
    code, out = _list()
    assert code == 0, out
    assert _rows(out)["t1"][8] == "widgets#7 (?)"


def test_a_runner_that_cannot_list_fails_the_command(
    monkeypatch: pytest.MonkeyPatch, forge: ListGh, workspaces: dict[str, Path]
) -> None:
    runner = ListRunner([])
    runner.fail = RuntimeError("herdr is down")
    _install(monkeypatch, runner)
    code, out = _list()
    assert code == 1
    assert "could not list" in out
