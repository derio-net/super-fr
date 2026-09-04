"""Shared pytest fixtures."""

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
