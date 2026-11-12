"""The scaffolded CI publishes the derived report (spec 2026-11-04 R20-R22).

The goldens in `tests/fixtures/acceptance_scaffold/*.published.golden` are the rendered
templates with Pages and the PR comment on. They are reviewed renderings of fr's own
template, not captures of a forge: a forge has nothing to capture them from.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.acceptance.scaffold import (
    BADGE_CLOSE,
    BADGE_OPEN,
    badge_line,
    init,
    publish_plan,
    render_workflow,
    write_badge,
)
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row
from tests.unit.settings_repo import git, land_on_main

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "acceptance_scaffold"
CI_TYPES = ["github-actions", "gitea-actions", "gitlab-ci"]
runner = CliRunner()


@pytest.mark.parametrize("ci_type", CI_TYPES)
def test_published_render_matches_the_golden(ci_type: str) -> None:
    got = render_workflow(ci_type, debt=True, pages=True, comment=True)
    assert got == (GOLDEN / f"{ci_type}.published.golden").read_text()


@pytest.mark.parametrize("ci_type", CI_TYPES)
@pytest.mark.parametrize("pages", [False, True])
@pytest.mark.parametrize("comment", [False, True])
def test_every_render_is_valid_yaml_with_no_token_left(
    ci_type: str, pages: bool, comment: bool
) -> None:
    text = render_workflow(ci_type, debt=True, pages=pages, comment=comment)
    assert "@@" not in text
    assert isinstance(yaml.safe_load(text), dict)


@pytest.mark.parametrize("ci_type", CI_TYPES)
def test_every_template_folds_over_full_history_and_checks(ci_type: str) -> None:
    text = render_workflow(ci_type, debt=False)
    assert ('GIT_DEPTH: "0"' in text) if ci_type == "gitlab-ci" else ("fetch-depth: 0" in text)
    assert "fr acceptance check" in text


@pytest.mark.parametrize("ci_type", ["github-actions", "gitea-actions"])
def test_actions_templates_write_the_job_summary(ci_type: str) -> None:
    assert 'fr acceptance summary >> "$GITHUB_STEP_SUMMARY"' in render_workflow(ci_type, debt=False)


def test_gitlab_exposes_the_report_artifact() -> None:
    job = yaml.safe_load(render_workflow("gitlab-ci", debt=False))["acceptance-report"]
    assert job["artifacts"]["expose_as"] == "Acceptance report"
    assert job["artifacts"]["paths"] == ["docs/acceptance/report.html"]


@pytest.mark.parametrize("ci_type", CI_TYPES)
def test_no_pages_job_unless_allowed(ci_type: str) -> None:
    text = render_workflow(ci_type, debt=True)
    assert "pages-check" not in text and "deploy-pages" not in text
    assert "pages" not in yaml.safe_load(text).get("jobs", yaml.safe_load(text))


def test_github_pages_job_rechecks_before_every_deploy() -> None:
    text = render_workflow("github-actions", debt=False, pages=True)
    job = yaml.safe_load(text)["jobs"]["pages"]
    steps = job["steps"]
    names = [s.get("name") or s.get("uses", "") for s in steps]
    check = next(i for i, s in enumerate(steps) if "pages-check" in s.get("run", ""))
    deploy = next(i for i, s in enumerate(steps) if "deploy-pages" in s.get("uses", ""))
    assert check < deploy, names
    # every step after the check is skipped when the check did not allow the deploy
    for s in steps[check + 1 :]:
        assert "steps.visibility.outputs.allowed == 'true'" in s["if"], s
    assert "default_branch" in job["if"] and "matrix" in job["needs"]
    assert job["permissions"]["pages"] == "write"
    # p4-r1: a refusal fails the job and names how to unpublish; it never just skips
    check_run = steps[check]["run"]
    assert "::error::" in check_run and "exit 1" in check_run and "pages" in check_run
    assert "::warning::" not in check_run
    # the matrix job never gets it
    assert "pages" not in yaml.safe_load(text)["jobs"]["matrix"].get("permissions", {})


def test_gitlab_pages_job_checks_first_and_fails_loudly() -> None:
    job = yaml.safe_load(render_workflow("gitlab-ci", debt=False, pages=True))["pages"]
    assert "fr acceptance pages-check" in job["script"][0]
    assert "exit 1" in job["script"][0] and "unpublish" in job["script"][0]
    assert "allow_failure" not in job
    # p4-r2: the check reads the forge, so the job carries a credential
    assert job["variables"]["GITLAB_TOKEN"] == "$FR_PAGES_TOKEN"
    # p4-r4: a failing matrix must not publish
    assert job["needs"] == ["acceptance-report"]
    assert job["artifacts"]["paths"] == ["public"]


def test_gitea_never_gets_a_pages_job() -> None:
    assert render_workflow("gitea-actions", debt=True, pages=True) == render_workflow(
        "gitea-actions", debt=True
    )


def test_comment_job_is_github_only_and_the_only_one_to_write_pull_requests() -> None:
    text = render_workflow("github-actions", debt=True, comment=True)
    jobs = yaml.safe_load(text)["jobs"]
    job = jobs["report-comment"]
    assert job["permissions"]["pull-requests"] == "write"
    assert "fr acceptance comment" in job["steps"][-1]["run"]
    assert "--yes" in job["steps"][-1]["run"]
    assert "pull-requests" not in jobs["matrix"].get("permissions", {})
    assert "pull-requests: write" in text  # also the debt job's, so count the job itself
    for ci in ("gitea-actions", "gitlab-ci"):
        assert "acceptance comment" not in render_workflow(ci, debt=True, comment=True)


# ---- publish_plan reads the settings ----

URL = "https://github.com/example-org/widgets.git"


def _real_repo(tmp_path: Path, settings: str = "", url: str = URL) -> Path:
    """An acceptance repo that is a real clone of a bare origin (so the settings, read from
    the default ref, are the ones landed there), whose origin URL then reads as `url`."""
    root = make_repo(tmp_path, row(id="a"), git=False)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "t")
    git(root, "config", "user.email", "t@example.invalid")
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    git(root, "remote", "add", "origin", str(origin))
    git(root, "add", "-A")
    git(root, "commit", "-qm", "seed")
    git(root, "push", "-q", "-u", "origin", "main")
    git(root, "remote", "set-head", "origin", "main")
    land_on_main(root, settings or "{}\n")
    git(root, "remote", "set-url", "origin", url)
    return root


def test_plan_defaults_to_no_comment_and_no_pages(tmp_path: Path) -> None:
    root = _real_repo(tmp_path)
    plan = publish_plan(root, "github-actions", None)
    assert (plan.pages, plan.comment) == (False, False)
    assert plan.notices == ()  # not asked: nothing to explain
    denied = publish_plan(root, "github-actions", (False, "visibility is unknown"))
    assert not denied.pages and any("no Pages" in n for n in denied.notices)


def test_plan_pages_follow_the_decision(tmp_path: Path) -> None:
    root = _real_repo(tmp_path)
    assert publish_plan(root, "github-actions", (True, "public")).pages
    assert not publish_plan(root, "github-actions", (False, "unknown")).pages
    assert not publish_plan(root, "gitea-actions", (True, "x")).pages


def test_plan_comment_needs_report_comment_and_comments_on(tmp_path: Path) -> None:
    root = _real_repo(tmp_path, "forge:\n  report_comment: on\n")
    assert publish_plan(root, "github-actions", None).comment
    assert not publish_plan(root, "gitlab-ci", None).comment
    assert any("report comment" in n for n in publish_plan(root, "gitlab-ci", None).notices)


def test_plan_comment_is_off_by_default(tmp_path: Path) -> None:
    root = _real_repo(tmp_path, "forge:\n  comments: on\n")
    assert not publish_plan(root, "github-actions", None).comment


# ---- the README badge ----


def _readme(root: Path, text: str = "# Widgets\n\nBody.\n") -> Path:
    (root / "README.md").write_text(text)
    return root / "README.md"


def _origin(root: Path, url: str = "https://github.com/example-org/widgets.git") -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", url], check=True)


def test_badge_points_at_pages_when_published(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row())
    _origin(root)
    assert (
        badge_line(root, "github-actions", pages=True)
        == "[Acceptance report](https://example-org.github.io/widgets/)"
    )


def test_badge_points_at_the_ci_run_otherwise(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row())
    _origin(root)
    line = badge_line(root, "github-actions", pages=False)
    assert line is not None
    assert "github.com/example-org/widgets/actions/workflows/acceptance-report.yml" in line
    assert "branch=main" in line and "github.io" not in line
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "remote",
            "set-url",
            "origin",
            "https://gitlab.example.com/g/p.git",
        ],
        check=True,
    )
    gl = badge_line(root, "gitlab-ci", pages=False)
    assert gl is not None and "badges/main/pipeline.svg" in gl and "/-/pipelines/latest" in gl


def test_write_badge_is_idempotent_and_marker_bounded(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row())
    readme = _readme(root)
    assert write_badge(root, "LINE-ONE") == "created"
    first = readme.read_text()
    assert f"{BADGE_OPEN}\nLINE-ONE\n{BADGE_CLOSE}" in first
    assert first.startswith("# Widgets\n") and first.endswith("Body.\n")
    assert write_badge(root, "LINE-ONE") == "current"
    assert readme.read_text() == first
    assert write_badge(root, "LINE-TWO") == "modified"
    assert readme.read_text() == first.replace("LINE-ONE", "LINE-TWO")


def test_write_badge_leaves_a_readmeless_repo_alone(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row())
    assert write_badge(root, "X") == "no-readme"
    assert not (root / "README.md").exists()


def test_init_scaffolds_pages_and_badge_when_allowed(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "", ci=False)
    _origin(root)
    _readme(root)
    out = init(
        root, "example-org", "widgets", backend="github", with_ci=True,
        ci_type="github-actions", tracking_type="github", pages_decision=(True, "public"),
    )  # fmt: skip
    wf = yaml.safe_load((root / ".github/workflows/acceptance-report.yml").read_text())
    assert "pages" in wf["jobs"]
    assert "README.md" in out.modified
    assert "github.io/widgets" in (root / "README.md").read_text()
    again = init(
        root, "example-org", "widgets", backend="github", with_ci=True,
        ci_type="github-actions", tracking_type="github", pages_decision=(True, "public"),
    )  # fmt: skip
    assert "README.md" not in again.modified


def test_init_fails_closed_without_a_pages_answer(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "", ci=False)
    _origin(root)
    _readme(root)
    out = init(
        root, "example-org", "widgets", backend="github", with_ci=True,
        ci_type="github-actions", tracking_type="github", pages_decision=(False, "unknown"),
    )  # fmt: skip
    wf = yaml.safe_load((root / ".github/workflows/acceptance-report.yml").read_text())
    assert "pages" not in wf["jobs"]
    assert any("no Pages" in n for n in out.notices)
    readme = (root / "README.md").read_text()
    assert "actions/workflows/acceptance-report.yml" in readme and "github.io" not in readme


def test_init_creates_no_readme(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "", ci=False)
    _origin(root)
    init(
        root, "example-org", "widgets", backend="github", with_ci=True,
        ci_type="github-actions", tracking_type="github",
    )  # fmt: skip
    assert not (root / "README.md").exists()


# ---- fr acceptance comment ----


class _Forge:
    def __init__(self, comments: list[dict[str, Any]] | None = None, login: str = "me") -> None:
        self.comments = comments or []
        self.login = login
        self.calls: list[tuple[str, Any]] = []

    def authenticated_login(self) -> str:
        if isinstance(self.login, Exception):
            raise self.login
        return self.login

    def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]:
        self.calls.append(("list", (repo, number)))
        return self.comments

    def comment_pr(self, repo: str, pr: int, body: str) -> None:
        self.calls.append(("post", (repo, pr, body)))

    def edit_issue_comment(self, repo: str, comment_id: int, body: str) -> None:
        self.calls.append(("edit", (repo, comment_id, body)))


def _comment_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forge: _Forge, settings: str):
    root = _real_repo(tmp_path, settings)
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    monkeypatch.setattr("fr.hostclient.client_for", lambda r: forge)
    return root


ON = "forge:\n  report_comment: on\n"


def test_comment_posts_one_marker_comment_with_the_markdown_report(tmp_path, monkeypatch):
    forge = _Forge()
    _comment_repo(tmp_path, monkeypatch, forge, ON)
    res = runner.invoke(app, ["acceptance", "comment", "--pr", "7", "--yes"])
    assert res.exit_code == 0, res.output
    kinds = [c[0] for c in forge.calls]
    assert kinds == ["list", "post"]
    repo, pr, body = forge.calls[1][1]
    assert (repo, pr) == ("example-org/widgets", 7)
    assert body.startswith("<!-- fr:acceptance-report -->\n# Acceptance coverage")


def test_comment_updates_the_existing_marker_comment_in_place(tmp_path, monkeypatch):
    forge = _Forge(
        [
            {"id": 5, "author": "me", "body": "unrelated"},
            {"id": 9, "author": "me", "body": "<!-- fr:acceptance-report -->\nold"},
        ]
    )
    _comment_repo(tmp_path, monkeypatch, forge, ON)
    res = runner.invoke(app, ["acceptance", "comment", "--pr", "7", "--yes"])
    assert res.exit_code == 0, res.output
    assert [c[0] for c in forge.calls] == ["list", "edit"]
    assert forge.calls[1][1][1] == 9


def test_comment_is_refused_without_yes(tmp_path, monkeypatch):
    forge = _Forge()
    _comment_repo(tmp_path, monkeypatch, forge, ON)
    res = runner.invoke(app, ["acceptance", "comment", "--pr", "7"])
    assert res.exit_code == 2, res.output
    assert "--yes" in res.output and forge.calls == []


def test_comment_is_refused_when_report_comment_is_off(tmp_path, monkeypatch):
    forge = _Forge()
    _comment_repo(tmp_path, monkeypatch, forge, "forge:\n  report_comment: off\n")
    res = runner.invoke(app, ["acceptance", "comment", "--pr", "7", "--yes"])
    assert res.exit_code == 2 and "report_comment" in res.output and forge.calls == []


def test_comment_is_refused_when_comments_are_off(tmp_path, monkeypatch):
    forge = _Forge()
    _comment_repo(tmp_path, monkeypatch, forge, "forge:\n  comments: off\n  report_comment: on\n")
    res = runner.invoke(app, ["acceptance", "comment", "--pr", "7", "--yes"])
    assert res.exit_code != 0 and forge.calls == []


def test_comment_body_is_capped_under_the_forge_limit(tmp_path, monkeypatch):
    forge = _Forge()
    root = _comment_repo(tmp_path, monkeypatch, forge, ON)
    monkeypatch.setattr("fr.commands.acceptance_cmd.COMMENT_LIMIT", 300)
    assert (root / "docs").is_dir()
    res = runner.invoke(app, ["acceptance", "comment", "--pr", "7", "--yes"])
    assert res.exit_code == 0, res.output
    body = forge.calls[-1][1][2]
    assert len(body) <= 300 and "truncated" in body


def test_a_foreign_authors_marker_comment_is_never_edited(tmp_path, monkeypatch):
    forge = _Forge(
        [{"id": 3, "author": "mallory", "body": "<!-- fr:acceptance-report -->\nforged"}]
    )
    _comment_repo(tmp_path, monkeypatch, forge, ON)
    res = runner.invoke(app, ["acceptance", "comment", "--pr", "7", "--yes"])
    assert res.exit_code == 0, res.output
    assert [c[0] for c in forge.calls] == ["list", "post"]  # a fresh comment, not an edit


def test_the_workflow_bot_owns_its_marker_comment(tmp_path, monkeypatch):
    forge = _Forge(
        [{"id": 4, "author": "github-actions", "body": "<!-- fr:acceptance-report -->\nold"}],
        login=RuntimeError("Resource not accessible by integration"),
    )
    _comment_repo(tmp_path, monkeypatch, forge, ON)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert runner.invoke(app, ["acceptance", "comment", "--pr", "7", "--yes"]).exit_code == 0
    assert [c[0] for c in forge.calls] == ["list", "edit"]


def test_an_unknown_identity_never_edits(tmp_path, monkeypatch):
    forge = _Forge(
        [{"id": 4, "author": "github-actions", "body": "<!-- fr:acceptance-report -->\nold"}],
        login=RuntimeError("no token"),
    )
    _comment_repo(tmp_path, monkeypatch, forge, ON)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert runner.invoke(app, ["acceptance", "comment", "--pr", "7", "--yes"]).exit_code == 0
    assert [c[0] for c in forge.calls] == ["list", "post"]
