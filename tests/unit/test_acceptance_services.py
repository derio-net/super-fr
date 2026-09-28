"""#774 phase 3 — `fr acceptance` follows the declared `ci` service (spec
2026-09-28-fr-profiles-services R4, §3.B, §3.E)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.acceptance.ci import ci_active
from fr.acceptance.scaffold import init
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

runner = CliRunner()
PROFILES = "profiles:\n  dev:\n    purpose: x\n"
GITHUB = "https://github.com/derio-net/demo.git"
GITLAB = "https://gitlab.com/example-org/demo.git"
GITHUB_WF = ".github/workflows/acceptance-report.yml"


def _repo(tmp_path: Path, services: str, remote: str = GITHUB) -> Path:
    root = tmp_path / "demo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=root, check=True)
    (root / ".devcontainer").mkdir()
    (root / ".devcontainer" / "fr-profiles.yaml").write_text(
        PROFILES + "schema_version: 2\n" + services
    )
    return root


def _invoke(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", *args])


class TestCiNone:
    def test_init_writes_no_pipeline_and_names_fr_services(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _repo(tmp_path, "ci: {type: none}\n")
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / ".github" / "workflows" / "ci.yml").write_text("on: push\n")
        result = _invoke(root, monkeypatch, "init")
        assert result.exit_code == 0, result.output
        assert not (root / GITHUB_WF).exists()
        assert "fr services" in result.output

    def test_with_ci_is_refused_naming_the_declaration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _repo(tmp_path, "ci: {type: none}\n")
        result = _invoke(root, monkeypatch, "init", "--with-ci")
        assert result.exit_code == 2, result.output
        assert "ci: {type: none}" in result.output
        assert not (root / "docs" / "acceptance").exists()

    def test_ci_status_refused_on_set_status_and_add(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = make_repo(tmp_path, row(id="target", status="skipped"), ci=True)
        (root / ".devcontainer").mkdir()
        (root / ".devcontainer" / "fr-profiles.yaml").write_text(
            PROFILES + "schema_version: 2\nci: {type: none}\n"
        )
        result = _invoke(
            root, monkeypatch, "set-status", "--id", "target", "--status", "ci", "--notes", "n"
        )
        assert result.exit_code != 0
        assert "ci: {type: none}" in result.output
        result = _invoke(
            root, monkeypatch, "add", "--id", "n", "--capability", "C",
            "--acceptance", "A", "--status", "ci",
        )  # fmt: skip
        assert result.exit_code != 0
        assert "ci: {type: none}" in result.output


class TestCiTypeDrivesScaffold:
    def test_gitlab_ci_on_a_github_forge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _repo(tmp_path, "ci: {type: gitlab-ci, host: gitlab.example.com}\n")
        result = _invoke(root, monkeypatch, "init")
        assert result.exit_code == 0, result.output
        assert (root / ".gitlab-ci.yml").is_file()
        assert not (root / GITHUB_WF).exists()
        assert ci_active(root)

    def test_github_actions_scaffolds_the_workflow(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _repo(tmp_path, "ci: {type: github-actions}\n")
        result = _invoke(root, monkeypatch, "init")
        assert result.exit_code == 0, result.output
        assert (root / GITHUB_WF).is_file()
        assert GITHUB_WF in (root / "docs/acceptance/matrix.yaml").read_text()

    def test_ci_status_allowed_when_declared_without_any_config_file(self, tmp_path: Path) -> None:
        root = _repo(tmp_path, "ci: {type: github-actions}\n")
        assert ci_active(root)

    def test_no_file_defers_to_the_raw_probe(self, tmp_path: Path) -> None:
        root = make_repo(tmp_path, "", ci=False)
        assert not ci_active(root)
        root2 = make_repo(tmp_path, "", name="own2", ci=True)
        assert ci_active(root2)


class TestDebtStepOnlyOnTheTrackersPlatform:
    def test_kept_when_tracking_is_the_ci_platform(self, tmp_path: Path) -> None:
        root = _repo(tmp_path, "ci: {type: github-actions}\n")
        init(root, "derio-net", "demo", "github", ci_type="github-actions", tracking_type="github")
        text = (root / GITHUB_WF).read_text()
        assert "Acceptance debt" in text
        assert "Acceptance debt" in (root / ".claude/rules/acceptance-matrix.md").read_text()

    @pytest.mark.parametrize(
        "ci_type, tracking, path",
        [
            ("github-actions", "none", GITHUB_WF),
            ("gitlab-ci", "github", ".gitlab-ci.yml"),
            ("gitea-actions", "github", ".gitea/workflows/acceptance-report.yml"),
            ("github-actions", "gitlab", GITHUB_WF),
        ],
    )
    def test_omitted_elsewhere(
        self, tmp_path: Path, ci_type: str, tracking: str, path: str
    ) -> None:
        root = _repo(tmp_path, "")
        outcome = init(root, "derio-net", "demo", "github", ci_type=ci_type, tracking_type=tracking)
        assert "Acceptance debt" not in (root / path).read_text()
        assert "Acceptance debt" not in (root / ".claude/rules/acceptance-matrix.md").read_text()
        assert any(n.startswith("no debt  the weekly") for n in outcome.notices)
        assert "on:" in (root / path).read_text() or "stages:" in (root / path).read_text()

    @pytest.mark.parametrize(
        "ci_type, tracking",
        [("gitlab-ci", "gitlab"), ("gitea-actions", "gitea")],
    )
    def test_kept_for_each_own_platform(self, tmp_path: Path, ci_type: str, tracking: str) -> None:
        root = _repo(tmp_path, "")
        init(root, "o", "demo", "github", ci_type=ci_type, tracking_type=tracking)
        paths = {
            "gitlab-ci": ".gitlab-ci.yml",
            "gitea-actions": ".gitea/workflows/acceptance-report.yml",
        }
        assert "Acceptance debt" in (root / paths[ci_type]).read_text()

    def test_cli_omits_it_under_tracking_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _repo(tmp_path, "ci: {type: github-actions}\ntracking: {type: none}\n")
        result = _invoke(root, monkeypatch, "init")
        assert result.exit_code == 0, result.output
        assert "Acceptance debt" not in (root / GITHUB_WF).read_text()
        assert "debt" in result.output


GOLDEN = Path(__file__).parent.parent / "fixtures" / "acceptance_scaffold"
CI_TYPES = ("github-actions", "gitea-actions", "gitlab-ci")


class TestGoldenRenders:
    """Captured from origin/main's scaffold.py before the debt split (r4)."""

    @pytest.mark.parametrize("ci_type", CI_TYPES)
    def test_debt_on_is_byte_identical_to_the_pre_split_template(self, ci_type: str) -> None:
        from fr.acceptance.scaffold import render_workflow

        assert render_workflow(ci_type, debt=True) == (GOLDEN / f"{ci_type}.golden").read_text()

    @pytest.mark.parametrize("debt", [True, False])
    @pytest.mark.parametrize("ci_type", CI_TYPES)
    def test_no_token_survives_a_render(self, ci_type: str, debt: bool) -> None:
        from fr.acceptance.scaffold import render_workflow

        assert "@@" not in render_workflow(ci_type, debt=debt)

    def test_debt_off_drops_the_issues_permission(self) -> None:
        from fr.acceptance.scaffold import render_workflow

        assert "issues: write" in render_workflow("github-actions", debt=True)
        off = render_workflow("github-actions", debt=False)
        assert "issues: write" not in off
        assert "permissions:\n  contents: read\n\njobs:" in off

    def test_rule_bullets_are_byte_identical_when_debt_is_kept(self, tmp_path: Path) -> None:
        gh = tmp_path / "gh"
        gh.mkdir()
        init(gh, "o", "r", "github", ci_type="github-actions", tracking_type="github")
        rule = (gh / ".claude/rules/acceptance-matrix.md").read_text()
        assert (GOLDEN / "bullet-github.golden").read_text() in rule
        gl = tmp_path / "gl"
        gl.mkdir()
        init(gl, "o", "r", "gitlab", ci_type="gitlab-ci", tracking_type="gitlab")
        rule = (gl / ".claude/rules/acceptance-matrix.md").read_text()
        generic = (GOLDEN / "bullet-generic.golden").read_text().format(path=".gitlab-ci.yml")
        assert generic in rule

    def test_the_omitted_notice_is_exact(self, tmp_path: Path) -> None:
        root = tmp_path / "r"
        root.mkdir()
        outcome = init(root, "o", "r", "github", ci_type="github-actions", tracking_type="none")
        assert outcome.notices == [
            'no debt  the weekly "Acceptance debt" issue step is omitted from '
            ".github/workflows/acceptance-report.yml — tracking is 'none', not the "
            "github-actions platform's own (github); see `fr services`"
        ]


class TestMalformedCiDeclarationRefuses:
    """r1 — a malformed `ci:` never falls through to the raw probe."""

    @pytest.mark.parametrize(
        "block", ["ci: none\n", "ci: {type: bogus}\n", "ci: {type: jenkins}\n"]
    )
    def test_set_status_ci_refused_and_matrix_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, block: str
    ) -> None:
        root = make_repo(tmp_path, row(id="target", status="skipped"), ci=True)
        (root / ".devcontainer").mkdir()
        (root / ".devcontainer" / "fr-profiles.yaml").write_text(
            PROFILES + "schema_version: 2\n" + block
        )
        matrix = root / "docs" / "acceptance" / "matrix.yaml"
        before = matrix.read_text()
        result = _invoke(
            root, monkeypatch, "set-status", "--id", "target", "--status", "ci", "--notes", "n"
        )
        assert result.exit_code != 0, result.output
        assert "fr-profiles.yaml" in result.output
        assert matrix.read_text() == before

    def test_add_ci_refused(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        root = make_repo(tmp_path, "", ci=True)
        (root / ".devcontainer").mkdir()
        (root / ".devcontainer" / "fr-profiles.yaml").write_text(
            PROFILES + "schema_version: 2\nci: none\n"
        )
        result = _invoke(
            root, monkeypatch, "add", "--id", "n", "--capability", "C",
            "--acceptance", "A", "--status", "ci",
        )  # fmt: skip
        assert result.exit_code != 0
        assert "fr-profiles.yaml" in result.output


class TestFrOnlyScaffoldIsNotCi:
    """r3 — v1 file whose only CI file is fr's own scaffold."""

    def _v1(self, tmp_path: Path) -> Path:
        root = tmp_path / "demo"
        root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "remote", "add", "origin", GITHUB], cwd=root, check=True)
        (root / ".devcontainer").mkdir()
        (root / ".devcontainer" / "fr-profiles.yaml").write_text(PROFILES + "backend: github\n")
        wf = root / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "acceptance-report.yml").write_text("on: push\n")
        return root

    def test_reason_says_only_the_scaffold_was_found(self, tmp_path: Path) -> None:
        from fr.acceptance.ci import ci_reason

        reason = ci_reason(self._v1(tmp_path))
        assert reason is not None
        assert "acceptance scaffold" in reason
        assert "declare `ci:`" in reason
        assert "no CI config" not in reason

    def test_set_status_ci_refusal_and_init_notice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = self._v1(tmp_path)
        result = _invoke(root, monkeypatch, "init")
        assert result.exit_code == 0, result.output
        assert "acceptance scaffold" in result.output
        assert "no CI config" not in result.output
