"""gh#775 — `fr acceptance` on a repo with no CI.

Take 9 of a recording ran `fr acceptance init` on a GitLab project with no CI:
it scaffolded `.gitlab-ci.yml` (installing fr from GitHub `main`), rewrote
`.gitignore` wholesale, and every row then moved to `ci` with no CI to run it.

Two causes, pinned separately:

- **A** — the CI-shaped outputs keyed off the forge backend, never off whether
  the repo has CI. So init scaffolds a pipeline only when the repo already has
  a CI config for its backend (or `--with-ci` asks), and a row reaches `ci`
  only in a repo that has one.
- **B** — the `.gitignore` edit rewrote the whole file (`splitlines()` +
  `join`), normalising its line endings and final newline. It now appends the
  one line and touches no other byte.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.acceptance.scaffold import init
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

runner = CliRunner()


def _repo(tmp_path: Path, remote: str = "https://gitlab.com/example-org/demo.git") -> Path:
    root = tmp_path / "demo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=root, check=True)
    return root


def _invoke(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", *args])


# ── A: init scaffolds CI only for a repo that has CI ──────────────────────


def test_init_on_gitlab_without_ci_writes_no_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    result = _invoke(root, monkeypatch, "init")
    assert result.exit_code == 0, result.output
    assert not (root / ".gitlab-ci.yml").exists()
    assert "--with-ci" in result.output, "the skip must say how to ask for one"


@pytest.mark.parametrize(
    "backend, remote",
    [
        ("github", "https://github.com/derio-net/demo.git"),
        ("gitlab", "https://gitlab.com/example-org/demo.git"),
    ],
)
def test_init_without_ci_names_no_pipeline_in_the_matrix_or_rule(
    tmp_path: Path, backend: str, remote: str
) -> None:
    root = _repo(tmp_path, remote)
    init(root, "example-org", "demo", backend=backend)  # type: ignore[arg-type]
    for rel in ("docs/acceptance/matrix.yaml", ".claude/rules/acceptance-matrix.md"):
        text = (root / rel).read_text()
        assert ".github/workflows" not in text, rel
        assert ".gitlab-ci.yml" not in text, rel
    assert not (root / ".github").exists()


def test_init_with_ci_flag_scaffolds_the_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    result = _invoke(root, monkeypatch, "init", "--with-ci")
    assert result.exit_code == 0, result.output
    assert "glab " in (root / ".gitlab-ci.yml").read_text()


def test_init_scaffolds_the_workflow_beside_an_existing_github_ci(tmp_path: Path) -> None:
    root = _repo(tmp_path, "https://github.com/derio-net/demo.git")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("on: push\n")
    outcome = init(root, "derio-net", "demo", backend="github")
    assert ".github/workflows/acceptance-report.yml" in outcome.created
    matrix = (root / "docs" / "acceptance" / "matrix.yaml").read_text()
    assert ".github/workflows/acceptance-report.yml" in matrix


def test_init_leaves_an_existing_gitlab_ci_untouched(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / ".gitlab-ci.yml").write_text("test:\n  script: [make]\n")
    outcome = init(root, "example-org", "demo", backend="gitlab")
    assert ".gitlab-ci.yml" in outcome.skipped
    assert (root / ".gitlab-ci.yml").read_text() == "test:\n  script: [make]\n"


# ── A: a row reaches `ci` only in a repo with CI ──────────────────────────


def test_set_status_ci_refused_in_a_repo_without_ci(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="target", status="skipped"), ci=False)
    matrix = root / "docs" / "acceptance" / "matrix.yaml"
    before = matrix.read_text()
    result = _invoke(
        root, monkeypatch, "set-status", "--id", "target", "--status", "ci", "--notes", "n"
    )
    assert result.exit_code != 0, result.output
    assert "no CI config" in result.output
    assert matrix.read_text() == before, "a refusal changes nothing"


def test_add_ci_refused_in_a_repo_without_ci(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, "", ci=False)
    result = _invoke(
        root,
        monkeypatch,
        "add",
        "--id",
        "new",
        "--capability",
        "C",
        "--acceptance",
        "A",
        "--status",
        "ci",
    )
    assert result.exit_code != 0, result.output
    assert "no CI config" in result.output


def test_non_ci_statuses_need_no_ci(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="target", status="not-implemented"), ci=False)
    result = _invoke(
        root, monkeypatch, "set-status", "--id", "target", "--status", "skipped", "--notes", "n"
    )
    assert result.exit_code == 0, result.output


def test_set_status_ci_allowed_with_a_ci_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="target", status="skipped"), ci=True)
    result = _invoke(
        root, monkeypatch, "set-status", "--id", "target", "--status", "ci", "--notes", "n"
    )
    assert result.exit_code == 0, result.output


# ── B: the .gitignore edit is one appended line, nothing else ─────────────


@pytest.mark.parametrize(
    "original, expected",
    [
        (b"node_modules\n", b"node_modules\ndocs/acceptance/report.html\n"),
        (b"node_modules", b"node_modules\ndocs/acceptance/report.html\n"),
        (b"a\r\nb\r\n", b"a\r\nb\r\ndocs/acceptance/report.html\r\n"),
        (b"a\n\n\n", b"a\n\n\ndocs/acceptance/report.html\n"),
    ],
)
def test_gitignore_edit_only_appends(tmp_path: Path, original: bytes, expected: bytes) -> None:
    root = _repo(tmp_path)
    (root / ".gitignore").write_bytes(original)
    init(root, "example-org", "demo", backend="gitlab")
    assert (root / ".gitignore").read_bytes() == expected


def test_gitignore_already_carrying_the_line_is_not_touched(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    original = b"x\r\ndocs/acceptance/report.html\r\ny"
    (root / ".gitignore").write_bytes(original)
    outcome = init(root, "example-org", "demo", backend="gitlab")
    assert ".gitignore" in outcome.skipped
    assert (root / ".gitignore").read_bytes() == original
