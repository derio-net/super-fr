"""The shipped `fr-debugging` shape (spec 2026-11-24-batch-merge-readiness §E, R10, R11):
a debug run has a cursor that walks `debug`, `review`, `deliver`, and the debug journal is
the one the record engine, the review evidence gate, the derived `findings` gate and the PR
body read.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from fr.journal.model import JournalEntry, append_journal_entry, journal_path, parse_journal
from fr.record.model import RECORD_SCHEMA_VERSION
from fr.workflow.artifacts import REPO_TRACKED_ARTIFACTS
from fr.workflow.check import check_workflow
from fr.workflow.resolve import resolve_workflow

from tests.integration.test_fr_goal_shape import SHIPPED_WORKFLOWS_DIR, _fr, _workspace
from tests.unit.record_support import write_record

pytestmark = pytest.mark.own_artifacts

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN = "r1"
SLUG = "2026-11-25-broken-thing"
JOURNAL_REL = f"docs/superpowers/journals/debug/{SLUG}.md"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _commit(root: Path, msg: str = "work") -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", msg, "--no-verify", "--allow-empty")


def _entry(kind: str, eid: str, **kw: object) -> JournalEntry:
    return JournalEntry(
        kind=kind,  # type: ignore[arg-type]
        scope="debug",
        id=eid,
        created=datetime.now().replace(microsecond=0).isoformat(),
        title=str(kw.pop("title", eid)),
        **kw,  # type: ignore[arg-type]
    )


def _started(tmp_path: Path) -> Path:
    root = _workspace(tmp_path, "fix/broken-thing")
    out = _fr(
        root, ["run", "start", "fr-debugging", "--branch", "fix/broken-thing", "--run-id", RUN]
    )
    assert out.exit_code == 0, out.output
    _commit(root, "cursor")
    return root


def _record(root: Path, step: str, **fields: object) -> Path:
    path = write_record(
        root,
        {
            "schema_version": RECORD_SCHEMA_VERSION,
            "run": RUN,
            "step": step,
            "outcome": "done",
            **fields,
        },
    )
    _commit(root, f"{step} record")
    return path


def _resolve(root: Path, record: Path, step: str):
    return _fr(
        root, ["run", "resolve", RUN, "--step", step, "--record", str(record), "--no-advance"]
    )


def _debug_done(root: Path) -> None:
    _fr(root, ["run", "advance", RUN])
    rec = _record(
        root,
        "debug",
        emitted={"debug": JOURNAL_REL},
        journal=[{"kind": "decision", "id": "root-cause", "title": "the cause", "body": "b"}],
    )
    # the journal file must exist for `emitted: debug` (a path that must exist)
    append_journal_entry(journal_path(root, "debug", SLUG), SLUG, _entry("discovery", "seed"))
    _commit(root, "debug journal")
    out = _resolve(root, rec, "debug")
    assert out.exit_code == 0, out.output


def _journal(root: Path):
    return parse_journal(journal_path(root, "debug", SLUG).read_text())


# --- the manifest -------------------------------------------------------------------


def test_the_shipped_manifest_passes_workflow_check_and_resolves() -> None:
    manifest = resolve_workflow("fr-debugging", REPO_ROOT, shipped_root=SHIPPED_WORKFLOWS_DIR)
    assert [s.id for s in manifest.steps] == ["debug", "review", "deliver"]
    assert manifest.unit == "run"
    assert check_workflow(manifest, None) == []
    deliver = manifest.steps[2]
    assert set(deliver.evidence) == {"tests", "docs", "settle"}
    assert manifest.steps[1].evidence == ("review", "reviewer", "findings") or set(
        manifest.steps[1].evidence
    ) == {"review", "reviewer", "findings"}


def test_debug_is_a_path_artifact_like_spec_and_plan() -> None:
    assert {"spec", "plan", "debug"} <= REPO_TRACKED_ARTIFACTS


def test_the_wheel_copy_resolves_the_same_shape() -> None:
    packaged = REPO_ROOT / "packages/fr/src/fr/defaults/workflows/fr-debugging.yaml"
    plugin = SHIPPED_WORKFLOWS_DIR / "fr-debugging.yaml"
    assert packaged.read_bytes() == plugin.read_bytes()


# --- the cursor walks debug, review, deliver -----------------------------------------


def test_a_run_starts_and_briefs_debug_first(tmp_path: Path) -> None:
    root = _started(tmp_path)
    out = _fr(root, ["run", "advance", RUN])
    assert out.exit_code == 0, out.output
    brief = json.loads(out.output[out.output.index("{") :])
    assert brief["step"] == "debug"
    # the pre-filled record asks for the journal path (review p4-r1)
    assert "debug: <path or url>" in brief["record"]["template"]


def test_a_debug_record_emits_the_journal_and_applies_its_entries_there(tmp_path: Path) -> None:
    root = _started(tmp_path)
    _debug_done(root)
    assert "root-cause" in {e.id for e in _journal(root)}
    from fr.run.model import load_run_state

    state = load_run_state(root, RUN)
    assert state.steps["debug"].emitted == {"debug": JOURNAL_REL}


def _review_record_fields(*, resolves: list[dict] | None = None) -> dict:
    return {
        "journal": [
            {"kind": "review", "id": "d-review", "title": "independent review", "body": "ok"},
            {
                "kind": "finding",
                "id": "d-r1",
                "title": "edge case",
                "body": "b",
                "review_scope": "in",
            },
        ],
        "resolves": resolves or [],
        "evidence": {"review": "d-review", "reviewer": "reviewer-1"},
    }


def test_review_is_refused_while_a_debug_finding_is_open(tmp_path: Path) -> None:
    root = _started(tmp_path)
    _debug_done(root)
    _fr(root, ["run", "advance", RUN])
    rec = _record(root, "review", **_review_record_fields())
    out = _resolve(root, rec, "review")
    assert out.exit_code != 0
    assert "filed against the fix are still open: d-r1" in out.output
    assert f"fr journal resolve --scope debug --slug {SLUG} --id d-r1" in out.output


def test_review_passes_once_the_finding_is_fixed(tmp_path: Path) -> None:
    root = _started(tmp_path)
    _debug_done(root)
    _fr(root, ["run", "advance", RUN])
    fields = _review_record_fields(
        resolves=[{"id": "d-r1", "state": "fixed", "body": "covered by a test"}]
    )
    rec = _record(root, "review", **fields)
    out = _resolve(root, rec, "review")
    assert out.exit_code == 0, out.output
    ids = {e.id for e in _journal(root)}
    assert {"d-review", "d-r1"} <= ids


def test_review_is_refused_without_a_review_entry(tmp_path: Path) -> None:
    root = _started(tmp_path)
    _debug_done(root)
    _fr(root, ["run", "advance", RUN])
    fields = _review_record_fields()
    fields["journal"] = []
    rec = _record(root, "review", **fields)
    out = _resolve(root, rec, "review")
    assert out.exit_code != 0
    assert f"--evidence review=d-review names no entry in the debug journal for {SLUG}" in (
        out.output.replace("\n", " ")
    )


def test_deliver_owes_no_proportionality(tmp_path: Path) -> None:
    from fr.workflow.resolve import resolve_workflow

    manifest = resolve_workflow("fr-debugging", REPO_ROOT, shipped_root=SHIPPED_WORKFLOWS_DIR)
    assert "proportionality" not in manifest.steps[2].evidence
    assert "walk" not in manifest.steps[2].evidence


# --- the PR body and deliver's leftovers read the debug journal ----------------------


def _debug_state(emitted: dict[str, str]):
    from types import SimpleNamespace

    return SimpleNamespace(run=RUN, steps={"debug": SimpleNamespace(emitted=emitted)})


def _finding_journal(root: Path) -> None:
    path = journal_path(root, "debug", SLUG)
    append_journal_entry(path, SLUG, _entry("finding", "d-r1", state="open", review_scope="in"))
    append_journal_entry(path, SLUG, _entry("finding", "d-r2", state="open", review_scope="out"))
    append_journal_entry(
        path,
        SLUG,
        _entry("finding", "d-r2-resolved", state="open", resolves="d-r2", out_of_scope=True),
    )


def test_the_pr_body_lists_the_debug_journals_findings(tmp_path: Path) -> None:
    from fr.record.pr_body import _findings

    _finding_journal(tmp_path)
    inside, outside = _findings(tmp_path, _debug_state({"debug": JOURNAL_REL}))  # type: ignore[arg-type]
    assert any("`d-r1`" in line and "(debug" in line for line in inside)
    assert any("`d-r2`" in line for line in outside)


def test_unaccounted_sees_an_open_out_of_scope_debug_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.record import pr_body

    monkeypatch.setattr(pr_body, "_has_tracker", lambda _root: True)
    _finding_journal(tmp_path)
    left = pr_body.unaccounted(tmp_path, _debug_state({"debug": JOURNAL_REL}), None)  # type: ignore[arg-type]
    assert [(x.kind, x.id) for x in left] == [("finding", "d-r2")]
    assert "fr journal file --scope debug --slug " + SLUG in left[0].fix


def test_deliver_gates_pass_with_tests_docs_and_settle_only(tmp_path: Path) -> None:
    root = _started(tmp_path)
    _debug_done(root)
    _fr(root, ["run", "advance", RUN])
    fields = _review_record_fields(
        resolves=[{"id": "d-r1", "state": "fixed", "body": "covered by a test"}]
    )
    assert _resolve(root, _record(root, "review", **fields), "review").exit_code == 0
    _fr(root, ["run", "advance", RUN])
    (root / "suite.log").write_text("n passed\n")
    out = _fr(
        root,
        [
            "run", "resolve", RUN, "--step", "deliver", "--state", "done",
            "--emitted", "pr=https://example.com/o/r/pull/1",
            "--evidence", "tests=suite.log",
        ],
    )  # fmt: skip
    # No forge in the sandbox: the one refusal left is the PR read, after every evidence
    # gate passed with no plan — and the PR body it rendered lists the debug journal.
    assert "cannot read the PR" in out.output
    assert "proportionality" not in out.output
    body = (root / "docs/superpowers/runs/r1.records/pr-body.md").read_text()
    assert "d-r1" in body


def test_deliver_is_refused_end_to_end_while_an_out_of_scope_finding_is_open(
    tmp_path: Path,
) -> None:
    root = _started(tmp_path)
    _debug_done(root)
    _fr(root, ["run", "advance", RUN])
    fields = _review_record_fields(
        resolves=[
            {"id": "d-r1", "state": "fixed", "body": "covered by a test"},
            {"id": "d-r2", "state": "out-of-scope", "body": "not caused by this fix"},
        ]
    )
    fields["journal"].append(
        {
            "kind": "finding",
            "id": "d-r2",
            "title": "a bug elsewhere",
            "body": "b",
            "review_scope": "out",
        }
    )
    assert _resolve(root, _record(root, "review", **fields), "review").exit_code == 0
    _fr(root, ["run", "advance", RUN])
    (root / "suite.log").write_text("n passed\n")
    out = _fr(
        root,
        [
            "run", "resolve", RUN, "--step", "deliver", "--state", "done",
            "--emitted", "pr=https://example.com/o/r/pull/1",
            "--evidence", "tests=suite.log",
        ],
    )  # fmt: skip
    text = out.output.replace("\n", " ")
    assert out.exit_code != 0
    assert "d-r2" in text
    assert "fr journal file --scope debug" in text


def test_a_debug_run_records_a_substitution_in_its_debug_journal(tmp_path: Path) -> None:
    from fr.commands.run_cmd import _run_journal

    state = _debug_state({"debug": JOURNAL_REL})
    assert _run_journal(tmp_path, state) == ("debug", SLUG)  # type: ignore[arg-type]
