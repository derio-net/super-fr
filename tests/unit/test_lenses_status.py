"""`fr lenses status` (spec 2026-11-12-review-lenses R5, R7): the branch's run's lens
set, one line per lens with each reason and the step that added it, or the rule and
a matching file; read-only."""

from __future__ import annotations

import json
from pathlib import Path

from tests.unit.record_support import (
    RUN,
    SLUG,
    commit_all,
    fr,
    implement_record,
    snapshot,
    started_run,
    write_record,
)

ITEM = {"kind": "lens", "lens": "security", "title": "the retry path builds a shell command"}


def _with_a_lens(tmp_path: Path) -> Path:
    root = started_run(tmp_path)
    record = write_record(root, implement_record(journal=[*implement_record()["journal"], ITEM]))  # type: ignore[misc]
    commit_all(root, "record")
    out = fr(
        root,
        ["run", "resolve", RUN, "--step", "implement-phase", "--item", "phase/1",
         "--record", str(record), "--no-advance"],
    )  # fmt: skip
    assert out.exit_code == 0, out.output
    return root


def test_status_prints_each_lens_with_its_reason_and_step_and_writes_nothing(
    tmp_path: Path,
) -> None:
    root = _with_a_lens(tmp_path)
    add = ["journal", "add", "--scope", "plan", "--slug", SLUG, "--kind", "lens"]
    cli = fr(root, [*add, "--lens", "tests", "--title", "only the happy path", "--phase", "1"])
    assert cli.exit_code == 0, cli.output
    before = snapshot(root)

    out = fr(root, ["lenses", "status"])

    assert out.exit_code == 0, out.output
    lines = out.stdout.splitlines()
    assert lines == [
        'security: "the retry path builds a shell command" (step implement-phase, lens-security-1)',
        'tests: "only the happy path" (command line, lens-tests-1)',
    ]
    assert snapshot(root) == before


def test_status_json_names_the_run_and_every_reason(tmp_path: Path) -> None:
    root = _with_a_lens(tmp_path)

    out = fr(root, ["lenses", "status", "--run", RUN, "--json"])

    assert out.exit_code == 0, out.output
    data = json.loads(out.stdout)
    assert data["run"] == RUN
    (lens,) = data["lenses"]
    assert lens["lens"] == "security" and lens["rule"] is None
    assert lens["reasons"][0]["step"] == "implement-phase"


def test_an_empty_set_says_no_lens_requested(tmp_path: Path) -> None:
    root = started_run(tmp_path)

    out = fr(root, ["lenses", "status"])

    assert out.exit_code == 0, out.output
    assert out.stdout.strip() == "no lens requested"


def test_a_dropped_lens_is_a_warning(tmp_path: Path) -> None:
    root = _with_a_lens(tmp_path)
    (root / ".fr").mkdir(exist_ok=True)
    (root / ".fr" / "lenses.yaml").write_text("disable: [security]\n")

    out = fr(root, ["lenses", "status"])

    assert out.exit_code == 0, out.output
    assert "no lens requested" in out.stdout
    assert "warning: lens security is not effective" in out.output


def test_an_unknown_run_is_exit_two(tmp_path: Path) -> None:
    root = started_run(tmp_path)
    out = fr(root, ["lenses", "status", "--run", "nope"])
    assert out.exit_code == 2, out.output
