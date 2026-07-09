"""Phase 5 — fr acceptance init (scaffold) + backfill emitter + trap-7 gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

runner = CliRunner()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "own"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/derio-net/own.git"],
        cwd=root,
        check=True,
    )
    return root


def _invoke(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", *args])


# ── T1: init scaffolding ───────────────────────────────────────────────────


def test_init_scaffolds_all_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    result = _invoke(root, monkeypatch, "init")
    assert result.exit_code == 0, result.output

    matrix = (root / "docs" / "acceptance" / "matrix.yaml").read_text()
    assert matrix.startswith("#")  # schema-comment header
    assert "org: derio-net" in matrix
    assert "repo: own" in matrix

    rule = (root / ".claude" / "rules" / "acceptance-matrix.md").read_text()
    assert "SAME PR" in rule
    assert "not-implemented" in rule and "skipped" in rule  # the status ladder

    gitignore = (root / ".gitignore").read_text()
    assert "docs/acceptance/report.html" in gitignore

    assert (root / ".github" / "workflows" / "acceptance-report.yml").exists()


def test_init_skeleton_passes_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    assert _invoke(root, monkeypatch, "init").exit_code == 0
    result = _invoke(root, monkeypatch, "check")
    assert result.exit_code == 0, result.output


def test_init_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    assert _invoke(root, monkeypatch, "init").exit_code == 0
    snapshot = {
        p: (root / p).read_text()
        for p in (
            "docs/acceptance/matrix.yaml",
            ".claude/rules/acceptance-matrix.md",
            ".gitignore",
            ".github/workflows/acceptance-report.yml",
        )
    }
    result = _invoke(root, monkeypatch, "init")
    assert result.exit_code == 0
    for p, text in snapshot.items():
        assert (root / p).read_text() == text, f"{p} changed on re-run"


def test_init_leaves_user_matrix_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    assert _invoke(root, monkeypatch, "init").exit_code == 0
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    edited = matrix_path.read_text() + row(id="user-row")
    matrix_path.write_text(edited)
    assert _invoke(root, monkeypatch, "init").exit_code == 0
    assert matrix_path.read_text() == edited


def test_add_works_on_fresh_skeleton(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`rows:` (implicit null) in the skeleton must accept the first append."""
    root = _repo(tmp_path)
    assert _invoke(root, monkeypatch, "init").exit_code == 0
    result = _invoke(
        root,
        monkeypatch,
        "add",
        "--id",
        "first",
        "--capability",
        "C",
        "--acceptance",
        "A",
        "--status",
        "not-implemented",
    )
    assert result.exit_code == 0, result.output
    assert _invoke(root, monkeypatch, "status").output.count("first") == 1


# ── T2: workflow content + trap-7 coverage gate ────────────────────────────


def _workflow(root: Path) -> dict:
    doc = yaml.safe_load((root / ".github" / "workflows" / "acceptance-report.yml").read_text())
    # YAML 1.1 parses the `on:` key as boolean True.
    doc["on"] = doc.get("on", doc.get(True))
    return doc


def test_workflow_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    assert _invoke(root, monkeypatch, "init").exit_code == 0
    wf = _workflow(root)
    for trigger in ("pull_request", "push"):
        paths = wf["on"][trigger]["paths"]
        assert "docs/acceptance/**" in paths
        assert "docs/superpowers/specs/**" in paths
        assert "docs/superpowers/implemented/specs/**" in paths
        assert ".github/workflows/**" in paths
    assert "schedule" in wf["on"]
    assert "workflow_dispatch" in wf["on"]

    steps = wf["jobs"]["matrix"]["steps"]
    scripted = "\n".join(s.get("run", "") for s in steps)
    assert "fr acceptance check" in scripted
    assert "fr acceptance report --link-mode github" in scripted
    assert "fr acceptance digest" in scripted
    digest_steps = [s for s in steps if "digest" in s.get("run", "")]
    assert all("schedule" in s.get("if", "") for s in digest_steps)
    uploads = [s for s in steps if "upload-artifact" in s.get("uses", "")]
    assert uploads and uploads[0]["with"]["path"] == "docs/acceptance/report.html"
    header = (root / ".github" / "workflows" / "acceptance-report.yml").read_text()
    assert "Sister-repo refs" in header  # trap-7 honesty note


def test_check_warns_on_uncovered_matrix_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trap 7 code-enforced: a matrix ref outside the workflow's PR path
    filters would only break at the weekly cron — warn at check time."""
    root = make_repo(tmp_path, row(id="a", unit='"own:scripts/x.sh"'))
    (root / "scripts").mkdir()
    (root / "scripts" / "x.sh").write_text("#!/bin/sh\n")
    wf_dir = root / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    wf_dir.joinpath("acceptance-report.yml").write_text(
        "on:\n  pull_request:\n    paths:\n"
        "      - docs/acceptance/**\n      - docs/superpowers/specs/**\n"
        "      - docs/superpowers/implemented/specs/**\n"
    )
    result = _invoke(root, monkeypatch, "check")
    assert result.exit_code == 0, result.output
    assert "scripts/x.sh" in result.output
    assert "path filters" in result.output


def test_check_no_warning_when_covered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="a", unit='"own:scripts/x.sh"'))
    (root / "scripts").mkdir()
    (root / "scripts" / "x.sh").write_text("#!/bin/sh\n")
    wf_dir = root / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    wf_dir.joinpath("acceptance-report.yml").write_text(
        "on:\n  pull_request:\n    paths:\n"
        "      - docs/acceptance/**\n      - docs/superpowers/specs/**\n"
        "      - docs/superpowers/implemented/specs/**\n      - scripts/**\n"
        "      - tests/**\n"
    )
    result = _invoke(root, monkeypatch, "check")
    assert "path filters" not in result.output


def test_check_glob_star_does_not_span_slash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review finding (#352): GitHub Actions' `*` stops at `/` (only `**`
    spans) — fnmatch's `*` spans, which would report "covered" for a path
    Actions would never trigger on. Exactly the false negative trap 7 exists
    to prevent."""
    root = make_repo(tmp_path, row(id="a", unit='"own:docs/sub/x.md"'))
    (root / "docs" / "sub").mkdir(parents=True)
    (root / "docs" / "sub" / "x.md").write_text("x\n")
    wf_dir = root / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    wf_dir.joinpath("acceptance-report.yml").write_text(
        "on:\n  pull_request:\n    paths:\n"
        "      - docs/*.md\n"  # does NOT cover docs/sub/x.md in Actions
        "      - docs/acceptance/**\n      - docs/superpowers/**\n      - tests/**\n"
    )
    result = _invoke(root, monkeypatch, "check")
    assert result.exit_code == 0, result.output
    assert "docs/sub/x.md" in result.output
    assert "path filters" in result.output


def test_check_globstar_spans_slash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="a", unit='"own:docs/sub/x.md"'))
    (root / "docs" / "sub").mkdir(parents=True)
    (root / "docs" / "sub" / "x.md").write_text("x\n")
    wf_dir = root / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    wf_dir.joinpath("acceptance-report.yml").write_text(
        "on:\n  pull_request:\n    paths:\n      - docs/**\n      - tests/**\n"
    )
    result = _invoke(root, monkeypatch, "check")
    assert "path filters" not in result.output


def test_check_no_workflow_no_coverage_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="a"))
    result = _invoke(root, monkeypatch, "check")
    assert "path filters" not in result.output


# ── T3: backfill emitter ───────────────────────────────────────────────────


def test_backfill_protocol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="a"))
    # an uncited spec with a Test Plan
    (root / "docs" / "superpowers" / "specs" / "uncited.md").write_text(
        "# u\n\n## Test Plan\n\n1. y\n"
    )
    # a live plan with no acceptance links
    plan = root / "docs" / "superpowers" / "plans" / "2026-01-01-toy"
    plan.mkdir(parents=True)
    (plan / "01.yaml").write_text(
        "schema_version: 2\nphase:\n  number: 1\n  title: T\n  tag: agentic\n"
        "tasks: []\nstate:\n  steps: {}\n  completion:\n    at: null\n"
    )
    result = _invoke(root, monkeypatch, "backfill")
    assert result.exit_code == 0, result.output
    out = result.output
    assert "uncited.md" in out
    assert "2026-01-01-toy" in out
    assert "one row per business acceptance" in out
    assert "choose skipped" in out  # honesty calibration
    assert "fr acceptance check" in out
    assert "tests/" in out  # test-tree hint


def test_backfill_clean_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="a"))
    result = _invoke(root, monkeypatch, "backfill")
    assert result.exit_code == 0
    assert "every Test Plan spec is cited" in result.output


# ── multi-backend: CI template becomes backend-conditional ─────────────────
# (docs/superpowers/specs/2026-07-09-multi-backend-git-host-adapters-design.md §10)


def _repo_with_backend(tmp_path: Path, backend: str) -> Path:
    root = _repo(tmp_path)
    (root / ".devcontainer").mkdir()
    (root / ".devcontainer" / "fr-profiles.yaml").write_text(
        f"backend: {backend}\nprofiles:\n  dev:\n    purpose: x\n"
    )
    return root


def test_init_github_backend_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression guard: backend="github" (the default) still writes
    .github/workflows/acceptance-report.yml, unchanged."""
    root = _repo(tmp_path)
    result = _invoke(root, monkeypatch, "init")
    assert result.exit_code == 0, result.output
    assert (root / ".github" / "workflows" / "acceptance-report.yml").exists()
    assert not (root / ".gitea").exists()
    assert not (root / ".gitlab-ci.yml").exists()


def test_init_gitea_backend_writes_gitea_workflows_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Gitea-backed repo writes .gitea/workflows/acceptance-report.yml —
    NOT .github/ — with tea calls instead of gh (Gitea Actions is
    YAML-schema-compatible with GitHub Actions, but uses its own
    directory, confirmed against Gitea's own docs)."""
    root = _repo_with_backend(tmp_path, "gitea")
    result = _invoke(root, monkeypatch, "init")
    assert result.exit_code == 0, result.output
    assert not (root / ".github" / "workflows" / "acceptance-report.yml").exists()
    wf = root / ".gitea" / "workflows" / "acceptance-report.yml"
    assert wf.exists()
    text = wf.read_text()
    assert "tea " in text or "tea\n" in text
    assert "gh issue" not in text
    # Same trigger/job/step YAML shape as GitHub Actions.
    doc = yaml.safe_load(text)
    assert "jobs" in doc


def test_init_gitlab_backend_writes_gitlab_ci_at_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A GitLab-backed repo writes .gitlab-ci.yml at the repo root — a
    genuinely different schema (stages/script), not the GitHub-Actions
    on/jobs/steps shape."""
    root = _repo_with_backend(tmp_path, "gitlab")
    result = _invoke(root, monkeypatch, "init")
    assert result.exit_code == 0, result.output
    assert not (root / ".github" / "workflows" / "acceptance-report.yml").exists()
    ci_file = root / ".gitlab-ci.yml"
    assert ci_file.exists()
    text = ci_file.read_text()
    assert "glab " in text
    assert "gh issue" not in text
    doc = yaml.safe_load(text)
    assert "stages" in doc
