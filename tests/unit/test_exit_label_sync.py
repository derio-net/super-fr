"""Label families and `sync_exit_labels` — spec 2026-10-14 exit-gates R7, §B."""

from __future__ import annotations

import types
from pathlib import Path

import pytest
from fr.ghclient import UnsupportedBatchOps
from fr.labels import gate_label, verification_label
from fr.run.model import RunState, StepRecord
from fr.verification.labels import LabelSyncError, sync_exit_labels

from tests.unit.fakes import FakeGhClient
from tests.unit.requirements_support import row, write_matrix

SPEC = "docs/spec.md"
REPO = "derio-net/super-fr"
URL = f"https://github.com/{REPO}/pull/5"


def test_label_families() -> None:
    assert verification_label("candidate").name == "verification:candidate"
    assert gate_label("tester").name == "gate:tester"
    assert gate_label("tester", passed=True).name == "gate:tester-passed"


def _repo(tmp_path: Path, section: str, remap: str | None = None) -> Path:
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / SPEC).write_text(
        f"# Spec\n\n## Requirements\n\nR1. x\n\n## Verification\n\n{section}\n"
    )
    write_matrix(tmp_path, [row(SPEC, rid="a", verify=None)])
    if remap is not None:
        (tmp_path / ".fr").mkdir(exist_ok=True)
        (tmp_path / ".fr" / "triage.yaml").write_text(remap)
    return tmp_path


def _state() -> RunState:
    return RunState(
        run="r1",
        workflow="fr-goal@1",
        branch="feat/x",
        started="2026-10-14T00:00:00Z",
        cursor="spec-review",
        steps={"brainstorm": StepRecord(state="done", emitted={"spec": SPEC})},
    )


def _fake(labels: list[str]) -> FakeGhClient:
    fake = FakeGhClient()
    fake.prs[(REPO, 5)] = {
        "state": "OPEN", "draft": True, "head_ref": "feat/x", "base_ref": "main",
        "mergeable": "UNKNOWN", "title": "t", "body": "b", "labels": list(labels),
    }  # fmt: skip
    return fake


@pytest.fixture(autouse=True)
def _tracking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fr._hosts.origin_slug", lambda _root: REPO)
    monkeypatch.setattr(
        "fr.services.resolve.resolve_tracking",
        lambda *_a, **_k: types.SimpleNamespace(type="github"),
    )


def test_it_adds_missing_and_removes_stale_but_never_a_passed_label(tmp_path: Path) -> None:
    root = _repo(tmp_path, "strategy: live")
    fake = _fake(["verification:old", "gate:devops", "gate:tester-passed", "bug"])
    out = sync_exit_labels(root, _state(), URL, client=fake)
    assert out.synced and out.warning is None
    (call,) = [c for c in fake.calls if c[0] == "edit_pr_labels"]
    assert call[1]["add"] == frozenset({"verification:live", "gate:tester"})
    assert call[1]["remove"] == frozenset({"verification:old", "gate:devops"})
    assert fake.pr_labels[(REPO, 5)] == {"verification:live", "gate:tester"}


def test_it_ensures_the_labels_before_editing(tmp_path: Path) -> None:
    root = _repo(tmp_path, "strategy: candidate")
    fake = _fake([])
    order: list[str] = []
    ensure, edit = fake.ensure_labels, fake.edit_pr_labels
    fake.ensure_labels = lambda *a, **k: (order.append("ensure"), ensure(*a, **k))[1]  # type: ignore[method-assign]
    fake.edit_pr_labels = lambda *a, **k: (order.append("edit"), edit(*a, **k))[1]  # type: ignore[method-assign]
    sync_exit_labels(root, _state(), URL, client=fake)
    assert order == ["ensure", "edit"]


def test_an_in_sync_pr_is_not_edited(tmp_path: Path) -> None:
    root = _repo(tmp_path, "strategy: candidate")
    fake = _fake(["verification:candidate", "unrelated"])
    out = sync_exit_labels(root, _state(), URL, client=fake)
    assert out.synced and not any(c[0] == "edit_pr_labels" for c in fake.calls)


def test_nothing_is_synced_under_tracking_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "fr.services.resolve.resolve_tracking", lambda *_a, **_k: types.SimpleNamespace(type="none")
    )
    fake = _fake([])
    out = sync_exit_labels(_repo(tmp_path, "strategy: live"), _state(), URL, client=fake)
    assert not out.synced and fake.calls == []


def test_an_unsupported_forge_is_a_warning(tmp_path: Path) -> None:
    class _Glab(UnsupportedBatchOps):
        backend = "gitlab"

        def ensure_labels(self, repo: str, labels: list) -> None: ...

    out = sync_exit_labels(_repo(tmp_path, "strategy: live"), _state(), URL, client=_Glab())  # type: ignore[arg-type]
    assert not out.synced and out.warning and "pr_view" in out.warning


def test_a_forge_failure_raises(tmp_path: Path) -> None:
    from fr.gh import GhError

    fake = _fake([])

    def boom(*a: object, **k: object) -> None:
        raise GhError("HTTP 500")

    fake.ensure_labels = boom  # type: ignore[method-assign]
    with pytest.raises(LabelSyncError, match="500"):
        sync_exit_labels(_repo(tmp_path, "strategy: live"), _state(), URL, client=fake)


def test_an_unreadable_remap_refuses_naming_the_problem(tmp_path: Path) -> None:
    root = _repo(tmp_path, "strategy: live", remap="exit: [unclosed\n")
    with pytest.raises(LabelSyncError, match="not valid triage config"):
        sync_exit_labels(root, _state(), URL, client=_fake([]))


def test_p2_r6_an_unreadable_exit_is_its_own_outcome(tmp_path: Path) -> None:
    root = _repo(tmp_path, "strategy: live")
    (root / SPEC).write_bytes(b"# Spec\n\n## Verification\n\nstrategy: live\n\xff\xfe\n")
    out = sync_exit_labels(root, _state(), URL, client=_fake([]))
    assert not out.synced and out.unknown and "cannot be read" in (out.warning or "")


def test_p2_r11_an_unsupported_forge_creates_no_labels(tmp_path: Path) -> None:
    ensured: list[object] = []

    class _Glab(UnsupportedBatchOps):
        backend = "gitlab"

        def ensure_labels(self, repo: str, labels: list) -> None:
            ensured.append(labels)

    out = sync_exit_labels(_repo(tmp_path, "strategy: live"), _state(), URL, client=_Glab())  # type: ignore[arg-type]
    assert out.warning and ensured == []


def test_p2_r7_a_missing_pr_is_not_an_unknown_forge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.verification.labels import ForgeUndeterminable, PrNotFound

    fake = FakeGhClient()  # no PR for the branch
    import fr._hosts

    monkeypatch.setattr(fr._hosts, "origin_slug", lambda _r: "o/r")
    with pytest.raises(PrNotFound) as e:
        sync_exit_labels(_repo(tmp_path, "strategy: live"), _state(), None, client=fake)
    assert not isinstance(e.value, ForgeUndeterminable)


def test_a_checkout_with_no_origin_has_no_forge_even_for_a_pr_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.verification.labels import ForgeUndeterminable

    monkeypatch.setattr("fr._hosts.origin_slug", lambda _root: None)
    with pytest.raises(ForgeUndeterminable):
        sync_exit_labels(_repo(tmp_path, "strategy: live"), _state(), URL, client=_fake([]))
