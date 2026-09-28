"""fr.services.detect — what "has CI" means offline (spec
2026-09-28-fr-profiles-services §3.C): a CI config counts, except the one case
fr itself caused — its own acceptance-report scaffold."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.services.detect import detect_ci

WORKFLOW = "name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"


def _write(root: Path, rel: str, text: str = WORKFLOW) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_nothing_is_absent(tmp_path: Path) -> None:
    for forge in ("github", "gitlab", "gitea"):
        assert detect_ci(tmp_path, forge) == "absent"


def test_a_real_workflow_beside_frs_own_is_real(tmp_path: Path) -> None:
    _write(tmp_path, ".github/workflows/ci.yml")
    _write(tmp_path, ".github/workflows/acceptance-report.yml")
    assert detect_ci(tmp_path, "github") == "real"


def test_only_frs_own_workflow_is_fr_only(tmp_path: Path) -> None:
    _write(tmp_path, ".github/workflows/acceptance-report.yml")
    assert detect_ci(tmp_path, "github") == "fr-only"


def test_an_empty_workflows_dir_is_absent(tmp_path: Path) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    assert detect_ci(tmp_path, "github") == "absent"


GITLAB_FR_ONLY = """\
stages:
  - acceptance

variables:
  X: "1"

acceptance-report:
  stage: acceptance
  script: [fr acceptance check]
"""


def test_gitlab_whose_only_job_is_frs_is_fr_only(tmp_path: Path) -> None:
    _write(tmp_path, ".gitlab-ci.yml", GITLAB_FR_ONLY)
    assert detect_ci(tmp_path, "gitlab") == "fr-only"


def test_gitlab_with_an_include_is_real(tmp_path: Path) -> None:
    _write(tmp_path, ".gitlab-ci.yml", "include:\n  - local: ci/jobs.yml\n" + GITLAB_FR_ONLY)
    assert detect_ci(tmp_path, "gitlab") == "real"


def test_gitlab_with_another_job_is_real(tmp_path: Path) -> None:
    _write(tmp_path, ".gitlab-ci.yml", GITLAB_FR_ONLY + "test:\n  script: [make test]\n")
    assert detect_ci(tmp_path, "gitlab") == "real"


def test_an_unparseable_gitlab_file_counts_as_real(tmp_path: Path) -> None:
    """Anything `ci_config` finds counts, save fr's own scaffold — and an
    unreadable file cannot be shown to be fr's."""
    _write(tmp_path, ".gitlab-ci.yml", "not: [valid, yaml: :::")
    assert detect_ci(tmp_path, "gitlab") == "real"


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ([".gitea/workflows/ci.yml"], "real"),
        ([".gitea/workflows/acceptance-report.yml"], "fr-only"),
        ([".github/workflows/ci.yml"], "real"),
        ([".github/workflows/acceptance-report.yml"], "fr-only"),
        # .gitea/workflows wins when present: Gitea reads .github only as a fallback
        ([".gitea/workflows/acceptance-report.yml", ".github/workflows/ci.yml"], "fr-only"),
    ],
)
def test_gitea_checks_gitea_then_github(tmp_path: Path, files: list[str], expected: str) -> None:
    for rel in files:
        _write(tmp_path, rel)
    assert detect_ci(tmp_path, "gitea") == expected
