"""Where the exit's labels sync — spec 2026-10-14 exit-gates R7, §B: brainstorm and
spec-review warn, `deliver` refuses on GitHub (the wiring; the sync is
test_exit_label_sync.py's)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run.model import load_run_state
from fr.verification import labels as labels_mod
from fr.verification.labels import LabelSyncError, SyncOutcome

from tests.unit.record_support import RUN, write_record
from tests.unit.test_deliver_pr_body import PR, _at_deliver, _body, _deliver
from tests.unit.test_record_apply import _at_spec_review, _resolve, _spec_review_record


class _Sync:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []
        self.result: SyncOutcome | Exception = SyncOutcome(synced=True)

    def __call__(self, repo_root: Path, state: object, pr: str | None, **_: object) -> SyncOutcome:
        self.calls.append((getattr(state, "cursor", "?"), pr))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def sync(monkeypatch: pytest.MonkeyPatch) -> _Sync:
    fake = _Sync()
    monkeypatch.setattr(labels_mod, "sync_exit_labels", fake)
    return fake


def test_p2_r1_the_early_sync_finds_the_pr_by_the_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No `_emitted_pr` patch: the run has no emitted pr, the branch lookup finds it."""
    from fr.verification import labels as lm

    from tests.unit.fakes import FakeGhClient

    fake = FakeGhClient()
    fake.prs[("o/r", 5)] = {
        "number": 5, "url": "u", "state": "OPEN", "draft": True, "head_ref": "feat/rec",
        "base_ref": "main", "mergeable": "UNKNOWN", "title": "t", "body": "b", "labels": [],
    }  # fmt: skip
    monkeypatch.setattr(lm, "client_for", lambda _root: fake)
    monkeypatch.setattr("fr._hosts.origin_slug", lambda _root: "o/r")
    root = _at_spec_review(tmp_path)
    out = _resolve(root, write_record(root, _spec_review_record()), step="spec-review", item=None)
    assert out.exit_code == 0, out.output
    assert any(c[0] == "open_pr_for_head" for c in fake.calls)
    assert any(c[0] == "edit_pr_labels" for c in fake.calls)
    assert "verification:" in " ".join(sorted(fake.pr_labels[("o/r", 5)]))


def test_p2_r1_a_run_with_no_pr_says_nothing_even_for_an_undecodable_spec(
    tmp_path: Path,
) -> None:
    root = _at_spec_review(tmp_path)
    (root / "docs" / "spec.md").write_bytes(b"# spec\n\xff\xfe\n")
    out = _resolve(root, write_record(root, _spec_review_record()), step="spec-review", item=None)
    assert out.exit_code == 0, out.output
    assert "labels not synced" not in out.output


def test_p2_r6_an_unreadable_exit_refuses_deliver_and_only_warns_early(
    tmp_path: Path, sync: _Sync, live: None
) -> None:
    sync.result = SyncOutcome(
        synced=False, unknown=True, warning="PR labels not synced: the exit cannot be read: x"
    )
    root = _at_spec_review(tmp_path)
    out = _resolve(root, write_record(root, _spec_review_record()), step="spec-review", item=None)
    assert out.exit_code == 0 and "cannot be read" in out.output
    root = _ready_deliver(tmp_path / "d", live)
    rec, out = _deliver(root)
    assert out.exit_code == 2 and "cannot be read" in out.output and rec.exists()


def test_p2_r7_no_open_pr_refuses_deliver_but_an_unknown_forge_only_warns(
    tmp_path: Path, sync: _Sync, live: None
) -> None:
    root = _ready_deliver(tmp_path, live)
    sync.result = labels_mod.PrNotFound("no open PR for branch 'feat/x' in o/r")
    rec, out = _deliver(root)
    assert out.exit_code == 2 and "no open PR" in out.output and rec.exists()


def test_p2_r3_deliver_refuses_a_lowering_nothing_accounts_for(
    tmp_path: Path, sync: _Sync, live: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _ready_deliver(tmp_path, live)
    monkeypatch.setattr(
        "fr.verification.baseline.unaccounted_lowerings",
        lambda *_a: ["row r1: kind `live` -> `none`"],
    )
    rec, out = _deliver(root)
    assert out.exit_code == 2 and "row r1" in out.output and "answered-by operator" in out.output
    assert rec.exists()


def test_deliver_warns_and_delivers_when_the_forge_cannot_be_determined(
    tmp_path: Path, sync: _Sync, live: None
) -> None:
    root = _ready_deliver(tmp_path, live)
    sync.result = labels_mod.ForgeUndeterminable("no `origin` remote, so no PR to label")
    _rec, out = _deliver(root)
    assert out.exit_code == 0, out.output
    assert "no `origin` remote" in out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"


def test_resolving_spec_review_syncs_the_labels(tmp_path: Path, sync: _Sync) -> None:
    root = _at_spec_review(tmp_path)
    out = _resolve(root, write_record(root, _spec_review_record()), step="spec-review", item=None)
    assert out.exit_code == 0, out.output
    # once for the brainstorm that set the run up, once for this spec-review
    assert [c[1] for c in sync.calls] == [None, None]


def test_a_failed_sync_at_spec_review_only_warns(tmp_path: Path, sync: _Sync) -> None:
    sync.result = LabelSyncError("HTTP 500")
    root = _at_spec_review(tmp_path)
    out = _resolve(root, write_record(root, _spec_review_record()), step="spec-review", item=None)
    assert out.exit_code == 0, out.output
    assert "HTTP 500" in out.output and "warn" in out.output.lower()


def test_a_run_with_no_pr_yet_resolves_silently(tmp_path: Path, sync: _Sync) -> None:
    sync.result = labels_mod.PrNotFound("no open PR for branch")
    root = _at_spec_review(tmp_path)
    out = _resolve(root, write_record(root, _spec_review_record()), step="spec-review", item=None)
    assert out.exit_code == 0, out.output
    assert "no open PR" not in out.output


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> None:
    import fr.gh

    monkeypatch.setattr(fr.gh, "view_pr_body", lambda ref, *, cwd=None: _body_text["v"])


_body_text = {"v": ""}


def _ready_deliver(tmp_path: Path, live: None) -> Path:
    root = _at_deliver(tmp_path)
    _body_text["v"] = "x"
    _deliver(root)  # renders pr-body.md (refused: the live body lacks the sections)
    _body_text["v"] = _body(root).read_text()
    return root


def test_deliver_refuses_when_the_github_sync_fails_and_names_the_retry(
    tmp_path: Path, sync: _Sync, live: None
) -> None:
    root = _ready_deliver(tmp_path, live)
    sync.result = LabelSyncError("HTTP 502")
    rec, out = _deliver(root)
    assert out.exit_code == 2, out.output
    assert "HTTP 502" in out.output and "fr run resolve" in out.output
    assert sync.calls[-1][1] == PR
    assert load_run_state(root, RUN).steps["deliver"].state == "running"
    assert rec.exists()


def test_deliver_warns_on_an_unsupported_forge(tmp_path: Path, sync: _Sync, live: None) -> None:
    root = _ready_deliver(tmp_path, live)
    sync.result = SyncOutcome(synced=False, warning="PR labels not synced: not supported")
    _rec, out = _deliver(root)
    assert out.exit_code == 0, out.output
    assert "not supported" in out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"


def test_deliver_syncs_nothing_it_was_told_to_skip(tmp_path: Path, sync: _Sync, live: None) -> None:
    root = _ready_deliver(tmp_path, live)
    sync.result = SyncOutcome(synced=False)  # tracking none
    _rec, out = _deliver(root)
    assert out.exit_code == 0, out.output
    assert "not synced" not in out.output


def test_resolving_spec_review_warns_of_an_ops_gap_without_a_plan(
    tmp_path: Path, sync: _Sync
) -> None:
    """spec 2026-11-01-ops-gate-probes R3: advisory, and the exit code is unchanged."""
    import subprocess

    root = _at_spec_review(tmp_path)
    (root / "docs" / "spec.md").write_text(
        "# spec\n\n## Verification\n\nstrategy: none\ngate: devops\n\n"
        "## Test Plan\n\n- run `pulumi up` on the stack\n"
    )
    subprocess.run(["git", "-C", str(root), "commit", "-qam", "gated spec"], check=True)
    out = _resolve(root, write_record(root, _spec_review_record()), step="spec-review", item=None)
    assert out.exit_code == 0, out.output
    assert "ops gap" in out.output and "will need ops" in out.output
    assert "pulumi up" in out.output
