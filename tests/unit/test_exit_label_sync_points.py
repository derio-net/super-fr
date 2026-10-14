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


def test_a_run_with_no_known_pr_syncs_nothing_and_prints_nothing(
    tmp_path: Path, sync: _Sync
) -> None:
    root = _at_spec_review(tmp_path)
    out = _resolve(root, write_record(root, _spec_review_record()), step="spec-review", item=None)
    assert out.exit_code == 0, out.output
    assert sync.calls == [] and "warning" not in out.output.lower()


def test_deliver_warns_and_delivers_when_the_forge_cannot_be_determined(
    tmp_path: Path, sync: _Sync, live: None
) -> None:
    root = _ready_deliver(tmp_path, live)
    sync.result = labels_mod.PrNotFound("no `origin` remote, so no PR to label")
    _rec, out = _deliver(root)
    assert out.exit_code == 0, out.output
    assert "no `origin` remote" in out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"


def test_resolving_spec_review_syncs_the_labels(
    tmp_path: Path, sync: _Sync, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("fr.commands.run_cmd._emitted_pr", lambda _s: PR)
    root = _at_spec_review(tmp_path)
    out = _resolve(root, write_record(root, _spec_review_record()), step="spec-review", item=None)
    assert out.exit_code == 0, out.output
    # once for the brainstorm that set the run up, once for this spec-review
    assert [c[1] for c in sync.calls] == [PR, PR]


def test_a_failed_sync_at_spec_review_only_warns(
    tmp_path: Path, sync: _Sync, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("fr.commands.run_cmd._emitted_pr", lambda _s: PR)
    sync.result = LabelSyncError("HTTP 500")
    root = _at_spec_review(tmp_path)
    out = _resolve(root, write_record(root, _spec_review_record()), step="spec-review", item=None)
    assert out.exit_code == 0, out.output
    assert "HTTP 500" in out.output and "warn" in out.output.lower()


def test_a_run_with_no_pr_yet_resolves_silently(
    tmp_path: Path, sync: _Sync, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("fr.commands.run_cmd._emitted_pr", lambda _s: PR)
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
