"""CI tripwire: every remote `uses:` in `.github/workflows/` is pinned by
full commit SHA with a `# vX.Y.Z` comment (spec 2026-09-27-ci-hardening
§3.C, super-fr#707).

A tag is a movable pointer — whoever controls the action's repo can move it
to new code, and the next run executes it with each workflow's token.
Pinning by SHA makes the executed code immutable; the trailing version
comment is what Dependabot (and a human diffing a bump) reads to know what
actually runs.

The check walks the COMPOSED YAML node graph (`yaml.compose`), not the text:
only `jobs.<id>.uses` and `jobs.<id>.steps[].uses` — the two places GitHub
reads a `uses` — are found, whatever their formatting (flow style, quoted
key, `uses :`), and a `uses:` line inside a `run: |` block is never mistaken
for one. A YAML comment does not survive parsing, so the version comment is
read from the source text AFTER the value node's end mark, on the line where
the value ends. One code path serves the real repo and every fixture.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
DEPENDABOT_PATH = REPO_ROOT / ".github" / "dependabot.yml"

# Exactly a full 40-hex commit SHA, per spec §3.C.
_SHA_PIN = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")

# A trailing `# vX.Y.Z` comment — exactly three dot-separated components, and
# nothing glued on (`v1.2.3.4`, `v1.2.3-rc1` are refused).
_VERSION_COMMENT = re.compile(r"#\s*v\d+\.\d+\.\d+(?=\s|$)")


def _workflow_files(workflows_dir: Path) -> list[Path]:
    """GitHub runs both extensions."""
    return sorted([*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")])


def _get(node: yaml.Node, key: str) -> yaml.Node | None:
    if not isinstance(node, yaml.MappingNode):
        return None
    for k, v in node.value:
        if isinstance(k, yaml.ScalarNode) and k.value == key:
            return v
    return None


def uses_nodes(path: Path) -> list[yaml.ScalarNode]:
    """Every `uses` value node — job-level (a reusable-workflow call, no
    `steps:`) and step-level — in file order."""
    root = yaml.compose(path.read_text())
    jobs = _get(root, "jobs") if root is not None else None
    found: list[yaml.ScalarNode] = []
    if not isinstance(jobs, yaml.MappingNode):
        return found
    for _, job in jobs.value:
        uses = _get(job, "uses")
        if isinstance(uses, yaml.ScalarNode):
            found.append(uses)
        steps = _get(job, "steps")
        if isinstance(steps, yaml.SequenceNode):
            for step in steps.value:
                uses = _get(step, "uses")
                if isinstance(uses, yaml.ScalarNode):
                    found.append(uses)
    return found


def parsed_uses(path: Path) -> list[str]:
    """The same refs by plain `yaml.safe_load` — an independent view that
    `uses_nodes` must agree with, so the node walk cannot silently miss one."""
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
    for path in _workflow_files(workflows_dir):
        lines = path.read_text().splitlines()
        for node in uses_nodes(path):
            ref = node.value
            if ref.startswith("./"):
                continue
            end = node.end_mark
            after_value = lines[end.line][end.column :] if end.line < len(lines) else ""
            if _SHA_PIN.match(ref) and _VERSION_COMMENT.search(after_value):
                continue
            violations.append(
                f"{path.name}:{node.start_mark.line + 1}: {ref} — pin by full commit SHA "
                "with the version tag in a trailing comment, e.g. "
                "`actions/checkout@<sha> # v4.4.0`"
            )
    return violations


# ── real repo ─────────────────────────────────────────────────────────────


def test_the_real_repos_workflows_have_no_violations() -> None:
    assert check_pins(WORKFLOWS_DIR) == []


def test_the_node_walk_and_safe_load_agree_for_every_real_workflow_file() -> None:
    files = _workflow_files(WORKFLOWS_DIR)
    assert files
    for path in files:
        assert [n.value for n in uses_nodes(path)] == parsed_uses(path), path.name


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


def _write_steps(tmp_path: Path, steps: str, name: str = "x.yml") -> Path:
    workflow = tmp_path / name
    workflow.write_text(
        "name: X\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n" + steps
    )
    return workflow


_SHA = "11d5960a326750d5838078e36cf38b85af677262"


def test_a_yaml_extension_workflow_is_checked_too(tmp_path: Path) -> None:
    workflow = _write_steps(tmp_path, "      - uses: actions/checkout@v4\n", name="x.yaml")
    violations = check_pins(tmp_path)
    assert len(violations) == 1
    assert violations[0].startswith(f"{workflow.name}:7:")


def test_a_four_component_version_comment_is_a_violation(tmp_path: Path) -> None:
    _write(tmp_path, f"- uses: actions/checkout@{_SHA} # v4.4.0.1")
    assert len(check_pins(tmp_path)) == 1


def test_a_prerelease_version_comment_is_a_violation(tmp_path: Path) -> None:
    _write(tmp_path, f"- uses: actions/checkout@{_SHA} # v4.4.0-rc1")
    assert len(check_pins(tmp_path)) == 1


def test_flow_style_uses_is_a_violation(tmp_path: Path) -> None:
    _write(tmp_path, "- {uses: a/b@v1}")
    assert len(check_pins(tmp_path)) == 1


def test_a_quoted_uses_key_is_a_violation(tmp_path: Path) -> None:
    _write(tmp_path, '- "uses": a/b@v1')
    assert len(check_pins(tmp_path)) == 1


def test_a_space_before_the_colon_is_a_violation(tmp_path: Path) -> None:
    _write(tmp_path, "- uses : a/b@v1")
    assert len(check_pins(tmp_path)) == 1


def test_a_uses_line_inside_a_run_block_is_not_a_uses(tmp_path: Path) -> None:
    _write_steps(
        tmp_path,
        f"      - uses: actions/checkout@{_SHA} # v4.4.0\n"
        "      - run: |\n"
        "          uses: not-an-action\n",
    )
    assert check_pins(tmp_path) == []


def test_a_commented_decoy_in_a_run_block_does_not_vouch_for_an_uncommented_pin(
    tmp_path: Path,
) -> None:
    _write_steps(
        tmp_path,
        f"      - run: |\n          uses: a/b@{_SHA} # v1.2.3\n      - {{uses: a/b@{_SHA}}}\n",
    )
    violations = check_pins(tmp_path)
    assert len(violations) == 1
    assert violations[0].startswith("x.yml:9:")


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
