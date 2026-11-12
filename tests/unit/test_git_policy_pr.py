"""`fr pr create` (spec 2026-11-04-repo-feature-settings R11, R12).

Every PR fr's skills open goes through it, always as a draft, and the cursor records
the url. Under `git.pr: ask` it waits for a verified operator approval exactly like
`fr push`, and `deliver` accepts only the PR the cursor recorded from it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from fr.cli import app
from fr.commands import pr_cmd
from fr.commands.run_cmd import _deliver_pr_ask_gate, _deliver_pr_gate
from fr.git_policy import ask as ask_mod
from fr.run.model import load_run_state
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.settings_repo import git, land_on_main, make_repo
from tests.unit.test_git_policy_push import _answered, _approve, _commit, _seed_run

runner = CliRunner()
SLUG = "derio-net/demo"


@pytest.fixture
def forge(monkeypatch: pytest.MonkeyPatch) -> FakeGhClient:
    client = FakeGhClient()
    monkeypatch.setattr(pr_cmd, "client_for", lambda root: client)
    monkeypatch.setattr(pr_cmd, "origin_slug", lambda root: SLUG)
    return client


def _repo(tmp_path: Path, settings: str | None = None) -> Path:
    repo = make_repo(tmp_path)
    if settings:
        land_on_main(repo, settings)
    git(repo, "switch", "-q", "-c", "feat/x")
    _seed_run(repo)
    (tmp_path / "body.md").write_text("Summary.\n")
    return repo


def _pr_request_id(output: str) -> str:
    for word in output.replace("`", " ").split():
        if word.startswith("pr-"):
            return word.rstrip(".,:;")
    raise AssertionError(output)


def _create(repo: Path, *args: str):
    return runner.invoke(
        app,
        ["pr", "create", "--title", "t", "--body-file", str(repo.parent / "body.md"), *args],
        env={"FR_REPO_ROOT": str(repo)},
    )


def test_pr_create_opens_a_draft_and_records_the_url_on_the_cursor(
    tmp_path: Path, forge: FakeGhClient
) -> None:
    repo = _repo(tmp_path)

    result = _create(repo)

    assert result.exit_code == 0, result.output
    [(name, call)] = [c for c in forge.calls if c[0] == "create_pr"]
    assert call == {
        "repo": SLUG, "head": "feat/x", "base": "main", "title": "t", "body": "Summary.\n",
        "draft": True,
    }  # fmt: skip
    url = f"https://github.com/{SLUG}/pull/100"
    assert load_run_state(repo, "r1").pr == url
    assert url in result.output
    assert git(repo, "status", "--porcelain", "--", "docs") == "", "the cursor is committed"


def test_there_is_no_flag_to_open_a_ready_pr(tmp_path: Path, forge: FakeGhClient) -> None:
    repo = _repo(tmp_path)
    for flag in ("--ready", "--no-draft", "--draft=false"):
        assert _create(repo, flag).exit_code == 2
    assert not forge.calls


def test_pr_ask_refuses_until_an_operator_decision_is_verified(
    tmp_path: Path, forge: FakeGhClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, "git:\n  pr: ask\n")
    _answered(monkeypatch, True)

    first = _create(repo)
    assert first.exit_code == 2, first.output
    rid = _pr_request_id(first.output)
    head = git(repo, "rev-parse", "HEAD").strip()
    assert rid == f"pr-feat-x-{head[:12]}" and "--answered-by operator" in first.output
    assert not forge.calls

    _approve(repo, rid)
    second = _create(repo)
    assert second.exit_code == 0, second.output
    assert [c[0] for c in forge.calls] == ["create_pr"]


def test_pr_ask_refuses_on_an_unobservable_transcript(
    tmp_path: Path, forge: FakeGhClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, "git:\n  pr: ask\n")
    _answered(monkeypatch, None)
    _approve(repo, _pr_request_id(_create(repo).output))

    result = runner.invoke(
        app,
        ["pr", "create", "--title", "t", "--body-file", str(tmp_path / "body.md")],
        env={"FR_REPO_ROOT": str(repo), "FR_HARNESS": "hermes"},
    )

    assert result.exit_code == 2, result.output
    assert "hermes" in result.output
    assert not forge.calls


def test_deliver_under_pr_ask_refuses_a_pr_fr_pr_create_did_not_open(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "git:\n  pr: ask\n")
    state = load_run_state(repo, "r1")

    with pytest.raises(typer.Exit) as e:
        _deliver_pr_gate(repo, state, f"https://github.com/{SLUG}/pull/9")
    assert e.value.exit_code == 2

    recorded = state.model_copy(update={"pr": f"https://github.com/{SLUG}/pull/7"})
    with pytest.raises(typer.Exit):
        _deliver_pr_ask_gate(repo, recorded, f"https://github.com/{SLUG}/pull/9")
    _deliver_pr_ask_gate(repo, recorded, f"https://github.com/{SLUG}/pull/7")
    _deliver_pr_ask_gate(repo, recorded, None)


def test_deliver_under_pr_auto_accepts_any_pr(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _deliver_pr_ask_gate(repo, load_run_state(repo, "r1"), "https://example.com/o/r/pull/3")


# --- review p4-r4: one recorded PR per run; a request id per request -----------


def _record_pr(repo: Path, url: str) -> None:
    cursor = repo / "docs" / "superpowers" / "runs" / "r1.yaml"
    cursor.write_text(cursor.read_text() + f"pr: {url}\n")
    git(repo, "commit", "-qam", "chore(fr): run r1 — pr create")


@pytest.mark.parametrize(
    ("pr_state", "says"),
    [("OPEN", "already exists and is open"), ("MERGED", "start a fresh branch"),
     ("CLOSED", "start a fresh branch")],
)  # fmt: skip
def test_pr_create_never_replaces_the_runs_recorded_pr(
    tmp_path: Path, forge: FakeGhClient, monkeypatch: pytest.MonkeyPatch, pr_state: str, says: str
) -> None:
    url = f"https://github.com/{SLUG}/pull/7"
    monkeypatch.setattr(
        forge,
        "pr_status_by_url",
        lambda u: {"state": pr_state} if u == url else None,
        raising=False,
    )
    repo = _repo(tmp_path)
    _record_pr(repo, url)

    result = _create(repo)

    assert result.exit_code == 2, result.output
    flat = " ".join(result.output.split())
    assert url in flat and says in flat
    assert not [c for c in forge.calls if c[0] == "create_pr"]
    assert load_run_state(repo, "r1").pr == url


def test_a_new_pr_request_after_an_approved_one_gets_a_new_id(
    tmp_path: Path, forge: FakeGhClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A journal id is create-only: the second request (a new head) must not reuse
    the first one's id, or it could never be approved."""
    repo = _repo(tmp_path, "git:\n  pr: ask\n")
    _answered(monkeypatch, True)
    first = _pr_request_id(_create(repo).output)
    _approve(repo, first)
    # The first request is set aside (as a consumed one is) and new work lands.
    ask_mod.consume(Path(git(repo, "rev-parse", "--absolute-git-dir").strip()), "pr", "feat/x")
    _commit(repo, "late", "feat(x): late")

    second = _pr_request_id(_create(repo).output)

    assert second != first
    _approve(repo, second)
    assert _create(repo).exit_code == 0
