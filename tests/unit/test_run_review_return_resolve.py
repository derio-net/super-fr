"""The reviewer-return checks at resolve (spec 2026-09-29-opencode-observe §D):
the recorded spec-review `input-coverage` block must be the one the reviewer
RETURNED (R5), on every harness whose return fr can read — OpenCode's child
session (the committed run-tree fixture, moved to the unit's clock) and a
Claude Code transcript alike."""

from __future__ import annotations

import json
from pathlib import Path

from fr.run import units
from fr.run.model import load_run_state
from fr.run.telemetry import parse_timestamp

from tests.unit.opencode_fixture import opencode_env, shifted
from tests.unit.requirements_support import row, write_input_entry, write_matrix
from tests.unit.test_run_cli import _invoke_as_harness, _invoke_measurable, _squash
from tests.unit.test_run_evidence_requirements import (
    _WITH_COVERAGE,
    SPEC,
    _brainstorm,
    _evidence,
    _review_entry,
    _started,
)
from tests.unit.test_run_evidence_separate_context import _later
from tests.unit.transcript_sessions import (
    AGENT_ID,
    TOOL_USE_ID,
    agent_result_row,
    dispatched_at,
)

INPUT = "fr observes example sessions for the demo"
REQUIREMENTS = """
## Requirements

| id | requirement | source |
|---|---|---|
| R1 | fr observes sessions. | input "fr observes example sessions" |
"""
# ses_rev's return in the fixture (tests/fixtures/usage/opencode/build.py
# REVIEW_RETURN): its review entry's body, as the journal holds it.
RETURNED_BODY = """Reviewed the spec against the input.

```input-coverage
| span | coverage |
|---|---|
| "fr observes example sessions" | R1 |
| "for the demo" | context |
```
"""
RECUT_BODY = RETURNED_BODY.replace(
    '| "fr observes example sessions" | R1 |',
    '| "fr observes" | R1 |\n| "example sessions" | R1 |',
)
RETURN_RECORD = "schema_version: 4\njournal:\n  - kind: review\n    id: review-1\n    body: |\n" + (
    "".join(f"      {line}\n" if line else "\n" for line in RETURNED_BODY.split("\n"))
)

SPEC_REVIEW = ["run", "resolve", "r1", "--step", "spec-review", "--state", "done"]


def _at_spec_review(tmp_path: Path) -> tuple[Path, Path, str]:
    """`spec-review` opened on a spec whose input is the fixture reviewer's.
    Returns when the unit opened."""
    repo, shipped = _started(tmp_path, spec_review=_WITH_COVERAGE)
    spec = repo / SPEC
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Example\n" + REQUIREMENTS)
    write_input_entry(repo, SPEC, body=INPUT)
    write_matrix(repo, [row(SPEC)])
    assert _brainstorm(repo, shipped).exit_code == 0
    advanced = _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {})
    assert advanced.exit_code == 0, advanced.output
    attempt = units.last_attempt(load_run_state(repo, "r1"), "step/spec-review")
    assert attempt is not None
    return repo, shipped, attempt.dispatched


def _on_opencode(tmp_path: Path, opened: str, *, session: str | None = "ses_run"):
    start = parse_timestamp(opened)
    assert start is not None
    return opencode_env(shifted(tmp_path, start), session=session)


def _resolve(repo: Path, shipped: Path, env: dict[str, str | None], reviewer: str):
    argv = [*SPEC_REVIEW, "--evidence", "review=sr-1", "--evidence", f"reviewer={reviewer}"]
    return _invoke_as_harness(repo, shipped, argv, env)


# --- OpenCode ------------------------------------------------------------------


def test_the_unedited_returned_block_resolves_on_opencode(tmp_path: Path) -> None:
    repo, shipped, opened = _at_spec_review(tmp_path)
    _review_entry(repo, body=RETURNED_BODY)

    result = _resolve(repo, shipped, _on_opencode(tmp_path, opened), "ses_rev")

    assert result.exit_code == 0, result.output
    assert _evidence(repo, "spec-review")["coverage"].startswith("2 spans")


def test_a_re_cut_block_is_refused_naming_the_row_on_opencode(tmp_path: Path) -> None:
    """#777, take 10 B: the orchestrator re-cut the reviewer's partition."""
    repo, shipped, opened = _at_spec_review(tmp_path)
    _review_entry(repo, body=RECUT_BODY)

    result = _resolve(repo, shipped, _on_opencode(tmp_path, opened), "ses_rev")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "differs from the one reviewer ses_rev returned" in out
    assert "line 4 of the block" in out
    assert "fr observes" in out
    assert "coverage" not in _evidence(repo, "spec-review")


def test_an_unexported_session_notes_the_return_unobserved(tmp_path: Path) -> None:
    repo, shipped, opened = _at_spec_review(tmp_path)
    _review_entry(repo, body=RECUT_BODY)

    result = _resolve(repo, shipped, _on_opencode(tmp_path, opened, session=None), "ses_rev")

    assert result.exit_code == 0, result.output
    assert "could not read what reviewer ses_rev returned" in _squash(result.stderr)
    assert "reviewer-return" in _evidence(repo, "spec-review")["unobserved"]


# --- Claude Code ---------------------------------------------------------------


def _cc_session(root: Path, opened: str, returned: str) -> None:
    session = dispatched_at(
        root, _later(opened), session_id="s-x", usage={}, agent_type="super-fr:fr-spec-reviewer"
    )
    row_ = agent_result_row(_later(opened), tool_use_id=TOOL_USE_ID, text=returned)
    with session.open("a") as handle:
        handle.write(json.dumps(row_) + "\n")


def _resolve_cc(repo: Path, shipped: Path, root: Path):
    argv = [*SPEC_REVIEW, "--evidence", "review=sr-1", "--evidence", f"reviewer={AGENT_ID}"]
    return _invoke_measurable(repo, shipped, argv, root, "s-x")


def test_the_unedited_returned_block_resolves_on_claude_code(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _at_spec_review(tmp_path)
    _cc_session(root, opened, RETURN_RECORD)
    _review_entry(repo, body=RETURNED_BODY)

    result = _resolve_cc(repo, shipped, root)

    assert result.exit_code == 0, result.output


def test_a_re_cut_block_is_refused_on_claude_code(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _at_spec_review(tmp_path)
    _cc_session(root, opened, RETURN_RECORD)
    _review_entry(repo, body=RECUT_BODY)

    result = _resolve_cc(repo, shipped, root)

    assert result.exit_code == 2, result.output
    assert "line 4 of the block" in _squash(result.output)


def test_a_return_with_no_block_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _at_spec_review(tmp_path)
    _cc_session(root, opened, "Reviewed the spec; it looks fine.")
    _review_entry(repo, body=RETURNED_BODY)

    result = _resolve_cc(repo, shipped, root)

    assert result.exit_code == 2, result.output
    assert "the reviewer returned no input-coverage block" in _squash(result.output)
