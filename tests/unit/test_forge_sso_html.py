"""R14: every tea / glab JSON read names a forward-auth login page (spec
2026-11-18-consumer-delivery). The HTML is a fixture shaped like a captured
forward-auth login page, hosts redacted."""

from __future__ import annotations

import ast
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fr import glab as _glab
from fr import tea as _tea
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "forge"
HTML = (FIXTURES / "sso_login_page.html").read_text()
SRC = Path(_tea.__file__).parent
MODULES = ("tea", "glab", "real_teaclient", "real_glabclient")
CAUSE = "SSO or forward-auth login page"


@pytest.fixture(autouse=True)
def _html_everywhere(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    d = tmp_path / "glab-config"
    d.mkdir()
    (d / "config.yml").write_text("hosts:\n    git.example.com: {}\n")
    monkeypatch.setenv("GLAB_CONFIG_DIR", str(d))
    monkeypatch.setattr(_tea, "_run_tea", lambda *a, **k: HTML)
    monkeypatch.setattr(_glab, "_run_glab", lambda *a, **k: HTML)


def _api_200(*_a: Any, **_k: Any) -> Any:
    done = subprocess.CompletedProcess(
        [], 0, stdout=HTML, stderr="HTTP/2 200 OK\ncontent-type: text/html\n"
    )
    return _tea.api_result(done)


def _glab_pr_for_branch() -> Any:
    def run(*_a: Any, **_k: Any) -> Any:
        return subprocess.CompletedProcess([], 0, stdout=HTML, stderr="")

    return RealGlabClient().pr_for_branch("b", cwd=Path.cwd(), run=run)


# site (module:function) -> callable that must raise naming the cause.
RAISING: dict[str, Callable[[], Any]] = {
    "tea:api_result": _api_200,
    "tea:view_issue": lambda: _tea.view_issue("o/r", 1),
    "glab:view_issue": lambda: _glab.view_issue("o/r", 1),
    "real_teaclient:pr_body": lambda: RealTeaClient().pr_body("1", cwd=Path.cwd()),
    "real_glabclient:list_linked_prs": lambda: RealGlabClient().list_linked_prs("o/r", 1),
    "real_glabclient:pr_status_by_url": lambda: RealGlabClient().pr_status_by_url(
        "https://git.example.com/o/r/-/merge_requests/1"
    ),
    "real_glabclient:pr_body": lambda: RealGlabClient().pr_body("1", cwd=Path.cwd()),
    "real_glabclient:authenticated_login": lambda: RealGlabClient().authenticated_login(),
    "real_glabclient:list_open_issues_with_body": lambda: (
        RealGlabClient().list_open_issues_with_body("o/r", search="", limit=10)
    ),
    "real_glabclient:open_pr_in_repo": lambda: RealGlabClient().open_pr_in_repo("o/r", "b"),
    "real_glabclient:pr_for_branch": _glab_pr_for_branch,
    "real_glabclient:repo_visibility": lambda: RealGlabClient().repo_visibility("o/r"),
    "real_glabclient:list_dir": lambda: RealGlabClient().list_dir("o/r", "docs"),
    "real_glabclient:read_file": lambda: RealGlabClient().read_file("o/r", "a.md"),
}

# Sites whose contract is a fallback value, so a login page is that value.
FALLBACK: dict[str, tuple[Callable[[], Any], Any]] = {
    "real_glabclient:issues_enabled": (lambda: RealGlabClient().issues_enabled("o/r"), None),
}

SITES = set(RAISING) | set(FALLBACK) | {"real_glabclient:pages_visibility"}


@pytest.mark.parametrize("site", sorted(RAISING))
def test_a_login_page_is_named(site: str) -> None:
    with pytest.raises((_tea.TeaError, _glab.GlabError)) as info:
        RAISING[site]()
    assert CAUSE in str(info.value)


@pytest.mark.parametrize("site", sorted(FALLBACK))
def test_a_fallback_site_keeps_its_value(site: str) -> None:
    call, expected = FALLBACK[site]
    assert call() == expected


def _loads_sites() -> set[str]:
    found: set[str] = set()
    for mod in MODULES:
        tree = ast.parse((SRC / f"{mod}.py").read_text())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            for node in ast.walk(fn):
                if not isinstance(node, ast.Call) or fn.name in ("loads", "_loads"):
                    continue
                f = node.func
                attr = (
                    isinstance(f, ast.Attribute)
                    and f.attr in ("loads", "_loads")
                    and isinstance(f.value, ast.Name)
                    and f.value.id in ("json", "_tea", "_glab")
                )
                bare = isinstance(f, ast.Name) and f.id in ("loads", "_loads")
                if attr or bare:
                    found.add(f"{mod}:{fn.name}")
    return found


def test_every_json_read_is_in_the_list() -> None:
    assert _loads_sites() == SITES
