"""`deliver`'s derived `settle` witness through `fr run resolve --step deliver` over a fake
forge (spec 2026-11-23-pr-readiness-wait R8, Test Plan 7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import typer
from fr.ghclient import UnsupportedForgeOperation
from fr.run.model import load_run_state

from tests.unit.record_support import RUN, commit_all, fr, git, write_record
from tests.unit.test_deliver_pr_body import PR, _at_deliver, live
from tests.unit.test_forge_quiet_pr_body import _land_policy

__all__ = ["live"]

pytestmark = pytest.mark.usefixtures("complete_live_pr")

HEAD = "c" * 40
REPO = "derio-net/super-fr"


class Forge:
    """Reads only: any other method fails the test."""

    def __init__(
        self,
        *,
        mergeable: str = "MERGEABLE",
        merge_state: str = "CLEAN",
        checks: list[dict[str, Any]] | None = None,
        unsupported: str | None = None,
    ) -> None:
        self.view = {
            "state": "OPEN",
            "head_oid": HEAD,
            "base_ref": "main",
            "mergeable": mergeable,
            "merge_state": merge_state,
        }
        self.checks = [{"name": "ci-ok", "bucket": "pass"}] if checks is None else checks
        self.unsupported = unsupported
        self.ops: list[str] = []

    def _op(self, op: str) -> None:
        self.ops.append(op)
        if op == self.unsupported:
            raise UnsupportedForgeOperation(op, "glab")

    def open_pr_for_head(self, repo: str, branch: str) -> dict[str, Any] | None:
        self._op("open_pr_for_head")
        return {"number": 1, "url": PR}

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        self._op("pr_view")
        return self.view

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        self._op("pr_checks")
        return self.checks

    def required_check_names(self, repo: str, base: str) -> list[str]:
        self._op("required_check_names")
        return []

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        raise AssertionError(f"the settle witness called {name}: it may only read")


@pytest.fixture
def at_deliver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = _at_deliver(tmp_path)
    monkeypatch.setattr("fr.settle.witness.origin_slug", lambda _root: REPO)
    monkeypatch.setattr("fr.settle.target.ci_none", lambda _root: False)
    return root


def _use(monkeypatch: pytest.MonkeyPatch, forge: Forge) -> Forge:
    monkeypatch.setattr("fr.settle.witness.client_for", lambda _root: forge)
    return forge


def _deliver(root: Path, **evidence: str) -> Any:
    data = {
        "run": RUN, "step": "deliver", "outcome": "done",
        "emitted": {"pr": PR}, "evidence": {"tests": "suite.log", **evidence},
    }  # fmt: skip
    rec = write_record(root, data)
    return fr(root, ["run", "resolve", RUN, "--step", "deliver", "--record", str(rec)])


def _witness(root: Path) -> str | None:
    record = load_run_state(root, RUN).steps["deliver"]
    unit = (record.units or {}).get("step/deliver")
    evidence = (unit.evidence if unit is not None else None) or record.evidence or {}
    return evidence.get("settle")


def _cursor(root: Path) -> bytes:
    return (root / "docs" / "superpowers" / "runs" / f"{RUN}.yaml").read_bytes()


def _settle_line(root: Path, *lines: str) -> None:
    spec = root / "docs" / "spec.md"
    spec.write_text(spec.read_text() + "\n## Verification\n\n" + "\n".join(lines) + "\n")
    commit_all(root, "settle override")
    (root / "suite.log").write_text("n passed\n")


def test_fix_and_a_clean_green_pr_records_the_witness(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _use(monkeypatch, Forge())

    out = _deliver(at_deliver)

    assert out.exit_code == 0, out.output
    assert _witness(at_deliver) == f"fix/fix:clean/green@{HEAD}"
    assert {"pr_view", "pr_checks"} <= set(forge.ops)


@pytest.mark.parametrize(
    ("forge", "said"),
    [
        (Forge(mergeable="CONFLICTING", merge_state="DIRTY"), "conflicting"),
        (Forge(checks=[{"name": "ci-ok", "bucket": "fail"}]), "red"),
    ],
)
def test_fix_refuses_a_conflicting_or_red_pr_naming_settle(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch, forge: Forge, said: str
) -> None:
    _use(monkeypatch, forge)
    before = _cursor(at_deliver)

    out = _deliver(at_deliver)

    assert out.exit_code == 2, out.output
    assert "settle" in out.output and said in out.output
    assert _cursor(at_deliver) == before


def test_a_pending_pr_exits_75_records_nothing_and_leaves_the_cursor(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, Forge(checks=[{"name": "ci-ok", "bucket": "pending"}]))
    before = _cursor(at_deliver)

    out = _deliver(at_deliver)

    assert out.exit_code == 75, out.output
    assert "settle" in out.output and "Nothing was recorded" in out.output
    assert _cursor(at_deliver) == before
    assert load_run_state(at_deliver, RUN).steps["deliver"].state == "running"


def test_report_records_the_states(at_deliver: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _land_policy(at_deliver, "git:\n  settle:\n    conflicts: report\n    ci: report\n")
    _use(monkeypatch, Forge(checks=[{"name": "ci-ok", "bucket": "fail"}]))

    out = _deliver(at_deliver)

    assert out.exit_code == 0, out.output
    assert _witness(at_deliver) == f"report/report:clean/red@{HEAD}"


def test_a_spec_override_relaxes_the_witness(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _settle_line(at_deliver, "settle.ci: report — the runners are down")
    _use(monkeypatch, Forge(checks=[{"name": "ci-ok", "bucket": "fail"}]))

    out = _deliver(at_deliver)

    assert out.exit_code == 0, out.output
    assert _witness(at_deliver) == f"fix/report:clean/red@{HEAD}"


def test_both_keys_off_records_off_and_reads_nothing(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _land_policy(at_deliver, "git:\n  settle:\n    conflicts: 'off'\n    ci: 'off'\n")
    forge = _use(monkeypatch, Forge())

    out = _deliver(at_deliver)

    assert out.exit_code == 0, out.output
    assert _witness(at_deliver) == "off"
    assert forge.ops == []


def test_a_managed_branch_records_managed(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(at_deliver, "checkout", "-q", "-b", "feat/batch-x")
    forge = _use(monkeypatch, Forge(mergeable="CONFLICTING", merge_state="DIRTY"))

    out = _deliver(at_deliver)

    assert out.exit_code == 0, out.output
    assert _witness(at_deliver) == "managed"
    assert forge.ops == []


def test_unsupported_is_recorded_and_refuses_nothing(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, Forge(unsupported="pr_view"))

    out = _deliver(at_deliver)

    assert out.exit_code == 0, out.output
    # Review p2-r2: an unsupported pr_view names the local HEAD, never an empty `@`.
    witness = _witness(at_deliver) or ""
    prefix, _, sha = witness.partition("@")
    assert prefix == "fix/fix:unsupported/unsupported"
    assert len(sha) == 40 and sha in git(at_deliver, "rev-list", "HEAD").split()


def test_a_passed_settle_value_is_refused(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, Forge())

    out = _deliver(at_deliver, settle="fix/fix:clean/green@x")

    assert out.exit_code == 2, out.output
    assert "not yours to pass" in out.output and "settle" in out.output


def test_another_derived_refusal_is_reported_before_the_settle_hold(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import run_cmd

    def refuse(*_a: object, **_k: object) -> str:
        run_cmd.err_console.print("proportionality: refused for the test")
        raise typer.Exit(2)

    monkeypatch.setattr(run_cmd, "_proportionality_witness", refuse)
    _use(monkeypatch, Forge(checks=[{"name": "ci-ok", "bucket": "pending"}]))

    out = _deliver(at_deliver)

    assert out.exit_code == 2, out.output
    assert "proportionality: refused for the test" in out.output
    assert "still settling" not in out.output


class _Failing(Forge):
    def __init__(self, exc: Exception) -> None:
        super().__init__()
        self.exc = exc

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        raise self.exc


@pytest.mark.parametrize(
    ("text", "code"),
    [
        # `fr.gh.classify`'s own rules, unpatched (l-tests-r4): a 5xx is `warn`...
        ("HTTP 502 bad gateway", 75),
        ("connection reset by peer", 75),
        # ...a 404 is `info` and bad credentials `unknown`: neither answers on a retry.
        ("HTTP 404: Not Found", 2),
        ("HTTP 401: Bad credentials", 2),
    ],
)
def test_a_transient_forge_failure_holds_and_a_permanent_one_refuses(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch, text: str, code: int
) -> None:
    from fr.gh import GhError

    _use(monkeypatch, _Failing(GhError(text)))

    out = _deliver(at_deliver)

    assert out.exit_code == code, out.output
    if code == 2:
        assert "refused the read" in out.output
        # l-errors-r4: a forge refusal is not a PR that failed to settle.
        assert "record an override" not in out.output


def test_only_a_failing_pr_is_offered_the_override(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, Forge(checks=[{"name": "ci-ok", "bucket": "fail"}]))

    out = _deliver(at_deliver)

    assert out.exit_code == 2, out.output
    assert "record an override" in out.output


def test_no_open_pr_names_its_own_remedy(at_deliver: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class NoPr(Forge):
        def open_pr_for_head(self, repo: str, branch: str) -> dict[str, Any] | None:
            return None

    _use(monkeypatch, NoPr())

    out = _deliver(at_deliver)

    assert out.exit_code == 2, out.output
    assert "fr pr create" in out.output
    assert "record an override" not in out.output


def test_tests_ci_still_refuses_a_conflicting_pr_with_conflicts_off(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.run import ci_evidence

    _settle_line(at_deliver, "settle.conflicts: off — the base is frozen")
    monkeypatch.setattr(ci_evidence, "_check_services", lambda _root: None)
    monkeypatch.setattr(ci_evidence, "_check_pushed", lambda _root: ("feat/rec", HEAD))
    forge = _use(monkeypatch, Forge(mergeable="CONFLICTING", merge_state="DIRTY"))
    monkeypatch.setattr("fr._hosts.origin_slug", lambda _root: REPO)
    monkeypatch.setattr("fr.hostclient.client_for", lambda _root: forge)

    out = _deliver(at_deliver, tests="ci")

    assert out.exit_code == 2, out.output
    assert "conflicts with its base" in out.output


# --- review p2-r1: the witness runs after every hard deliver gate, before the forge write


def test_a_pr_body_refusal_is_reported_before_the_settle_hold(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch, live: dict[str, str]
) -> None:
    live["body"] = "## Summary\n\nno fr sections\n"
    _use(monkeypatch, Forge(checks=[{"name": "ci-ok", "bucket": "pending"}]))

    out = _deliver(at_deliver)

    assert out.exit_code == 2, out.output
    assert "lacks required section" in out.output
    assert "still settling" not in out.output


def test_the_exit_guard_refuses_before_the_settle_hold(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import run_cmd

    def refuse(*_a: object) -> None:
        run_cmd.err_console.print("exit guard: refused for the test")
        raise typer.Exit(2)

    monkeypatch.setattr(run_cmd, "_deliver_exit_guard", refuse)
    _use(monkeypatch, Forge(checks=[{"name": "ci-ok", "bucket": "pending"}]))

    out = _deliver(at_deliver)

    assert out.exit_code == 2, out.output
    assert "exit guard: refused for the test" in out.output
    assert "still settling" not in out.output


def test_a_pending_pr_holds_before_the_label_sync_writes_the_forge(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import run_cmd

    synced: list[object] = []
    rendered: list[object] = []
    real_render = run_cmd._deliver_pr_gate

    def gate(*a: object) -> None:
        rendered.append(a)
        real_render(*a)  # type: ignore[arg-type]

    monkeypatch.setattr(run_cmd, "_deliver_pr_gate", gate)
    monkeypatch.setattr(run_cmd, "_deliver_label_sync", lambda *a: synced.append(a))
    _use(monkeypatch, Forge(checks=[{"name": "ci-ok", "bucket": "pending"}]))

    out = _deliver(at_deliver)

    assert out.exit_code == 75, out.output
    assert rendered, "the PR body is rendered before the hold"
    assert synced == []


def test_a_settled_pr_syncs_labels_after_the_witness(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import run_cmd

    synced: list[object] = []
    monkeypatch.setattr(run_cmd, "_deliver_label_sync", lambda *a: synced.append(a))
    _use(monkeypatch, Forge())

    out = _deliver(at_deliver)

    assert out.exit_code == 0, out.output
    assert len(synced) == 1
    assert _witness(at_deliver) == f"fix/fix:clean/green@{HEAD}"


def test_a_first_resolve_with_no_pr_gets_the_pr_gates_message(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr import gh as fr_gh
    from fr.gh import GhError

    def no_pr(ref: str, *, cwd: Path | None = None) -> str:
        raise GhError("no pull requests found")

    monkeypatch.setattr(fr_gh, "view_pr_body", no_pr)
    _use(monkeypatch, Forge(checks=[{"name": "ci-ok", "bucket": "pending"}]))
    data = {"run": RUN, "step": "deliver", "outcome": "done", "evidence": {"tests": "suite.log"}}
    rec = write_record(at_deliver, data)

    out = fr(at_deliver, ["run", "resolve", RUN, "--step", "deliver", "--record", str(rec)])

    assert out.exit_code == 2, out.output
    assert "fr pr create" in out.output
    assert "still settling" not in out.output


# --- review p2-r3: an unparseable origin asks the backend before it refuses


@pytest.mark.parametrize("cls", ["glab", "tea"])
def test_no_origin_slug_on_a_glab_or_tea_client_is_unsupported(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch, cls: str
) -> None:
    from fr.real_glabclient import RealGlabClient
    from fr.real_teaclient import RealTeaClient

    client = RealGlabClient() if cls == "glab" else RealTeaClient()
    monkeypatch.setattr("fr.settle.witness.origin_slug", lambda _root: None)
    monkeypatch.setattr("fr.settle.witness.client_for", lambda _root: client)

    out = _deliver(at_deliver)

    assert out.exit_code == 0, out.output
    assert (_witness(at_deliver) or "").startswith("fix/fix:unsupported/unsupported@")


def test_no_origin_slug_on_a_github_client_refuses(
    at_deliver: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("fr.settle.witness.origin_slug", lambda _root: None)
    _use(monkeypatch, Forge())

    out = _deliver(at_deliver)

    assert out.exit_code == 2, out.output
    assert "cannot read the forge repository" in out.output
