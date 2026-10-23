"""The op status engine (spec 2026-10-22-fr-ops R3, R5, R7, R9, §C, §D).

Pure over an injected runner, identity resolver and journal port, so no test
here runs a subprocess.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from fr.journal.model import JournalEntry, append_journal_entry, journal_path, op_body
from fr.ops.engine import OrderError, exit_code, order, status
from fr.ops.evidence import JournalEvidence, OpEvidence, fold, record_op
from fr.ops.identity import IdentityError
from fr.ops.load import LoadedOp
from fr.ops.model import Op

SRC = Path("ops.yaml")


class FakeRunner:
    """Maps a command to `(exit, last line)`; an unknown command exits 1. A
    command keyed `(cmd, identity-env-value)` answers per identity."""

    def __init__(self, answers: Mapping[object, tuple[int, str]]) -> None:
        self.answers = dict(answers)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, command: str, env: Mapping[str, str]) -> tuple[int, str]:
        self.calls.append((command, dict(env)))
        for value in env.values():
            if (command, value) in self.answers:
                return self.answers[(command, value)]
        return self.answers.get(command, (1, ""))


class FakeIdentities:
    def __init__(self, envs: Mapping[str, Mapping[str, str] | None]) -> None:
        self.envs = envs

    def __call__(self, name: str) -> Mapping[str, str]:
        env = self.envs.get(name)
        if env is None:
            raise IdentityError(f"identity {name!r}: TOKEN could not be read")
        return env


class FakeJournal:
    def __init__(self, latest: Mapping[str, OpEvidence] | None = None) -> None:
        self.by_op = dict(latest or {})
        self.asked: list[tuple[str, bool]] = []

    def latest(self, op_id: str, *, runbook: bool) -> OpEvidence | None:
        self.asked.append((op_id, runbook))
        return self.by_op.get(op_id)


def _lo(legacy: str | None = None, runbook: bool = False, **fields: object) -> LoadedOp:
    data: dict[str, object] = {"id": "a", "summary": "s", "phase": "pre-merge"}
    data.update(fields)
    return LoadedOp(Op.model_validate(data), SRC, 1, legacy=legacy, runbook=runbook)  # type: ignore[arg-type]


def _ev(result: str, **kw: str) -> OpEvidence:
    return OpEvidence(result=result, created="2026-10-22T10:00:00+00:00", **kw)


def _one(lo: LoadedOp, runner: FakeRunner | None = None, **kw: object):
    (row,) = status(
        [lo],
        runner=runner or FakeRunner({}),
        identities=kw.pop("identities", FakeIdentities({})),  # type: ignore[arg-type]
        journal=kw.pop("journal", FakeJournal()),  # type: ignore[arg-type]
    )
    return row


# --- each state ----------------------------------------------------------------


def test_done_checked() -> None:
    row = _one(_lo(check="probe"), FakeRunner({"probe": (0, "")}))
    assert (row.state, row.how) == ("DONE", "checked")


def test_open_carries_the_checks_last_line_as_its_reason() -> None:
    row = _one(_lo(check="probe"), FakeRunner({"probe": (1, "HTTP 404: key missing")}))
    assert row.state == "OPEN"
    assert row.reason == "HTTP 404: key missing"


def test_done_attested_for_a_checkless_op() -> None:
    row = _one(_lo(), journal=FakeJournal({"a": _ev("attested", attested_by="operator")}))
    assert (row.state, row.how) == ("DONE", "attested")


def test_na_legacy_runs_no_probe() -> None:
    """p1-r3: a legacy `decommissioned`/`n/a` status reads N/A (legacy)."""
    runner = FakeRunner({})
    row = _one(_lo(legacy="n/a", check="probe"), runner)
    assert (row.state, row.how, row.label) == ("N/A", "legacy", "N/A (legacy)")
    assert runner.calls == []


def test_done_legacy() -> None:
    row = _one(_lo(legacy="done"))
    assert (row.state, row.how) == ("DONE", "legacy")


def test_na_when_na_if_passes() -> None:
    runner = FakeRunner({"not-here": (0, ""), "probe": (1, "x")})
    row = _one(_lo(check="probe", na_if="not-here"), runner)
    assert row.state == "N/A"
    assert [c for c, _ in runner.calls] == ["not-here"]


def test_unverifiable_without_a_check() -> None:
    row = _one(_lo())
    assert row.state == "UNVERIFIABLE"


def test_cannot_verify_on_exit_127() -> None:
    row = _one(_lo(check="probe"), FakeRunner({"probe": (127, "bash: kubectl: not found")}))
    assert row.state == "CANNOT-VERIFY"


def test_cannot_verify_on_an_unreadable_identity() -> None:
    row = _one(
        _lo(check="probe", identities=["admin"]),
        FakeRunner({"probe": (0, "")}),
        identities=FakeIdentities({"admin": None}),
    )
    assert row.state == "CANNOT-VERIFY"
    assert row.identity == "admin"


# --- proof -----------------------------------------------------------------------


def test_check_proof_is_done_only_from_a_recorded_proof() -> None:
    lo = _lo(check="proof")
    assert _one(lo).state == "OPEN"
    assert _one(lo, journal=FakeJournal({"a": _ev("done")})).state == "OPEN"
    row = _one(lo, journal=FakeJournal({"a": _ev("proof")}))
    assert (row.state, row.how) == ("DONE", "proof")


def test_a_proof_check_runs_nothing() -> None:
    runner = FakeRunner({})
    _one(_lo(check="proof"), runner)
    assert runner.calls == []


# --- identities -----------------------------------------------------------------


def test_the_check_runs_once_per_identity_and_all_must_pass() -> None:
    runner = FakeRunner({("probe", "tok-admin"): (0, ""), ("probe", "tok-ro"): (1, "HTTP 403")})
    ids = FakeIdentities({"admin": {"TOKEN": "tok-admin"}, "reader": {"TOKEN": "tok-ro"}})
    row = _one(_lo(check="probe", identities=["admin", "reader"]), runner, identities=ids)
    assert row.state == "OPEN"
    assert row.identity == "reader"
    assert len(runner.calls) == 2
    assert [env["TOKEN"] for _, env in runner.calls] == ["tok-admin", "tok-ro"]


def test_every_identity_passing_is_done() -> None:
    runner = FakeRunner({"probe": (0, "")})
    ids = FakeIdentities({"admin": {"TOKEN": "a"}, "reader": {"TOKEN": "b"}})
    row = _one(_lo(check="probe", identities=["admin", "reader"]), runner, identities=ids)
    assert row.state == "DONE"


def test_identity_values_never_appear_in_the_report() -> None:
    secret = "s3cr3t-value"
    runner = FakeRunner({"probe": (1, f"denied for token {secret}")})
    ids = FakeIdentities({"admin": {"TOKEN": secret}})
    row = _one(_lo(check="probe", identities=["admin"]), runner, identities=ids)
    assert secret not in repr(row)
    assert secret not in str(row.as_row())


# --- disables / escalate ----------------------------------------------------------


def test_disables_reports_open_with_its_consequence_and_is_never_na() -> None:
    runner = FakeRunner({"not-here": (0, ""), "probe": (1, "missing")})
    lo = _lo(check="probe", na_if="not-here", disables="nightly backups stop")
    row = _one(lo, runner)
    assert row.state == "OPEN"
    assert "nightly backups stop" in (row.reason or "")


def test_a_passing_escalate_on_a_non_done_op_escalates() -> None:
    runner = FakeRunner({"probe": (1, "missing"), "already": (0, "")})
    row = _one(_lo(check="probe", escalate="already"), runner)
    assert row.state == "ESCALATE"


def test_escalate_is_not_run_for_a_done_op() -> None:
    runner = FakeRunner({"probe": (0, ""), "already": (0, "")})
    row = _one(_lo(check="probe", escalate="already"), runner)
    assert row.state == "DONE"
    assert "already" not in [c for c, _ in runner.calls]


def test_a_failing_escalate_leaves_the_state() -> None:
    runner = FakeRunner({"probe": (1, "missing"), "already": (1, "")})
    assert _one(_lo(check="probe", escalate="already"), runner).state == "OPEN"


# --- exit codes -------------------------------------------------------------------


def test_exit_codes() -> None:
    def rows(*states_how: str):
        out = []
        for i, s in enumerate(states_how):
            lo = _lo(id=f"o{i}", check="probe") if s != "LEGACY" else _lo(id=f"o{i}", legacy="done")
            runner = FakeRunner({"probe": {"DONE": (0, ""), "OPEN": (1, "x")}.get(s, (0, ""))})
            out.append(_one(lo, runner))
        return out

    assert exit_code(rows("DONE", "LEGACY")) == 0
    assert exit_code(rows("DONE", "OPEN")) == 1
    esc = _one(_lo(check="p", escalate="e"), FakeRunner({"p": (1, ""), "e": (0, "")}))
    assert exit_code([*rows("OPEN"), esc]) == 3
    assert exit_code([_one(_lo())]) == 1  # UNVERIFIABLE


# --- order ------------------------------------------------------------------------


def test_order_is_topological_and_stable() -> None:
    ops = [_lo(id="c", needs=["b"]), _lo(id="a"), _lo(id="b", needs=["a"])]
    assert [lo.op.id for lo in order(ops)] == ["a", "b", "c"]


def test_order_refuses_a_cycle_and_an_unknown_id() -> None:
    with pytest.raises(OrderError, match="cycle"):
        order([_lo(id="a", needs=["b"]), _lo(id="b", needs=["a"])])
    with pytest.raises(OrderError, match="ghost"):
        order([_lo(id="a", needs=["ghost"])])


def test_order_ignores_a_need_that_is_known_but_not_selected() -> None:
    assert [lo.op.id for lo in order([_lo(id="b", needs=["a"])], known={"a", "b"})] == ["b"]


# --- evidence: the fold and the journal ---------------------------------------------


def _entry(eid: str, op: str, result: str, created: str, **kw: str) -> JournalEntry:
    return JournalEntry(
        kind="op",
        scope="plan",
        id=eid,
        created=created,
        title=f"op {op}: {result}",
        body=op_body(op=op, result=result, **kw),
    )


def test_the_latest_entry_wins() -> None:
    entries = [
        _entry("e1", "a", "attested", "2026-10-22T10:00:00+00:00", attested_by="operator"),
        _entry("e2", "a", "open", "2026-10-22T11:00:00+00:00", reason="regressed"),
        _entry("e3", "b", "proof", "2026-10-22T09:00:00+00:00"),
    ]
    folded = fold(entries)
    assert folded["a"].result == "open" and folded["a"].reason == "regressed"
    assert folded["b"].result == "proof"
    row = _one(_lo(), journal=FakeJournal(folded))
    assert row.state == "UNVERIFIABLE"


def test_record_op_writes_through_the_journal_engine_and_reads_back(tmp_path: Path) -> None:
    (tmp_path / "docs/superpowers/plans/p").mkdir(parents=True)
    record_op(tmp_path, "p", op="a", result="attested", phase="pre-merge", attested_by="operator")
    record_op(tmp_path, "p", op="a", result="open", phase="pre-merge", reason="x")
    ev = JournalEvidence(tmp_path, "p")
    latest = ev.latest("a", runbook=False)
    assert latest is not None and latest.result == "open"
    text = journal_path(tmp_path, "plan", "p").read_text()
    assert "op a: attested" in text and "op a: open" in text


def test_runbook_evidence_is_read_from_live_and_archived_plan_journals(tmp_path: Path) -> None:
    from fr.journal.model import archived_journal_path

    old = _entry("o1", "rb", "attested", "2026-01-01T00:00:00+00:00", attested_by="operator")
    archived = archived_journal_path(tmp_path, "plan", "old-plan")
    archived.parent.mkdir(parents=True)
    append_journal_entry(archived, "old-plan", old)
    other = journal_path(tmp_path, "plan", "other")
    append_journal_entry(other, "other", _entry("o2", "rb", "proof", "2026-02-01T00:00:00+00:00"))
    ev = JournalEvidence(tmp_path, "mine")
    latest = ev.latest("rb", runbook=True)
    assert latest is not None and latest.result == "proof"
    # A plan op only ever reads its own plan's journal.
    assert ev.latest("rb", runbook=False) is None


def test_status_asks_the_journal_with_the_ops_runbook_flag() -> None:
    journal = FakeJournal()
    _one(_lo(runbook=True), journal=journal)
    assert journal.asked == [("a", True)]


# --- masking (R5, p1-r4) ---------------------------------------------------------

PEM = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7\n"
    "q2Lz8xY4w1Vb7RkM0nQe5p0dTq8sJx3Y9bK2LmWzQ1rT6uV4e8\n"
    "-----END PRIVATE KEY-----"
)


def _as_identity(line: str, secret: str = PEM, rc: int = 1):
    runner = FakeRunner({"probe": (rc, line)})
    ids = FakeIdentities({"admin": {"KEY": secret}})
    return _one(_lo(check="probe", identities=["admin"]), runner, identities=ids)


def _leaks(reason: str | None, secret: str = PEM) -> list[str]:
    import base64

    pieces = [t for t in secret.split() if len(t) >= 6]
    forms = pieces + [base64.b64encode(secret.encode()).decode()]
    return [f for f in forms if reason and f in reason]


def test_a_secret_line_echoed_alone_is_masked() -> None:
    row = _as_identity("denied for MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7")
    assert row.state == "OPEN"
    assert not _leaks(row.reason), row.reason
    assert "***" in (row.reason or "")


def test_a_base64_echo_of_the_secret_is_masked() -> None:
    import base64

    echoed = base64.b64encode(PEM.encode()).decode()
    row = _as_identity(f"got {echoed[:120]}")
    assert echoed[:120] not in (row.reason or "")
    row = _as_identity(f"got {base64.b64encode(b'tok-abcdef12').decode()}", "tok-abcdef12")
    assert base64.b64encode(b"tok-abcdef12").decode() not in (row.reason or "")


def test_a_url_encoded_secret_is_masked() -> None:
    from urllib.parse import quote

    secret = "p@ss/word with+chars"
    row = _as_identity(f"GET /?t={quote(secret, safe='')} 401", secret)
    assert quote(secret, safe="") not in (row.reason or "")
    assert "401" in (row.reason or "")


def test_a_token_of_a_secret_is_masked() -> None:
    row = _as_identity("user longpassword123 refused", "admin longpassword123")
    assert "longpassword123" not in (row.reason or "")


def test_a_body_like_line_as_an_identity_reports_only_the_exit() -> None:
    assert _as_identity('{"message": "Bad credentials"}', "tok-xyz", rc=22).reason == "exit 22"
    assert _as_identity("[1, 2]", "tok-xyz", rc=1).reason == "exit 1"
    assert _as_identity("x" * 201, "tok-xyz", rc=1).reason == "exit 1"
    assert _as_identity("HTTP 404: missing", "tok-xyz", rc=1).reason == "HTTP 404: missing"


def test_p3_r3_a_recorded_na_closes_an_op_only_while_it_carries_na_if() -> None:
    from fr.ops.evidence import recorded_close

    na = _ev("na")
    assert recorded_close(_lo(na_if="probe", check="c"), na) == "N/A (recorded)"
    assert recorded_close(_lo(check="c"), na) is None
    assert recorded_close(_lo(na_if="probe"), _ev("done")) is None  # checkless: attest only


def test_p3_r3_op_body_takes_the_na_result() -> None:
    from fr.journal.model import op_body

    assert "result: na" in op_body(op="a", result="na", phase="pre-merge")
