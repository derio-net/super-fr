"""Pins the shape of the combined Pages workflow (spec 2026-10-03 §A, §B, §D;
spec 2026-11-11-docs-currency §C: the site is built from sources, renderer pinned)."""

from __future__ import annotations

import importlib.util
import re
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
CI = REPO / ".github" / "workflows" / "ci.yml"
PIN = REPO / ".github" / "blog-craft.ref"
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"


def _doc() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def _steps() -> list[dict]:
    return _doc()["jobs"]["deploy"]["steps"]


def _runs() -> list[str]:
    return [s["run"] for s in _steps() if "run" in s]


def test_triggers_cover_every_input_of_the_site() -> None:
    on = ci_budget.workflow_on(_doc())
    assert on["push"]["branches"] == ["main"]
    assert set(on["push"]["paths"]) == {
        "docs/explainers/**",
        "docs/*.md",
        "docs/reference/**",
        "docs/acceptance/**",
        ".fr/docs.yaml",
        "scripts/build-site.py",
        "scripts/site/**",
        ".github/blog-craft.ref",
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


def test_site_is_built_from_sources_plus_report_in_one_artifact() -> None:
    builds = [r for r in _runs() if "scripts/build-site.py" in r]
    assert len(builds) == 1
    build = builds[0]
    assert "uv run --isolated --no-project --with markdown --with pyyaml python" in build
    assert "_site" in build
    assert '--ref "$GITHUB_SHA"' in build
    assert "--blog-craft .blog-craft" in build
    assert not any("cp -R docs/explainers" in r for r in _runs())
    uploads = [s for s in _steps() if "actions/upload-pages-artifact" in s.get("uses", "")]
    assert len(uploads) == 1
    assert uploads[0]["with"]["path"] == "_site"


def _pin_wiring(steps: list[dict]) -> None:
    pins = [i for i, s in enumerate(steps) if ".github/blog-craft.ref" in s.get("run", "")]
    assert len(pins) == 1
    pin = steps[pins[0]]
    assert pin.get("id")
    checks = [
        i
        for i, s in enumerate(steps)
        if s.get("uses", "").startswith("actions/checkout")
        and s.get("with", {}).get("repository") == "derio-net/blog-craft"
    ]
    assert len(checks) == 1 and checks[0] > pins[0]
    check = steps[checks[0]]
    assert check["uses"].startswith(CHECKOUT)
    assert check["with"]["ref"] == f"${{{{ steps.{pin['id']}.outputs.sha }}}}"
    assert check["with"]["path"] == ".blog-craft"


def test_blog_craft_is_checked_out_at_the_pinned_ref() -> None:
    _pin_wiring(_steps())
    own = [s for s in _steps() if s.get("uses", "").startswith("actions/checkout")]
    assert own[0]["uses"].startswith(CHECKOUT)


def test_the_pin_is_one_full_sha_and_no_workflow_names_it() -> None:
    sha = PIN.read_text().strip()
    assert re.fullmatch(r"[0-9a-f]{40}", sha), sha
    assert len(PIN.read_text().splitlines()) == 1
    for wf in (REPO / ".github" / "workflows").glob("*.y*ml"):
        text = wf.read_text()
        assert sha not in text, f"{wf.name} names the renderer pin itself"
        # a workflow checking blog-craft out must read the pin from the file
        if "derio-net/blog-craft" in text:
            assert ".github/blog-craft.ref" in text, wf.name


def test_ci_builds_the_site_on_every_pull_request() -> None:
    ci = yaml.safe_load(CI.read_text())
    job = ci["jobs"]["site-build"]
    assert "if" not in job
    _pin_wiring(job["steps"])
    runs = [s["run"] for s in job["steps"] if "run" in s]
    assert any("scripts/build-site.py" in r and "--blog-craft .blog-craft" in r for r in runs)
    assert "site-build" in ci["jobs"]["ci-ok"]["needs"]


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
    md = (REPO / "docs" / "explainers" / "index.md").read_text()
    assert "](./acceptance/)" in md


def test_readme_has_acceptance_badge() -> None:
    readme = (REPO / "README.md").read_text()
    assert "[![Acceptance]" in readme
    assert "](https://derio-net.github.io/super-fr/acceptance/)" in readme


# super-fr#924: the render may fail (the migration gate refuses over stale artifacts,
# by design), but that refusal must not take the explainers deploy down with it.


def _index(pred) -> int:
    hits = [i for i, s in enumerate(_steps()) if pred(s)]
    assert len(hits) == 1, hits
    return hits[0]


def _render() -> dict:
    return _steps()[_index(lambda s: "fr acceptance report" in s.get("run", ""))]


def _on_render_failure() -> list[tuple[int, dict]]:
    want = f"steps.{_render()['id']}.outcome == 'failure'"
    return [(i, s) for i, s in enumerate(_steps()) if str(s.get("if", "")).strip() == want]


def test_concurrency_never_cancels_a_running_deploy() -> None:
    assert _doc()["concurrency"] == {"group": "pages", "cancel-in-progress": False}


def test_a_failed_render_cannot_skip_the_deploy() -> None:
    render = _render()
    assert render.get("id")
    assert render.get("continue-on-error") is True
    for action in ("configure-pages", "upload-pages-artifact", "deploy-pages"):
        step = _steps()[_index(lambda s, a=action: f"actions/{a}" in s.get("uses", ""))]
        assert "if" not in step, action


def test_a_failed_render_publishes_a_placeholder_before_upload() -> None:
    upload = _index(lambda s: "actions/upload-pages-artifact" in s.get("uses", ""))
    render = _index(lambda s: "fr acceptance report" in s.get("run", ""))
    before = [s for i, s in _on_render_failure() if render < i < upload]
    assert len(before) == 1
    assert "_site/acceptance/index.html" in before[0]["run"]


def test_a_failed_render_still_fails_the_run_after_deploying() -> None:
    # In its own job: a failing step inside the `environment:` job would mark the
    # github-pages deployment itself failed, though the site went live.
    jobs = _doc()["jobs"]
    outcome = f"${{{{ steps.{_render()['id']}.outcome }}}}"
    (key,) = [k for k, v in jobs["deploy"].get("outputs", {}).items() if v == outcome]
    deploy = _index(lambda s: "actions/deploy-pages" in s.get("uses", ""))
    assert deploy == len(_steps()) - 1
    (gate,) = [j for name, j in jobs.items() if name != "deploy"]
    assert gate["needs"] == "deploy"
    assert "environment" not in gate
    assert str(gate["if"]).strip() == f"needs.deploy.outputs.{key} == 'failure'"
    assert any("exit 1" in s.get("run", "") for s in gate["steps"])


def test_the_placeholder_says_the_report_was_not_rendered(tmp_path: Path) -> None:
    import subprocess

    upload = _index(lambda s: "actions/upload-pages-artifact" in s.get("uses", ""))
    (step,) = [s for i, s in _on_render_failure() if i < upload]
    env = {
        "PATH": "/usr/bin:/bin",
        "GITHUB_SHA": "0123456789abcdef0123456789abcdef01234567",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_REPOSITORY": "derio-net/super-fr",
        "GITHUB_RUN_ID": "42",
    }
    subprocess.run(
        ["bash", "-eo", "pipefail", "-c", step["run"]], cwd=tmp_path, env=env, check=True
    )
    page = (tmp_path / "_site" / "acceptance" / "index.html").read_text()
    assert "not rendered" in page
    assert "0123456789ab" in page
    assert "https://github.com/derio-net/super-fr/actions/runs/42" in page
    assert (
        "https://github.com/derio-net/super-fr/blob/"
        "0123456789abcdef0123456789abcdef01234567/docs/acceptance/report_linked.md" in page
    )
