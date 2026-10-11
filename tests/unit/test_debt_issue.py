"""`fr debt issue` (spec 2026-10-11-debt-engine R9-R11) against a recording forge double."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import debt_cmd
from fr.debt import render
from fr.debt.model import AcceptanceDebt, DebtReport, DebtRow, SourceStatus
from fr.ghclient import ListingCapped
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

runner = CliRunner()
SLUG = "derio-net/widgets"
LEGACY = "Counts: skipped 1.\n\n<!-- fr-acceptance-digest -->\n\n_generated_"


def _report(debt: bool, *, unavailable: bool = False) -> DebtReport:
    rows = (DebtRow(id="a", status="unwired", acceptance="does a"),) if debt else ()
    acc = AcceptanceDebt(by_status={"unwired": 1} if debt else {"ci": 1}, rows=rows)
    sources = {"forge": SourceStatus(state="unavailable", why="down")} if unavailable else {}
    return DebtReport(acceptance=acc, sources=sources, generated_at="2026-10-11T00:00:00+00:00")


class Gh(FakeGhClient):
    capped = False

    def list_open_issues_with_body(self, repo, *, search, limit):  # noqa: ANN001, ANN201
        got = super().list_open_issues_with_body(repo, search=search, limit=limit)
        if self.capped:
            raise ListingCapped(got, limit)
        return got


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Gh, dict[str, DebtReport]]:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "remote", "add", "origin", f"https://github.com/{SLUG}.git"],
        check=True,
    )
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    gh = Gh()
    box = {"report": _report(True)}
    monkeypatch.setattr(debt_cmd, "_client", lambda root: gh)
    monkeypatch.setattr(debt_cmd, "_compute", lambda root, c, slug, days: box["report"])
    return gh, box


def _mutations(gh: Gh) -> list[str]:
    return [n for n, _ in gh.calls if n in {"create_issue", "edit_issue", "close_issue"}]


def test_without_yes_it_previews_and_writes_nothing(env: tuple[Gh, dict]) -> None:
    gh, _ = env
    r = runner.invoke(app, ["debt", "issue"])
    assert r.exit_code == 0, r.output
    assert "create: widgets: Technical debt" in r.output and "preview" in r.output
    assert _mutations(gh) == []


def test_creates_the_titled_issue(env: tuple[Gh, dict]) -> None:
    gh, _ = env
    r = runner.invoke(app, ["debt", "issue", "--yes"])
    assert r.exit_code == 0, r.output
    made = gh.issues[(SLUG, 1)] if (SLUG, 1) in gh.issues else next(iter(gh.issues.values()))
    create = next(c for n, c in gh.calls if n == "create_issue")
    assert create["title"] == "widgets: Technical debt" and render.MARKER in create["body"]
    assert made.body == create["body"]


def test_renames_a_legacy_digest_issue_in_place_with_both_markers(env: tuple[Gh, dict]) -> None:
    gh, _ = env
    gh.add_issue(SLUG, 7, body=LEGACY)
    gh.issue_titles[(SLUG, 7)] = "Acceptance debt"
    r = runner.invoke(app, ["debt", "issue", "--yes"])
    assert r.exit_code == 0, r.output
    assert _mutations(gh) == ["edit_issue"]
    body = gh.issues[(SLUG, 7)].body
    assert gh.issue_titles[(SLUG, 7)] == "widgets: Technical debt"
    assert render.MARKER in body and "fr-debt-figures:" in body
    assert render.parse_figures(body) is not None


def test_refreshes_an_issue_that_already_carries_the_new_marker(env: tuple[Gh, dict]) -> None:
    gh, _ = env
    gh.add_issue(SLUG, 4, body=f"old\n\n{render.MARKER}\n")
    assert runner.invoke(app, ["debt", "issue", "--yes"]).exit_code == 0
    assert _mutations(gh) == ["edit_issue"] and gh.calls[-1][1]["number"] == 4


def test_several_issues_use_the_oldest_and_warn(env: tuple[Gh, dict]) -> None:
    gh, _ = env
    gh.add_issue(SLUG, 9, body=f"{render.MARKER}\n")
    gh.add_issue(SLUG, 3, body=LEGACY)
    r = runner.invoke(app, ["debt", "issue", "--yes"])
    assert r.exit_code == 0, r.output
    assert "::warning::" in r.output and "#3" in r.output and "#9" in r.output
    assert [c["number"] for n, c in gh.calls if n == "edit_issue"] == [3]


def test_an_issue_merely_quoting_the_marker_is_not_the_debt_issue(env: tuple[Gh, dict]) -> None:
    gh, _ = env
    gh.add_issue(SLUG, 2, body=f"the digest writes `{render.MARKER}` somewhere")
    assert runner.invoke(app, ["debt", "issue", "--yes"]).exit_code == 0
    assert _mutations(gh) == ["create_issue"]


def test_zero_debt_closes_the_issue_with_a_comment(env: tuple[Gh, dict]) -> None:
    gh, box = env
    box["report"] = _report(False)
    gh.add_issue(SLUG, 5, body=f"{render.MARKER}\n")
    assert runner.invoke(app, ["debt", "issue", "--yes"]).exit_code == 0
    closed = next(c for n, c in gh.calls if n == "close_issue")
    assert closed["number"] == 5 and closed["comment"]
    assert gh.issues[(SLUG, 5)].state == "CLOSED"


def test_zero_debt_with_no_issue_files_nothing(env: tuple[Gh, dict]) -> None:
    gh, box = env
    box["report"] = _report(False)
    r = runner.invoke(app, ["debt", "issue", "--yes"])
    assert r.exit_code == 0 and _mutations(gh) == []


def test_an_unreadable_source_is_never_read_as_zero_debt(env: tuple[Gh, dict]) -> None:
    gh, box = env
    box["report"] = _report(False, unavailable=True)
    gh.add_issue(SLUG, 5, body=f"{render.MARKER}\n")
    assert runner.invoke(app, ["debt", "issue", "--yes"]).exit_code == 0
    assert _mutations(gh) == ["edit_issue"]


def test_a_capped_listing_that_found_nothing_refuses_to_open_a_duplicate(
    env: tuple[Gh, dict],
) -> None:
    gh, _ = env
    gh.capped = True
    r = runner.invoke(app, ["debt", "issue", "--yes"])
    assert r.exit_code == 1 and "::warning::partial" in r.output
    assert _mutations(gh) == []


def test_a_forge_refusal_is_named_and_exits_nonzero(env: tuple[Gh, dict]) -> None:
    from tests.unit.fakes import FakeGhError

    gh, _ = env
    gh.fail_on_mutation = 0
    r = runner.invoke(app, ["debt", "issue", "--yes"])
    assert r.exit_code == 1 and "forge refused" in r.output
    assert isinstance(FakeGhError("x"), Exception)


def test_the_identity_is_the_origin_remote_never_the_matrix(
    env: tuple[Gh, dict], tmp_path: Path
) -> None:
    gh, _ = env
    m = tmp_path / "docs" / "acceptance"
    m.mkdir(parents=True)
    (m / "matrix.yaml").write_text("schema_version: 5\norg: evil\nrepo: elsewhere\nrows: []\n")
    r = runner.invoke(app, ["debt", "issue", "--yes"])
    assert r.exit_code == 1 and "matrix names evil/elsewhere" in r.output
    assert _mutations(gh) == []


def test_an_unusable_issue_number_is_refused(env: tuple[Gh, dict]) -> None:
    gh, _ = env
    gh.add_issue(SLUG, 5, body=f"{render.MARKER}\n")
    orig: Any = gh.list_open_issues_with_body
    gh.list_open_issues_with_body = lambda *a, **k: [  # type: ignore[method-assign]
        {**i, "number": "--web"} for i in orig(*a, **k)
    ]
    r = runner.invoke(app, ["debt", "issue", "--yes"])
    assert r.exit_code == 1 and "unusable issue number" in r.output


def test_a_marker_bearing_issue_by_another_author_is_ignored_not_edited(
    env: tuple[Gh, dict],
) -> None:
    gh, _ = env
    gh.add_issue(SLUG, 8, body=f"{render.MARKER}\n")
    gh.issue_authors[(SLUG, 8)] = "mallory\x1b[31m"
    r = runner.invoke(app, ["debt", "issue", "--yes"])
    assert r.exit_code == 0, r.output
    assert "ignoring issue #8 by mallory?[31m" in r.output and "\x1b" not in r.output
    assert gh.issues[(SLUG, 8)].body == f"{render.MARKER}\n"
    assert _mutations(gh) == ["create_issue"]


def test_the_bot_authored_legacy_issue_is_renamed(env: tuple[Gh, dict]) -> None:
    gh, _ = env
    gh.add_issue(SLUG, 363, body=LEGACY)
    gh.issue_titles[(SLUG, 363)] = "Acceptance debt"
    gh.issue_authors[(SLUG, 363)] = "github-actions[bot]"
    assert runner.invoke(app, ["debt", "issue", "--yes"]).exit_code == 0
    assert gh.issue_titles[(SLUG, 363)] == "widgets: Technical debt"
    assert _mutations(gh) == ["edit_issue"]


SECRET = "https://x-access-token:SECRET@github.com/o/r.git"


def test_an_error_source_shows_only_its_category_in_the_body() -> None:
    report = DebtReport(
        acceptance=AcceptanceDebt(by_status={"ci": 1}),
        sources={
            "forge": SourceStatus(
                state="unavailable", why=f"fatal: {SECRET} /Users/me/x ghp_" + "a" * 30
            ),
            "git": SourceStatus(state="read", why=f"local ref; fetch failed: {SECRET}"),
        },
        generated_at="2026-10-11T00:00:00+00:00",
    )
    body = render.markdown(report)
    assert "forge: forge error" in body and "git: fetch failed" in body
    for leak in ("SECRET", "x-access-token", "/Users/me", "ghp_"):
        assert leak not in body


def test_redact_removes_credentials_tokens_and_home_paths() -> None:
    out = render.redact(
        f"{SECRET} glpat-abcdefghij1234 github_pat_{'b' * 25} gho_{'c' * 25} /home/ann/repo"
    )
    assert "SECRET" not in out and "glpat" not in out and "github_pat" not in out
    assert "gho_" not in out and "/home/ann" not in out and "~/repo" in out
    assert "https://***@github.com" in out


def test_a_forge_error_carrying_a_credential_url_is_redacted_on_the_terminal(
    env: tuple[Gh, dict],
) -> None:
    from tests.unit.fakes import FakeGhError

    gh, _ = env

    def boom(*a: object, **k: object) -> None:
        raise FakeGhError(f"cannot reach {SECRET}")

    gh.create_issue = boom  # type: ignore[method-assign]
    r = runner.invoke(app, ["debt", "issue", "--yes"])
    assert r.exit_code == 1 and "SECRET" not in r.output and "***@" in r.output
