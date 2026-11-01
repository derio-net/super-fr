"""The op model and its legacy reader (spec 2026-10-22-fr-ops R1, R2, §A)."""

from __future__ import annotations

import datetime

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
    op, legacy = LegacyOp.model_validate(FRANK).to_op()
    assert op.id == "rotate-token"
    assert op.summary == "needs an admin UI click"
    assert op.phase == "post-merge"
    assert op.commands == ("open the admin page", "rotate")
    assert op.verify == "the runner reconnects"
    assert legacy is None


@pytest.mark.parametrize(
    ("status", "legacy"),
    [
        ("done", "done"),
        ("done 2026-07-27 rotated by hand", "done"),
        ("Done", "done"),
        ("decommissioned", "n/a"),
        ("n/a", "n/a"),
        ("pending", None),
        ("deferred", None),
        ("blocked on the vendor", None),
        ("donework", None),
    ],
)
def test_legacy_status_maps_per_r2(status: str, legacy: str | None) -> None:
    _, got = LegacyOp.model_validate({**FRANK, "status": status}).to_op()
    assert got == legacy


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


def test_legacy_keeps_an_unknown_key_as_prose() -> None:
    """p1-r3: frank's real runbook carries note/notes/done_note/decommissioned; the
    legacy carrier is a convention fr does not own, so it never refuses a key."""
    legacy = LegacyOp.model_validate(
        {**FRANK, "note": "n", "notes": ["a", "b"], "done_note": "x", "decommissioned": "2026"}
    )
    assert legacy.prose_keys == ("decommissioned", "done_note", "note", "notes")
    assert legacy.to_op()[0].id == "rotate-token"
    assert LegacyOp.model_validate(FRANK).prose_keys == ()


def test_legacy_keeps_non_string_commands_and_verify_as_prose() -> None:
    op, _ = LegacyOp.model_validate(
        {
            **FRANK,
            "commands": [
                "open https://registrar.example.com",
                {"host": "192.0.2.10", "run": "dig"},
            ],
            "verify": [{"expect": "192.0.2.10"}],
            "when": datetime.date(2026, 7, 27),
        }
    ).to_op()
    assert op.commands is not None and op.commands[0] == "open https://registrar.example.com"
    assert "192.0.2.10" in op.commands[1] and "dig" in op.commands[1]
    assert op.verify is not None and "192.0.2.10" in op.verify[0]


def test_ops_yaml_op_stays_strict() -> None:
    with pytest.raises(ValidationError, match="note"):
        Op.model_validate({"id": "a", "summary": "s", "phase": "pre-merge", "note": "x"})


# --- the `none:` acknowledgement (spec 2026-11-01-ops-gate-probes R4) ------------------


def test_an_ops_file_may_acknowledge_no_ops() -> None:
    from fr.ops.model import OpsFile

    assert OpsFile.model_validate({"schema_version": 2, "none": "reboot only"}).none == "reboot only"
    assert OpsFile.model_validate({"schema_version": 2, "none": "x", "ops": []}).ops == ()
    assert OpsFile.model_validate({"schema_version": 2}).none is None


def test_none_beside_a_non_empty_ops_is_refused_by_name() -> None:
    from fr.ops.model import OpsFile

    op = {"id": "a", "summary": "s", "phase": "pre-merge"}
    with pytest.raises(ValidationError, match="none"):
        OpsFile.model_validate({"schema_version": 2, "none": "x", "ops": [op]})


def test_an_empty_none_is_refused() -> None:
    from fr.ops.model import OpsFile

    with pytest.raises(ValidationError):
        OpsFile.model_validate({"schema_version": 2, "none": ""})
