"""CI tripwire: forge operations go through the adapter, not `gh` (gh#742).

`fr.hostclient.client_for(repo_root)` is the seam that makes fr work on
GitLab and Gitea repos. `deliver`'s live-PR check went around it — the spec
prescribed `fr.gh`, the plan's test mocked `fr.gh`, and every review passed
it — so on a GitLab checkout `deliver` refused forever and no run could
close out. Nothing asked "does this work on every supported forge?".

This asks it mechanically. Under `packages/*/src`, none of these may appear
outside the files that ARE the GitHub backend:

- an import of `fr.gh` (`from fr import gh`, `from fr.gh import …`,
  `import fr.gh`);
- a `["gh", …]` argv literal.

There is no allowlist (spec 2026-10-06-forge-remainder §4.G, R7): the sites
that predated this tripwire — triage collect, the isolation lookups and the
fr-vk rate-limit guard — now all go through the adapter. A future exemption
means arguing for a `BACKEND` entry in a diff.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGES = Path(__file__).resolve().parents[2] / "packages"

# The GitHub backend itself: the `gh` wrappers, its adapter, and the factory
# that names every backend's error class.
BACKEND = {
    "fr/src/fr/gh.py",
    "fr/src/fr/real_ghclient.py",
    # `github-rest` (spec 2026-10-07-cloud-triage §A): the same GitHub backend
    # over `gh api` REST routes, chosen by `forge.api` inside `hostclient`.
    "fr/src/fr/real_ghrestclient.py",
    "fr/src/fr/hostclient.py",
}


def offences(source: str) -> list[str]:
    """Each direct `fr.gh` import or `["gh", …]` argv in *source*."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            if node.module == "fr.gh" or (
                node.module == "fr" and any(a.name == "gh" for a in node.names)
            ):
                found.append(f"line {node.lineno}: import of fr.gh")
        elif isinstance(node, ast.Import):
            if any(a.name == "fr.gh" for a in node.names):
                found.append(f"line {node.lineno}: import of fr.gh")
        elif isinstance(node, ast.List) and node.elts:
            first = node.elts[0]
            if isinstance(first, ast.Constant) and first.value == "gh" and len(node.elts) > 1:
                found.append(f'line {node.lineno}: ["gh", …] argv')
    return found


def _sources(root: Path = PACKAGES) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.glob("*/src/**/*.py"))
    }


def _bypasses(root: Path = PACKAGES) -> dict[str, list[str]]:
    """Every non-backend module under *root*'s `*/src` with a direct `gh` use."""
    return {
        rel: hits
        for rel, text in _sources(root).items()
        if rel not in BACKEND and (hits := offences(text))
    }


def test_the_scan_sees_every_form() -> None:
    assert offences("from fr import gh")
    assert offences("from fr import gh as _gh")
    assert offences("from fr.gh import GhError")
    assert offences("import fr.gh")
    assert offences('subprocess.run(["gh", "pr", "view", ref])')


def test_the_scan_ignores_prose_and_other_forges() -> None:
    assert not offences('"""reads the body through `fr.gh`"""')
    assert not offences("# from fr import gh")
    assert not offences("from fr import glab, tea")
    assert not offences('run(["glab", "mr", "view"])')
    assert not offences('TAG = {"github": "gh"}')
    assert not offences('x = ["gh"]')


def test_no_forge_call_bypasses_the_adapter() -> None:
    offenders = _bypasses()
    assert not offenders, (
        "direct `gh` use outside the GitHub backend — route it through "
        "`fr.hostclient.client_for(repo_root)` (add the operation to the "
        "`GhClient` protocol and implement it, or declare it unsupported, on "
        f"every backend): {offenders}"
    )


def test_a_planted_gh_import_outside_the_backend_is_reported(tmp_path: Path) -> None:
    """Test Plan 1, through the REAL scan (review p2-r3): with no allowlist, a
    non-backend module importing `fr.gh` is reported, and a backend file is not."""
    src = tmp_path / "fr" / "src" / "fr"
    src.mkdir(parents=True)
    (src / "plant.py").write_text("from fr import gh\n\ngh.viewer_login()\n", encoding="utf-8")
    (src / "gh.py").write_text(
        'import subprocess\nsubprocess.run(["gh", "api"])\n', encoding="utf-8"
    )
    assert _bypasses(tmp_path) == {"fr/src/fr/plant.py": ["line 1: import of fr.gh"]}
