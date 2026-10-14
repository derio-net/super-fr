"""`deliver` accounts for leftovers (spec 2026-10-14 exit-gates R9, R11, §C).

R9: an out-of-scope finding, an owed journal entry, an owed row citing the spec
and a narrowing decision are each refused until accounted for, each printed
with the command that accounts for it. R11: `Closes #n` is refused when a gated
row cites #n, and when a narrowing decision the operator did not answer names it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.exceptions import Exit
from fr.acceptance.model import Matrix, Row
from fr.journal.model import JournalEntry, append_journal_entry, journal_path, owed_body
from fr.record.pr_body import premature_closes, unaccounted
from fr.run.model import load_run_state
from fr.verification.exit import Exit as RunExit
from fr.verification.exit import run_exit

from tests.unit.test_verification_walk import RUN, SPEC, SPEC_REF, _git, _repo

IDENTITY = ("o", "proj")
STAMP = "2026-10-14T00:00:00+00:00"


def _rows(root: Path, rows: list[dict[str, object]]) -> None:
    base = {"capability": "c", "origin": [f"{SPEC_REF}#R1"]}
    (root / "docs/acceptance/matrix.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 4,
                "org": "o",
                "repo": "proj",
                "rows": [{**base, "acceptance": f"{r['id']} works", **r} for r in rows],
            }
        )
    )


def _spec(root: Path, section: str) -> None:
    (root / SPEC).write_text(f"# S\n\n## Verification\n\n{section}")


def _journal(root: Path, *entries: JournalEntry) -> None:
    path = journal_path(root, "spec", "s")
    for e in entries:
        append_journal_entry(path, "s", e)


def _commit(root: Path) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed", "--no-verify")


def _leftovers(root: Path):
    state = load_run_state(root, RUN)
    return unaccounted(root, state, run_exit(root, state))


def _out_of_scope(fid: str = "f1") -> tuple[JournalEntry, JournalEntry]:
    return (
        JournalEntry(
            kind="finding", scope="spec", id=fid, created=STAMP, title="old bug", state="open"
        ),
        JournalEntry(
            kind="finding", scope="spec", id=f"{fid}-resolved", created=STAMP,
            title=f"resolves {fid}", state="open", resolves=fid, out_of_scope=True,
        ),
    )  # fmt: skip


def _owed(oid: str = "o1") -> JournalEntry:
    return JournalEntry(
        kind="owed", scope="spec", id=oid, created=STAMP, title="walk it",
        body=owed_body(what="walk", why="main", how="resolve", key="spec:s#step1"),
    )  # fmt: skip


def _narrowing(did: str = "d1", **kw: object) -> JournalEntry:
    return JournalEntry(
        kind="decision", scope="spec", id=did, created=STAMP, title="ships half",
        narrows=("#4",), **kw,  # type: ignore[arg-type]
    )  # fmt: skip


# --- R9: unaccounted ---------------------------------------------------------------


def test_each_kind_of_leftover_is_listed_with_its_fix(tmp_path: Path) -> None:
    root = _repo(tmp_path, rows={"owed-row": None})
    _rows(root, [{"id": "owed-row", "status": "walk-owed", "verify": "candidate"}])
    _journal(root, *_out_of_scope(), _owed(), _narrowing())
    _commit(root)

    found = {(left.kind, left.id): left for left in _leftovers(root)}

    assert set(found) == {
        ("finding", "f1"),
        ("owed", "o1"),
        ("row", "owed-row"),
        ("narrowing", "d1"),
    }
    for key in [("finding", "f1"), ("owed", "o1"), ("narrowing", "d1")]:
        assert f"fr journal file --scope spec --slug s --id {key[1]}" in found[key].fix
    row_fix = found[("row", "owed-row")].fix
    assert "fr verification set --run w1 --row owed-row --gate tester" in row_fix
    assert "fr acceptance set-status --id owed-row --status walk-owed --issue" in row_fix


def test_accounted_leftovers_are_not_listed(tmp_path: Path) -> None:
    root = _repo(tmp_path, rows={"gated": None, "issued": None, "walked": None})
    _spec(root, "strategy: candidate\ngate: gated=tester\n")
    _rows(
        root,
        [
            {"id": "gated", "status": "walk-owed"},
            {"id": "issued", "status": "unwired", "issues": ["o/proj#9"]},
            {"id": "walked", "status": "ci"},
        ],
    )
    f1, oos = _out_of_scope()
    deferred = JournalEntry(
        kind="finding", scope="spec", id="f1-resolved-2", created=STAMP, title="resolves f1",
        state="open", resolves="f1", tracked_by="o/proj#10",
    )  # fmt: skip
    filed = JournalEntry(
        kind="finding", scope="spec", id="o1-resolved", created=STAMP, title="resolves o1",
        state="open", resolves="o1", filed_as="o/proj#11",
    )  # fmt: skip
    files = _narrowing("d1-filed", remainder_tracked_by="o/proj#12")
    _journal(root, f1, oos, deferred, _owed(), filed, _narrowing(), files)
    _commit(root)

    assert _leftovers(root) == []


def test_under_tracking_none_only_the_gate_route_applies(tmp_path: Path) -> None:
    root = _repo(tmp_path, rows={"owed-row": None, "issued": None})
    _rows(
        root,
        [
            {"id": "owed-row", "status": "not-implemented"},
            {"id": "issued", "status": "unwired", "issues": ["o/proj#9"]},
        ],
    )
    (root / ".devcontainer").mkdir()
    (root / ".devcontainer/fr-profiles.yaml").write_text(
        "schema_version: 2\nprofiles:\n  dev:\n    purpose: x\ntracking: {type: none}\n"
    )
    _journal(root, *_out_of_scope(), _owed(), _narrowing())
    _commit(root)

    found = _leftovers(root)

    assert {(left.kind, left.id) for left in found} == {("row", "owed-row"), ("row", "issued")}
    for left in found:
        assert "fr verification set" in left.fix and "set-status" not in left.fix


def test_the_deliver_gate_refuses_printing_every_leftover_and_its_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.commands import run_cmd

    root = _repo(tmp_path, rows={})
    _journal(root, *_out_of_scope())
    _commit(root)

    with pytest.raises(Exit) as exc:
        run_cmd._deliver_leftovers_gate(root, load_run_state(root, RUN))

    assert exc.value.exit_code == 2
    err = capsys.readouterr().err.replace("\n", " ")
    assert "f1" in err and "fr journal file --scope spec --slug s --id f1" in err


# --- R11: premature_closes ---------------------------------------------------------


def _row(rid: str, *, verify: str | None, issues: tuple[str, ...], status: str = "ci") -> Row:
    return Row(
        id=rid,
        capability="c",
        acceptance=f"{rid} works",
        origin=(f"{SPEC_REF}#R1",),
        status=status,
        verify=verify,
        issues=issues,
    )


def _exit(row_gates: dict[str, str]) -> RunExit:
    return RunExit(
        kinds=frozenset({"candidate"}),
        run_gate="none",
        gates=frozenset(g for g in row_gates.values() if g != "none"),
        gated_rows=(),
        rank=1,
        rows=(),
        row_gates=row_gates,
        row_kinds={},
        run_kind="candidate",
    )


def _never(_row: Row) -> bool:
    return False


def test_a_close_over_a_gated_rows_issue_is_refused_even_when_pre_merge() -> None:
    matrix = Matrix(rows=(_row("gated", verify="candidate", issues=("o/proj#7",)),))

    found = premature_closes(
        "Closes #7\n", matrix, IDENTITY, _never, exit=_exit({"gated": "tester"})
    )

    assert [(p.ref, p.rows, p.fix) for p in found] == [("o/proj#7", ("gated",), "Refs o/proj#7")]


def test_a_pre_merge_gate_holds_nothing() -> None:
    matrix = Matrix(rows=(_row("rev", verify="candidate", issues=("o/proj#7",)),))
    assert (
        premature_closes("Closes #7\n", matrix, IDENTITY, _never, exit=_exit({"rev": "owner"}))
        == []
    )


def test_a_narrowing_the_operator_did_not_answer_holds_its_issue_open() -> None:
    found = premature_closes(
        "Closes #4\nCloses #5\n",
        Matrix(),
        IDENTITY,
        _never,
        narrowings=(_narrowing(), _narrowing("d2", decided_by="operator").model_copy(
            update={"narrows": ("#5",)}
        )),
    )  # fmt: skip

    assert [(p.ref, p.decisions, p.fix) for p in found] == [("o/proj#4", ("d1",), "Refs o/proj#4")]


# --- review p3-r5: an owed row's tracking issue ---------------------------------------


@pytest.mark.parametrize("status", ["not-implemented", "unwired", "walk-owed"])
def test_p3_r5_a_close_over_an_owed_rows_tracking_issue_is_refused(status: str) -> None:
    matrix = Matrix(rows=(_row("owed", verify="candidate", issues=("o/proj#9",), status=status),))

    found = premature_closes("Closes #9\n", matrix, IDENTITY, _never)

    assert [(p.ref, p.tracks, p.fix) for p in found] == [("o/proj#9", ("owed",), "Refs o/proj#9")]


def test_p3_r5_a_finished_rows_issue_may_close() -> None:
    matrix = Matrix(rows=(_row("done", verify="candidate", issues=("o/proj#9",)),))
    assert premature_closes("Closes #9\n", matrix, IDENTITY, _never) == []


# --- review p3-r4: a journal that does not parse ------------------------------------


@pytest.mark.parametrize("gate", ["leftovers", "closes"])
def test_p3_r4_an_unparseable_journal_refuses_the_deliver_gates_naming_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], gate: str
) -> None:
    from fr.commands import run_cmd

    root = _repo(tmp_path, rows={})
    _rows(root, [{"id": "r", "status": "ci", "issues": ["o/proj#1"]}])
    path = journal_path(root, "spec", "s")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Journal: s\n<!-- fr:journal kind=finding scope=spec id=f1 created=x -->\n"
        "### f1 · finding · no state\n"
    )
    _commit(root)
    state = load_run_state(root, RUN)

    with pytest.raises(Exit) as exc:
        if gate == "leftovers":
            run_cmd._deliver_leftovers_gate(root, state)
        else:
            run_cmd._refuse_premature_closes(root, state, "Closes #4\n")

    assert exc.value.exit_code == 2
    err = capsys.readouterr().err.replace("\n", " ")
    assert "docs/superpowers/journals/specs/s.md" in err and "does not parse" in err


def test_the_gate_refuses_a_gated_row_close_under_a_remap_to_pre_merge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.commands import run_cmd

    root = _repo(tmp_path, rows={"r1": None})
    (root / ".fr/triage.yaml").write_text("exit:\n  gates:\n    candidate: tester\n")
    _rows(root, [{"id": "r1", "status": "ci", "verify": "candidate", "issues": ["o/proj#7"]}])
    _commit(root)

    with pytest.raises(Exit):
        run_cmd._refuse_premature_closes(root, load_run_state(root, RUN), "Closes #7\n")
    assert "Refs o/proj#7" in capsys.readouterr().err.replace("\n", " ")


def test_the_gate_still_refuses_an_unwalked_post_merge_row_under_a_remap_to_none(
    tmp_path: Path,
) -> None:
    from fr.commands import run_cmd

    root = _repo(tmp_path, rows={"r1": None})
    (root / ".fr/triage.yaml").write_text("exit:\n  gates:\n    live: none\n")
    _rows(root, [{"id": "r1", "status": "walk-owed", "verify": "live", "issues": ["o/proj#7"]}])
    _commit(root)

    with pytest.raises(Exit):
        run_cmd._refuse_premature_closes(root, load_run_state(root, RUN), "Closes #7\n")


def test_the_gate_refuses_a_close_over_an_unanswered_narrowing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.commands import run_cmd

    root = _repo(tmp_path, rows={})
    _journal(root, _narrowing())
    _commit(root)

    with pytest.raises(Exit):
        run_cmd._refuse_premature_closes(root, load_run_state(root, RUN), "Closes #4\n")
    err = capsys.readouterr().err.replace("\n", " ")
    assert "d1" in err and "Refs o/proj#4" in err
