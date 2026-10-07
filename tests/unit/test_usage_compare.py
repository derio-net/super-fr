"""`fr usage compare` (spec 2026-10-06-cost-evidence §F, R10): two sets of
runs over usage files, cursors of every version and plan journals. Fixtures
are shaped after real cursors: phase units nest under the group step
`implement` (v5+ `units`, v1-v4 `items`)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fr.cli import app
from fr.journal.model import JournalEntry, appended_journal_text
from fr.usage.compare import (
    RunInputs,
    load_run_inputs,
    mark_shared,
    render_compare,
    render_steps,
    run_row,
    select_runs,
    set_summary,
    step_table,
)
from fr.usage.file import Capture, Figure, ModelFigures, SessionEntry, UsageFile, dump_usage
from typer.testing import CliRunner

PLAN = "docs/superpowers/plans/2026-10-01-new-thing"
OLD_PLAN = "docs/superpowers/plans/2026-09-01-old-thing"

V8_CURSOR = f"""schema_version: 8
run: 2026-10-01-feat-new
workflow: fr-goal@1
branch: feat/new
started: '2026-10-01T10:00:00+00:00'
cursor: deliver
steps:
  plan:
    state: done
    at: '2026-10-01T11:00:00+00:00'
    emitted:
      plan: {PLAN}
  implement:
    state: done
    at: '2026-10-01T13:00:00+00:00'
    members: [implement-phase, review-phase]
    units:
      phase/1/implement-phase: {{state: done}}
      phase/1/review-phase: {{state: done}}
      phase/2/implement-phase: {{state: done}}
      phase/2/review-phase: {{state: done}}
"""

V4_CURSOR = f"""run: 2026-09-01-feat-old
workflow: fr-goal@1
branch: feat/old
started: '2026-09-01T10:00:00+00:00'
cursor: deliver
steps:
  plan:
    state: done
    at: '2026-09-01T11:00:00+00:00'
    emitted:
      plan: {OLD_PLAN}
  implement:
    state: done
    at: '2026-09-01T13:00:00+00:00'
    items:
      phase/1/implement-phase: done
      phase/1/review-phase: done
    members: [implement-phase, review-phase]
"""

NO_USAGE_CURSOR = """schema_version: 8
run: 2026-10-02-feat-bare
workflow: fr-goal@1
branch: feat/bare
started: '2026-10-02T10:00:00+00:00'
cursor: implement
steps:
  implement:
    state: running
    units:
      phase/1/implement-phase: {state: done}
      phase/2: {state: done}
"""


def _fig(**kw: object) -> Figure:
    return Figure(**kw)  # type: ignore[arg-type]


def _usage(run: str, entries: list[SessionEntry], version: int = 2) -> str:
    cap = Capture(
        host="h-0a1b2c3d",
        harness="claude-code",
        mode="devcontainer",
        captured_at="2026-10-01T14:00:00+00:00",
        at=["resolve:deliver"],
        sessions=entries,
    )
    return dump_usage(UsageFile(schema_version=version, run=run, captures=[cap]))


def _journal(slug: str, entries: list[JournalEntry]) -> str:
    text: str | None = None
    for e in entries:
        text = appended_journal_text(text, slug, e)
    assert text is not None
    return text


def _finding(fid: str, phase: int | None, state: str = "open") -> JournalEntry:
    return JournalEntry(
        kind="finding",
        scope="plan",
        id=fid,
        created="2026-10-01T12:00:00+00:00",
        phase=phase,
        title=fid,
        state=state,
        review_scope="in",  # type: ignore[arg-type]
    )


def _resolution(fid: str, state: str, n: int = 1) -> JournalEntry:
    return JournalEntry(
        kind="finding",
        scope="plan",
        id=f"{fid}-r{n}",
        created="2026-10-01T12:30:00+00:00",
        phase=None,
        title=f"resolves {fid}",
        state=state,
        resolves=fid,  # type: ignore[arg-type]
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    runs = tmp_path / "docs/superpowers/runs"
    usage = tmp_path / "docs/superpowers/usage"
    arch_runs = tmp_path / "docs/superpowers/implemented/runs"
    arch_usage = tmp_path / "docs/superpowers/implemented/usage"
    arch_journals = tmp_path / "docs/superpowers/implemented/journals/plans"
    journals = tmp_path / "docs/superpowers/journals/plans"
    for d in (runs, usage, arch_runs, arch_usage, arch_journals, journals):
        d.mkdir(parents=True)
    (runs / "2026-10-01-feat-new.yaml").write_text(V8_CURSOR)
    (runs / "2026-10-02-feat-bare.yaml").write_text(NO_USAGE_CURSOR)
    (arch_runs / "2026-09-01-feat-old.yaml").write_text(V4_CURSOR)
    main = SessionEntry(
        session="s-main",
        role="main",
        models={"claude-opus-5-5": ModelFigures(usd=3.0, usd_source="exact")},
        steps={"implement": _fig(usd=3.0, turns=40)},
        steps_by_role={
            "main": {"implement": _fig(usd=2.0, turns=30, cache_read=1000, output=100)},
            "subagent": {"implement": _fig(usd=1.0, turns=10, cache_read=3000, output=300)},
        },
    )
    (usage / "2026-10-01-feat-new.yaml").write_text(_usage("2026-10-01-feat-new", [main]))
    old = SessionEntry(session="s-old", role="main", steps={"implement": _fig(usd=None, turns=12)})
    (arch_usage / "2026-09-01-feat-old.yaml").write_text(
        _usage("2026-09-01-feat-old", [old], version=1)
    )
    for base, names in (
        (tmp_path / PLAN, ("01", "02")),
        (tmp_path / "docs/superpowers/implemented/plans/2026-09-01-old-thing", ("01", "02", "03")),
    ):
        base.mkdir(parents=True)
        (base / "_meta.yaml").write_text("title: x\n")
        for n in names:
            (base / f"{n}.yaml").write_text("phase: x\n")
    # new plan: phase 1 has two findings (one re-opened), phase 2 none
    (journals / "2026-10-01-new-thing.md").write_text(
        _journal(
            "2026-10-01-new-thing",
            [
                _finding("a", 1),
                _finding("b", 1),
                _resolution("a", "fixed", 1),
                _resolution("a", "open", 2),
                _resolution("a", "fixed", 3),
                _resolution("b", "fixed"),
                _finding("loose", None),  # type: ignore[arg-type]
            ],
        )
    )
    # old plan: archived journal, one finding
    (arch_journals / "2026-09-01-old-thing.md").write_text(
        _journal("2026-09-01-old-thing", [_finding("o1", 1, "fixed")])
    )
    return tmp_path


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_select_by_date_splits_on_started(repo: Path) -> None:
    before = select_runs(repo, "2026-10-01", before=True)
    after = select_runs(repo, "2026-10-01", before=False)
    assert before == ["2026-09-01-feat-old"]
    assert after == ["2026-10-01-feat-new", "2026-10-02-feat-bare"]


def test_select_by_timestamp_splits_within_a_day(repo: Path) -> None:
    assert select_runs(repo, "2026-10-01T09:00:00Z", before=False)[0] == "2026-10-01-feat-new"
    assert "2026-10-01-feat-new" not in select_runs(repo, "2026-10-01T10:00:01Z", before=False)
    assert "2026-10-01-feat-new" in select_runs(repo, "2026-10-01T10:00:01Z", before=True)


def test_select_by_run_id_is_that_one_run(repo: Path) -> None:
    assert select_runs(repo, "2026-10-02-feat-bare", before=True) == ["2026-10-02-feat-bare"]


def test_select_unknown_selector_is_refused(repo: Path) -> None:
    with pytest.raises(ValueError, match="no run"):
        select_runs(repo, "2026-13-99-nope", before=True)


def test_v8_row_counts_phases_turns_split_findings_and_reopens(repo: Path) -> None:
    row = run_row(load_run_inputs(repo, "2026-10-01-feat-new"))
    assert row.phases == 2
    assert row.turns == 40
    assert row.main is not None and row.main.cache_read == 1000 and row.main.output == 100
    assert row.subagent is not None and row.subagent.cache_read == 3000
    assert row.usd == 3.0 and row.priced is True
    assert row.findings == 2  # phased: a, b
    assert row.unphased == 1  # `loose` is its own column, never divided in
    assert row.findings_per_phase == 1.0
    assert row.reopened == 1


def test_pre_v5_cursor_reads_items_and_a_v1_usage_file(repo: Path) -> None:
    row = run_row(load_run_inputs(repo, "2026-09-01-feat-old"))
    assert row.phases == 3  # the plan folder has 01-03; the cursor lists only phase/1
    assert row.turns == 12
    assert row.main is None and row.subagent is None  # no split observed
    assert row.usd is None and row.priced is False
    assert row.findings == 1 and row.reopened == 0


def test_run_missing_its_usage_file_is_dashed_but_counted(repo: Path) -> None:
    inputs = load_run_inputs(repo, "2026-10-02-feat-bare")
    row = run_row(inputs)
    assert row.phases == 2  # no plan: the cursor's keys, with a bare `phase/2` marker
    assert row.turns is None and row.usd is None and row.main is None
    assert row.findings is None and row.findings_per_phase is None
    summary = set_summary([row])
    assert summary.n == 1 and summary.priced == 0


def test_set_summary_takes_medians_and_counts_priced(repo: Path) -> None:
    rows = [
        run_row(load_run_inputs(repo, r)) for r in select_runs(repo, "2026-10-01", before=False)
    ]
    summary = set_summary(rows)
    assert summary.n == 2
    assert summary.priced == 1
    assert summary.turns == 40  # median over the runs that have one
    assert summary.usd == 3.0


def test_run_inputs_is_plain_data(repo: Path) -> None:
    assert isinstance(load_run_inputs(repo, "2026-10-01-feat-new"), RunInputs)


def test_cli_prints_two_tables_deterministically_and_writes_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    args = [
        "usage",
        "compare",
        "--before",
        "2026-10-01",
        "--after",
        "2026-10-01",
        "--repo",
        str(repo),
    ]
    before = _snapshot(repo)
    first = CliRunner().invoke(app, args)
    second = CliRunner().invoke(app, args)
    assert first.exit_code == 0, first.output
    assert first.output == second.output
    assert "2026-10-01-feat-new" in first.output and "2026-09-01-feat-old" in first.output
    assert "median" in first.output and "n=" in first.output
    assert "—" in first.output
    assert _snapshot(repo) == before


def test_cli_refuses_an_unknown_selector(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    r = CliRunner().invoke(
        app, ["usage", "compare", "--before", "nope", "--after", "2026-10-01", "--repo", str(repo)]
    )
    assert r.exit_code == 2


def test_usage_stays_read_only_for_the_migration_gate() -> None:
    from fr.artifacts.trigger import READ_ONLY_COMMANDS

    assert "usage" in READ_ONLY_COMMANDS


def _shared_repo(repo: Path) -> None:
    """A second v8 run whose usage file names the same session as `feat-new`."""
    cursor = V8_CURSOR.replace("2026-10-01-feat-new", "2026-10-01-feat-twin").replace(
        "feat/new", "feat/twin"
    )
    (repo / "docs/superpowers/runs/2026-10-01-feat-twin.yaml").write_text(cursor)
    twin = SessionEntry(session="s-main", role="main", steps={"implement": _fig(turns=5)})
    (repo / "docs/superpowers/usage/2026-10-01-feat-twin.yaml").write_text(
        _usage("2026-10-01-feat-twin", [twin])
    )


def test_a_session_shared_by_two_runs_of_a_set_is_marked(repo: Path) -> None:
    _shared_repo(repo)
    ids = ["2026-10-01-feat-new", "2026-10-01-feat-twin", "2026-10-02-feat-bare"]
    rows = mark_shared([run_row(load_run_inputs(repo, r)) for r in ids])
    assert [r.shared for r in rows] == [1, 1, 0]
    out = render_compare([], rows)
    assert "shared" in out and "2 of 3 runs share a session" in out


def test_unshared_sets_carry_no_footnote(repo: Path) -> None:
    rows = mark_shared([run_row(load_run_inputs(repo, "2026-10-01-feat-new"))])
    assert "share a session" not in render_compare([], rows)


def test_steps_use_the_v2_main_split_where_it_exists(repo: Path) -> None:
    table = step_table([load_run_inputs(repo, "2026-10-01-feat-new")])
    impl = table.steps["implement"]
    assert (impl.turns, impl.cache_read, impl.output, impl.usd) == (30, 1000, 100, 2.0)
    assert impl.usd_per_turn == pytest.approx(2.0 / 30)
    assert table.sources == {"steps_by_role.main": 1, "role: main entry": 0, "none": 0}


def test_steps_fall_back_to_the_main_entry_of_a_v1_file(repo: Path) -> None:
    table = step_table([load_run_inputs(repo, "2026-09-01-feat-old")])
    impl = table.steps["implement"]
    assert impl.turns == 12 and impl.cache_read is None and impl.usd is None
    assert impl.usd_per_turn is None
    assert table.sources["role: main entry"] == 1


def test_steps_take_medians_over_runs_and_say_which_source(repo: Path) -> None:
    inputs = [load_run_inputs(repo, r) for r in ("2026-10-01-feat-new", "2026-10-02-feat-bare")]
    table = step_table(inputs)
    assert table.sources["none"] == 1
    text = render_steps("after", table)
    assert "implement" in text and "steps_by_role.main" in text and "$/turn" in text
    assert render_steps("after", table) == text


def test_cli_steps_prints_a_table_per_set(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    args = [
        "usage",
        "compare",
        "--before",
        "2026-10-01",
        "--after",
        "2026-10-01",
        "--repo",
        str(repo),
        "--steps",
    ]
    before = _snapshot(repo)
    r = CliRunner().invoke(app, args)
    assert r.exit_code == 0, r.output
    assert "Main-session steps (before" in r.output and "Main-session steps (after" in r.output
    assert _snapshot(repo) == before


def test_the_journal_fold_reports_reopens_without_a_second_walk() -> None:
    from fr.journal.model import effective_finding_states, finding_states_and_reopens

    entries = [
        _finding("a", 1),
        _resolution("a", "fixed", 1),
        _resolution("a", "open", 2),
        _resolution("a", "fixed", 3),
        _finding("b", 1),
    ]
    states, reopened = finding_states_and_reopens(entries)
    assert reopened == ["a"]
    assert states == effective_finding_states(entries)
