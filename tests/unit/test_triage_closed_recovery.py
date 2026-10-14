"""Public recovery seam, disposable state, no actual terminal clients."""

import pytest
from fr.triage.batch import last_dispatch
from fr.triage.model import load_judgements
from fr_dispatch.protocols import ReplacementResult

from tests.unit.test_triage_batch_replace import env as replacement_env
from tests.unit.test_triage_batch_replace import invoke


@pytest.fixture
def env(tmp_path, monkeypatch):
    return replacement_env.__wrapped__(tmp_path, monkeypatch)


def test_recovery_preview(env):
    path = env[0] / "judgements.yaml"
    before = path.read_bytes()
    result = invoke(
        env, "--recover", "--harness", "opencode", "--model", "openai/new", "--reason", "closed"
    )
    assert result.exit_code == 0, result.output
    assert "HOLD" in result.output
    assert path.read_bytes() == before
    assert env[3].calls == ["inspect"]
    assert env[2].request.recover


@pytest.mark.parametrize(
    "args", [[], ["--model", "openai/new"], ["--harness", "claude", "--model", "new"], ["--repair"]]
)
def test_recovery_explicit_intent_required(env, args):
    result = invoke(env, "--recover", "--reason", "closed", *args, "--yes")
    assert result.exit_code == 2
    assert "execute" not in env[3].calls


def test_recovery_success_preserves_lifecycle_and_changes_owner(env):
    from fr.triage.batch import effective_handle

    path = env[0] / "judgements.yaml"
    original = load_judgements(path).batches[0]
    env[3].result = ReplacementResult(
        True, "uptake-confirmed", "target", pane="fresh", session="ses_fresh"
    )
    result = invoke(
        env,
        "--recover",
        "--harness",
        "opencode",
        "--model",
        "openai/new",
        "--reason",
        "closed",
        "--yes",
    )
    assert result.exit_code == 0, result.output
    b = load_judgements(path).batches[0]
    assert last_dispatch(b) == last_dispatch(original)
    assert b.ids == original.ids and b.wave == original.wave and b.after == original.after
    assert effective_handle(b) == "fresh"
    assert b.events[-1].session == "ses_fresh"
    assert b.events[-1].pane == "p1"
    # Ordinary replacement now addresses the successful owner, not the old dispatch.
    result = invoke(env, "--model", "openai/next", "--reason", "change")
    assert result.exit_code == 0, result.output
    assert env[2].request.pane == "fresh"


def test_same_model_recovery_is_not_noop(env):
    from fr.triage.batch import save_batches
    from fr.triage.model import Launch

    path = env[0] / "judgements.yaml"
    j = load_judgements(path)
    b = j.batches[0].model_copy(
        update={"launch": Launch(runner="herdr", harness="opencode", model="openai/new")}
    )
    save_batches(path, [b], read=j.batches)
    result = invoke(
        env, "--recover", "--harness", "opencode", "--model", "openai/new", "--reason", "closed"
    )
    assert result.exit_code == 0, result.output


def test_effective_owner_ignores_failure_and_old_dispatch_success():
    from fr.triage.batch import effective_handle

    from tests.unit.test_triage_replacement_events import audit, batch

    b = batch()
    original = last_dispatch(b)
    success = audit("success").model_copy(
        update={"recover": True, "target_pane": "fresh", "session": "ses_new"}
    )
    b = b.model_copy(update={"events": [original, success, audit("failure")]})
    assert effective_handle(b) == "fresh"
    b = b.model_copy(
        update={"events": [*b.events, original.model_copy(update={"handle": "later-dispatch"})]}
    )
    assert effective_handle(b) == "later-dispatch"


def test_old_audit_schema_defaults_and_new_metadata_stamp():
    from fr.triage.model import Judgements
    from pydantic import ValidationError

    from tests.unit.test_triage_replacement_events import audit, batch

    b = batch().model_copy(update={"events": [audit("success")]})
    data = {
        "schema": 11,
        "tiers": [{"n": 1, "title": "Now"}],
        "issues": {"repo#1": {"tier": 1}},
        "batches": [b],
    }
    assert Judgements.model_validate(data).batches[0].events[0].target_pane is None
    data["batches"] = [
        b.model_copy(update={"events": [audit("success").model_copy(update={"recover": True})]})
    ]
    with pytest.raises(ValidationError, match="schema 12"):
        Judgements.model_validate(data)


def test_live_scope_driver_refuses_before_effects(env):
    import json
    import os

    path = env[0] / "judgements.yaml"
    before = path.read_bytes()
    (env[0] / "drive.lock").write_text(json.dumps({"pid": os.getpid(), "started": "fixture"}))
    result = invoke(
        env,
        "--recover",
        "--harness",
        "opencode",
        "--model",
        "openai/new",
        "--reason",
        "closed",
        "--yes",
    )
    assert result.exit_code == 2 and "driver" in result.output, result.output
    assert path.read_bytes() == before and "prepare" not in env[3].calls


@pytest.mark.parametrize("pane,session", [(None, None), ("pane-1", "ses_new"), ("fresh", None)])
def test_recovery_success_requires_actual_new_ownership(pane, session):
    from fr.triage.model import ReplacementEvent
    from pydantic import ValidationError

    from tests.unit.test_triage_replacement_events import audit

    raw = {
        **audit("success").model_dump(),
        "recover": True,
        "target_pane": pane,
        "session": session,
    }
    with pytest.raises(ValidationError, match="actual pane"):
        ReplacementEvent.model_validate(raw)
