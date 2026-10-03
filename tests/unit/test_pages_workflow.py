"""Pins the shape of the combined Pages workflow (spec 2026-10-03 §A, §B, §D)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ci_budget", REPO / "scripts" / "ci_budget.py")
assert _spec is not None and _spec.loader is not None
ci_budget = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("ci_budget", ci_budget)
_spec.loader.exec_module(ci_budget)

WORKFLOW = REPO / ".github" / "workflows" / "pages.yml"


def _doc() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def _steps() -> list[dict]:
    return _doc()["jobs"]["deploy"]["steps"]


def _runs() -> list[str]:
    return [s["run"] for s in _steps() if "run" in s]


def test_triggers_cover_explainers_and_acceptance() -> None:
    on = ci_budget.workflow_on(_doc())
    assert on["push"]["branches"] == ["main"]
    assert set(on["push"]["paths"]) == {
        "docs/explainers/**",
        "docs/acceptance/**",
        "packages/fr/src/fr/acceptance/**",
    }
    assert "workflow_dispatch" in on


def test_render_step_is_sha_pinned_into_the_site() -> None:
    runs = [r for r in _runs() if "fr acceptance report" in r]
    assert len(runs) == 1
    run = runs[0]
    assert "--link-mode github" in run
    assert '--ref "$GITHUB_SHA"' in run or "${{ github.sha }}" in run
    assert "--out _site/acceptance/index.html" in run


def test_site_is_explainers_plus_report_in_one_artifact() -> None:
    assert any("docs/explainers/." in r and "_site" in r for r in _runs())
    uploads = [s for s in _steps() if "actions/upload-pages-artifact" in s.get("uses", "")]
    assert len(uploads) == 1
    assert uploads[0]["with"]["path"] == "_site"


def test_report_is_never_gated_on_acceptance_check() -> None:
    assert not any("fr acceptance check" in r for r in _runs())
    assert not any("fr acceptance check" in str(s.get("if", "")) for s in _steps())


def test_render_does_not_skip_migration() -> None:
    # Any env level (workflow, job, step) would reach the render, so pin the whole file.
    assert "FR_SKIP_MIGRATION" not in WORKFLOW.read_text()


def test_fr_is_installed_like_acceptance_report_installs_it() -> None:
    def setup_uv(steps: list[dict]) -> list[str]:
        return [s["uses"] for s in steps if "astral-sh/setup-uv" in s.get("uses", "")]

    acceptance = yaml.safe_load(
        (REPO / ".github" / "workflows" / "acceptance-report.yml").read_text()
    )
    want = setup_uv(acceptance["jobs"]["matrix"]["steps"])
    assert len(want) == 1
    assert setup_uv(_steps()) == want
    assert "uv tool install ./packages/fr" in [r.strip() for r in _runs()]


def test_workflow_name_unchanged() -> None:
    assert _doc()["name"] == "Deploy explainers to Pages"


def test_index_links_to_acceptance_report() -> None:
    html = (REPO / "docs" / "explainers" / "index.html").read_text()
    assert 'href="./acceptance/"' in html


def test_readme_has_acceptance_badge() -> None:
    readme = (REPO / "README.md").read_text()
    assert "[![Acceptance]" in readme
    assert "](https://derio-net.github.io/super-fr/acceptance/)" in readme
