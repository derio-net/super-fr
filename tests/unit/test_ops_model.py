"""The op model and its legacy reader (spec 2026-10-22-fr-ops R1, R2, §A)."""

from __future__ import annotations

import pytest
from fr.ops.model import LegacyOp, Op, UndoNone
from pydantic import ValidationError

FULL: dict[str, object] = {
    "id": "seal-secret",
    "summary": "Seal the CI secret",
    "phase": "pre-merge",
    "needs": ["create-key"],
    "check": "test -s secrets/ci.enc",
    "na_if": 'test -n "$NO_CI"',
    "apply": "fr ops seal --encrypt 'sops -e {in} > {out}' --target secrets/ci.enc",
    "undo": "git checkout secrets/ci.enc",
    "mutating": True,
    "interactive": True,
    "side_effects": ["rewrites secrets/ci.enc"],
    "identities": ["admin", "reader"],
    "ready": "curl -fsS https://example.com/ready",
    "disables": "nightly backups silently stop",
    "escalate": "test -e /tmp/breach",
    "vacuous_if": "the file exists but is empty",
    "commands": ["sops -e secrets/ci.yaml"],
    "verify": "the file decrypts",
}


def test_an_op_needs_id_summary_and_phase() -> None:
    op = Op.model_validate({"id": "a", "summary": "s", "phase": "post-merge"})
    assert op.needs == () and op.check is None and not op.mutating and not op.interactive
    for missing in ("id", "summary", "phase"):
        data = {"id": "a", "summary": "s", "phase": "post-merge"}
        del data[missing]
        with pytest.raises(ValidationError, match=missing):
            Op.model_validate(data)


def test_an_op_refuses_an_unknown_phase() -> None:
    with pytest.raises(ValidationError):
        Op.model_validate({"id": "a", "summary": "s", "phase": "whenever"})


def test_an_op_accepts_every_optional_r1_field() -> None:
    op = Op.model_validate(FULL)
    assert op.needs == ("create-key",)
    assert op.identities == ("admin", "reader")
    assert op.mutating and op.interactive
    assert op.undo == "git checkout secrets/ci.enc"
    assert op.disables and op.escalate and op.vacuous_if and op.ready
    assert op.commands == ("sops -e secrets/ci.yaml",)
    assert op.verify == "the file decrypts"


def test_check_proof_is_reserved() -> None:
    op = Op.model_validate({"id": "a", "summary": "s", "phase": "pre-merge", "check": "proof"})
    assert op.is_proof
    assert not Op.model_validate(FULL).is_proof


def test_undo_may_be_none_with_a_reason() -> None:
    op = Op.model_validate(
        {"id": "a", "summary": "s", "phase": "pre-merge", "undo": {"none": "a deleted key"}}
    )
    assert op.undo == UndoNone(none="a deleted key")
    with pytest.raises(ValidationError):
        Op.model_validate({"id": "a", "summary": "s", "phase": "pre-merge", "undo": {"none": ""}})


def test_an_op_refuses_an_unknown_key_naming_it() -> None:
    with pytest.raises(ValidationError, match="chekc"):
        Op.model_validate({"id": "a", "summary": "s", "phase": "pre-merge", "chekc": "true"})


def test_an_op_is_frozen() -> None:
    op = Op.model_validate(FULL)
    with pytest.raises(ValidationError):
        op.id = "b"  # type: ignore[misc]


def test_an_op_id_is_a_token() -> None:
    with pytest.raises(ValidationError):
        Op.model_validate({"id": "has space", "summary": "s", "phase": "pre-merge"})


# --- LegacyOp: frank's `# manual-operation` blocks ----------------------------


FRANK = {
    "id": "rotate-token",
    "layer": "ci",
    "app": "forgejo",
    "plan": "2026-10-01-ci",
    "when": "after the runner is up",
    "why_manual": "needs an admin UI click",
    "commands": ["open the admin page", "rotate"],
    "verify": "the runner reconnects",
}


def test_legacy_accepts_frank_fields_and_defaults() -> None:
    op, done = LegacyOp.model_validate(FRANK).to_op()
    assert op.id == "rotate-token"
    assert op.summary == "needs an admin UI click"
    assert op.phase == "post-merge"
    assert op.commands == ("open the admin page", "rotate")
    assert op.verify == "the runner reconnects"
    assert done is False


def test_legacy_status_done_maps_to_legacy_done() -> None:
    _, done = LegacyOp.model_validate({**FRANK, "status": "done"}).to_op()
    assert done is True
    _, pending = LegacyOp.model_validate({**FRANK, "status": "pending"}).to_op()
    assert pending is False


def test_legacy_accepts_any_r1_field_and_its_own_phase() -> None:
    op, _ = LegacyOp.model_validate(
        {**FRANK, "phase": "pre-merge", "check": "true", "identities": ["admin"]}
    ).to_op()
    assert op.phase == "pre-merge"
    assert op.check == "true"
    assert op.identities == ("admin",)


def test_legacy_summary_wins_over_why_manual() -> None:
    op, _ = LegacyOp.model_validate({**FRANK, "summary": "explicit"}).to_op()
    assert op.summary == "explicit"


def test_legacy_needs_a_summary_or_why_manual() -> None:
    data = {k: v for k, v in FRANK.items() if k != "why_manual"}
    with pytest.raises(ValidationError, match="summary"):
        LegacyOp.model_validate(data).to_op()


def test_legacy_refuses_an_unknown_key() -> None:
    with pytest.raises(ValidationError, match="owner"):
        LegacyOp.model_validate({**FRANK, "owner": "me"})
