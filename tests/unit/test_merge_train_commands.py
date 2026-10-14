"""`fr triage batch merge` under the approval gate (spec 2026-10-11-merge-train-safety
§A "Merging", "Recording and voiding", §B; R1, R2, R3, R8).

Reuses `test_triage_batch_merge`'s fakes: `MergeForge` (labels on by default) and
`FakeCheckout`, through `triage_batch_cmd.make_client` / `make_checkout`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.triage.model import load_judgements

from tests.unit.test_triage_batch_merge import _merge, _setup

TWO = [
    ("one", 1, None, "patch", "4.21.2", ["a.py"]),
    ("two", 2, None, "patch", "4.21.3", ["b.py"]),
]


def _events(tmp_path: Path, bid: str) -> list[dict[str, object]]:
    raw = yaml.safe_load((tmp_path / "judgements.yaml").read_text("utf-8"))
    batch = next(b for b in raw["batches"] if b["id"] == bid)
    return [e for e in batch["events"] if e["kind"] != "dispatch"]


def test_a_default_merge_holds_an_unlabelled_batch_and_merges_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, _ = _setup(tmp_path, monkeypatch, TWO)
    forge.prs[1001]["labels"] = []
    code, out = _merge(tmp_path, "--yes")
    assert code == 0, out
    assert "held one: PR #1001 awaits the approved-fr label" in out
    assert [n for n, _, _ in forge.merged] == [1002]


def test_naming_an_unapproved_batch_exits_2_naming_the_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, _ = _setup(tmp_path, monkeypatch, TWO)
    forge.prs[1001]["labels"] = []
    code, out = _merge(tmp_path, "one", "--yes")
    assert code == 2
    assert "approved-fr" in out and "one" in out
    assert forge.merged == []


def test_when_every_batch_is_unapproved_there_is_nothing_to_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, _ = _setup(tmp_path, monkeypatch, TWO)
    for pr in forge.prs.values():
        pr["labels"] = []
    code, out = _merge(tmp_path, "--yes")
    assert code == 0, out
    assert "nothing to merge" in out
    assert forge.merged == []


def test_merge_settles_approvals_only_under_yes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, _ = _setup(tmp_path, monkeypatch, TWO)
    code, out = _merge(tmp_path)
    assert code == 0, out
    assert "would record approval of PR #1001 at head-one" in out
    assert _events(tmp_path, "one") == []

    code, out = _merge(tmp_path, "--yes")
    assert code == 0, out
    assert "approval of PR #1001 recorded at head-one" in out
    (approval,) = _events(tmp_path, "one")
    assert (approval["kind"], approval["pr"], approval["head"]) == ("approval", 1001, "head-one")
    assert load_judgements(tmp_path / "judgements.yaml").schema_ == 10


def test_a_session_push_after_approval_voids_it_and_removes_the_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _setup(tmp_path, monkeypatch, TWO[:1])
    forge.prs[1001]["state"] = "OPEN"
    code, _ = _merge(tmp_path)  # a preview records nothing
    assert _events(tmp_path, "one") == []
    # record the approval at head-one without merging: a failing check holds the merge
    forge.checks[1001] = [{"name": "lint", "bucket": "fail"}]
    code, out = _merge(tmp_path, "--yes")
    assert code == 1 and "approval of PR #1001 recorded at head-one" in out
    forge.prs[1001]["head_oid"] = "session-push"
    checkout.up_to_date.add("session-push")
    code, out = _merge(tmp_path, "--yes")
    assert "approval of PR #1001 at head-one voided: head moved to session-push" in out
    assert forge.label_edits == [(1001, frozenset(), frozenset({"approved-fr"}))]
    assert forge.merged == []
    assert _events(tmp_path, "one")[-1]["voided_at"] == "session-push"


def test_an_update_merge_pushes_is_recorded_and_keeps_the_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _setup(tmp_path, monkeypatch, TWO[:1])
    checkout.up_to_date.discard("head-one")  # behind main by a code commit: updated
    code, out = _merge(tmp_path, "--yes")
    assert code == 0, out
    assert [n for n, _, _ in forge.merged] == [1001]
    kinds = [(e["kind"], e.get("head_before"), e.get("base")) for e in _events(tmp_path, "one")]
    assert kinds[0] == ("approval", None, None)
    assert kinds[1][0] == "update" and kinds[1][1] == "head-one"
    assert kinds[1][2] == "origin/main@fetched"


def test_merge_creates_the_missing_label_under_yes_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, _ = _setup(tmp_path, monkeypatch, TWO[:1])
    forge.labels_defined.clear()
    code, out = _merge(tmp_path)
    assert "created label" not in out and forge.created_labels == []
    code, out = _merge(tmp_path, "--yes")
    assert "created label approved-fr on derio-net/super-fr" in out
    assert forge.created_labels == ["approved-fr"]
