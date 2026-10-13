"""`fr acceptance init --refresh-ci` (spec 2026-10-11-debt-engine R13)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.scaffold import refresh_ci, render_workflow

LEGACY_GITHUB = """\
name: acceptance-report
on: {push: {}}
jobs:
  matrix:
    steps:
      - run: fr acceptance check
      - name: Upsert acceptance-debt issue (weekly digest)
        run: fr acceptance digest > /tmp/digest.md
"""


def _put(root: Path, rel: str, text: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text)


@pytest.mark.parametrize(
    ("ci", "rel"),
    [
        ("github-actions", ".github/workflows/acceptance-report.yml"),
        ("gitea-actions", ".gitea/workflows/acceptance-report.yml"),
    ],
)
def test_a_legacy_scaffold_is_rewritten_to_the_current_one(
    tmp_path: Path, ci: str, rel: str
) -> None:
    _put(tmp_path, rel, LEGACY_GITHUB)
    out = refresh_ci(tmp_path, ci, debt=True)
    assert out.status == "rewritten"
    assert (tmp_path / rel).read_text() == render_workflow(ci, debt=True)
    text = (tmp_path / rel).read_text()
    assert "fetch-depth: 0" in text and "fr debt issue --yes" in text and "debt:" in text
    assert refresh_ci(tmp_path, ci, debt=True).status == "current"


def test_a_new_step_file_is_also_rewritten(tmp_path: Path) -> None:
    rel = ".github/workflows/acceptance-report.yml"
    _put(tmp_path, rel, "name: acceptance-report\nsteps:\n  - run: fr debt issue\n")
    assert refresh_ci(tmp_path, "github-actions", debt=True).status == "rewritten"


def test_a_foreign_file_is_refused_and_untouched(tmp_path: Path) -> None:
    rel = ".github/workflows/acceptance-report.yml"
    for body in ("name: something-else\nrun: fr acceptance digest\n", "name: acceptance-report\n"):
        _put(tmp_path, rel, body)
        assert refresh_ci(tmp_path, "github-actions", debt=True).status == "foreign"
        assert (tmp_path / rel).read_text() == body


def test_gitlab_is_never_rewritten_and_prints_the_job(tmp_path: Path) -> None:
    shared = (
        "stages: [build, acceptance]\nbuild:\n  script: make\nacceptance-report:\n  script: x\n"
    )
    _put(tmp_path, ".gitlab-ci.yml", shared)
    out = refresh_ci(tmp_path, "gitlab-ci", debt=True)
    assert out.status == "paste" and out.text.startswith("acceptance-report:")
    assert "fr debt issue --yes" in out.text and "GIT_DEPTH" in out.text
    assert (tmp_path / ".gitlab-ci.yml").read_text() == shared


def test_gitlab_without_the_job_is_foreign(tmp_path: Path) -> None:
    _put(tmp_path, ".gitlab-ci.yml", "build:\n  script: make\n")
    assert refresh_ci(tmp_path, "gitlab-ci", debt=True).status == "foreign"


def test_a_missing_file_is_reported(tmp_path: Path) -> None:
    assert refresh_ci(tmp_path, "github-actions", debt=True).status == "missing"


def test_the_cli_flag_rewrites_and_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from fr.cli import app
    from typer.testing import CliRunner

    subprocess.run(["git", "init", "-q", "-b", "work", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "remote", "add", "origin", "https://github.com/o/r.git"],
        check=True,
    )
    rel = ".github/workflows/acceptance-report.yml"
    _put(tmp_path, rel, LEGACY_GITHUB)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    r = CliRunner().invoke(app, ["acceptance", "init", "--refresh-ci"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / rel).read_text() == render_workflow("github-actions", debt=True)


def test_the_cli_flag_refuses_a_foreign_file_with_exit_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from fr.cli import app
    from typer.testing import CliRunner

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "remote", "add", "origin", "https://github.com/o/r.git"],
        check=True,
    )
    _put(tmp_path, ".github/workflows/acceptance-report.yml", "name: mine\n")
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    r = CliRunner().invoke(app, ["acceptance", "init", "--refresh-ci"])
    assert r.exit_code == 1 and "not an fr-scaffolded" in r.output
