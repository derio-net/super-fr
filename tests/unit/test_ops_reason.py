"""One sanitiser for every op reason that is recorded or printed (spec 2026-10-22-fr-ops
R5/R7; security review of phase 2's apply): identity AND `env_passthrough` values are
masked, and a body-looking line (JSON, or over 200 characters) is dropped whether or
not the op runs as an identity."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from pathlib import Path

from fr.journal.model import journal_path
from fr.ops.apply import ShellApplier, apply_ops
from fr.ops.evidence import record_op
from fr.ops.load import LoadedOp
from fr.ops.mask import clip_output, evidence_lines, passthrough_values, sanitise_reason

from tests.unit.test_ops_apply import FakePrompt, Idents, NoJournal, World, op

PASS_VALUE = "kube-ctx-ABCDEF-123456"


def test_a_json_body_is_dropped_without_an_identity() -> None:
    assert sanitise_reason('{"message": "forbidden", "token": "x"}', ()) == ""
    assert sanitise_reason("x" * 201, ()) == ""
    assert sanitise_reason("short and fine", ()) == "short and fine"


def test_passthrough_values_are_masked_in_every_form(monkeypatch) -> None:
    monkeypatch.setenv("FR_TEST_PASS", PASS_VALUE)
    secrets = passthrough_values(("FR_TEST_PASS", "FR_TEST_UNSET"))
    b64 = base64.b64encode(PASS_VALUE.encode()).decode()
    line = sanitise_reason(f"ctx {PASS_VALUE} enc {b64}", secrets)
    assert PASS_VALUE not in line and b64 not in line and line.count("***") == 2


def test_a_short_passthrough_value_is_not_a_secret(monkeypatch) -> None:
    """`DEBUG=1` passed through must not mask every `1` in `exit 1`."""
    monkeypatch.setenv("FR_TEST_FLAG", "1")
    assert passthrough_values(("FR_TEST_FLAG",)) == []


def test_a_passthrough_value_on_stderr_never_reaches_the_journal(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FR_TEST_PASS", PASS_VALUE)
    (tmp_path / "docs/superpowers/plans/p").mkdir(parents=True)
    applier = ShellApplier(tmp_path, passthrough=("FR_TEST_PASS",))
    w = World()

    def record(**kw: object) -> None:
        record_op(tmp_path, "p", **kw)  # type: ignore[arg-type]

    res = apply_ops(
        [op("a", apply='echo "denied in $FR_TEST_PASS" >&2; exit 3')],
        runner=w.runner, applier=applier, identities=Idents(), journal=NoJournal(),
        prompt=FakePrompt(), record=record, yes=True,
    )  # fmt: skip
    text = journal_path(tmp_path, "plan", "p").read_text()
    assert "op a: failed" in text
    assert PASS_VALUE not in text and PASS_VALUE not in res.steps[-1].message


def test_record_op_masks_passthrough_values_from_the_repo_config(
    tmp_path: Path, monkeypatch
) -> None:
    """The writer is the last net: a caller that forgot to sanitise still cannot leak."""
    monkeypatch.setenv("FR_TEST_PASS", PASS_VALUE)
    (tmp_path / ".fr").mkdir()
    (tmp_path / ".fr/ops.yaml").write_text("env_passthrough: [FR_TEST_PASS]\n")
    (tmp_path / "docs/superpowers/plans/p").mkdir(parents=True)
    record_op(tmp_path, "p", op="a", result="failed", reason=f"saw {PASS_VALUE}")
    record_op(tmp_path, "p", op="b", result="failed", reason='{"body": "leak"}')
    text = journal_path(tmp_path, "plan", "p").read_text()
    assert PASS_VALUE not in text and '"body"' not in text


def test_a_json_stderr_body_on_a_non_identity_op_records_only_the_exit_code() -> None:
    w = World()

    def applier(o: LoadedOp, env: Mapping[str, str], interactive: bool) -> tuple[int, str]:
        return 4, '{"error": "denied", "request_id": "abc"}'

    apply_ops(
        [op("a")], runner=w.runner, applier=applier, identities=Idents(), journal=NoJournal(),
        prompt=FakePrompt(), record=w.record, yes=True,
    )  # fmt: skip
    assert w.written == [{"op": "a", "result": "failed", "phase": "pre-merge",
                          "identity": None, "reason": "exit 4"}]  # fmt: skip


def test_a_json_check_line_on_a_non_identity_op_reads_exit_n_in_status() -> None:
    from fr.ops.engine import status

    from tests.unit.test_ops_engine import FakeIdentities, FakeJournal, FakeRunner, _lo

    (row,) = status(
        [_lo(check="probe")],
        runner=FakeRunner({"probe": (1, '{"items": []}')}),
        identities=FakeIdentities({}),
        journal=FakeJournal(),
    )
    assert row.state == "OPEN" and row.reason == "exit 1"


def test_clip_output_keeps_the_last_40_lines_each_at_most_200_chars() -> None:
    out = "\n".join(["x" * 300] + [f"l{i}" for i in range(45)])
    lines = clip_output(out, ()).splitlines()
    assert lines == [f"l{i}" for i in range(5, 45)]
    assert all(len(line) <= 200 for line in clip_output("y" * 500, ()).splitlines())


def test_evidence_is_the_last_three_non_blank_lines_within_300_chars() -> None:
    assert evidence_lines("a\n\nb\nc\n\nd\n", ()) == "b; c; d"
    assert len(evidence_lines("z" * 1000, ())) == 300


def test_output_and_evidence_mask_secret_values() -> None:
    secret = "s3cr3t-value-123"
    assert secret not in clip_output(f"token={secret}\nok", [secret])
    assert secret not in evidence_lines(f"token={secret}\nok", [secret])
    assert "***" in evidence_lines(f"token={secret}", [secret])
