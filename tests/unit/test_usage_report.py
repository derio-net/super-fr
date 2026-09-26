"""`fr.usage.rollup` / `fr.usage.render` / `fr usage collect|report`.

Spec 2026-09-25-lean-cost-aware-process §5.A.2/5, Test Plan items 1 and 3.
Rollup tests build normalized `UsageRecord`s directly: they test fr's own
arithmetic, not a harness format (the readers' fixtures cover that).
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import pytest
from fr.cli import app
from fr.usage.model import Cost, Message, Tokens, ToolCall, UsageRecord
from fr.usage.readers import claude_code
from fr.usage.render import render_html, render_table
from fr.usage.rollup import OUTSIDE, rollup, windows_from_cursor
from typer.testing import CliRunner

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "usage"
CC_SESSION = "145101c9-bdfc-4f5d-a8be-617eeced7485"


def _msg(
    model: str, ts: str | None = None, calls: tuple[ToolCall, ...] = (), **tokens: int
) -> Message:
    return Message(ts=ts, model=model, tokens=Tokens(**tokens), tool_calls=calls)


def _rec(session: str, messages: list[Message], by_model: dict[str, float] | None) -> UsageRecord:
    total = sum(by_model.values()) if by_model else None
    cost = Cost(usd=total, source="exact", by_model=by_model) if by_model else Cost()
    return UsageRecord(session=session, harness="claude-code", messages=tuple(messages), cost=cost)


EDIT = ToolCall(name="Edit", target="packages/fr/src/fr/x.py")
READ_SPEC = ToolCall(name="Read", target="docs/superpowers/specs/x.md")


# (a) the split: fixed ratios only, sums back to the harness total ----------


def test_rollup_splits_each_models_dollars_by_the_fixed_ratios_only() -> None:
    # 100 input == 1000 cache-read == 20 output == 80 cache-write-5m == 50 cache-write-1h
    messages = [
        _msg("m-a", calls=(EDIT,), input=100),
        _msg("m-a", calls=(READ_SPEC,), cache_read=1000),
        _msg("m-a", calls=(EDIT,), output=20),
        _msg("m-a", calls=(READ_SPEC,), cache_write_5m=80),
        _msg("m-b", calls=(EDIT,), cache_write_1h=50),
    ]
    result = rollup([_rec("s", messages, {"m-a": 8.0, "m-b": 3.0})])
    assert result.total == pytest.approx(11.0)
    assert result.by_activity["implementation"] == pytest.approx(4.0 + 3.0)
    assert result.by_activity["paperwork"] == pytest.approx(4.0)
    assert sum(result.by_activity.values()) == pytest.approx(result.total, abs=0.01)


def test_rollup_of_a_real_session_sums_back_to_the_harness_total() -> None:
    record = claude_code.read(FIXTURES / "claude-code" / f"{CC_SESSION}.jsonl")
    result = rollup([record])
    assert result.total == pytest.approx(record.cost.usd)
    assert sum(result.by_activity.values()) == pytest.approx(record.cost.usd, abs=0.01)


def test_a_billed_model_with_no_messages_is_unattributed_not_dropped() -> None:
    result = rollup([_rec("s", [_msg("m-a", input=10)], {"m-a": 1.0, "side-model": 0.5})])
    assert result.by_sub["unattributed"] == pytest.approx(0.5)
    assert sum(result.by_activity.values()) == pytest.approx(1.5)


# (b) step windows ----------------------------------------------------------


def test_step_windows_are_prev_at_exclusive_to_at_inclusive() -> None:
    cursor = {
        "started": "2026-09-25T10:00:00+00:00",
        "steps": {
            "brainstorm": {"state": "done", "at": "2026-09-25T10:10:00+00:00"},
            "implement": {"state": "done", "at": "2026-09-25T10:20:00+00:00"},
            "deliver": {"state": "pending"},
        },
    }
    windows = windows_from_cursor(cursor)
    assert [w.step for w in windows] == ["brainstorm", "implement"]
    messages = [
        _msg("m", ts="2026-09-25T10:10:00.400Z", input=10),  # == brainstorm.at (to the second)
        _msg("m", ts="2026-09-25T10:10:01Z", input=10),  # just after -> implement
        _msg("m", ts="2026-09-25T09:59:00Z", input=10),  # before the run
    ]
    result = rollup([_rec("s", messages, {"m": 3.0})], windows=windows)
    assert sum(result.by_step["brainstorm"].values()) == pytest.approx(1.0)
    assert sum(result.by_step["implement"].values()) == pytest.approx(1.0)
    assert sum(result.by_step[OUTSIDE].values()) == pytest.approx(1.0)


# (c) 1/k per tool call; no call -> narration ----------------------------


def test_a_message_splits_evenly_across_its_tool_calls() -> None:
    messages = [_msg("m", calls=(EDIT, READ_SPEC), input=100), _msg("m", input=100)]
    result = rollup([_rec("s", messages, {"m": 4.0})])
    assert result.by_activity["implementation"] == pytest.approx(1.0)
    assert result.by_activity["paperwork"] == pytest.approx(1.0)
    assert result.by_sub["narration"] == pytest.approx(2.0)


# (d) unavailable is never zero ---------------------------------------------


def test_unavailable_and_unpriced_sessions_render_a_dash_never_zero() -> None:
    gone = UsageRecord(session="gone-1", harness="hermes", unavailable="hermes-agent#6775")
    unpriced = _rec("free-1", [_msg("m", input=10)], None)
    result = rollup([gone, unpriced])
    assert result.total is None
    table = render_table(result)
    html = render_html(result)
    for text in (table, html):
        assert "—" in text
        assert "$0" not in text
    assert "hermes-agent#6775" in table


# (e) the CLI ----------------------------------------------------------------


@pytest.fixture
def transcripts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "projects"
    project = root / "-work-example"
    project.mkdir(parents=True)
    shutil.copy(FIXTURES / "claude-code" / f"{CC_SESSION}.jsonl", project)
    shutil.copytree(FIXTURES / "claude-code" / CC_SESSION, project / CC_SESSION)
    monkeypatch.setenv("FR_TRANSCRIPT_ROOT", str(root))
    monkeypatch.setenv("FR_USAGE_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("COLUMNS", "200")
    # The CLI resolves its default repo from cwd. Keep these tests on their
    # temporary fixture tree rather than inheriting the developer's isolated
    # worktree marker (usage is correctly refused inside devcontainers).
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_collect_writes_a_normalized_record_under_the_cache(transcripts: Path) -> None:
    result = CliRunner().invoke(app, ["usage", "collect", "--session", CC_SESSION])
    assert result.exit_code == 0, result.output
    written = transcripts / "cache" / "claude-code" / f"{CC_SESSION}.json"
    data = json.loads(written.read_text())
    assert data["session"] == CC_SESSION
    assert data["unavailable"] is None
    assert len(result.output.strip().splitlines()) == 1


def test_collect_of_an_unknown_session_records_unavailable(transcripts: Path) -> None:
    result = CliRunner().invoke(app, ["usage", "collect", "--session", "no-such-session"])
    assert result.exit_code == 0, result.output
    data = json.loads((transcripts / "cache" / "claude-code" / "no-such-session.json").read_text())
    assert data["unavailable"]


def _repo_with_run(root: Path) -> Path:
    repo = root / "repo"
    runs = repo / "docs" / "superpowers" / "runs"
    runs.mkdir(parents=True)
    (runs / "2026-09-21-r.yaml").write_text(
        "schema_version: 6\nrun: 2026-09-21-r\nworkflow: fr-goal@1\nbranch: b\n"
        "started: '2026-09-21T11:00:00+00:00'\ncursor: deliver\nsteps:\n"
        "  brainstorm:\n    state: done\n    at: '2026-09-21T11:40:00+00:00'\n"
        "  implement:\n    state: done\n    at: '2026-09-21T13:00:00+00:00'\n"
        "    units:\n      phase/1:\n        attempts:\n        - harness: claude-code\n"
        f"          session: {CC_SESSION}\n"
    )
    return repo


def test_report_for_a_run_prints_models_activities_and_steps(transcripts: Path) -> None:
    repo = _repo_with_run(transcripts)
    runner = CliRunner()
    collected = runner.invoke(
        app, ["usage", "collect", "--run", "2026-09-21-r", "--repo", str(repo)]
    )
    assert collected.exit_code == 0, collected.output
    result = runner.invoke(
        app, ["usage", "report", "--run", "2026-09-21-r", "--repo", str(repo), "--format", "table"]
    )
    assert result.exit_code == 0, result.output
    out = result.output
    for needle in ("claude-fable-5-1", "paperwork", "implementation"):
        assert needle in out
    # p1-r7: a By-step ROW per step — line-anchored, so a column header or the
    # `implementation` activity row cannot satisfy it
    for step in ("brainstorm", "implement"):
        assert re.search(rf"^\W*{step}\s+│\s+\$[\d.,]+\s+│", out, re.M), (step, out)


def test_rollup_step_keys_are_the_cursor_steps_the_messages_fall_in() -> None:
    record = claude_code.read(FIXTURES / "claude-code" / f"{CC_SESSION}.jsonl")
    windows = windows_from_cursor(
        {
            "started": "2026-09-21T11:00:00+00:00",
            "steps": {
                "brainstorm": {"at": "2026-09-21T11:40:00+00:00"},
                "implement": {"at": "2026-09-21T13:00:00+00:00"},
            },
        }
    )
    result = rollup([record], windows=windows)
    assert {"brainstorm", "implement"} <= set(result.by_step)
    assert set(result.by_step) <= {"brainstorm", "implement", OUTSIDE}
    # p1-r10: every message is one turn of exactly one step
    assert sum(result.turns_by_step.values()) == len(record.messages)


# p1-r10: turns (messages) per activity and per step --------------------------


def test_rollup_counts_turns_per_activity_and_per_step() -> None:
    windows = windows_from_cursor(
        {
            "started": "2026-09-25T10:00:00+00:00",
            "steps": {
                "plan": {"at": "2026-09-25T10:10:00+00:00"},
                "implement": {"at": "2026-09-25T10:20:00+00:00"},
            },
        }
    )
    messages = [
        _msg("m", ts="2026-09-25T10:05:00Z", calls=(READ_SPEC,), input=10),
        _msg("m", ts="2026-09-25T10:06:00Z", calls=(READ_SPEC, EDIT), input=10),
        _msg("m", ts="2026-09-25T10:15:00Z", calls=(EDIT, EDIT), input=10),
        _msg("m", ts="2026-09-25T10:16:00Z", input=10),
    ]
    result = rollup([_rec("s", messages, {"m": 4.0})], windows=windows)
    # a message is one turn of every activity it touched (so these may sum past
    # the message count), and one turn of its step
    assert dict(result.turns_by_activity) == {"paperwork": 2, "implementation": 2, "other": 1}
    assert dict(result.turns_by_step) == {"plan": 2, "implement": 2}
    # unpriced messages are still turns: a turn costs context whether or not
    # the harness put a dollar figure on it
    unpriced = rollup([_rec("free", messages, None)], windows=windows)
    assert dict(unpriced.turns_by_activity) == dict(result.turns_by_activity)
    for text in (render_table(result), render_html(result)):
        assert "turns" in text


def test_the_table_renders_turns_in_the_activity_and_step_rows() -> None:
    windows = windows_from_cursor(
        {
            "started": "2026-09-25T10:00:00+00:00",
            "steps": {"plan": {"at": "2026-09-25T10:10:00+00:00"}},
        }
    )
    messages = [_msg("m", ts="2026-09-25T10:05:00Z", calls=(READ_SPEC,), input=10)] * 3
    table = render_table(rollup([_rec("s", messages, {"m": 3.0})], windows=windows))
    assert re.search(r"^\W*paperwork\s+│\s+\$3\.00\s+│\s+100\.0%\s+│\s+3\s+│", table, re.M), table
    assert re.search(r"^\W*plan\s+│\s+\$3\.00\s+│\s+3\s+│", table, re.M), table


# p1-r8 / p1-r9: which sessions a run report reads ------------------------------


def test_report_reads_sessions_added_to_the_cursor_after_collect(transcripts: Path) -> None:
    repo = _repo_with_run(transcripts)
    runner = CliRunner()
    assert (
        runner.invoke(
            app, ["usage", "collect", "--run", "2026-09-21-r", "--repo", str(repo)]
        ).exit_code
        == 0
    )
    cursor = repo / "docs" / "superpowers" / "runs" / "2026-09-21-r.yaml"
    cursor.write_text(
        cursor.read_text()
        + "      phase/2:\n        attempts:\n        - harness: claude-code\n"
        + "          session: later-session-0000\n"
    )
    result = runner.invoke(app, ["usage", "report", "--run", "2026-09-21-r", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    assert CC_SESSION[:8] in result.output
    assert "later-se" in result.output


def test_an_unknown_attempt_harness_is_unavailable_not_relabelled(transcripts: Path) -> None:
    repo = _repo_with_run(transcripts)
    cursor = repo / "docs" / "superpowers" / "runs" / "2026-09-21-r.yaml"
    cursor.write_text(
        cursor.read_text()
        + "      phase/2:\n        attempts:\n        - harness: codex\n"
        + "          session: codex-session-0000\n"
        + "      phase/3:\n        attempts:\n        - session: bare-session-0000\n"
    )
    result = CliRunner().invoke(
        app, ["usage", "report", "--run", "2026-09-21-r", "--repo", str(repo)]
    )
    assert result.exit_code == 0, result.output
    codex = next(line for line in result.output.splitlines() if "codex-se" in line)
    assert "codex" in codex.replace("codex-se", "")
    assert "no reader for this harness" in result.output
    bare = next(line for line in result.output.splitlines() if "bare-ses" in line)
    assert "claude-code" in bare  # only a MISSING harness defaults to claude-code


def test_report_html_is_one_self_contained_file(transcripts: Path) -> None:
    out = transcripts / "page.html"
    runner = CliRunner()
    assert runner.invoke(app, ["usage", "collect", "--session", CC_SESSION]).exit_code == 0
    result = runner.invoke(
        app, ["usage", "report", "--session", CC_SESSION, "--format", "html", "-o", str(out)]
    )
    assert result.exit_code == 0, result.output
    page = out.read_text()
    assert page.lstrip().lower().startswith("<!doctype html>")
    assert "<script src" not in page and "<link" not in page
    assert CC_SESSION[:8] in page


def test_usage_is_exempt_from_the_migration_gate() -> None:
    from fr.artifacts import trigger

    assert "usage" in trigger.READ_ONLY_COMMANDS


# golden: the audit's nine sessions (local only) ----------------------------

GOLDEN = [
    line.strip()
    for line in (FIXTURES / "golden_sessions.txt").read_text().splitlines()
    if line.strip() and not line.startswith("#")
]
GOLDEN_ROOT = Path(
    os.environ.get("FR_GOLDEN_TRANSCRIPTS", str(Path.home() / ".claude" / "projects"))
)


def _golden(session: str) -> Path | None:
    hits = sorted(GOLDEN_ROOT.glob(f"*/{session}.jsonl")) if GOLDEN_ROOT.is_dir() else []
    return hits[0] if len(hits) == 1 else None


@pytest.mark.skipif(
    not all(_golden(s) for s in GOLDEN),
    reason="the audit's nine transcripts exist only on the operator's host",
)
def test_golden_audit_pooled_shares() -> None:
    records = [claude_code.read(_golden(s)) for s in GOLDEN]  # type: ignore[arg-type]
    assert all(r.unavailable is None for r in records)
    result = rollup(records)
    paperwork = 100 * (result.share("paperwork") or 0)
    implementation = 100 * (result.share("implementation") or 0)
    assert paperwork == pytest.approx(30.2, abs=0.5)
    assert implementation == pytest.approx(32.9, abs=0.5)


# p1-r11 / spec §7.3: the per-session half of the claim — "23–37% in every
# session", within the same 0.5 points as the pooled share. One session has its
# own expected figure: e50c7ff5 mixes Opus, Sonnet and Haiku, and the audit's
# prototype priced each THREAD by its model mix, where this engine prices each
# MESSAGE by its own model (spec §5.A.2). The prototype's method over this
# engine's classifications gives the published 23.6%; the per-message figure,
# 21.9%, is the correct one (plan journal p1-golden-e50, refuted).
GOLDEN_EXPECTED_BAND = {"e50c7ff5-b51f-415b-bc3c-dbc90e454a47": (21.9 - 0.5, 21.9 + 0.5)}


@pytest.mark.parametrize("session", GOLDEN)
def test_golden_audit_every_sessions_paperwork_share_is_23_to_37(session: str) -> None:
    path = _golden(session)
    if path is None:
        pytest.skip("the audit's transcripts exist only on the operator's host")
    record = claude_code.read(path)
    assert record.unavailable is None
    paperwork = 100 * (rollup([record]).share("paperwork") or 0)
    low, high = GOLDEN_EXPECTED_BAND.get(session, (23 - 0.5, 37 + 0.5))
    assert low <= paperwork <= high, (session, paperwork)


def test_a_sub_cent_figure_is_not_rendered_as_zero() -> None:
    from fr.usage.render import _usd

    assert _usd(0.0012) == "<$0.01"
    assert _usd(None) == "—"
    assert _usd(1.234) == "$1.23"
