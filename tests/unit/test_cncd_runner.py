"""Unit tests for `fr_cncd.runner.CncdRunner` — config + the non-HTTP
protocol methods (cnc-fr spec 2026-07-02, §3.5).

Config mirrors VkRunner's env convention: `CNCD_URL` is the base URL of
the cncd server (explicit `base_url=` wins), `CNCD_SLOT_BUDGET`
optionally caps per-tick dispatches. `preflight()` fails every eligible
phase cleanly when unset — same contract the VK runner has for its
project id.

Dedup is deliberately server-side: cncd's ingest is idempotent by
content hash (spec §3.3), so `existing_dispatches()` is honestly empty
and a re-POST after a lost GH synced-stamp is a no-op, not a duplicate.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_cncd_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CNCD_URL", raising=False)
    monkeypatch.delenv("CNCD_SLOT_BUDGET", raising=False)


def test_runner_name_is_cncd():
    from fr_cncd import CncdRunner

    assert CncdRunner.name == "cncd"


def test_satisfies_runner_protocol():
    from fr_cncd import CncdRunner
    from fr_dispatch.protocols import Runner

    runner: Runner = CncdRunner(base_url="http://localhost:8787")
    assert runner.name == "cncd"


def test_preflight_fails_cleanly_without_cncd_url():
    from fr_cncd import CncdRunner

    blocker = CncdRunner().preflight()
    assert blocker is not None
    assert "CNCD_URL" in blocker


def test_preflight_ok_with_env(monkeypatch):
    from fr_cncd import CncdRunner

    monkeypatch.setenv("CNCD_URL", "http://cncd.local:8787")
    runner = CncdRunner()
    assert runner.preflight() is None
    assert runner.base_url == "http://cncd.local:8787"


def test_explicit_base_url_beats_env(monkeypatch):
    from fr_cncd import CncdRunner

    monkeypatch.setenv("CNCD_URL", "http://from-env:1")
    assert CncdRunner(base_url="http://explicit:2").base_url == "http://explicit:2"


def test_base_url_trailing_slash_normalized():
    from fr_cncd import CncdRunner

    assert CncdRunner(base_url="http://cncd.local:8787/").base_url == "http://cncd.local:8787"


def test_dedup_key_is_repo_hash_issue():
    from fr_cncd import CncdRunner

    runner = CncdRunner(base_url="http://x")
    assert runner.dedup_key("agentic-stoa/cnc-demo", 42) == "agentic-stoa/cnc-demo#42"


def test_existing_dispatches_empty_server_side_idempotence():
    from fr_cncd import CncdRunner

    assert CncdRunner(base_url="http://x").existing_dispatches() == set()


def test_can_dispatch_any_repo():
    from fr_cncd import CncdRunner

    runner = CncdRunner(base_url="http://x")
    assert runner.can_dispatch_repo("agentic-stoa/cnc-demo") is True
    assert runner.can_dispatch_repo("some/other") is True


def test_slot_budget_default_and_env_override(monkeypatch):
    from fr_cncd import CncdRunner
    from fr_cncd.runner import DEFAULT_SLOT_BUDGET

    runner = CncdRunner(base_url="http://x")
    assert runner.slot_budget() == DEFAULT_SLOT_BUDGET
    monkeypatch.setenv("CNCD_SLOT_BUDGET", "3")
    assert runner.slot_budget() == 3


def test_refresh_is_a_noop():
    from fr_cncd import CncdRunner

    CncdRunner(base_url="http://x").refresh()  # must not raise
