"""`deliver` accounts for leftovers, end to end (spec 2026-10-14 exit-gates R9,
R10): a full `fr run resolve --step deliver` against a stubbed forge refuses
while the run leaves an out-of-scope finding and an untracked owed row, and
delivers once `fr journal file` filed the one and the row carries its issue.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.journal.model import effective_finding_states, journal_path, parse_journal
from fr.run.model import load_run_state

from tests.unit.fakes import FakeGhClient
from tests.unit.record_support import (
    RUN,
    SEEDED_ROW,
    SLUG,
    commit_all,
    fr,
    implement_record,
    started_run,
    write_record,
)
from tests.unit.test_deliver_pr_body import _body, _deliver


class StubForge(FakeGhClient):
    def viewer_login(self) -> str:
        return "me"

    def list_issues(self, repo, state, limit, fields=None):  # noqa: ANN001, ANN201
        return []


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    import fr.gh

    served: dict[str, str] = {}
    monkeypatch.setattr(fr.gh, "view_pr_body", lambda ref, *, cwd=None: served["body"])
    return served


def _as_github(root: Path) -> None:
    """Point `origin`'s configured url at github.com/t/t (the seeded matrix's
    identity), served by the local bare repo through `insteadOf`."""

    def git(*a: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *a], check=True, capture_output=True, text=True
        ).stdout.strip()

    bare = git("remote", "get-url", "origin")
    url = "https://github.com/t/t.git"
    git("config", f"url.{bare}.insteadOf", url)
    git("remote", "set-url", "origin", url)


def _at_deliver_with_leftovers(tmp_path: Path) -> Path:
    root = started_run(tmp_path)
    _as_github(root)
    impl = implement_record(
        journal=[
            {"kind": "finding", "id": "p1-f1", "title": "edge case", "review_scope": "in"},
            {"kind": "finding", "id": "p1-f2", "title": "old debt", "review_scope": "out"},
        ],
        resolves=[
            {"id": "p1-f1", "state": "fixed", "body": "covered"},
            {"id": "p1-f2", "state": "out-of-scope", "body": "predates this change"},
        ],
    )
    step = ["run", "resolve", RUN, "--step"]
    rec = write_record(root, impl)
    out = fr(root, [*step, "implement-phase", "--item", "phase/1", "--record", str(rec)])
    assert out.exit_code == 0, out.output
    review = {
        "run": RUN, "step": "review-phase", "item": "phase/1", "outcome": "done",
        "journal": [{"kind": "review", "id": "r-p1", "title": "review", "body": "clean"}],
        "evidence": {"review": "r-p1", "reviewer": "reviewer-1"},
    }  # fmt: skip
    rec = write_record(root, review)
    out = fr(root, [*step, "review-phase", "--item", "phase/1", "--record", str(rec)])
    assert out.exit_code == 0, out.output
    commit_all(root, "at deliver")
    (root / "suite.log").write_text("n passed\n")
    return root


def test_deliver_refuses_leftovers_then_passes_after_journal_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, live: dict[str, str]
) -> None:
    from fr.commands import journal_cmd

    root = _at_deliver_with_leftovers(tmp_path)
    forge = StubForge()
    monkeypatch.setattr(journal_cmd, "_make_gh_client", lambda: forge)
    live["body"] = "unread: the leftovers refuse first"

    _rec, out = _deliver(root)

    assert out.exit_code == 2, out.output
    text = " ".join(out.output.split())
    assert f"fr journal file --scope plan --slug {SLUG} --id p1-f2" in text
    assert f"--row {SEEDED_ROW} --gate tester" in text
    assert load_run_state(root, RUN).steps["deliver"].state == "running"

    filed = fr(root, ["journal", "file", "--scope", "plan", "--slug", SLUG, "--id", "p1-f2"])
    assert filed.exit_code == 0, filed.output
    entries = parse_journal(journal_path(root, "plan", SLUG).read_text())
    assert effective_finding_states(entries)["p1-f2"] == "deferred"
    created = [kw for name, kw in forge.calls if name == "create_issue"]
    assert [c["labels"] for c in created] == [frozenset({"follow-up"})]

    row = fr(
        root,
        [
            *("acceptance", "set-status", "--id", SEEDED_ROW, "--status", "unwired"),
            *("--issue", "t/t#2", "--notes", "the rest is tracked in t/t#2"),
        ],
    )
    assert row.exit_code == 0, row.output
    commit_all(root, "accounted")
    (root / "suite.log").write_text("n passed\n")

    _deliver(root)  # renders the PR body fr owns; the live one is not it yet
    live["body"] = _body(root).read_text()
    _rec, out = _deliver(root)

    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"


def test_p3_r9_under_tracking_none_an_unfiled_out_of_scope_finding_delivers_and_is_listed(
    tmp_path: Path, live: dict[str, str]
) -> None:
    """No tracker: nothing can be filed, so the out-of-scope finding is no
    leftover — it rides in the PR body's out-of-scope section, as before."""
    root = _at_deliver_with_leftovers(tmp_path)
    (root / ".devcontainer").mkdir(exist_ok=True)
    (root / ".devcontainer/fr-profiles.yaml").write_text(
        "schema_version: 2\nprofiles:\n  dev:\n    purpose: x\ntracking: {type: none}\n"
    )
    # The seeded row is not owed here; the leftover under test is the finding alone.
    row = fr(
        root,
        [
            *("acceptance", "set-status", "--id", SEEDED_ROW, "--status", "manual"),
            *("--notes", "an operator process, never automated"),
        ],
    )
    assert row.exit_code == 0, row.output
    commit_all(root, "tracking none")
    (root / "suite.log").write_text("n passed\n")

    live["body"] = "not yet"
    _rec, out = _deliver(root)  # renders the body: the live one is not it
    assert "unaccounted" not in out.output, out.output
    body = _body(root).read_text()
    out_of_scope = body.split("## Out-of-scope findings")[1].split("## ")[0]
    assert "p1-f2" in out_of_scope
    live["body"] = body

    _rec, out = _deliver(root)

    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"
