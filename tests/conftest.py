"""Shared pytest fixtures."""

import os
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(autouse=True)
def _default_vk_project_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default `VK_DERIO_OPS_PROJECT` for the suite.

    The bridge reads this env var to scope `create_issue` / `list_issues`
    to the right VK project — VK requires it when the MCP server isn't
    running inside a workspace context. Setting it here keeps the
    existing tests' tick() calls transparent. Tests that want to
    exercise the unset path can `monkeypatch.delenv` explicitly.
    """
    monkeypatch.setenv("VK_DERIO_OPS_PROJECT", "test-vk-project-id")


@pytest.fixture(autouse=True)
def _skip_artifact_migration_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the CLI-entry migration gate out of the rest of the suite.

    `fr.cli`'s root callback migrates stale artifacts before every command
    (spec §3.C). In-process `CliRunner` tests and `fr` subprocesses inherit the
    *pytest process's* cwd, so without this the gate resolves super-fr's own
    repo root and refuses ~100 unrelated CLI tests the moment any live plan in
    this repo carries a pre-4.0.0 `fr_version` ceiling — i.e. the suite's
    result would depend on the repo's own artifact state rather than on the
    code under test.

    `FR_SKIP_MIGRATION=1` is the mechanism's own documented bypass, so this is
    using the escape hatch it ships rather than a hole cut for tests.
    `tests/unit/test_migration_trigger.py` owns the gate and deletes this
    variable for the invocations that must see it.
    """
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")


WIDE_TERMINAL_COLUMNS = "200"
"""Terminal width every in-process CLI test renders at (review r5-e15).

Rich wraps to the terminal width, and under `CliRunner` that width comes from
`$COLUMNS` (or a narrow default). So an assertion like
`assert "not under this repo" in result.output` — or any assertion naming a
PATH — passes or fails depending on how long `tmp_path` happens to be on the
machine running the suite: `test_archive_cmd.py::test_archive_refuses_plan_dir_
outside_repo` failed under a long pytest tmp root and passed under a short one.

Pinned here rather than per-test so a new CLI test cannot reintroduce the
fragility by forgetting. It is deliberately WIDE rather than infinite: output
that must survive a NARROW terminal (the `fr run advance` JSON brief) has its
own test that sets `COLUMNS=40` explicitly, and that test still overrides this.
"""


@pytest.fixture(autouse=True)
def _wide_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", WIDE_TERMINAL_COLUMNS)


# The pin above only reaches a console that reads `$COLUMNS` LIVE. rich
# snapshots it into `_width` in `Console.__init__`, and `fr.commands.*` build
# their consoles at import — i.e. at collection, before any fixture — so a
# `COLUMNS` already in the environment then freezes them for the whole session.
# Under `pytest -n auto` on Linux one always is: pytest's capture plugin imports
# `readline` in the main process, GNU readline `setenv`s COLUMNS=80/LINES=24
# behind `os.environ`'s back, and execnet spawns every worker with that C-level
# environment (PR #615's first CI run: four tests wrapped at 80). This conftest
# is imported before any test module, so dropping them here keeps every
# module-level console live. Pinned by test_suite_isolation_inherited_columns.
for _inherited in ("COLUMNS", "LINES"):
    os.environ.pop(_inherited, None)


def uv_tool_bin_dir(env: Mapping[str, str]) -> Path:
    """Where `uv tool install` links executables under `env` — uv's own order:
    `UV_TOOL_BIN_DIR`, `XDG_BIN_HOME`, `$XDG_DATA_HOME/../bin`, `~/.local/bin`."""
    for key in ("UV_TOOL_BIN_DIR", "XDG_BIN_HOME"):
        if env.get(key):
            return Path(env[key])
    if env.get("XDG_DATA_HOME"):
        return Path(env["XDG_DATA_HOME"]).parent / "bin"
    return Path(env.get("HOME") or Path.home()) / ".local" / "bin"


def link_state(path: Path) -> str:
    """What `path` is, as a comparable string: a symlink's target, a file's
    size and mtime, or absent."""
    if path.is_symlink():
        return f"symlink to {os.readlink(path)}"
    if path.exists():
        st = path.stat()
        return f"file {st.st_size} {st.st_mtime_ns}"
    return "absent"


@pytest.fixture(scope="session", autouse=True)
def _operators_fr_survives_the_suite() -> Iterator[None]:
    """gh#683: an install test that isolated `UV_TOOL_DIR` but not
    `UV_TOOL_BIN_DIR` relinked the operator's real `~/.local/bin/fr` into a
    pytest tmpdir, and every host suite run left `fr` dangling. Whatever a test
    installs, the real `fr` link must be exactly as the suite found it."""
    real = uv_tool_bin_dir(os.environ) / "fr"
    before = link_state(real)
    yield
    after = link_state(real)
    assert after == before, (
        f"the suite changed the operator's {real}: was {before}, now {after}. An install "
        "test is missing UV_TOOL_BIN_DIR isolation. Repair: "
        'ln -sf "$(uv tool dir)/fr/bin/fr" ' + str(real)
    )


@pytest.fixture(autouse=True)
def _transcript_root_off_the_operators_machine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Point `fr.run.telemetry` at an empty tmp root for the whole suite.

    V2 telemetry reads the harness's own transcripts, which on a developer
    machine live under `~/.claude/projects` — and this suite frequently runs
    INSIDE a Claude Code session, whose `CLAUDE_CODE_SESSION_ID` is therefore
    set in `os.environ` and inherited by every `CliRunner` invocation. Without
    this, a `fr run resolve` test would read the operator's real transcripts,
    and the result would depend on their machine's session history rather than
    on the code under test.

    `FR_TRANSCRIPT_ROOT` is the module's own documented override, so this uses
    the escape hatch it ships. `tests/unit/test_run_telemetry.py` and the
    measured-status tests set it to a root they built themselves.
    """
    monkeypatch.setenv("FR_TRANSCRIPT_ROOT", str(tmp_path / "no-transcripts-here"))


@pytest.fixture(autouse=True)
def _opencode_db_off_the_operators_machine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The OpenCode half of the fixture above: `fr.run.telemetry.OpenCodeReader`
    reads `~/.local/share/opencode/opencode.db` unless `FR_OPENCODE_DB` says
    otherwise, and a test that completes a step under an OpenCode harness
    signal would otherwise measure the operator's real sessions."""
    monkeypatch.setenv("FR_OPENCODE_DB", str(tmp_path / "no-opencode-db-here.db"))


@pytest.fixture(autouse=True)
def _sessions_dir_off_the_operators_machine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Point session bindings at a tmp dir for the whole suite.

    Same reason as the transcript root above, one step further: `fr run start`
    and `fr isolation up` now bind the ambient `CLAUDE_CODE_SESSION_ID` when no
    `--session` is given (2026-09-21 debug journal, C4). A suite run inside a
    Claude Code session would otherwise write bindings for the OPERATOR's live
    session into `~/.cache/fr/sessions`. Tests that inspect bindings still set
    `FR_SESSIONS_DIR` themselves, which overrides this.
    """
    monkeypatch.setenv("FR_SESSIONS_DIR", str(tmp_path / "sessions-sandbox"))


@pytest.fixture(autouse=True)
def _no_ambient_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the operator's live `CLAUDE_CODE_SESSION_ID` for the whole suite.

    `fr run start`, `fr isolation up` and `down` now default to the ambient
    session (debug journal 2026-09-21 C4), so a suite run INSIDE a Claude Code
    session behaved differently from CI, where no session id exists — found
    when merging main made two `down --all` tests fail locally only. A test
    that needs a session sets one explicitly; nothing inherits the operator's.
    """
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)


@pytest.fixture(autouse=True)
def _fresh_vk_repo_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test with an empty `fr_vk.config` repo cache.

    `fr_vk.config._cache` is a process-global `list_repos` snapshot that
    production clears once per tick. A test that fills it through `tick()` and
    a later one that calls `dispatch_phase` directly (no tick, so no clear)
    used to share it — `test_bridge_e2e.py`'s `{foo, bar}` registry broke
    `test_bridge_lifecycle.py` whenever the order put them together, which
    `pytest -n auto` does. monkeypatch restores the slot afterwards too, so a
    test cannot leak it forward either.
    """
    from fr_vk import config

    monkeypatch.setattr(config, "_cache", None)


@pytest.fixture
def complete_live_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve a live PR body carrying every required section, so a `deliver`
    resolve (or any step emitting `pr`) passes the live-PR check (spec
    2026-09-25 §5.C.4, p3-r2) — the check runs; the PR simply complies."""
    import fr.gh
    from fr.record.pr_body import REQUIRED_SECTIONS

    body = "\n\n".join(f"{h}\n\nNone." for h in REQUIRED_SECTIONS)
    monkeypatch.setattr(fr.gh, "view_pr_body", lambda ref, *, cwd=None: body)
