"""`fr triage collect` CLI paths: usage errors, forge errors, org scope, limits.

Review r-p1-untested. The forge is replaced at the `make_forge` seam; nothing
here reaches a real forge, and every state directory is under tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.triage.errors import ForgeError
from typer.testing import CliRunner

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "triage"


def _load(name: str) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return data


class _Forge:
    def __init__(self, *, fail_with: str | None = None) -> None:
        self.fail_with = fail_with
        self.pr_limits: list[int] = []
        self.viewed: list[tuple[str, int]] = []

    def list_repos(self, *, owner: str, limit: int) -> list[dict[str, Any]]:
        return [{"name": "alpha", "isArchived": False}, {"name": "beta", "isArchived": False}]

    def list_issues(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        if self.fail_with is not None and repo.endswith(("/super-fr", "/beta")):
            raise ForgeError(self.fail_with)
        return _load("super-fr-issues.json")

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        self.pr_limits.append(limit)
        return _load("super-fr-prs.json")

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]:
        self.viewed.append((repo, number))
        return {
            "number": number,
            "title": "gone",
            "body": "",
            "labels": [],
            "state": "CLOSED",
            "url": f"https://github.com/{repo}/issues/{number}",
            "closedAt": "2026-09-20T10:00:00Z",
        }


def _run(monkeypatch: pytest.MonkeyPatch, forge: _Forge, *args: str) -> Any:
    import fr.commands.triage_cmd as triage_cmd

    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    return CliRunner().invoke(app, ["triage", "collect", *args])


@pytest.mark.parametrize(
    "args",
    [[], ["--repo", "derio-net/super-fr", "--org", "derio-net"]],
    ids=["neither", "both"],
)
def test_not_exactly_one_of_repo_or_org_is_a_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    result = _run(monkeypatch, _Forge(), *args, "--dir", str(tmp_path))

    assert result.exit_code == 2
    assert "exactly one of --repo OWNER/REPO or --org OWNER" in result.output
    assert not (tmp_path / "facts.json").exists()


def test_a_forge_error_exits_2_and_prints_the_message_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `[/red]` would raise MarkupError, and `[manual]` vanish, if rich parsed it (r7).
    forge = _Forge(fail_with="[manual] boom [/red] tail")

    result = _run(monkeypatch, forge, "--repo", "derio-net/super-fr", "--dir", str(tmp_path))

    assert result.exit_code == 2
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "[manual] boom [/red] tail" in result.output
    assert not (tmp_path / "facts.json").exists()


def test_org_scope_reports_a_skipped_repo_verbatim_and_still_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _Forge(fail_with="[no access] [/red]")

    result = _run(monkeypatch, forge, "--org", "example-org", "--dir", str(tmp_path))

    assert result.exit_code == 0, result.output
    assert "example-org/beta" in result.output
    assert "[no access] [/red]" in result.output
    facts = json.loads((tmp_path / "facts.json").read_text(encoding="utf-8"))
    assert facts["skipped"] == [{"repo": "example-org/beta", "reason": "[no access] [/red]"}]
    assert facts["schema"] == 1


def test_pr_limit_widens_the_window_and_a_full_list_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _Forge()
    n = len(_load("super-fr-prs.json"))

    result = _run(
        monkeypatch,
        forge,
        "--repo",
        "derio-net/super-fr",
        "--dir",
        str(tmp_path),
        "--pr-limit",
        str(n),
    )

    assert result.exit_code == 0, result.output
    assert forge.pr_limits == [n]
    assert "possibly truncated" in result.output
    facts = json.loads((tmp_path / "facts.json").read_text(encoding="utf-8"))
    assert facts["warnings"] == [{"source": "prs", "target": "derio-net/super-fr", "limit": n}]


def test_collect_views_the_judged_issues_that_are_no_longer_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "judgements.yaml").write_text(
        'schema: 1\ntiers: [{n: 1, title: T}]\nissues:\n  "super-fr#430": {tier: 1}\n',
        encoding="utf-8",
    )
    forge = _Forge()

    result = _run(monkeypatch, forge, "--repo", "derio-net/super-fr", "--dir", str(tmp_path))

    assert result.exit_code == 0, result.output
    assert forge.viewed == [("derio-net/super-fr", 430)]
    facts = json.loads((tmp_path / "facts.json").read_text(encoding="utf-8"))
    closed = [i for i in facts["issues"] if i["number"] == 430]
    assert closed and closed[0]["state"] == "closed"


def test_a_bad_judgements_file_exits_2_naming_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "judgements.yaml").write_text("schema: 2\n", encoding="utf-8")

    result = _run(monkeypatch, _Forge(), "--repo", "derio-net/super-fr", "--dir", str(tmp_path))

    assert result.exit_code == 2
    assert "judgements.yaml" in result.output


def test_an_unviewed_judgement_is_reported_verbatim_and_still_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review r-p2-unviewed: a failed view is said out loud, never silently dropped."""
    (tmp_path / "judgements.yaml").write_text(
        'schema: 1\ntiers: [{n: 1, title: T}]\nissues:\n  "super-fr#430": {tier: 1}\n',
        encoding="utf-8",
    )
    forge = _Forge()

    def view_issue(*, repo: str, number: int) -> dict[str, Any]:
        raise ForgeError("[rate limit] [/red]")

    forge.view_issue = view_issue  # type: ignore[method-assign]

    result = _run(monkeypatch, forge, "--repo", "derio-net/super-fr", "--dir", str(tmp_path))

    assert result.exit_code == 0, result.output
    assert "super-fr#430" in result.output
    assert "[rate limit] [/red]" in result.output
    facts = json.loads((tmp_path / "facts.json").read_text(encoding="utf-8"))
    assert facts["unviewed"] == [{"key": "super-fr#430", "reason": "[rate limit] [/red]"}]


def test_org_scope_with_every_repo_skipped_exits_2_with_the_reasons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review r-p2-empty: an empty board would look like a clean backlog."""
    forge = _Forge(fail_with="[no access] [/red]")
    forge.list_repos = lambda *, owner, limit: [  # type: ignore[method-assign]
        {"name": "beta", "isArchived": False}
    ]

    result = _run(monkeypatch, forge, "--org", "example-org", "--dir", str(tmp_path))

    assert result.exit_code == 2
    assert "example-org/beta" in result.output
    assert "[no access] [/red]" in result.output
    assert not (tmp_path / "facts.json").exists()


# ------------------------------------------------ review r-p3-softwrap
#
# rich hard-wraps at the terminal width, which splits a forge or judgement
# string across lines and breaks verbatim output. Every print of such text uses
# soft_wrap=True. tests/conftest.py pins COLUMNS=200 for the whole suite, so
# these tests narrow it to 40 themselves, or they would prove nothing.


@pytest.fixture
def narrow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "40")


LONG = (
    "[denied] the forge refused this request for a reason long enough that rich "
    "would split it across two lines at eighty columns"
)


def _judged_430(tmp_path: Path) -> None:
    (tmp_path / "judgements.yaml").write_text(
        'schema: 1\ntiers: [{n: 1, title: T}]\nissues:\n  "super-fr#430": {tier: 1}\n',
        encoding="utf-8",
    )


def test_a_long_skipped_reason_prints_on_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, narrow: None
) -> None:
    result = _run(
        monkeypatch, _Forge(fail_with=LONG), "--org", "example-org", "--dir", str(tmp_path)
    )

    assert result.exit_code == 0, result.output
    assert LONG in result.output


def test_a_long_unviewed_reason_prints_on_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, narrow: None
) -> None:
    _judged_430(tmp_path)
    forge = _Forge()

    def view_issue(*, repo: str, number: int) -> dict[str, Any]:
        raise ForgeError(LONG)

    forge.view_issue = view_issue  # type: ignore[method-assign]
    result = _run(monkeypatch, forge, "--repo", "derio-net/super-fr", "--dir", str(tmp_path))

    assert result.exit_code == 0, result.output
    assert LONG in result.output


def test_a_long_forge_error_prints_on_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, narrow: None
) -> None:
    result = _run(
        monkeypatch, _Forge(fail_with=LONG), "--repo", "derio-net/super-fr", "--dir", str(tmp_path)
    )

    assert result.exit_code == 2
    assert LONG in result.output


@pytest.mark.parametrize("command", ["check", "render"])
def test_an_unreadable_state_file_error_prints_on_one_line(
    tmp_path: Path, command: str, narrow: None
) -> None:
    """_load_state's TriageError quotes the state file's path; it must not be split."""
    (tmp_path / "facts.json").write_text("{}", encoding="utf-8")

    result = CliRunner().invoke(
        app, ["triage", command, "--repo", "derio-net/super-fr", "--dir", str(tmp_path)]
    )

    assert result.exit_code == 2
    assert f"{tmp_path / 'facts.json'}: " in result.output
