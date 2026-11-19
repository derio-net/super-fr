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
from fr.acceptance.pages import UNKNOWN
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "forge"
HTML = (FIXTURES / "sso_login_page.html").read_text()
REDIRECT = "".join(
    ln + "\n"
    for ln in (FIXTURES / "sso_login_redirect.txt").read_text().splitlines()
    if not ln.startswith("#")
)
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


def _api_401() -> Any:
    done = subprocess.CompletedProcess(
        [], 0, stdout=HTML, stderr="HTTP/2 401 Unauthorized\ncontent-type: text/html\n"
    )
    return _tea.api_result(done)


def _api_302_fixture() -> Any:
    # The captured-shape header block is tea's stderr for a redirect.
    done = subprocess.CompletedProcess([], 0, stdout="", stderr=REDIRECT)
    return _tea.api_result(done)


def _glab_pr_for_branch() -> Any:
    def run(*_a: Any, **_k: Any) -> Any:
        return subprocess.CompletedProcess([], 0, stdout=HTML, stderr="")

    return RealGlabClient().pr_for_branch("b", cwd=Path.cwd(), run=run)


# site (module:function) -> callable that must raise naming the cause.
RAISING: dict[str, Callable[[], Any]] = {
    "tea:api_result": _api_200,
    "tea:api_result_401": _api_401,
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

# Sites whose contract is a fallback value, so a login page is that value. None today:
# issues_enabled and pages_visibility read a fallback for other failures but re-raise a
# login page (l-errors-r3), so the caller can name it.
FALLBACK: dict[str, tuple[Callable[[], Any], Any]] = {}

RAISING["real_glabclient:issues_enabled"] = lambda: RealGlabClient().issues_enabled("o/r")
RAISING["real_glabclient:pages_visibility"] = lambda: RealGlabClient().pages_visibility("o/r")


def test_pages_visibility_keeps_unknown_for_an_ordinary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_a: Any, **_k: Any) -> str:
        raise _glab.GlabError("glab: HTTP 500")

    monkeypatch.setattr(_glab, "_run_glab", fail)
    assert RealGlabClient().pages_visibility("o/r") == UNKNOWN


def test_a_login_page_on_the_pages_read_is_a_refusal_naming_the_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fr.acceptance.pages import pages_allowed

    class Client(RealGlabClient):
        def repo_visibility(self, repo: str) -> str:
            return "private"

    monkeypatch.setattr("fr._hosts.origin_slug", lambda _root: "o/r")
    allowed, reason = pages_allowed(Path.cwd(), Client())
    assert allowed is False
    assert "Pages visibility could not be read" in reason
    assert CAUSE in reason


SITES = {k for k in RAISING if "_401" not in k} | set(FALLBACK)


@pytest.mark.parametrize("site", sorted(RAISING))
def test_a_login_page_is_named(site: str) -> None:
    with pytest.raises((_tea.TeaError, _glab.GlabError)) as info:
        RAISING[site]()
    assert CAUSE in str(info.value)


@pytest.mark.parametrize("site", sorted(FALLBACK))
def test_a_fallback_site_keeps_its_value(site: str) -> None:
    call, expected = FALLBACK[site]
    assert call() == expected


def test_a_login_page_reaches_the_services_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.services.init import issues_enabled_for
    from fr.services.model import ServicesError

    monkeypatch.setattr("fr._hosts.origin_slug", lambda _root: "o/r")
    with pytest.raises(ServicesError) as info:
        issues_enabled_for(Path.cwd(), "gitlab", "git.example.com")
    assert CAUSE in str(info.value)


def test_a_302_fixture_header_block_names_the_proxy() -> None:
    with pytest.raises(_tea.TeaError) as info:
        _api_302_fixture()
    assert "auth.example.com/login" in str(info.value)
    assert "forward-auth" in str(info.value)


def test_the_read_error_says_which_read_failed() -> None:
    with pytest.raises(_tea.TeaError, match=r"^`tea issues` output: .*" + CAUSE):
        _tea.loads(HTML, "`tea issues` output")
    with pytest.raises(_glab.GlabError, match=r"^`glab x` output: .*" + CAUSE):
        _glab._loads(HTML, "`glab x` output")


# (module, function) -> why a raw json.loads is allowed there.
RAW_ALLOWED: dict[tuple[str, str], str] = {
    ("tea", "loads"): "the wrapper itself",
    ("glab", "_loads"): "the wrapper itself",
    ("tea", "api_result"): "reads the body and names HTML via not_json_reason",
    ("real_glabclient", "pr_for_branch"): "catches the decode error and names HTML itself",
}


def raw_json_loads(source: str, mod: str) -> set[tuple[str, str]]:
    """Every (module, function) holding a raw `json.loads` call; module level is `<module>`."""
    found: set[tuple[str, str]] = set()

    def walk(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                walk(child, child.name)
                continue
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "loads"
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == "json"
            ):
                found.add((mod, scope))
            walk(child, scope)

    walk(ast.parse(source), "<module>")
    return found


def test_no_raw_json_loads_outside_the_allowlist() -> None:
    found: set[tuple[str, str]] = set()
    for mod in MODULES:
        found |= raw_json_loads((SRC / f"{mod}.py").read_text(), mod)
    assert found == set(RAW_ALLOWED)


def test_the_walker_catches_a_new_raw_call_in_a_listed_function() -> None:
    src = (
        "import json\n"
        "def api_result(x):\n    json.loads(x)\n    json.loads(x)\n"
        "async def g(x):\n    json.loads(x)\n"
        "json.loads('1')\n"
    )
    got = raw_json_loads(src, "tea")
    assert got == {("tea", "api_result"), ("tea", "g"), ("tea", "<module>")}
    assert ("tea", "h") not in RAW_ALLOWED


def _wrapped_sites() -> set[str]:
    found: set[str] = set()
    for mod in MODULES:
        tree = ast.parse((SRC / f"{mod}.py").read_text())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef) or fn.name in ("loads", "_loads"):
                continue
            for node in ast.walk(fn):
                f = node.func if isinstance(node, ast.Call) else None
                if (
                    isinstance(f, ast.Attribute)
                    and f.attr in ("loads", "_loads")
                    and isinstance(f.value, ast.Name)
                    and f.value.id in ("_tea", "_glab")
                ) or (isinstance(f, ast.Name) and f.id in ("loads", "_loads")):
                    found.add(f"{mod}:{fn.name}")
    return found


def test_every_wrapped_json_read_is_in_the_list() -> None:
    raw_sites = {"tea:api_result", "real_glabclient:pr_for_branch"}  # raw reads, in RAW_ALLOWED
    assert _wrapped_sites() == SITES - raw_sites


# R6 (spec 2026-11-19-consumer-followups, gh#1554): RealTeaClient's six fail-soft
# sites re-raise a TeaError that names a login page, in either form api_result
# produces, and keep their empty answer for every other TeaError.
SSO_302 = "HTTP/2 302\nlocation: https://sso.example.com/login\ncontent-type: text/html\n"

# site -> (call, the site's fail-soft answer)
TEA_FAIL_SOFT: dict[str, tuple[Callable[[], Any], Any]] = {
    "list_linked_prs": (lambda: RealTeaClient().list_linked_prs("o/r", 1), []),
    "pr_status_by_url": (
        lambda: RealTeaClient().pr_status_by_url("https://git.example.com/o/r/pulls/1"),
        None,
    ),
    "default_branch": (lambda: RealTeaClient().default_branch(cwd=Path.cwd()), None),
    "pr_for_branch": (lambda: RealTeaClient().pr_for_branch("b", cwd=Path.cwd()), None),
    "file_exists": (lambda: RealTeaClient().file_exists("o/r", "a.md"), False),
    "list_dir": (lambda: RealTeaClient().list_dir("o/r", "docs"), []),
}


def _tea_api_answers(
    monkeypatch: pytest.MonkeyPatch, *, returncode: int = 0, stdout: str = "", stderr: str = ""
) -> None:
    done = subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)
    monkeypatch.setattr(_tea, "run_cli", lambda *_a, **_k: done)


LOGIN_ANSWERS = {
    "html-200": {"stdout": HTML, "stderr": "HTTP/2 200 OK\ncontent-type: text/html\n"},
    "redirect-302": {"stdout": "", "stderr": SSO_302},
}
OTHER_ANSWERS = {
    "json-404": {"stdout": '{"message":"not found"}', "stderr": "HTTP/2 404 Not Found\n"},
    "tea-exit-1": {"returncode": 1, "stderr": "tea: no login configured\n"},
}


@pytest.mark.parametrize("answer", sorted(LOGIN_ANSWERS))
@pytest.mark.parametrize("site", sorted(TEA_FAIL_SOFT))
def test_a_tea_fail_soft_site_re_raises_a_login_page(
    monkeypatch: pytest.MonkeyPatch, site: str, answer: str
) -> None:
    _tea_api_answers(monkeypatch, **LOGIN_ANSWERS[answer])  # type: ignore[arg-type]
    call, _ = TEA_FAIL_SOFT[site]
    with pytest.raises(_tea.TeaError) as info:
        call()
    assert _tea.names_login_page(info.value)
    assert ("forward-auth" in str(info.value)) and ("SSO" in str(info.value))


@pytest.mark.parametrize("answer", sorted(OTHER_ANSWERS))
@pytest.mark.parametrize("site", sorted(TEA_FAIL_SOFT))
def test_a_tea_fail_soft_site_keeps_its_answer_for_any_other_error(
    monkeypatch: pytest.MonkeyPatch, site: str, answer: str
) -> None:
    _tea_api_answers(monkeypatch, **OTHER_ANSWERS[answer])  # type: ignore[arg-type]
    call, expected = TEA_FAIL_SOFT[site]
    assert call() == expected


def _api_error(**answer: Any) -> _tea.TeaError:
    with pytest.raises(_tea.TeaError) as info:
        _tea.api_result(subprocess.CompletedProcess([], 0, **answer))
    return info.value


def test_names_login_page_knows_both_forms_and_nothing_else() -> None:
    assert _tea.names_login_page(_api_error(**LOGIN_ANSWERS["html-200"]))
    assert _tea.names_login_page(_api_error(**LOGIN_ANSWERS["redirect-302"]))
    assert _tea.names_login_page(_api_error(stdout="", stderr=REDIRECT))
    assert not _tea.names_login_page(_api_error(**OTHER_ANSWERS["json-404"]))
    assert not _tea.names_login_page(_tea.TeaError("tea exited with code 1"))
