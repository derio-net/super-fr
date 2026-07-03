"""FakeGhClient remote read surface (list_dir / read_file) — the contents-API
test double backing the cross-repo spec-status resolution (#339)."""

from __future__ import annotations

import pytest

from tests.unit.fakes import FakeGhClient, FakeGhError


def _preload() -> FakeGhClient:
    gh = FakeGhClient()
    base = "docs/superpowers/plans/p"
    gh.remote_tree = {
        ("owner/repo", f"{base}/_meta.yaml"): "schema_version: 2\n",
        ("owner/repo", f"{base}/01.yaml"): "phase:\n  number: 1\n",
        ("owner/repo", f"{base}/_prose.md"): "# prose\n",
    }
    return gh


def test_list_dir_returns_child_names() -> None:
    gh = _preload()
    names = gh.list_dir("owner/repo", "docs/superpowers/plans/p")
    assert sorted(names) == ["01.yaml", "_meta.yaml", "_prose.md"]


def test_list_dir_absent_is_empty() -> None:
    gh = _preload()
    assert gh.list_dir("owner/repo", "docs/superpowers/plans/nope") == []
    assert gh.list_dir("other/repo", "docs/superpowers/plans/p") == []


def test_read_file_returns_content() -> None:
    gh = _preload()
    assert gh.read_file("owner/repo", "docs/superpowers/plans/p/01.yaml") == "phase:\n  number: 1\n"


def test_read_file_absent_raises() -> None:
    gh = _preload()
    with pytest.raises(FakeGhError):
        gh.read_file("owner/repo", "docs/superpowers/plans/p/99.yaml")


def test_calls_recorded() -> None:
    gh = _preload()
    gh.list_dir("owner/repo", "docs/superpowers/plans/p")
    gh.read_file("owner/repo", "docs/superpowers/plans/p/01.yaml")
    methods = [name for name, _ in gh.calls]
    assert "list_dir" in methods and "read_file" in methods
