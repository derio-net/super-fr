"""The `usage` artifact kind — `docs/superpowers/usage/<run-id>.yaml` (spec §5.B.1-2).

Five properties: the spec's example round-trips; `fr validate artifacts` accepts
a good file and rejects a duplicate key; a re-capture replaces only its own
host's entry; the host label is a hash that carries no name; and — the privacy
allowlist (finding p2-r12) — a capture serializes numbers and ids only, never a
tool call's command or path, a hostname or a URL, whatever the source record
held.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml
from fr.artifacts.registry import ARTIFACT_KINDS, iter_artifact_paths
from fr.artifacts.validate import validate_repo
from fr.usage.file import (
    Capture,
    UsageFile,
    UsageFileError,
    dump_usage,
    host_label,
    parse_usage,
    session_entry,
    upsert_capture,
)
from fr.usage.model import Cost, Message, Tokens, ToolCall, UsageRecord
from fr.usage.rollup import windows_from_cursor

RUN = "2019-03-04-feat-widget"

SPEC_EXAMPLE = f"""schema_version: 1
run: {RUN}
captures:
  - host: h-3f9a2c1e
    harness: claude-code
    mode: host-worktree
    captured_at: '2019-03-04T12:00:00+00:00'
    at: [deliver]
    sessions:
      - session: 11111111-aaaa
        role: main
        models:
          claude-opus-5-5: {{input: 10, cache_write: 20, cache_read: 300, output: 4,
                            usd: 1.5, usd_source: exact}}
        activity:
          paperwork: {{usd: 0.5, turns: 3}}
          implementation: {{usd: 1.0, turns: 2}}
        steps:
          brainstorm: {{usd: 1.5, turns: 5}}
        briefs:
          phase/1/implement-phase: 347
      - session: 22222222-bbbb
        unavailable: transcript pruned
"""


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_usage_is_a_registered_kind_at_version_one() -> None:
    kind = ARTIFACT_KINDS["usage"]
    assert kind.current_version == 1
    assert kind.locator == "docs/superpowers/usage/*.yaml"


def test_the_spec_example_round_trips() -> None:
    parsed = parse_usage(SPEC_EXAMPLE)
    assert parsed.run == RUN
    assert parsed.captures[0].sessions[0].models["claude-opus-5-5"].cache_read == 300
    assert parsed.captures[0].sessions[1].unavailable == "transcript pruned"
    again = parse_usage(dump_usage(parsed))
    assert again == parsed


def test_validate_artifacts_accepts_a_usage_file(tmp_path: Path) -> None:
    _write(tmp_path, f"docs/superpowers/usage/{RUN}.yaml", SPEC_EXAMPLE)
    assert list(iter_artifact_paths(tmp_path, "usage"))
    report = validate_repo(tmp_path)
    assert report.ok, [str(i) for i in report.issues]


def test_validate_artifacts_rejects_a_duplicate_key(tmp_path: Path) -> None:
    doubled = SPEC_EXAMPLE.replace("    at: [deliver]\n", "    at: [deliver]\n    at: [closeout]\n")
    _write(tmp_path, f"docs/superpowers/usage/{RUN}.yaml", doubled)
    report = validate_repo(tmp_path)
    assert not report.ok
    assert any("duplicate" in str(i) for i in report.issues if i.kind == "usage")


def test_two_captures_from_one_host_are_invalid() -> None:
    data = yaml.safe_load(SPEC_EXAMPLE)
    data["captures"].append(dict(data["captures"][0], at=["closeout"]))
    with pytest.raises(UsageFileError):
        parse_usage(yaml.safe_dump(data))


def test_a_host_label_that_names_a_host_is_invalid() -> None:
    with pytest.raises(UsageFileError):
        parse_usage(SPEC_EXAMPLE.replace("h-3f9a2c1e", "laptop.corp.example"))


def _capture(host: str, at: str, session: str) -> Capture:
    return Capture.model_validate(
        {
            "host": host,
            "harness": "claude-code",
            "mode": "host-worktree",
            "captured_at": "2019-03-04T12:00:00+00:00",
            "at": [at],
            "sessions": [{"session": session, "unavailable": "x"}],
        }
    )


def test_upsert_replaces_only_the_same_hosts_entry() -> None:
    base = UsageFile(run=RUN)
    a, b = host_label(RUN, "alpha"), host_label(RUN, "beta")
    one = upsert_capture(base, _capture(a, "deliver", "s1"))
    two = upsert_capture(one, _capture(b, "resolve:review", "s2"))
    three = upsert_capture(two, _capture(a, "closeout", "s3"))
    assert [c.host for c in three.captures] == [a, b]
    assert three.captures[0].at == ("closeout",)  # upsert replaces; capture() merges
    assert three.captures[0].sessions[0].session == "s3"
    assert three.captures[1] == two.captures[1]


def test_host_label_is_a_prefix_of_the_sha256_of_run_and_hostname() -> None:
    digest = hashlib.sha256((RUN + "laptop.corp.example").encode()).hexdigest()[:8]
    assert host_label(RUN, "laptop.corp.example") == f"h-{digest}"
    assert host_label(RUN, "a") != host_label("other-run", "a")


def test_a_capture_serializes_no_host_url_path_or_content() -> None:
    """p2-r12: a `UsageRecord` carries raw tool-call targets — commands and
    paths. The file is an ALLOWLIST projection: nothing of them survives."""
    hostname = "laptop.corp.example"
    record = UsageRecord(
        session="33333333-cccc",
        harness="claude-code",
        messages=(
            Message(
                ts="2019-03-04T00:30:00Z",
                model="claude-opus-5-5",
                tokens=Tokens(input=5, output=7, cache_read=11),
                tool_calls=(
                    ToolCall(name="Bash", target=f"ssh {hostname} cat ~/.aws/credentials"),
                    ToolCall(name="Read", target="/Users/someone/secret/notes.md"),
                    ToolCall(name="Bash", target="curl https://billing.example.com/v1"),
                ),
            ),
        ),
        cost=Cost(usd=0.25, source="exact", by_model={"claude-opus-5-5": 0.25}),
    )
    windows = windows_from_cursor(
        {"started": "2019-03-04T00:00:00Z", "steps": {"brainstorm": {"at": "2019-03-04T01:00Z"}}}
    )
    capture = Capture(
        host=host_label(RUN, hostname),
        harness="claude-code",
        mode="host-worktree",
        captured_at="2019-03-04T12:00:00+00:00",
        at=("deliver",),
        sessions=(session_entry(record, windows),),
    )
    text = dump_usage(upsert_capture(UsageFile(run=RUN), capture))
    for needle in (hostname, "corp", "http", "/Users", "~/", "credentials", "notes.md"):
        assert needle not in text, f"{needle!r} leaked into the usage file"
    parsed = parse_usage(text)
    entry = parsed.captures[0].sessions[0]
    assert entry.models["claude-opus-5-5"].output == 7
    assert entry.models["claude-opus-5-5"].usd == pytest.approx(0.25)
    assert entry.steps["brainstorm"].turns == 1
    assert sum(f.usd or 0 for f in entry.activity.values()) == pytest.approx(0.25)


def test_at_is_a_non_empty_list_of_distinct_capture_events() -> None:
    """p2-r29: `at` records every capture event from the host, in order."""
    parsed = parse_usage(SPEC_EXAMPLE.replace("at: [deliver]", "at: [deliver, closeout]"))
    assert parsed.captures[0].at == ("deliver", "closeout")
    for bad in ("at: deliver", "at: []", "at: [deliver, deliver]", "at: [deliver, nope]"):
        with pytest.raises(UsageFileError):
            parse_usage(SPEC_EXAMPLE.replace("at: [deliver]", bad))
