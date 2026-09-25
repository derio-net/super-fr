"""The verbs are one-entry records (spec 2026-09-25-lean-cost-aware-process
§5.C.6, §7 item 11): each builds a single-entry record and hands it to the
same apply engine `fr run resolve --record` uses, keeping its flags, exit
codes and refusals, and printing one line on success."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.record import apply as engine
from typer.testing import CliRunner

SLUG = "2026-09-25-verbs"
PLAN_REL = f"docs/superpowers/plans/{SLUG}"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    from fr.plan_ops import PhaseSpec, create

    root = (tmp_path / "repo").resolve()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "seed").write_text("seed\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    _git(root, "checkout", "-qb", "feat/verbs")
    (root / "docs").mkdir()
    (root / "docs" / "spec.md").write_text(
        "# spec\n\n## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|--|--|--|--|\n"
    )
    create(
        repo_root=root,
        slug=SLUG,
        spec="docs/spec.md",
        target_repo="derio-net/super-fr",
        fr_version=">=3.0.0,<5.0.0",
        phases=[
            PhaseSpec(
                number=1,
                title="P1",
                tasks=({"number": 1, "title": "t", "steps": [{"id": "P1.T1.S1", "text": "do"}]},),
                skeleton=True,
            )
        ],
        prose="# p\n",
    )
    (root / "docs" / "acceptance").mkdir()
    (root / "docs" / "acceptance" / "matrix.yaml").write_text(
        "# the registry\norg: derio-net\nrepo: super-fr\nrows:\n"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "plan", "--no-verify")
    return root


def _fr(root: Path, argv: list[str]):
    return CliRunner().invoke(app, argv, env={**os.environ, "VK_REPO_ROOT": str(root)})


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str | None, object]]:
    calls: list[tuple[str | None, object]] = []
    real = engine.apply_record

    def recording(repo_root, run_id, record, **kw):
        calls.append((run_id, record))
        return real(repo_root, run_id, record, **kw)

    monkeypatch.setattr(engine, "apply_record", recording)
    return calls


def _one_line(result) -> str:
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert len(lines) == 1, result.stdout
    return lines[0]


def _clean(root: Path) -> None:
    assert _git(root, "status", "--porcelain", "--", "docs").strip() == "", _git(
        root, "status", "--porcelain"
    )


JOURNAL_ADD = [
    "journal", "add", "--scope", "plan", "--slug", SLUG, "--kind", "finding",
    "--state", "open", "--phase", "1", "--id", "f1", "--title", "a finding",
]  # fmt: skip


def test_journal_add_is_a_one_entry_record(repo: Path, spy) -> None:
    line = _one_line(_fr(repo, JOURNAL_ADD))

    assert "f1" in line
    [(run_id, record)] = spy
    assert run_id is None and [e.id for e in record.journal] == ["f1"]
    _clean(repo)


def test_journal_add_keeps_its_refusals(repo: Path, spy) -> None:
    assert _fr(repo, JOURNAL_ADD).exit_code == 0
    again = _fr(repo, JOURNAL_ADD)
    assert again.exit_code == 2
    assert "already exists" in again.output
    untagged = _fr(repo, [a for a in JOURNAL_ADD if a not in ("--phase", "1")])
    assert untagged.exit_code == 2 and "--phase N or --global" in untagged.output


def test_journal_resolve_is_a_one_entry_record(repo: Path, spy) -> None:
    assert _fr(repo, JOURNAL_ADD).exit_code == 0
    spy.clear()
    resolve = [
        "journal", "resolve", "--scope", "plan", "--slug", SLUG, "--id", "f1",
        "--state", "fixed", "--note", "done", "--phase", "1",
    ]  # fmt: skip
    line = _one_line(_fr(repo, resolve))

    assert line == "f1 → fixed (record f1-resolved)"
    [(run_id, record)] = spy
    assert run_id is None and [r.id for r in record.resolves] == ["f1"]
    _clean(repo)
    missing = _fr(repo, [*resolve[:7], "nope", *resolve[8:]])
    assert missing.exit_code == 2


def test_plan_edit_tick_and_complete_are_one_entry_records(repo: Path, spy) -> None:
    line = _one_line(_fr(repo, ["plan", "edit", str(repo / PLAN_REL), "--tick", "P1.T1.S1"]))
    assert line == "ticked P1.T1.S1 → x"
    [(_, record)] = spy
    assert [t.id for t in record.tick_items()] == ["P1.T1.S1"]
    _clean(repo)

    spy.clear()
    line = _one_line(_fr(repo, ["plan", "edit", str(repo / PLAN_REL), "--complete-phase", "1"]))
    assert line.startswith("phase 1: marked complete")
    [(_, record)] = spy
    assert record.complete is not None and record.complete.phase == 1
    _clean(repo)

    unknown = _fr(repo, ["plan", "edit", str(repo / PLAN_REL), "--tick", "P1.T9.S9"])
    assert unknown.exit_code == 2


def test_acceptance_add_and_set_status_are_one_entry_records(repo: Path, spy) -> None:
    add = [
        "acceptance", "add", "--id", "row-a", "--capability", "c", "--acceptance", "a",
        "--origin", "super-fr:docs/spec.md", "--status", "not-implemented",
    ]  # fmt: skip
    line = _one_line(_fr(repo, add))
    assert line == "added row row-a (not-implemented)"
    [(_, record)] = spy
    assert [a.id for a in record.acceptance] == ["row-a"]
    _clean(repo)

    spy.clear()
    move = ["acceptance", "set-status", "--id", "row-a", "--status", "skipped", "--notes", "why"]
    line = _one_line(_fr(repo, move))
    assert line == "row-a: not-implemented → skipped"
    assert len(spy) == 1
    _clean(repo)

    assert _fr(repo, add).exit_code == 2  # duplicate id, refused as before
    assert _fr(repo, [*move[:3], "nope", *move[4:]]).exit_code == 2


def test_run_resolve_record_routes_through_the_engine(tmp_path: Path, spy) -> None:
    from tests.unit.record_support import (
        RUN,
        commit_all,
        fr,
        implement_record,
        started_run,
        write_record,
    )

    root = started_run(tmp_path)
    record = write_record(root, implement_record())
    commit_all(root)
    argv = ["run", "resolve", RUN, "--step", "implement-phase", "--item", "phase/1"]
    out = fr(root, [*argv, "--record", str(record)])

    assert out.exit_code == 0, out.output
    [(run_id, _)] = spy
    assert run_id == RUN
