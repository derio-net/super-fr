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
