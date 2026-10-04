"""Characterisation: herdr takes the wave driver's close-out item unchanged
(wave-driver spec §C, Test Plan 7).

The close-out reuses unit `run` with `payload.kind: closeout` and item id
`<repo>/run/closeout-<batch-id>`. These tests pin that `fr_herdr` needs no change
for it: the agent name is unique per batch and stable, `can_dispatch` ignores
`payload.kind`, and `dispatch` takes the model and checkout from the payload the
driver fills from `resolve_launch` and the `--checkout` map. herdr itself is
faked at `_run_herdr`, as in `test_fr_herdr_runner.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fr.commands.triage_batch_cmd import _closeout_item
from fr.triage.batch_drive import closeout_item_id
from fr.triage.model import Batch, Launch
from fr_herdr.runner import HerdrRunner, agent_name

from tests.unit.test_fr_herdr_runner import AGENT_NAME, _Herdr

REPO = "example-org/alpha"


@pytest.fixture
def herdr(monkeypatch: pytest.MonkeyPatch) -> _Herdr:
    from fr_herdr import runner as herdr_runner

    fake = _Herdr()
    monkeypatch.setattr(herdr_runner, "_run_herdr", fake)
    monkeypatch.setattr(herdr_runner.shutil, "which", lambda name: "/usr/local/bin/herdr")
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("HERDR_WORKSPACE_ID", "w2")
    return fake


def _batch(bid: str, **kw: Any) -> Batch:
    events = [
        {"kind": "dispatch", "at": "2026-10-01T10:00:00Z", "runner": "herdr", "handle": "h",
         "branch": f"feat/batch-{bid}"},
    ]  # fmt: skip
    return Batch.model_validate(
        {"id": bid, "title": bid, "ids": ["alpha#1"], "events": events, **kw}
    )


def _closeout(bid: str, *, model: str = "orchestrator-model", checkout: str = "/work/alpha") -> Any:
    launch = Launch(runner="herdr", harness="claude", model=model)
    return _closeout_item(REPO, _batch(bid), launch, run="r-1", checkout=Path(checkout))


def test_the_closeout_agent_name_is_stable_and_unique_per_batch() -> None:
    a, b = closeout_item_id(REPO, "lifecycle"), closeout_item_id(REPO, "lifecycle-two")
    assert agent_name(a) == agent_name(a)
    assert agent_name(a) != agent_name(b)
    # and never the name of the batch's own run tab
    assert agent_name(a) != agent_name(f"{REPO}/run/batch-lifecycle")
    long_a = closeout_item_id(REPO, "a-very-long-batch-identifier-one")
    long_b = closeout_item_id(REPO, "a-very-long-batch-identifier-two")
    assert agent_name(long_a) != agent_name(long_b)
    assert all(AGENT_NAME.match(agent_name(i)) for i in (a, b, long_a, long_b))


def test_can_dispatch_accepts_a_closeout_item(herdr: _Herdr) -> None:
    item = _closeout("lifecycle")
    assert item.payload["kind"] == "closeout"
    assert item.id == f"{REPO}/run/closeout-lifecycle"
    assert HerdrRunner.from_env().can_dispatch(item)


def test_dispatch_takes_model_and_checkout_from_the_payload(herdr: _Herdr) -> None:
    item = _closeout("lifecycle", model="m-orchestrator", checkout="/clones/alpha")
    HerdrRunner.from_env().dispatch(item)
    text = herdr.text()
    assert "--cwd /clones/alpha" in text
    assert "--model m-orchestrator" in text
    assert f"--label {item.id}" in text
    assert "fr pickup --run r-1" in text
