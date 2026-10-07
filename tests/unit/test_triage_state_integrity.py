"""Triage reads the state it was asked for (batch `triage-state-integrity`).

One test group per member: a state directory holding another scope's facts is
refused (gh#886), the same-name refusal holds on every verb (gh#954), facts schema 4
is stamped on every scope for a reason (gh#885), origins collect never reports a
window it did not read in full (gh#888), and `gitseam` says what `show()` returns
(gh#889). The forge is faked; nothing here reaches `gh`.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_cmd
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout, GitError
from fr.triage.model import FACTS_SCHEMA, Facts, Scope
from fr.triage.origins import OriginsFacts, collect_origins, write_facts
from typer.testing import CliRunner

from tests.unit.triage_fixtures import NOW, FakeForge
from tests.unit.triage_origins_fixtures import OriginsForge, raw_issue, raw_pr

ALPHA, BETA = "example-org/alpha", "other-org/beta"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def _invoke(*args: str) -> Any:
    return CliRunner().invoke(app, ["triage", *args])


def _write_facts(d: Path, scope: Scope) -> None:
    facts = Facts(
        schema=4,
        scope=scope.name,
        kind=scope.kind,
        collected_at=NOW.isoformat(),
        repos=list(scope.repos) or [scope.target],
        issues=[],
    )
    d.mkdir(parents=True, exist_ok=True)
    (d / "facts.json").write_text(json.dumps(facts.to_json()), encoding="utf-8")


# ------------------------------------------------- gh#886: facts of another scope


@pytest.mark.parametrize("verb", [["check"], ["render"], ["batch", "list"], ["batch", "suggest"]])
def test_a_state_directory_holding_another_repos_facts_is_refused(
    tmp_path: Path, verb: list[str]
) -> None:
    _write_facts(tmp_path, Scope(kind="repo", target=ALPHA))
    (tmp_path / "judgements.yaml").write_text(
        "schema: 3\ntiers:\n  - {n: 1, title: Now}\nissues:\n  'alpha#1': {tier: 1}\n"
        "batches:\n  - {id: one, title: One, ids: ['alpha#1']}\n",
        encoding="utf-8",
    )
    before = sorted(p.name for p in tmp_path.iterdir())
    result = _invoke(*verb, "--repo", BETA, "--dir", str(tmp_path))
    assert result.exit_code == 2, result.output
    assert "example-org--alpha" in result.output and "other-org--beta" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert sorted(p.name for p in tmp_path.iterdir()) == before  # nothing written


def test_facts_of_another_scope_kind_are_refused_even_under_the_same_name(
    tmp_path: Path,
) -> None:
    """An org scope `example-org` and a repo scope named the same can never share facts."""
    _write_facts(tmp_path, Scope(kind="repo", target=ALPHA))
    doc = json.loads((tmp_path / "facts.json").read_text(encoding="utf-8"))
    doc["scope"] = "example-org"  # the org scope's name, but kind: repo
    (tmp_path / "facts.json").write_text(json.dumps(doc), encoding="utf-8")
    result = _invoke("check", "--org", "example-org", "--dir", str(tmp_path))
    assert result.exit_code == 2, result.output
    assert "repo" in result.output and "org" in result.output


def test_facts_of_the_requested_scope_still_load(tmp_path: Path) -> None:
    _write_facts(tmp_path, Scope(kind="repo", target=ALPHA))
    result = _invoke("check", "--repo", ALPHA.upper(), "--dir", str(tmp_path))
    assert result.exit_code == 0, result.output


def test_origins_facts_of_another_scope_are_refused(tmp_path: Path) -> None:
    write_facts(
        tmp_path / "origins-facts.json",
        OriginsFacts(scope=ALPHA, since="2026-09-01", collected_at="x", issues=[]),
    )
    for verb in ("check", "render"):
        result = _invoke("origins", verb, "--repo", BETA, "--dir", str(tmp_path))
        assert result.exit_code == 2, result.output
        assert ALPHA in result.output and BETA in result.output
    assert not (tmp_path / "origins.html").exists()


# ------------------------------------------- gh#954: same-named repos, every verb


@pytest.mark.parametrize(
    "verb",
    [
        ["collect"],
        ["check"],
        ["render"],
        ["batch", "list"],
        ["batch", "drive"],
        ["origins", "collect", "--since", "2026-09-01"],
        ["origins", "check"],
    ],
)
def test_every_verb_refuses_a_group_of_two_repos_sharing_a_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verb: list[str]
) -> None:
    """Judgement keys are `<repo-name>#<n>`: two owners' `same#1` would be one key. The
    refusal is what keeps them apart (gh#954); `--dir` onto another scope's state is
    the only way round it, and gh#886 closes that."""
    forge = FakeForge(issues={}, prs={})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    result = _invoke(*verb, "--repo", "one/same,two/same", "--dir", str(tmp_path / "s"))
    assert result.exit_code == 2, result.output
    assert "same" in result.output
    assert forge.calls == [] and not (tmp_path / "s").exists()


# ----------------------------------------- gh#885: schema 4 on every scope, why


@pytest.mark.parametrize("flag", [["--repo", ALPHA], ["--org", "example-org"]])
def test_repo_and_org_facts_are_stamped_schema_4_because_their_shape_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: list[str]
) -> None:
    """Not only groups: #876, #906 and #939 added `viewer`, `judged_prs`, per-PR
    `author`/`cross_repo` and per-config `post_merge`/`pr_authors` under schema 4, on
    every scope. v5.1.1, the last schema-3 reader, rejects those keys (closed-world
    model), so a repo or org file stamped 3 would fail there as "invalid facts"
    instead of the honest "unsupported schema 4; re-run collect" (gh#885)."""
    forge = FakeForge(
        issues={ALPHA: []},
        prs={ALPHA: []},
        repos=[{"name": "alpha", "isArchived": False}],
    )
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    result = _invoke("collect", *flag, "--dir", str(tmp_path))
    assert result.exit_code == 0, result.output
    written = json.loads((tmp_path / "facts.json").read_text(encoding="utf-8"))
    assert written["schema"] == FACTS_SCHEMA == 7
    assert {"viewer", "judged_prs"} <= written.keys()


# ------------------------------------------ gh#888: origins reads a window whole


class _CappedForge(OriginsForge):
    """Serves exactly the rows given, newest first, as `gh` lists them."""

    def __init__(self, issues: list[dict[str, Any]], prs: list[dict[str, Any]]) -> None:
        super().__init__()
        self.issues, self.prs = issues, prs


def _issues(*created: str) -> list[dict[str, Any]]:
    return [raw_issue(n, c, None, "") for n, c in enumerate(created, start=1)]


def _prs(*created: str) -> list[dict[str, Any]]:
    return [{**raw_pr(100 + n, True, []), "createdAt": c} for n, c in enumerate(created)]


def _origins(forge: OriginsForge, *, issue_limit: int = 3, pr_limit: int = 3) -> OriginsFacts:
    return collect_origins(
        forge,
        Scope(kind="repo", target="example-org/widgets"),
        since=date(2026, 9, 1),
        now=datetime(2026, 9, 10, tzinfo=UTC),
        issue_limit=issue_limit,
        pr_limit=pr_limit,
    )


def test_a_full_issue_page_still_inside_the_window_is_refused_naming_a_covered_since() -> None:
    forge = _CappedForge(
        _issues("2026-09-09T10:00:00Z", "2026-09-05T10:00:00Z", "2026-09-03T10:00:00Z"), []
    )
    with pytest.raises(TriageError) as err:
        _origins(forge)
    message = str(err.value)
    assert "example-org/widgets" in message and "issue" in message
    assert "--since 2026-09-04" in message  # the day after the oldest row read


def test_a_full_pr_page_still_inside_the_window_is_refused() -> None:
    forge = _CappedForge(
        _issues("2026-09-02T10:00:00Z"),
        _prs("2026-09-09T10:00:00Z", "2026-09-06T10:00:00Z", "2026-09-02T10:00:00Z"),
    )
    with pytest.raises(TriageError, match=r"PR.*--since 2026-09-03"):
        _origins(forge)


def test_a_full_page_that_reaches_past_the_window_is_complete_and_says_nothing() -> None:
    forge = _CappedForge(
        _issues("2026-09-09T10:00:00Z", "2026-09-05T10:00:00Z", "2026-08-20T10:00:00Z"),
        _prs("2026-09-09T10:00:00Z", "2026-09-06T10:00:00Z", "2026-08-01T10:00:00Z"),
    )
    facts = _origins(forge)
    assert [i.number for i in facts.issues] == [1, 2]
    assert facts.warnings == []


def test_a_refused_origins_collect_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _CappedForge(
        _issues("2026-09-09T10:00:00Z", "2026-09-05T10:00:00Z", "2026-09-03T10:00:00Z"), []
    )
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    args = ["origins", "collect", "--repo", "example-org/widgets", "--since", "2026-09-01",
            "--dir", str(tmp_path)]  # fmt: skip
    result = _invoke(*args, "--issue-limit", "3")
    assert result.exit_code == 2, result.output
    assert "--since 2026-09-04" in result.output and "--issue-limit" in result.output
    assert not (tmp_path / "origins-facts.json").exists()
    # The limit flag is the other way through: a page below its limit is everything.
    result = _invoke(*args, "--issue-limit", "4")
    assert result.exit_code == 0, result.output
    assert (tmp_path / "origins-facts.json").exists()


def test_a_full_page_with_no_creation_date_names_no_since_only_the_limit() -> None:
    """No date to count from: a suggested --since would move a day per re-run, forever."""
    undated = [{k: v for k, v in r.items() if k != "createdAt"} for r in _prs("x", "y", "z")]
    with pytest.raises(TriageError) as err:
        _origins(_CappedForge(_issues("2026-09-02T10:00:00Z"), undated))
    assert "--since" not in str(err.value) and "raise --pr-limit" in str(err.value)


def test_a_full_page_of_rows_from_today_names_no_future_since() -> None:
    forge = _CappedForge(_issues(*[f"2026-09-10T0{h}:00:00Z" for h in (3, 2, 1)]), [])
    with pytest.raises(TriageError) as err:
        _origins(forge)
    assert "--since" not in str(err.value) and "raise --issue-limit" in str(err.value)


def test_architecture_render_never_shows_origins_facts_of_another_scope(tmp_path: Path) -> None:
    """gh#979's guarantee, as it holds once the architecture page reads no origins data
    (spec 2026-10-05-triage-pages-goal R6: filings and origin counts live on the origins
    page, whose verbs refuse a foreign scope, pinned above). A foreign origins-facts.json
    beside the state cannot reach this page, so the render succeeds without it."""
    _write_facts(tmp_path, Scope(kind="repo", target=ALPHA))
    write_facts(
        tmp_path / "origins-facts.json",
        OriginsFacts(scope=BETA, since="2026-09-01", collected_at="x", issues=[]),
    )
    result = _invoke("architecture", "render", "--repo", ALPHA, "--dir", str(tmp_path))
    assert result.exit_code == 0, result.output
    page = (tmp_path / "architecture.html").read_text(encoding="utf-8")
    assert BETA not in page


# ------------------------------------------------ gh#889: what show() returns


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _clone(tmp_path: Path, files: dict[str, bytes]) -> Checkout:
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "--quiet", str(origin), str(clone))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(clone, "config", k, v)
    _git(clone, "checkout", "--quiet", "-b", "main")
    for name, body in files.items():
        (clone / name).parent.mkdir(parents=True, exist_ok=True)
        (clone / name).write_bytes(body)
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "seed")
    _git(clone, "push", "--quiet", "origin", "main")
    return Checkout(clone)


BINARY = bytes(range(256))


def test_show_of_a_binary_blob_is_a_git_error_naming_the_file(tmp_path: Path) -> None:
    checkout = _clone(tmp_path, {"logo.png": BINARY})
    with pytest.raises(GitError, match=r"logo\.png.*UTF-8"):
        checkout.show("HEAD", "logo.png")


def test_show_returns_the_blob_text_exactly_line_endings_included(tmp_path: Path) -> None:
    checkout = _clone(tmp_path, {"a.yml": "é: 1\r\nb: 2\r\n".encode()})
    assert checkout.show("HEAD", "a.yml") == "é: 1\r\nb: 2\r\n"
    assert checkout.show_bytes("HEAD", "a.yml") == "é: 1\r\nb: 2\r\n".encode()
    assert checkout.show("HEAD", "missing.yml") is None
    assert checkout.show_bytes("HEAD", "missing.yml") is None


def test_snapshot_paths_copies_every_file_byte_for_byte(tmp_path: Path) -> None:
    files = {
        ".github/workflows/ci.yml": b"on: push\r\n",
        ".github/logo.png": BINARY,
        ".github/workflows/déploiement.yml": b"on: tag\n",  # git C-quotes it without -z
    }
    checkout = _clone(tmp_path, files)
    dest = tmp_path / "snap"
    checkout.snapshot_paths("HEAD", (".github",), dest)
    for name, body in files.items():
        assert (dest / name).read_bytes() == body
