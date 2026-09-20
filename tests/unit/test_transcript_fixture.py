"""The captured Claude Code transcript fixtures — the phase-1 smoke test for
the riskiest external format this plan depends on (bounded-executor-handoff,
P1.T2). See `tests/fixtures/transcripts/claude-code-session.NOTE.md` for the
capture and redaction record, and the plan journal (`--phase 1`) for what the
real shape turned out to be relative to spec §2's claims.

This is deliberately RED-then-GREEN in one step: the assertions ARE the
capture's contract, pinning exactly what a V2 parser (phase 4) may rely on.

**Two files, because the harness writes two.** The phase-1 capture disproved
spec §5.C's assumption that subagent turns interleave into the orchestrator's
stream. They do not: an orchestrator session file is `isSidechain: false`
throughout, and each dispatched subagent gets its own
`subagents/agent-<agentId>.jsonl` that is `isSidechain: true` throughout,
correlated back by its companion `.meta.json`'s `toolUseId`. A single merged
fixture would be a file shape the harness never emits, and a phase-4 parser
written against it would filter one stream and read zero subagent tokens from
every real transcript on disk.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "transcripts"
ORCHESTRATOR = FIXTURES / "claude-code-session.jsonl"
SUBAGENT = FIXTURES / "claude-code-subagent.jsonl"
SUBAGENT_META = FIXTURES / "claude-code-subagent.meta.json"

REQUIRED_USAGE_KEYS = {
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
}


def _load(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def test_both_fixtures_parse_as_jsonl() -> None:
    for path in (ORCHESTRATOR, SUBAGENT):
        records = _load(path)
        assert records, f"{path.name} must carry at least one record"
        assert all(isinstance(r, dict) for r in records)


def test_every_assistant_record_carries_all_four_usage_keys() -> None:
    """Not "at least one": a fixture that lost usage on every record but one
    would satisfy that and still leave a phase-4 parser unexercised."""
    seen = 0
    for path in (ORCHESTRATOR, SUBAGENT):
        for r in _load(path):
            if r.get("type") != "assistant":
                continue
            message = r.get("message")
            assert isinstance(message, dict), f"{path.name}: assistant record without message"
            usage = message.get("usage")
            assert isinstance(usage, dict), f"{path.name}: assistant record without usage"
            missing = REQUIRED_USAGE_KEYS - set(usage)
            assert not missing, f"{path.name}: usage missing {sorted(missing)}"
            seen += 1
    assert seen, "fixtures must carry at least one assistant record"


def test_usage_carries_more_than_the_four_keys_a_parser_needs() -> None:
    """A phase-4 parser must PROJECT onto the four keys rather than assume the
    usage object is exactly those four — the real object is wider."""
    extras: set[str] = set()
    for path in (ORCHESTRATOR, SUBAGENT):
        for r in _load(path):
            message = r.get("message")
            if isinstance(message, dict) and isinstance(message.get("usage"), dict):
                extras |= set(message["usage"]) - REQUIRED_USAGE_KEYS
    assert extras, "expected the real usage object to carry keys beyond the four"


def test_the_orchestrator_stream_holds_no_sidechain_records() -> None:
    """The refutation of spec §5.C, pinned. `isSidechain` is false (or absent)
    for every record an orchestrator session file holds, so filtering one
    stream on it can never find a subagent's turns."""
    records = _load(ORCHESTRATOR)
    values = {r.get("isSidechain") for r in records}
    assert True not in values, f"orchestrator fixture carried a sidechain record: {values}"
    assert False in values, "expected explicit isSidechain=false records"
    assert not any("agentId" in r for r in records), "orchestrator records carry no agentId"


def test_the_subagent_stream_is_sidechain_throughout_and_self_identifies() -> None:
    records = _load(SUBAGENT)
    assert all(r.get("isSidechain") is True for r in records)
    agent_ids = {r.get("agentId") for r in records}
    assert len(agent_ids) == 1 and None not in agent_ids, agent_ids
    # parentUuid chains only the subagent's OWN turns, starting at null — it
    # does not reach back to the dispatching tool_use, which is why §5.C's
    # parentUuid walk cannot work.
    assert records[0].get("parentUuid") is None


def test_the_subagent_shares_the_orchestrators_session_id() -> None:
    """`sessionId` is NOT a per-agent identifier — attribution cannot key on
    it. The subagent's own identity is `agentId`."""
    orch_sessions = {r.get("sessionId") for r in _load(ORCHESTRATOR) if r.get("sessionId")}
    sub_sessions = {r.get("sessionId") for r in _load(SUBAGENT) if r.get("sessionId")}
    assert sub_sessions and sub_sessions <= orch_sessions, (sub_sessions, orch_sessions)


def test_meta_tool_use_id_is_what_correlates_the_two_files() -> None:
    """The actual attribution mechanism, and the one a phase-4 reader must
    use: the subagent file's companion `.meta.json` carries the `toolUseId` of
    the `Agent` tool_use in the orchestrator stream that dispatched it."""
    meta = json.loads(SUBAGENT_META.read_text())
    dispatch_ids = {
        block["id"]
        for r in _load(ORCHESTRATOR)
        if isinstance(r.get("message"), dict)
        for block in (r["message"].get("content") or [])
        if isinstance(block, dict) and block.get("type") == "tool_use"
    }
    assert meta["toolUseId"] in dispatch_ids, (meta["toolUseId"], dispatch_ids)
    # The same file also carries the tier binding actually used, which V2 can
    # report without asking the harness anything.
    assert meta["agentType"] and meta["model"]


def test_non_assistant_record_types_are_present_and_carry_no_usage() -> None:
    """A parser must select on type == "assistant" before reading usage: a
    real session interleaves many record types that have none."""
    others = [r for r in _load(ORCHESTRATOR) if r.get("type") != "assistant"]
    assert others, "fixture must exercise the non-assistant record types"
    for r in others:
        message = r.get("message")
        if isinstance(message, dict):
            assert "usage" not in message


def test_no_identity_survived_the_redaction() -> None:
    """Asserts the PROPERTY, never the identities. Naming the strings that
    were scrubbed would reintroduce them into a public repo's source — which
    is the leak this test exists to prevent (third-party-privacy.md)."""
    for path in sorted(FIXTURES.iterdir()):
        text = path.read_text()
        assert "/Users/" not in text, f"{path.name}: a real macOS home path survived"
        # Path characters only: a looser class swallows the trailing backtick
        # of a markdown span and the angle brackets of a `<name>` placeholder,
        # which made this fire on the note's own explanation of itself.
        homes = set(re.findall(r"/home/[A-Za-z0-9._-]+", text))
        assert homes <= {"/home/user"}, f"{path.name}: unexpected home paths {sorted(homes)}"
