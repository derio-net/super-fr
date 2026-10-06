"""`deliver`'s `walk` evidence (spec 2026-10-06-verification-strategies §C, R10,
R11): owed when the run's spec gives the run or a row an agent-driven pre-merge
strategy, verified like `tests` — on HEAD's code tree, every step passing, every
owed row covered — and omittable when it is not owed (in-flight back-compat)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.exceptions import Exit
from fr.commands import run_cmd
from fr.run.model import load_run_state
from fr.workflow.model import Step

from tests.unit.test_verification_walk import RUN, SPEC, _git, _home, _logs, _repo, _walk

__all__ = ["_home"]

DELIVER = Step(id="deliver", kind="agent", evidence=("tests", "walk"))


def _verify(root: Path, offered: dict[str, str]) -> dict[str, str]:
    state = load_run_state(root, RUN)
    return run_cmd._verified_evidence(
        root,
        state,
        DELIVER,
        key="step/deliver",
        phase=None,
        offered=offered,
        state_value="done",
    )


def _walked(root: Path, home: Path) -> str:
    assert _walk(root, "--row", "ok").exit_code == 0
    return str(_logs(home)[-1])


def _owed_good(tmp_path: Path) -> Path:
    return _repo(tmp_path, rows={"ok": "echo fine"})


def _refused(root: Path, offered: dict[str, str], capsys: pytest.CaptureFixture[str]) -> str:
    with pytest.raises(Exit):
        _verify(root, offered)
    err = capsys.readouterr().err
    return err.replace("\n", " ")


def test_a_passing_log_on_head_covering_every_owed_row_is_accepted(
    tmp_path: Path, _home: Path
) -> None:
    root = _owed_good(tmp_path)
    log = _walked(root, _home)

    got = _verify(root, {"tests": "t", "walk": log})

    assert got["walk"].startswith(Path(log).name + "@")


@pytest.fixture(autouse=True)
def _no_tests_offer(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests exercise `walk`; `tests` is another witness with its own tests."""
    monkeypatch.setattr(run_cmd, "_verify_tests_log", lambda key, log, root, *, opened: "t@0")


def test_a_stale_code_tree_is_refused_naming_it(
    tmp_path: Path, _home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _owed_good(tmp_path)
    log = _walked(root, _home)
    (root / "new.py").write_text("x = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "code", "--no-verify")

    assert "code tree" in _refused(root, {"tests": "t", "walk": log}, capsys)


def test_a_failing_step_is_refused(
    tmp_path: Path, _home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)  # rows ok + bad
    assert _walk(root).exit_code == 1

    assert "'row:bad' failed" in _refused(
        root, {"tests": "t", "walk": str(_logs(_home)[0])}, capsys
    )


def test_a_missing_row_is_refused_by_id(
    tmp_path: Path, _home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path, rows={"ok": "true", "other": "true"})
    log = _walked(root, _home)  # walked only `ok`

    assert "'other' is not covered" in _refused(root, {"tests": "t", "walk": log}, capsys)


def test_a_hand_written_log_is_refused(
    tmp_path: Path, _home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _owed_good(tmp_path)
    fake = tmp_path / "walk.log"
    fake.write_text("all steps passed, honest\n")

    assert "not a walk log" in _refused(root, {"tests": "t", "walk": str(fake)}, capsys)


def test_an_owed_walk_that_is_not_offered_is_refused_naming_the_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _owed_good(tmp_path)

    assert "--evidence walk=" in _refused(root, {"tests": "t"}, capsys)


def test_walk_none_is_refused_while_a_walk_is_owed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _owed_good(tmp_path)

    assert "owed" in _refused(root, {"tests": "t", "walk": "none"}, capsys)


def test_an_agent_pre_merge_row_with_no_scenario_is_refused_by_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path, rows={"ok": "true", "unscripted": None})

    assert "'unscripted'" in _refused(root, {"tests": "t"}, capsys)


def _without_section(root: Path) -> None:
    (root / SPEC).write_text("# S\n\nno verification section\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "spec", "--no-verify")


def test_a_spec_with_no_verification_section_owes_nothing(tmp_path: Path) -> None:
    root = _owed_good(tmp_path)
    _without_section(root)

    assert "walk" not in _verify(root, {"tests": "t"})  # absent: accepted
    assert _verify(root, {"tests": "t", "walk": "none"})["walk"] == "none"


def test_a_post_merge_only_spec_owes_nothing(tmp_path: Path) -> None:
    root = _repo(tmp_path, strategy="live")

    assert "walk" not in _verify(root, {"tests": "t"})
    assert _verify(root, {"tests": "t", "walk": "none"})["walk"] == "none"


@pytest.mark.parametrize("name", ["fr-goal", "fr-goal-light"])
def test_both_shipped_shapes_declare_walk_on_deliver(name: str) -> None:
    from fr.workflow.model import parse_manifest

    root = Path(__file__).resolve().parents[2]
    for copy in (root / "plugins/super-fr/workflows", root / "packages/fr/src/fr/workflows"):
        manifest = parse_manifest((copy / f"{name}.yaml").read_text())
        (deliver,) = [s for s in manifest.steps if s.id == "deliver"]
        assert "walk" in deliver.evidence, copy
