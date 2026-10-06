"""`fr archive` open ends → issues (spec 2026-10-06-archive-followups-design §C)."""

from __future__ import annotations

from pathlib import Path

from fr.journal.model import (
    JournalEntry,
    append_journal_entry,
    effective_finding_states,
    journal_path,
    parse_journal,
    resolution_entry,
    resolution_record_id,
)


def _finding(fid: str = "f1", title: str = "a finding") -> JournalEntry:
    return JournalEntry(
        kind="finding",
        scope="plan",
        id=fid,
        created="2026-10-06T00:00:00+00:00",
        state="open",
        title=title,
        body="why it matters",
    )


# --- T1: the shared deferral builder (R12) ---


def test_resolution_entry_builds_the_deferral_the_record_engine_builds(tmp_path: Path) -> None:
    f = _finding()
    entry = resolution_entry(
        target=f,
        taken={"f1"},
        created="2026-10-06T01:00:00+00:00",
        state="deferred",
        body="Filed at archive as https://x.example/issues/1.",
        phase=None,
        tracked_by="https://x.example/issues/1",
    )
    assert entry.id == resolution_record_id("f1", {"f1"}) == "f1-resolved"
    assert entry.title == "resolves f1: a finding"
    assert entry.state == "open"
    assert entry.resolves == "f1"
    assert entry.tracked_by == "https://x.example/issues/1"
    assert entry.scope == "plan"
    assert entry.kind == "finding"
    assert entry.out_of_scope is False
    assert effective_finding_states([f, entry]) == {"f1": "deferred"}


# --- T2: listing and selection (R8, R9) ---


def _journal(
    repo: Path, scope: str, slug: str, entries: list[JournalEntry], *, archived: bool = False
) -> Path:
    from fr.journal.model import archived_journal_path

    path = (archived_journal_path if archived else journal_path)(repo, scope, slug)  # type: ignore[arg-type]
    for e in entries:
        append_journal_entry(path, slug, e)
    return path


def _entry(
    scope: str,
    fid: str,
    title: str = "t",
    *,
    state: str = "open",
    resolves: str | None = None,
    tracked_by: str | None = None,
    out_of_scope: bool = False,
) -> JournalEntry:
    return JournalEntry(
        kind="finding",
        scope=scope,  # type: ignore[arg-type]
        id=fid,
        created="2026-10-06T00:00:00+00:00",
        state=state,  # type: ignore[arg-type]
        title=title,
        body=f"body of {fid}",
        resolves=resolves,
        tracked_by=tracked_by,
        out_of_scope=out_of_scope,
    )


def test_open_ends_keeps_open_and_out_of_scope_and_drops_the_rest(tmp_path: Path) -> None:
    from fr.archive_followups import open_ends

    _journal(
        tmp_path,
        "plan",
        "p1",
        [
            _entry("plan", "a", "still open"),
            _entry("plan", "b", "scoped out"),
            _entry("plan", "b-resolved", resolves="b", out_of_scope=True),
            _entry("plan", "c", "fixed", state="fixed"),
            _entry("plan", "d", "deferred"),
            _entry("plan", "d-resolved", resolves="d", tracked_by="https://x.example/i/1"),
            _entry("plan", "e", "refuted", state="refuted"),
        ],
        archived=True,
    )
    ends = open_ends(tmp_path, [("plan", "p1")])
    assert [(e.qid, e.state, e.title) for e in ends] == [
        ("plan/p1/a", "open", "still open"),
        ("plan/p1/b", "out-of-scope", "scoped out"),
    ]
    assert ends[0].body == "body of a"
    assert ends[0].path.name == "p1.md"


def test_open_ends_reads_a_missing_or_unparseable_journal_as_empty(tmp_path: Path) -> None:
    from fr.archive_followups import open_ends
    from fr.journal.model import archived_journal_path

    path = archived_journal_path(tmp_path, "spec", "bad")
    path.parent.mkdir(parents=True)
    path.write_text("<!-- fr:journal kind=finding scope=spec id=x created=NOPE -->\n")
    assert open_ends(tmp_path, [("spec", "bad"), ("plan", "missing")]) == []


def test_journals_from_log_names_the_archived_journals(tmp_path: Path) -> None:
    from fr.archive_followups import journals_from_log

    base = Path("docs/superpowers")
    moves = [
        (base / "plans/p1", base / "implemented/plans/p1"),
        (base / "journals/plans/p1.md", base / "implemented/journals/plans/p1.md"),
        (base / "journals/specs/s1.md", base / "implemented/journals/specs/s1.md"),
        (base / "journals/debug/d1.md", base / "implemented/journals/debug/d1.md"),
        (base / "journals/weird/z.md", base / "implemented/journals/weird/z.md"),
    ]
    assert journals_from_log(moves) == [("plan", "p1"), ("spec", "s1"), ("debug", "d1")]


def _two_journals(repo: Path) -> list:
    from fr.archive_followups import open_ends

    _journal(
        repo,
        "plan",
        "p1",
        [_entry("plan", "f1", "plan one"), _entry("plan", "u", "u")],
        archived=True,
    )
    _journal(
        repo,
        "spec",
        "s1",
        [_entry("spec", "f1", "spec one"), _entry("spec", "x", "x")],
        archived=True,
    )
    return open_ends(repo, [("plan", "p1"), ("spec", "s1")])


def test_select_all_returns_every_listed_end(tmp_path: Path) -> None:
    from fr.archive_followups import select

    listed = _two_journals(tmp_path)
    chosen, refused = select(listed, "all", tmp_path)
    assert chosen == listed and refused == []


def test_select_a_bare_id_must_be_unique_among_the_listed(tmp_path: Path) -> None:
    from fr.archive_followups import select

    listed = _two_journals(tmp_path)
    chosen, refused = select(listed, "u,x", tmp_path)
    assert [e.qid for e in chosen] == ["plan/p1/u", "spec/s1/x"] and refused == []
    chosen, refused = select(listed, "f1", tmp_path)
    assert refused and "ambiguous" in refused[0] and "plan/p1/f1" in refused[0]
    chosen, refused = select(listed, "nope", tmp_path)
    assert refused and "nope" in refused[0]


def test_select_a_qid_resolves_against_its_journal_live_or_archived(tmp_path: Path) -> None:
    from fr.archive_followups import select

    _journal(tmp_path, "plan", "live", [_entry("plan", "q1", "live one")])
    _journal(tmp_path, "spec", "old", [_entry("spec", "q2", "old one")], archived=True)
    chosen, refused = select([], "plan/live/q1, spec/old/q2", tmp_path)
    assert refused == []
    assert [(e.qid, e.title) for e in chosen] == [
        ("plan/live/q1", "live one"),
        ("spec/old/q2", "old one"),
    ]


def test_select_refuses_a_qid_that_is_not_an_open_end(tmp_path: Path) -> None:
    from fr.archive_followups import select

    _journal(tmp_path, "plan", "p", [_entry("plan", "done", state="fixed")])
    for bad in ("plan/p/done", "plan/p/ghost", "plan/nojournal/x", "weird/p/x", "a/b/c/d"):
        chosen, refused = select([], bad, tmp_path)
        assert chosen == [] and len(refused) == 1, bad


# --- T3: filing, write-back, and the open-ends step (R9-R12) ---

import subprocess  # noqa: E402

import pytest  # noqa: E402
from fr.commands import archive_cmd  # noqa: E402
from fr.ghclient import UnsupportedForgeOperation  # noqa: E402

from tests.unit.fakes import FakeGhClient, FakeGhError  # noqa: E402
from tests.unit.test_archive_cmd import _add_plan, _invoke, _repo, _seed  # noqa: E402

SLUG = "2026-05-25-bookmarks"
OWN = "acme/widgets"
MATRIX = "schema_version: 4\norg: acme\nrepo: widgets\nrows: []\n"


class DedupGh(FakeGhClient):
    """A fake forge that can list its open issues."""

    def __init__(self, existing: list[dict] | None = None) -> None:
        super().__init__()
        self.listed = existing or []
        self.list_args: list[tuple] = []

    def list_issues(self, repo, state, limit, fields=None):  # noqa: ANN001, ANN201
        self.list_args.append((repo, state, limit, fields))
        return list(self.listed)


class NoListGh(FakeGhClient):
    def list_issues(self, repo, state, limit, fields=None):  # noqa: ANN001, ANN201
        raise UnsupportedForgeOperation("list_issues", "gitlab")


def _created(gh: FakeGhClient) -> list[dict]:
    return [kw for name, kw in gh.calls if name == "create_issue"]


def _open_ends_repo(tmp_path: Path, *, extra: list[JournalEntry] | None = None) -> Path:
    """A real git repo whose plan is archivable and whose plan journal carries
    two open findings (one out-of-scope) and a fixed one."""
    repo = _repo(tmp_path)
    _add_plan(repo, SLUG, ticked=True)
    (repo / "docs/acceptance").mkdir(parents=True)
    (repo / "docs/acceptance/matrix.yaml").write_text(MATRIX)
    _journal(
        repo,
        "plan",
        SLUG,
        [
            _entry("plan", "f1", "first open"),
            _entry("plan", "f2", "second, scoped out"),
            _entry("plan", "f2-resolved", resolves="f2", out_of_scope=True),
            _entry("plan", "f3", "was fixed", state="fixed"),
            *(extra or []),
        ],
    )
    _seed(repo)
    return repo


def _archived_journal(repo: Path) -> Path:
    return repo / f"docs/superpowers/implemented/journals/plans/{SLUG}.md"


def _states(repo: Path) -> dict[str, str]:
    return dict(effective_finding_states(parse_journal(_archived_journal(repo).read_text())))


def _archive(monkeypatch, repo: Path, gh: FakeGhClient, *flags: str):  # noqa: ANN001, ANN202
    return _invoke(monkeypatch, repo, gh, ["archive", f"docs/superpowers/plans/{SLUG}", *flags])


def _interactive(monkeypatch, answers: list[str]) -> list[str]:  # noqa: ANN001
    asked: list[str] = []
    monkeypatch.setattr("fr.artifacts.trigger.is_interactive", lambda **kw: True)

    def fake_input(prompt: str = "") -> str:
        asked.append(prompt)
        return answers.pop(0)

    monkeypatch.setattr("builtins.input", fake_input)
    return asked


def test_issues_all_files_every_end_marks_it_and_defers_the_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _open_ends_repo(tmp_path)
    gh = DedupGh()
    result = _archive(monkeypatch, repo, gh, "--issues", "all")
    assert result.exit_code == 0, result.output
    made = _created(gh)
    assert [m["title"] for m in made] == ["first open", "second, scoped out"]
    assert all(m["repo"] == OWN and m["labels"] == frozenset({"follow-up"}) for m in made)
    assert f"<!-- fr:journal plan/{SLUG}/f1 -->" in made[0]["body"]
    assert "body of f1" in made[0]["body"]
    assert f"docs/superpowers/implemented/journals/plans/{SLUG}.md" in made[0]["body"]
    assert gh.list_args == [(OWN, "open", 200, "number,url,body")]
    assert _states(repo) == {
        "f1": "deferred",
        "f2": "deferred",
        "f3": "fixed",
    }
    entries = parse_journal(_archived_journal(repo).read_text())
    rec = next(e for e in entries if e.resolves == "f1")
    assert rec.tracked_by == f"https://github.com/{OWN}/issues/1"
    assert "Filed at archive as" in rec.body
    # staged, never committed
    diff = subprocess.run(
        ["git", "-C", str(repo), "diff", "--quiet", "--", str(_archived_journal(repo))],
        check=False,
    )
    assert diff.returncode == 0, "the journal rewrite must be staged"
    assert "  open ends:" in result.output and f"plan/{SLUG}/f1: first open" in result.output


def test_an_ensure_labels_failure_files_without_the_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class NoLabels(DedupGh):
        def ensure_labels(self, repo, labels):  # noqa: ANN001, ANN201
            raise FakeGhError("forbidden")

    repo = _open_ends_repo(tmp_path)
    gh = NoLabels()
    result = _archive(monkeypatch, repo, gh, "--issues", "all")
    assert result.exit_code == 0, result.output
    assert [m["labels"] for m in _created(gh)] == [frozenset(), frozenset()]


def test_an_open_issue_with_the_marker_is_reused_not_duplicated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _open_ends_repo(tmp_path)
    url = f"https://github.com/{OWN}/issues/77"
    gh = DedupGh([{"number": 77, "url": url, "body": f"x <!-- fr:journal plan/{SLUG}/f1 --> y"}])
    result = _archive(monkeypatch, repo, gh, "--issues", f"plan/{SLUG}/f1")
    assert result.exit_code == 0, result.output
    assert _created(gh) == []
    rec = next(e for e in parse_journal(_archived_journal(repo).read_text()) if e.resolves == "f1")
    assert rec.tracked_by == url
    assert _states(repo)["f1"] == "deferred" and _states(repo)["f2"] == "out-of-scope"


def test_dedup_falls_back_to_none_when_the_forge_cannot_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _open_ends_repo(tmp_path)
    gh = NoListGh()
    result = _archive(monkeypatch, repo, gh, "--issues", "all")
    assert result.exit_code == 0, result.output
    assert len(_created(gh)) == 2


def test_a_per_finding_create_failure_is_reported_and_the_rest_proceed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _open_ends_repo(tmp_path)

    class FirstFails(DedupGh):
        def create_issue(self, repo, *, title, body, labels):  # noqa: ANN001, ANN201
            if title == "first open":
                raise FakeGhError("boom")
            return super().create_issue(repo, title=title, body=body, labels=labels)

    gh = FirstFails()
    result = _archive(monkeypatch, repo, gh, "--issues", "all")
    assert result.exit_code == 0, result.output
    assert f"warning: could not file plan/{SLUG}/f1" in result.output
    assert _states(repo) == {"f1": "open", "f2": "deferred", "f3": "fixed"}


def test_no_issues_only_lists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _open_ends_repo(tmp_path)
    gh = DedupGh()
    result = _archive(monkeypatch, repo, gh, "--no-issues")
    assert result.exit_code == 0, result.output
    assert _created(gh) == [] and f"plan/{SLUG}/f1: first open" in result.output
    assert _states(repo)["f1"] == "open"


def test_issues_and_no_issues_together_is_a_usage_error_before_any_move(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _open_ends_repo(tmp_path)
    result = _archive(monkeypatch, repo, DedupGh(), "--issues", "all", "--no-issues")
    assert result.exit_code == 2, result.output
    assert "--issues and --no-issues" in result.output
    assert (repo / f"docs/superpowers/plans/{SLUG}").is_dir()
    assert not _archived_journal(repo).exists()


def test_non_interactive_with_no_flag_only_lists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _open_ends_repo(tmp_path)
    gh = DedupGh()
    result = _archive(monkeypatch, repo, gh)  # CliRunner: not interactive
    assert result.exit_code == 0, result.output
    assert _created(gh) == [] and f"plan/{SLUG}/f2: second, scoped out" in result.output


def test_interactive_yes_files_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _open_ends_repo(tmp_path)
    asked = _interactive(monkeypatch, ["y"])
    gh = DedupGh()
    result = _archive(monkeypatch, repo, gh)
    assert result.exit_code == 0, result.output
    assert len(asked) == 1 and "[y/N/select]" in asked[0]
    assert len(_created(gh)) == 2


def test_interactive_default_files_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _open_ends_repo(tmp_path)
    _interactive(monkeypatch, [""])
    gh = DedupGh()
    assert _archive(monkeypatch, repo, gh).exit_code == 0
    assert _created(gh) == []


def test_interactive_select_files_the_chosen_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _open_ends_repo(tmp_path)
    _interactive(monkeypatch, ["select", "f2"])
    gh = DedupGh()
    result = _archive(monkeypatch, repo, gh)
    assert result.exit_code == 0, result.output
    assert [m["title"] for m in _created(gh)] == ["second, scoped out"]


def test_tracking_none_only_lists_whatever_the_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _open_ends_repo(tmp_path)
    prof = repo / ".devcontainer"
    prof.mkdir()
    (prof / "fr-profiles.yaml").write_text(
        "schema_version: 2\nprofiles:\n  dev:\n    purpose: x\ntracking: {type: none}\n"
    )
    gh = DedupGh()
    result = _archive(monkeypatch, repo, gh, "--issues", "all")
    assert result.exit_code == 0, result.output
    assert _created(gh) == []
    assert "no tracker configured" in result.output
    assert f"plan/{SLUG}/f1: first open" in result.output


def test_an_invalid_services_declaration_only_lists_with_the_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _open_ends_repo(tmp_path)
    prof = repo / ".devcontainer"
    prof.mkdir()
    (prof / "fr-profiles.yaml").write_text("schema_version: 2\ntracking: {type: bogus}\n")
    gh = DedupGh()
    result = _archive(monkeypatch, repo, gh, "--issues", "all")
    assert result.exit_code == 0, result.output
    assert _created(gh) == []
    assert "services declaration" in result.output and "invalid" in result.output


def test_an_unknown_qid_refuses_before_anything_is_filed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _open_ends_repo(tmp_path)
    gh = DedupGh()
    result = _archive(monkeypatch, repo, gh, "--issues", f"plan/{SLUG}/f1,plan/{SLUG}/ghost")
    assert result.exit_code == 0, result.output  # archive's exit code is never changed
    assert _created(gh) == []
    assert "warning: --issues refused" in result.output and "ghost" in result.output
    assert _states(repo)["f1"] == "open"


def test_explicit_qids_file_even_when_nothing_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R9: the brief's command works after an earlier archive already moved the journal."""
    repo = _open_ends_repo(tmp_path)
    assert _archive(monkeypatch, repo, DedupGh(), "--no-issues").exit_code == 0
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "archived"], check=True)
    gh = DedupGh()
    result = _invoke(
        monkeypatch,
        repo,
        gh,
        ["archive", "--all", "--issues", f"plan/{SLUG}/f2"],
    )
    assert result.exit_code == 0, result.output
    assert [m["title"] for m in _created(gh)] == ["second, scoped out"]
    assert _states(repo)["f2"] == "deferred"


def test_a_followup_failure_never_changes_the_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _open_ends_repo(tmp_path)
    monkeypatch.setattr(
        archive_cmd, "_open_ends_step", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )
    result = _archive(monkeypatch, repo, DedupGh(), "--issues", "all")
    assert result.exit_code == 0, result.output
    assert "note: open ends skipped" in result.output
