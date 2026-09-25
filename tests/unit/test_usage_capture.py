"""Usage capture at deliver, at a new host's first resolve, and at archive (spec §5.B.3).

Capture rides calls that already happen, costs no inference, commits in the
SAME commit as the cursor move, and never fails its step.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.usage.file import archived_usage_path, host_label, load_usage, usage_path
from typer.testing import CliRunner

from tests.unit.test_run_cli import _repo, _write_shape

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "usage"
CC_SESSION = "145101c9-bdfc-4f5d-a8be-617eeced7485"
RUN = "r1"

SHAPE = """
workflow: capture
schema: 1
unit: run
steps:
  - id: brainstorm
    kind: agent
    emits: [spec]
  - id: plan
    kind: agent
    needs: [spec]
    emits: [plan]
  - id: review
    kind: agent
  - id: deliver
    kind: agent
    needs: [spec, plan]
    emits: [pr]
"""

EMITS = {
    "brainstorm": ["--emitted", "spec=docs/superpowers/specs/2026-09-30-fixture-design.md"],
    "plan": ["--emitted", "plan=docs/superpowers/plans/2026-09-30-fixture"],
    "review": [],
    "deliver": ["--emitted", "pr=https://github.com/derio-net/super-fr/pull/1"],
}


@pytest.fixture
def transcripts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "projects"
    project = root / "-work-example"
    project.mkdir(parents=True)
    shutil.copy(FIXTURES / "claude-code" / f"{CC_SESSION}.jsonl", project)
    shutil.copytree(FIXTURES / "claude-code" / CC_SESSION, project / CC_SESSION)
    monkeypatch.setenv("FR_TRANSCRIPT_ROOT", str(root))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", CC_SESSION)
    monkeypatch.setenv("FR_HARNESS", "claude-code")
    monkeypatch.setenv("FR_HOSTNAME", "laptop.corp.example")
    return root


def _invoke(repo: Path, shipped: Path, argv: list[str], **extra: str):
    env = {
        **os.environ,
        "VK_REPO_ROOT": str(repo),
        "FR_SHIPPED_WORKFLOWS_DIR": str(shipped),
        **extra,
    }
    return CliRunner().invoke(app, argv, env=env)


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "capture", SHAPE)
    spec_dir = repo / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "2026-09-30-fixture-design.md").write_text("# Fixture\n")
    plan_dir = repo / "docs" / "superpowers" / "plans" / "2026-09-30-fixture"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "_meta.yaml").write_text("plan: 2026-09-30-fixture\n")
    started = _invoke(repo, shipped, ["run", "start", "capture", "--branch", "b", "--run-id", RUN])
    assert started.exit_code == 0, started.output
    return repo, shipped


def _step(repo: Path, shipped: Path, step: str, **extra: str):
    advanced = _invoke(repo, shipped, ["run", "advance", RUN], **extra)
    assert advanced.exit_code == 0, advanced.output
    return _invoke(
        repo,
        shipped,
        ["run", "resolve", RUN, "--step", step, "--state", "done", *EMITS[step]],
        **extra,
    )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def test_resolving_deliver_captures_every_readable_session_in_the_cursors_commit(
    tmp_path: Path, transcripts: Path
) -> None:
    repo, shipped = _setup(tmp_path)
    for step in ("brainstorm", "plan", "review"):
        assert _step(repo, shipped, step).exit_code == 0
    result = _step(repo, shipped, "deliver")
    assert result.exit_code == 0, result.output

    usage = load_usage(usage_path(repo, RUN))
    assert usage is not None
    # p2-r29: one capture per host, every capture event from it kept in order
    assert [c.at for c in usage.captures] == [("resolve:brainstorm", "deliver")]
    capture = usage.captures[0]
    assert capture.host == host_label(RUN, "laptop.corp.example")
    assert capture.mode == "host-worktree"
    assert capture.harness == "claude-code"
    sessions = {s.session: s for s in capture.sessions}
    assert CC_SESSION in sessions and sessions[CC_SESSION].unavailable is None
    assert sessions[CC_SESSION].models

    # the SAME commit as the cursor move, and nothing left over
    changed = _git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert f"docs/superpowers/usage/{RUN}.yaml" in changed
    assert f"docs/superpowers/runs/{RUN}.yaml" in changed
    assert (
        _git(repo, "status", "--porcelain", "--", "docs/superpowers/usage", "docs/superpowers/runs")
        == ""
    )
    assert "laptop.corp.example" not in usage_path(repo, RUN).read_text()


def test_capture_records_each_dispatch_brief_under_the_unit_that_claimed_it(
    tmp_path: Path, transcripts: Path
) -> None:
    """p2-r24: `briefs` is filled from the transcript — the dispatch prompt's
    size, keyed by the cursor unit whose attempt names that agent."""
    from fr.run.model import load_run_state

    repo, shipped = _setup(tmp_path)
    assert _invoke(repo, shipped, ["run", "advance", RUN]).exit_code == 0
    claimed = _invoke(
        repo, shipped, ["run", "claim", RUN, "--step", "brainstorm", "--agent", "af7cb1e9fc08366c6"]
    )
    assert claimed.exit_code == 0, claimed.output
    resolved = _invoke(
        repo,
        shipped,
        ["run", "resolve", RUN, "--step", "brainstorm", "--state", "done", *EMITS["brainstorm"]],
    )
    assert resolved.exit_code == 0, resolved.output
    (unit,) = [
        key
        for key, record in (load_run_state(repo, RUN).steps["brainstorm"].units or {}).items()
        if any(a.agent == "af7cb1e9fc08366c6" for a in record.attempts)
    ]

    usage = load_usage(usage_path(repo, RUN))
    assert usage is not None
    entry = next(s for s in usage.captures[0].sessions if s.session == CC_SESSION)
    assert entry.briefs == {unit: 2480, "toolu_01UnnGBPuZbTDsutzsmhochi": 96}


def test_a_new_hosts_first_resolve_appends_its_capture_and_a_known_host_adds_nothing(
    tmp_path: Path, transcripts: Path
) -> None:
    repo, shipped = _setup(tmp_path)
    assert _step(repo, shipped, "brainstorm").exit_code == 0
    first = load_usage(usage_path(repo, RUN))
    assert first is not None and [c.at for c in first.captures] == [("resolve:brainstorm",)]

    assert _step(repo, shipped, "plan", FR_HOSTNAME="pod-7.example").exit_code == 0
    second = load_usage(usage_path(repo, RUN))
    assert second is not None
    assert [c.at for c in second.captures] == [("resolve:brainstorm",), ("resolve:plan",)]
    assert second.captures[1].host == host_label(RUN, "pod-7.example")
    before = usage_path(repo, RUN).read_bytes()

    assert _step(repo, shipped, "review", FR_HOSTNAME="pod-7.example").exit_code == 0
    assert usage_path(repo, RUN).read_bytes() == before


def test_a_reader_that_raises_is_unavailable_and_the_resolve_still_succeeds(
    tmp_path: Path, transcripts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.usage import readers

    class Boom:
        def read(self, source: Path, session: str | None = None):
            raise RuntimeError("reader exploded")

    monkeypatch.setitem(readers.READERS, "claude-code", Boom())  # type: ignore[index]
    repo, shipped = _setup(tmp_path)
    for step in ("brainstorm", "plan", "review"):
        assert _step(repo, shipped, step).exit_code == 0
    result = _step(repo, shipped, "deliver")
    assert result.exit_code == 0, result.output
    usage = load_usage(usage_path(repo, RUN))
    assert usage is not None
    entry = next(s for s in usage.captures[0].sessions if s.session == CC_SESSION)
    assert entry.unavailable


def test_a_readers_exception_text_never_reaches_the_committed_file(
    tmp_path: Path, transcripts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p2-r21: a reader that catches its own failure reports the exception's
    text — paths, usernames. The committed projection maps it to a closed
    vocabulary (`reader failed: <ExcType>`), never the text."""
    from fr.run import telemetry

    def denied(path: Path):
        raise PermissionError(13, "Permission denied", "/Users/someone/secret/t.jsonl")

    monkeypatch.setattr(telemetry, "_read_records", denied)
    repo, shipped = _setup(tmp_path)
    for step in ("brainstorm", "plan", "review"):
        assert _step(repo, shipped, step).exit_code == 0
    assert _step(repo, shipped, "deliver").exit_code == 0

    text = usage_path(repo, RUN).read_text()
    assert "/Users/" not in text and "someone" not in text
    usage = load_usage(usage_path(repo, RUN))
    assert usage is not None
    entry = next(s for s in usage.captures[0].sessions if s.session == CC_SESSION)
    assert entry.unavailable == "reader failed: PermissionError"


@pytest.mark.parametrize(
    ("reason", "committed"),
    [
        (
            "PermissionError: [Errno 13] Permission denied: '/Users/x/a'",
            "reader failed: PermissionError",
        ),
        (
            "OpenCode database unreadable: unable to open /home/x/db",
            "reader failed: database unreadable",
        ),
        ("Hermes database unreadable: /home/x/state.db", "reader failed: database unreadable"),
        ("unreadable transcript: abc.jsonl", "reader failed: unreadable transcript"),
        ("unreadable subagent transcript: agent-1.jsonl", "reader failed: unreadable transcript"),
        ("reader failed: RuntimeError", "reader failed: RuntimeError"),
        (
            "no transcript found for this session on this host",
            "no transcript found for this session on this host",
        ),
        ("session not in the OpenCode database", "session not in the OpenCode database"),
        ("something nobody anticipated at /Users/x", "reader failed"),
    ],
)
def test_the_committed_unavailable_reason_is_a_closed_vocabulary(
    reason: str, committed: str
) -> None:
    from fr.usage.file import committed_reason

    assert committed_reason(reason) == committed


def test_the_acp_constant_is_kept_verbatim() -> None:
    from fr.usage.file import committed_reason
    from fr.usage.readers.hermes import ACP_ZERO_TOKENS

    assert committed_reason(ACP_ZERO_TOKENS) == ACP_ZERO_TOKENS


def test_a_corrupt_usage_file_never_fails_the_resolve(tmp_path: Path, transcripts: Path) -> None:
    repo, shipped = _setup(tmp_path)
    path = usage_path(repo, RUN)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("captures: [not, a, mapping\n")
    result = _step(repo, shipped, "brainstorm")
    assert result.exit_code == 0, result.output
    assert path.read_text() == "captures: [not, a, mapping\n"


def test_archive_captures_the_closeout_session_and_moves_the_file(
    tmp_path: Path, transcripts: Path
) -> None:
    from fr.archive import _archive_run

    repo, shipped = _setup(tmp_path)
    for step in ("brainstorm", "plan", "review", "deliver"):
        assert _step(repo, shipped, step, CLAUDE_CODE_SESSION_ID="deliver-session").exit_code == 0

    _archive_run(repo, Path("docs/superpowers/plans/2026-09-30-fixture"))

    assert not usage_path(repo, RUN).exists()
    archived = load_usage(archived_usage_path(repo, RUN))
    assert archived is not None
    capture = archived.captures[0]
    # p2-r29: closeout merges into the host's capture, never erasing deliver
    assert capture.at == ("resolve:brainstorm", "deliver", "closeout")
    by_id = {s.session: s for s in capture.sessions}
    assert by_id[CC_SESSION].unavailable is None, "the closeout session is captured"
    assert "deliver-session" in by_id, "the delivering session is kept"
    staged = _git(repo, "diff", "--cached", "--name-only").split()
    assert f"docs/superpowers/implemented/usage/{RUN}.yaml" in staged
