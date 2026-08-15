"""Unit tests for `fr_cncd.runner.CncdRunner` — config + the non-HTTP
protocol methods (cnc-fr spec 2026-07-02, §3.5).

Config mirrors VkRunner's env convention: `CNCD_URL` is the base URL of
the cncd server (explicit `base_url=` wins), `CNCD_SLOT_BUDGET`
optionally caps per-tick dispatches. `preflight(items)` fails every
eligible phase cleanly when unset — same contract the VK runner has for
its project id.

Dedup is deliberately server-side: cncd's ingest is idempotent by
content hash (spec §3.3), so `existing_dispatches()` is honestly empty
and a re-POST after a lost GH synced-stamp is a no-op, not a duplicate.

**v2 (2026-08-14 workflow-shapes spec §4.D).** `preflight` takes the
tick's `items` (config-only here — cncd's preflight never inspects
them, unlike VK's title-to-id dedup mapping); `can_dispatch(item)`
replaces `can_dispatch_repo(repo)`; `dedup_key` is gone (identity lives
on `WorkItem.id`, and cncd never used its own dedup_key for anything —
dedup is server-side).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_cncd_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CNCD_URL", raising=False)
    monkeypatch.delenv("CNCD_SLOT_BUDGET", raising=False)


def _item(repo: str = "agentic-stoa/cnc-demo", issue_number: int = 42):
    """A minimal phase-unit WorkItem — enough for `can_dispatch`."""
    from fr_dispatch.work_item import WorkItem, item_id, parent_id

    iid = item_id(repo, "some-spec", "some-plan", phase=1)
    return WorkItem(
        id=iid,
        unit="phase",
        workflow="fr-goal",
        repo=repo,
        parent=parent_id(iid),
        inputs=(),
        payload={"issue_number": issue_number},
        tracking=f"https://github.com/{repo}/issues/{issue_number}",
    )


def test_runner_name_is_cncd():
    from fr_cncd import CncdRunner

    assert CncdRunner.name == "cncd"


def test_satisfies_runner_protocol():
    from fr_cncd import CncdRunner
    from fr_dispatch.protocols import Runner

    runner: Runner = CncdRunner(base_url="http://localhost:8787")
    assert runner.name == "cncd"


def test_declares_capabilities():
    from fr_cncd import CncdRunner

    assert CncdRunner.capabilities == frozenset({"git", "tests", "scm"})


def test_preflight_fails_cleanly_without_cncd_url():
    from fr_cncd import CncdRunner

    blocker = CncdRunner().preflight([])
    assert blocker is not None
    assert "CNCD_URL" in blocker


def test_preflight_ok_with_env(monkeypatch):
    from fr_cncd import CncdRunner

    monkeypatch.setenv("CNCD_URL", "http://cncd.local:8787")
    runner = CncdRunner()
    assert runner.preflight([]) is None
    assert runner.base_url == "http://cncd.local:8787"


def test_preflight_ignores_items_content(monkeypatch):
    """cncd's preflight is config-only — unlike VK, it never inspects the
    items it's handed (no title-to-id mapping to build)."""
    from fr_cncd import CncdRunner

    monkeypatch.setenv("CNCD_URL", "http://cncd.local:8787")
    runner = CncdRunner()
    assert runner.preflight([_item(), _item(issue_number=43)]) is None


def test_explicit_base_url_beats_env(monkeypatch):
    from fr_cncd import CncdRunner

    monkeypatch.setenv("CNCD_URL", "http://from-env:1")
    assert CncdRunner(base_url="http://explicit:2").base_url == "http://explicit:2"


def test_base_url_trailing_slash_normalized():
    from fr_cncd import CncdRunner

    assert CncdRunner(base_url="http://cncd.local:8787/").base_url == "http://cncd.local:8787"


def test_no_dedup_key_method():
    """`dedup_key` is gone — identity lives on `WorkItem.id` now."""
    from fr_cncd import CncdRunner

    assert not hasattr(CncdRunner, "dedup_key")


def test_existing_dispatches_empty_server_side_idempotence():
    from fr_cncd import CncdRunner

    assert CncdRunner(base_url="http://x").existing_dispatches() == set()


def test_can_dispatch_any_repo():
    from fr_cncd import CncdRunner

    runner = CncdRunner(base_url="http://x")
    assert runner.can_dispatch(_item("agentic-stoa/cnc-demo")) is True
    assert runner.can_dispatch(_item("some/other")) is True


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
