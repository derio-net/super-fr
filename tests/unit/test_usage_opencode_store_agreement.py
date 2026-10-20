"""The run reader and the usage reader agree on an OpenCode 2 session (spec
2026-10-20-opencode-2-support §D: "one adapter, both readers"): both read
`fr.run.opencode_store`, so their tool calls and figures cannot drift."""

from __future__ import annotations

from pathlib import Path

from fr.run import observed, opencode_store
from fr.usage.readers import opencode

FIXTURE = Path(__file__).parents[1] / "fixtures" / "opencode" / "two-sessions.db"


def test_both_readers_import_the_one_adapter() -> None:
    assert observed.store_version is opencode_store.store_version
    assert opencode.store_version is opencode_store.store_version
    assert opencode.open_ro is opencode_store.open_ro


def test_both_readers_see_the_same_tool_calls_of_a_2x_session() -> None:
    view = observed.OpenCodeSession(FIXTURE, "ses_v2demo")
    parts = view._parts()
    assert parts is not None
    record = opencode.read(FIXTURE, "ses_v2demo")
    usage_calls = [c.name for m in record.messages if m.agent == "main" for c in m.tool_calls]
    assert (
        [p.tool for p in parts]
        == usage_calls
        == [
            "skill",
            "question",
            "shell",
            "subagent",
            "shell",
        ]
    )


def test_both_readers_agree_on_the_dispatched_child_and_its_figures() -> None:
    view = observed.OpenCodeSession(FIXTURE, "ses_v2demo")
    dispatches = view.dispatches(observed._dt.datetime.fromtimestamp(0, tz=observed._dt.UTC))
    record = opencode.read(FIXTURE, "ses_v2demo")
    assert [d.agent_id for d in dispatches or []] == list(record.briefs)
    assert {m.agent_id for m in record.messages if m.agent != "main"} == {"ses_v2child"}


def test_both_readers_refuse_a_1x_session_with_the_same_reason() -> None:
    record = opencode.read(FIXTURE, "ses_v1only")
    assert record.unavailable is not None
    assert opencode_store.V1_ONLY_REASON in record.unavailable
    env = {
        "FR_HARNESS": "opencode",
        "FR_OPENCODE_DB": str(FIXTURE),
        "OPENCODE_SESSION_ID": "ses_v1only",
    }
    assert opencode_store.V1_ONLY_REASON in observed.why_unobservable("opencode", env, "commands")
