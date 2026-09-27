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

`KNOWN` is a closed set of the sites that predate this tripwire, each with
the reason it stays for now. A file listed there that no longer offends
fails too, so the set only shrinks: delete its line.
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
    "fr/src/fr/hostclient.py",
}

KNOWN = {
    # Triage collection is GitHub-only by design today (its own `Forge`
    # protocol has one implementation, `GhForge`) — gh#742 item 1.
    "fr/src/fr/triage/collect.py": "triage is GitHub-only (gh#742)",
    # A second copy of the adapter's backend branching (gh/glab/tea), which
    # works on every forge but duplicates `client_for` — gh#742 item 1.
    "fr/src/fr/isolation/local.py": "own gh/glab/tea branching (gh#742)",
    # Classifies a `GhError` from the GitHub-issue bridge as a rate limit.
    "fr-vk/src/fr_vk/bridge_cli.py": "rate-limit classification of GhError",
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


def _sources() -> dict[str, str]:
    return {
        path.relative_to(PACKAGES).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(PACKAGES.glob("*/src/**/*.py"))
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
    offenders = {
        rel: hits
        for rel, text in _sources().items()
        if rel not in BACKEND and rel not in KNOWN and (hits := offences(text))
    }
    assert not offenders, (
        "direct `gh` use outside the GitHub backend — route it through "
        "`fr.hostclient.client_for(repo_root)` (add the operation to the "
        "`GhClient` protocol and implement it, or declare it unsupported, on "
        f"every backend): {offenders}"
    )


def test_every_known_site_still_offends() -> None:
    sources = _sources()
    stale = sorted(rel for rel in KNOWN if not offences(sources.get(rel, "")))
    assert not stale, f"no longer bypasses the adapter — remove it from KNOWN: {stale}"
