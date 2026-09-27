"""CI tripwire: every remote `uses:` in `.github/workflows/` is pinned by
full commit SHA with a `# vX.Y.Z` comment (spec 2026-09-27-ci-hardening
§3.C, super-fr#707).

A tag is a movable pointer — whoever controls the action's repo can move it
to new code, and the next run executes it with each workflow's token.
Pinning by SHA makes the executed code immutable; the trailing version
comment is what Dependabot (and a human diffing a bump) reads to know what
actually runs.

The scan is TEXT-based (`check_pins`), because a YAML comment does not
survive `yaml.safe_load` — but a regex scan can be evaded by an unusual
formatting of the `uses:` line (flow-style, odd quoting), so a second check
(`scanned_uses` vs `parsed_uses`) asserts the two views agree per file.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
DEPENDABOT_PATH = REPO_ROOT / ".github" / "dependabot.yml"

# Matches a `uses:` key at the start of a line (job-level, or a step's
# `- uses:`) — deliberately anchored so a flow-style `{uses: ...}` mapping,
# which never has `uses:` right after the dash, does NOT match. That's the
# gap `scanned_uses` vs `parsed_uses` exists to catch.
_USES_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<rest>.+?)\s*$")

# Exactly a full 40-hex commit SHA, per spec §3.C.
_SHA_PIN = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")

# A trailing `# vX.Y.Z` comment — exactly three dot-separated components.
_VERSION_COMMENT = re.compile(r"#\s*v\d+\.\d+\.\d+\b")


def _extract_ref(rest: str) -> str:
    """Pull the ref value out of a `uses:` line's remainder, stripping an
    optional quote and any trailing inline comment."""
    if rest and rest[0] in ("'", '"'):
        quote = rest[0]
        end = rest.find(quote, 1)
        if end != -1:
            return rest[1:end]
        return rest[1:]
    match = re.match(r"[^\s#]+", rest)
    return match.group(0) if match else rest


def scanned_uses(path: Path) -> list[str]:
    """Every `uses:` ref found by the text regex scan, in file order."""
    refs: list[str] = []
    for line in path.read_text().splitlines():
        match = _USES_LINE.match(line)
        if match:
            refs.append(_extract_ref(match.group("rest")))
    return refs


def parsed_uses(path: Path) -> list[str]:
    """Every `uses:` ref found by parsing the file as YAML — both the
    job-level shape (a reusable-workflow call, no `steps:`) and the
    step-level shape."""
    doc = yaml.safe_load(path.read_text()) or {}
    refs: list[str] = []
    for job in (doc.get("jobs") or {}).values():
        if "uses" in job:
            refs.append(job["uses"])
        for step in job.get("steps") or []:
            if "uses" in step:
                refs.append(step["uses"])
    return refs


def check_pins(workflows_dir: Path) -> list[str]:
    """Violations as `<file>:<line>: <ref> — <reason>` strings. Empty means
    the tripwire passes."""
    violations: list[str] = []
    for path in sorted(workflows_dir.glob("*.yml")):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            match = _USES_LINE.match(line)
            if not match:
                continue
            ref = _extract_ref(match.group("rest"))
            if ref.startswith("./"):
                continue
            if _SHA_PIN.match(ref) and _VERSION_COMMENT.search(line):
                continue
            violations.append(
                f"{path.name}:{lineno}: {ref} — pin by full commit SHA with the "
                "version tag in a trailing comment, e.g. "
                "`actions/checkout@<sha> # v4.4.0`"
            )
    return violations


# ── real repo ─────────────────────────────────────────────────────────────


def test_the_real_repos_workflows_have_no_violations() -> None:
    assert check_pins(WORKFLOWS_DIR) == []


def test_scanned_and_parsed_uses_agree_for_every_real_workflow_file() -> None:
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        assert sorted(scanned_uses(path)) == sorted(parsed_uses(path)), path.name


# ── negative fixtures (tmp dir) ────────────────────────────────────────────


def _write(tmp_path: Path, uses_line: str) -> Path:
    workflow = tmp_path / "x.yml"
    workflow.write_text(
        "name: X\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n"
        f"      {uses_line}\n"
    )
    return workflow


def test_a_tag_is_a_violation(tmp_path: Path) -> None:
    workflow = _write(tmp_path, "- uses: actions/checkout@v4")
    violations = check_pins(tmp_path)
    assert len(violations) == 1
    assert violations[0].startswith(f"{workflow.name}:7:")
    assert "actions/checkout@v4" in violations[0]


def test_a_short_sha_is_a_violation(tmp_path: Path) -> None:
    workflow = _write(tmp_path, "- uses: actions/checkout@a1b2c3d # v4.4.0")
    violations = check_pins(tmp_path)
    assert len(violations) == 1
    assert violations[0].startswith(f"{workflow.name}:7:")


def test_a_full_sha_with_no_comment_is_a_violation(tmp_path: Path) -> None:
    workflow = _write(tmp_path, "- uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262")
    violations = check_pins(tmp_path)
    assert len(violations) == 1
    assert violations[0].startswith(f"{workflow.name}:7:")


def test_a_two_component_version_comment_is_a_violation(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path,
        "- uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4",
    )
    violations = check_pins(tmp_path)
    assert len(violations) == 1
    assert violations[0].startswith(f"{workflow.name}:7:")


def test_a_docker_ref_is_a_violation(tmp_path: Path) -> None:
    workflow = _write(tmp_path, "- uses: docker://alpine:3.18")
    violations = check_pins(tmp_path)
    assert len(violations) == 1
    assert violations[0].startswith(f"{workflow.name}:7:")


def test_a_local_job_level_ref_passes(tmp_path: Path) -> None:
    workflow = tmp_path / "x.yml"
    workflow.write_text(
        "name: X\non: [push]\njobs:\n"
        "  reusable:\n"
        "    uses: ./.github/workflows/fr-spec-status.yml\n"
    )
    assert check_pins(tmp_path) == []


def test_flow_style_uses_evades_the_regex_scan_but_the_multiset_check_catches_it(
    tmp_path: Path,
) -> None:
    workflow = tmp_path / "x.yml"
    workflow.write_text(
        "name: X\non: [push]\njobs:\n"
        "  build:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - {uses: a/b@v1}\n"
    )
    # The regex scan misses the flow-style mapping entirely...
    assert scanned_uses(workflow) == []
    # ...which is exactly why the multiset equality is a separate assertion
    # over the real files, not a redundant one: it would fail here.
    assert sorted(scanned_uses(workflow)) != sorted(parsed_uses(workflow))


# ── dependabot.yml (spec §3.B) ──────────────────────────────────────────────


def test_dependabot_yml_matches_spec_shape() -> None:
    doc = yaml.safe_load(DEPENDABOT_PATH.read_text())
    assert doc["version"] == 2
    updates = doc["updates"]
    assert len(updates) == 1
    update = updates[0]
    assert update["package-ecosystem"] == "github-actions"
    assert update["directory"] == "/"
    assert update["schedule"]["interval"] == "weekly"
    groups = update["groups"]
    assert len(groups) == 1
    (group,) = groups.values()
    assert group["patterns"] == ["*"]
