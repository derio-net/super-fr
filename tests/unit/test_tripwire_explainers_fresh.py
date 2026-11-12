"""CI tripwire: the published pages are built from sources, never committed as HTML.

Before spec 2026-11-11-docs-currency, `docs/explainers/*.html` were committed
renderer output (or hand-authored), so a PR that edited the prose and not the
page left the published article stale. Now `.github/workflows/pages.yml` renders
every page from its Markdown source at deploy time (`scripts/build-site.py`), and
`fr docs check` is the currency gate. What stays checkable here: no rendered
explainer is tracked, and every configured page parses with `fr.docs`, so a page
cannot be published without the `covers` and `reviewed` front matter the gate reads.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from fr.docs import load

REPO_ROOT = Path(__file__).resolve().parents[2]


def _tracked() -> list[str]:
    done = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return [p for p in done.stdout.split("\0") if p]


def test_no_rendered_html_is_tracked_under_the_explainers() -> None:
    html = [p for p in _tracked() if p.startswith("docs/explainers/") and p.endswith(".html")]
    assert not html, (
        f"rendered pages are tracked: {html}. The site is built from the Markdown "
        "sources at deploy time; delete these (see .claude/rules/explainers-currency.md)."
    )


def test_the_explainer_html_is_ignored() -> None:
    done = subprocess.run(
        ["git", "check-ignore", "-q", "docs/explainers/index.html"], cwd=REPO_ROOT
    )
    assert done.returncode == 0, "docs/explainers/*.html must be git-ignored"


def test_every_configured_page_parses_with_fr_docs() -> None:
    config = load.load_config(REPO_ROOT)
    assert config is not None, ".fr/docs.yaml is missing"
    pages, errors = load.load_pages(REPO_ROOT, config, _tracked())
    assert not errors, [f"{e.path}: {e.message}" for e in errors]
    paths = {p.path for p in pages}
    assert {
        "docs/explainers/index.md",
        "docs/explainers/why-fr.md",
        "docs/explainers/01-fr-goal.md",
        "docs/explainers/fr-isolation.md",
        "docs/explainers/fr-wave-driver.md",
        "docs/explainers/fr-exit-gates.md",
    } <= paths
