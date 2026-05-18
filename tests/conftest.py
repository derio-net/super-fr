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
