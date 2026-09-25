"""`fr.usage.readers` — one normalized `UsageRecord` per harness session.

Spec 2026-09-25-lean-cost-aware-process §5.A.1-3/7, Test Plan item 1. The
fixtures are redacted captures (tests/fixtures/usage/NOTE.md); expected figures
are derived here straight from the fixture bytes, never from the reader.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import pytest
from fr.usage.readers import claude_code

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "usage"
CC_SESSION = "145101c9-bdfc-4f5d-a8be-617eeced7485"
CC_MAIN = FIXTURES / "claude-code" / f"{CC_SESSION}.jsonl"
CC_FILES = [CC_MAIN, *sorted((FIXTURES / "claude-code" / CC_SESSION / "subagents").glob("*.jsonl"))]


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _expected_per_model() -> tuple[dict[str, Counter], dict[str, Counter], int, int]:
    """(deduped per-model sums, naive per-record sums, distinct messages, tool_use blocks)."""
    deduped: dict[str, Counter] = defaultdict(Counter)
    naive: dict[str, Counter] = defaultdict(Counter)
    messages = 0
    tool_uses = 0
    for path in CC_FILES:
        seen: set[str] = set()
        for rec in _records(path):
            if rec.get("type") != "assistant":
                continue
            msg = rec["message"]
            model = msg["model"]
            if model.startswith("<"):
                continue
            tool_uses += sum(1 for c in msg["content"] if c.get("type") == "tool_use")
            usage = msg["usage"]
            figures = {
                "input": usage["input_tokens"],
                "cache_read": usage["cache_read_input_tokens"],
                "output": usage["output_tokens"],
            }
            naive[model].update(figures)
            if msg["id"] in seen:
                continue
            seen.add(msg["id"])
            messages += 1
            deduped[model].update(figures)
    return deduped, naive, messages, tool_uses


def _last_cost_state() -> dict:
    return [r for r in _records(CC_MAIN) if r.get("type") == "cost-state"][-1]


def test_claude_code_reader_counts_each_message_id_once() -> None:
    record = claude_code.read(CC_MAIN)
    deduped, naive, messages, tool_uses = _expected_per_model()

    assert record.unavailable is None
    assert record.harness == "claude-code"
    assert record.session == CC_SESSION
    assert len(record.messages) == messages

    got: dict[str, Counter] = defaultdict(Counter)
    for m in record.messages:
        got[m.model].update(
            {"input": m.tokens.input, "cache_read": m.tokens.cache_read, "output": m.tokens.output}
        )
    assert got == deduped
    # the fixture really carries duplicates: a per-record sum would be larger
    assert any(naive[m]["output"] > deduped[m]["output"] for m in deduped)
    # tool_use blocks written on later records of the same message still count
    assert sum(len(m.tool_calls) for m in record.messages) == tool_uses


def test_claude_code_cost_is_the_harness_figure() -> None:
    record = claude_code.read(CC_MAIN)
    state = _last_cost_state()

    assert record.cost.source == "exact"
    assert record.cost.usd == pytest.approx(state["totalCostUSD"])
    assert sum(record.cost.by_model.values()) == pytest.approx(state["totalCostUSD"])
    # the harness's "[1m]" context suffix is normalized away so it joins messages
    assert all("[" not in model for model in record.cost.by_model)


def test_claude_code_subagent_messages_carry_their_agent() -> None:
    record = claude_code.read(CC_MAIN)
    agents = {m.agent for m in record.messages}
    assert agents == {"main", "super-fr:fr-phase-executor"}


def test_claude_code_unreadable_source_is_unavailable_never_zero(tmp_path: Path) -> None:
    record = claude_code.read(tmp_path / "missing.jsonl")
    assert record.unavailable
    assert record.messages == ()
    assert record.cost.usd is None
    assert record.cost.source == "none"


# --- OpenCode and Hermes, behind one protocol (P1.T2) ---------------------

OC_DB = FIXTURES / "opencode" / "opencode.db"
HERMES_DB = FIXTURES / "hermes" / "state.db"


def test_every_harness_has_a_reader_behind_one_protocol() -> None:
    from fr.usage.readers import READERS, UsageReader

    assert set(READERS) == {"claude-code", "opencode", "hermes"}
    assert all(isinstance(reader, UsageReader) for reader in READERS.values())


def test_opencode_paid_session_cost_is_exact() -> None:
    from fr.usage.readers import opencode

    record = opencode.read(OC_DB, "ses_paid")
    assert record.unavailable is None
    assert record.harness == "opencode"
    assert record.cost.source == "exact"
    assert record.cost.usd == pytest.approx(0.0123)
    assert record.cost.by_model == {"claude-sonnet-5": pytest.approx(0.0123)}
    [message] = record.messages
    assert message.model == "claude-sonnet-5"
    # reasoning is billed as output; cache.write has no TTL split -> 5-minute
    assert (message.tokens.input, message.tokens.output, message.tokens.cache_read) == (
        200,
        400,
        10000,
    )
    assert message.tokens.cache_write_5m + message.tokens.cache_write_1h == 2000
    assert [(c.name, c.target) for c in message.tool_calls] == [("bash", "uv run pytest -q")]


def test_opencode_free_model_has_no_dollar_figure_not_zero() -> None:
    from fr.usage.readers import opencode

    record = opencode.read(OC_DB, "ses_free")
    assert record.unavailable is None
    assert len(record.messages) == 1
    assert record.cost.source == "none"
    assert record.cost.usd is None


def test_opencode_missing_database_or_session_is_unavailable(tmp_path: Path) -> None:
    from fr.usage.readers import opencode

    assert opencode.read(tmp_path / "nope.db", "ses_paid").unavailable
    assert opencode.read(OC_DB, "ses_absent").unavailable
    assert not (tmp_path / "nope.db").exists()  # read-only: never creates the file


def test_hermes_actual_cost_is_exact_and_attribution_coarse() -> None:
    from fr.usage.readers import hermes

    record = hermes.read(HERMES_DB, "h_actual")
    assert record.unavailable is None
    assert record.harness == "hermes"
    assert record.attribution == "coarse"
    assert record.cost.source == "exact"
    # the session plus its delegate child, both harness-reported
    assert record.cost.usd == pytest.approx(0.048 + 0.002)
    names = [c.name for m in record.messages for c in m.tool_calls]
    assert names == ["terminal", "read_file", "write_file", "terminal"]
    assert [c.target for m in record.messages for c in m.tool_calls][:3] == [
        "uv run pytest -q",
        "docs/superpowers/specs/x.md",
        "packages/fr/src/fr/x.py",
    ]
    assert {m.agent for m in record.messages} == {"main", "delegate"}


def test_hermes_without_actual_cost_is_estimated() -> None:
    from fr.usage.readers import hermes

    record = hermes.read(HERMES_DB, "h_estimated")
    assert record.cost.source == "estimated"
    assert record.cost.usd == pytest.approx(0.0071)


def test_hermes_zero_token_acp_session_is_unavailable_never_zero() -> None:
    from fr.usage.readers import hermes

    record = hermes.read(HERMES_DB, "h_acp")
    assert record.unavailable is not None
    assert "hermes-agent#6775" in record.unavailable
    assert record.cost.usd is None


def test_hermes_missing_database_is_unavailable(tmp_path: Path) -> None:
    from fr.usage.readers import hermes

    assert hermes.read(tmp_path / "nope.db", "h_actual").unavailable
    assert not (tmp_path / "nope.db").exists()


# --- phase-1 review fixes (p1-r1, p1-r3, p1-r4, p1-r5) ----------------------


def test_opencode_copilot_routed_cost_is_estimated_not_exact() -> None:
    # p1-r1 / spec §5.A.2: Copilot bills by subscription, so OpenCode's non-zero
    # `cost` on a github-copilot message is its own estimate
    from fr.usage.readers import opencode

    record = opencode.read(OC_DB, "ses_copilot")
    assert record.cost.source == "estimated"
    assert record.cost.usd == pytest.approx(0.0184639)


def test_opencode_session_is_exact_only_if_every_priced_message_is() -> None:
    from fr.usage.readers import opencode

    record = opencode.read(OC_DB, "ses_mixed")
    assert record.cost.source == "estimated"
    assert record.cost.usd == pytest.approx(0.0123 + 0.0184639)
    assert opencode.read(OC_DB, "ses_paid").cost.source == "exact"


def _db_copy(src: Path, tmp_path: Path, *statements: str) -> Path:
    import sqlite3

    db = tmp_path / src.name
    shutil.copy(src, db)
    con = sqlite3.connect(db)
    for statement in statements:
        con.execute(statement)
    con.commit()
    con.close()
    return db


@pytest.mark.parametrize(
    "statement",
    [
        # a non-numeric cell where a count belongs
        "UPDATE messages SET token_count = 'many' WHERE session_id = 'h_actual'",
        # a timestamp no clock can hold
        "UPDATE messages SET timestamp = 'yesterday' WHERE session_id = 'h_actual'",
        # bytes that are not UTF-8 in a TEXT column
        "UPDATE messages SET tool_calls = CAST(x'fffe' AS TEXT) WHERE session_id = 'h_actual'",
    ],
)
def test_hermes_one_bad_row_is_unavailable_never_a_crash(tmp_path: Path, statement: str) -> None:
    # p1-r3 / spec §5.A.7: a reader reports, it never raises
    from fr.usage.readers import hermes

    record = hermes.read(_db_copy(HERMES_DB, tmp_path, statement), "h_actual")
    assert record.unavailable
    assert record.cost.usd is None


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE message SET time_created = 99999999999999999999 WHERE id = 'msg_a1'",
        "UPDATE message SET data = CAST(x'fffe' AS TEXT) WHERE id = 'msg_a1'",
        "UPDATE message SET time_created = 'noon' WHERE id = 'msg_a1'",
    ],
)
def test_opencode_one_bad_row_is_unavailable_or_tolerated_never_a_crash(
    tmp_path: Path, statement: str
) -> None:
    from fr.usage.readers import opencode

    record = opencode.read(_db_copy(OC_DB, tmp_path, statement), "ses_paid")
    # a row the reader can read around (a non-numeric time) is tolerated; one it
    # cannot is `unavailable` — either way a record comes back
    assert record.unavailable or record.cost.source == "exact"


def test_hermes_unrecorded_per_model_cost_is_omitted_not_priced_at_zero(tmp_path: Path) -> None:
    # p1-r4: Hermes defaults session_model_usage costs to 0 — "not recorded", not
    # "$0". With every per-model figure absent, the session total is split over
    # the messages by tokens, not dumped into unattributed.
    from fr.usage.readers import hermes
    from fr.usage.rollup import rollup

    db = _db_copy(
        HERMES_DB,
        tmp_path,
        "UPDATE session_model_usage SET actual_cost_usd = 0, estimated_cost_usd = 0",
    )
    record = hermes.read(db, "h_actual")
    assert record.cost.source == "exact"
    assert record.cost.by_model == {}
    result = rollup([record])
    assert result.by_sub.get("unattributed", 0.0) == pytest.approx(0.0)
    assert sum(result.by_activity.values()) == pytest.approx(0.05)


def test_hermes_mixed_actual_and_estimated_rows_sum_per_row_as_estimated(tmp_path: Path) -> None:
    # p1-r5: the child has only an estimate; the session still has a figure
    from fr.usage.readers import hermes

    db = _db_copy(
        HERMES_DB,
        tmp_path,
        "UPDATE sessions SET actual_cost_usd = NULL WHERE id = 'h_actual_child'",
        "UPDATE session_model_usage SET actual_cost_usd = 0 WHERE session_id = 'h_actual_child'",
    )
    record = hermes.read(db, "h_actual")
    assert record.cost.source == "estimated"
    assert record.cost.usd == pytest.approx(0.048 + 0.002)
    assert record.cost.by_model == {"anthropic/claude-sonnet-5": pytest.approx(0.048 + 0.002)}


def test_hermes_a_row_with_no_figure_at_all_leaves_the_session_unpriced(tmp_path: Path) -> None:
    from fr.usage.readers import hermes

    db = _db_copy(
        HERMES_DB,
        tmp_path,
        "UPDATE sessions SET actual_cost_usd = NULL, estimated_cost_usd = NULL "
        "WHERE id = 'h_actual_child'",
    )
    record = hermes.read(db, "h_actual")
    assert record.cost.source == "none"
    assert record.cost.usd is None
