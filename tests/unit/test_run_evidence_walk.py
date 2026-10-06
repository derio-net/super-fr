"""`deliver`'s `walk` evidence (spec 2026-10-06-verification-strategies §C, R10,
R11): owed when the run's spec gives the run or a row an agent-driven pre-merge
strategy, verified like `tests` — on HEAD's code tree, every step passing, every
owed row covered — and omittable when it is not owed (in-flight back-compat)."""

from __future__ import annotations

import datetime as _dt
import os
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
    fake = _home / ".cache/fr/walks" / RUN / "walk.log"
    fake.parent.mkdir(parents=True)
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


# --- who ran the walk (review p3-r1) ------------------------------------------------

_OPENED = "2026-10-06T16:00:00+00:00"


def _forged(root: Path, home: Path, *, where: Path | None = None) -> Path:
    """A header-complete log no walk wrote: HEAD's code tree, every step 0, the
    smoke and the owed row — exactly what `check_walk_log` asks of a log."""
    from fr.run.code_tree import code_tree
    from fr.verification.walk import WalkLog, WalkStep

    steps = tuple(
        WalkStep(n, 0, 0.1) for n in ("install", "smoke:version", "smoke:status", "row:ok")
    )
    log = WalkLog(RUN, "candidate", code_tree(root), "claude-code", "m-1", steps)
    path = where or home / ".cache/fr/walks" / RUN / "forged.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(log.render())
    stamp = _dt.datetime.fromisoformat("2026-10-06T16:08:00+00:00").timestamp()
    os.utime(path, (stamp, stamp))
    return path


def _session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    from tests.unit.transcript_sessions import ran_at

    projects = tmp_path / "projects"
    ran_at(
        projects,
        "2026-10-06T16:05:00.000Z",
        until="2026-10-06T16:09:00.000Z",
        session_id="s-walk",
        command=command,
    )
    monkeypatch.setenv("FR_TRANSCRIPT_ROOT", str(projects))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s-walk")
    monkeypatch.setenv("CLAUDECODE", "1")


def _gate(root: Path, log: Path, *, opened: str | None = _OPENED) -> str:
    state = load_run_state(root, RUN)
    owed = run_cmd._walk_obligation("step/deliver", root, state)
    return run_cmd._verify_walk("step/deliver", str(log), root, state, owed, opened=opened)


def test_a_forged_log_no_command_of_yours_walked_is_refused(
    tmp_path: Path, _home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _owed_good(tmp_path)
    log = _forged(root, _home)
    _session(tmp_path, monkeypatch, f"cat /dev/null > {tmp_path / 'other.txt'}")

    with pytest.raises(Exit):
        _gate(root, log)

    assert "fr verification walk --run w1" in capsys.readouterr().err.replace("\n", " ")


def test_a_log_inside_the_window_of_your_walk_command_is_accepted(
    tmp_path: Path, _home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _owed_good(tmp_path)
    log = _forged(root, _home)
    _session(tmp_path, monkeypatch, f"cd {root} && uv run fr verification walk --run w1 --model m")

    assert _gate(root, log).startswith("forged.log@")


def test_a_walk_command_for_another_run_does_not_witness_this_one(
    tmp_path: Path, _home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _owed_good(tmp_path)
    log = _forged(root, _home)
    _session(tmp_path, monkeypatch, "fr verification walk --run other --model m")

    with pytest.raises(Exit):
        _gate(root, log)


def test_a_log_outside_the_runs_walk_dir_is_refused(
    tmp_path: Path, _home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _owed_good(tmp_path)
    log = _forged(root, _home, where=tmp_path / "elsewhere" / "walk.log")
    _session(tmp_path, monkeypatch, "fr verification walk --run w1 --model m")

    with pytest.raises(Exit):
        _gate(root, log)

    assert ".cache/fr/walks/w1" in capsys.readouterr().err.replace("\n", "")


def test_an_unreadable_transcript_records_the_walk_unobserved(
    tmp_path: Path, _home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _owed_good(tmp_path)
    log = _forged(root, _home)
    run_cmd._take_unobserved()  # a gate an earlier test noted is not this one's

    assert _gate(root, log).startswith("forged.log@")

    assert run_cmd._take_unobserved() == {"unobserved": "walk"}
    assert "unobserved=walk" in capsys.readouterr().err.replace("\n", " ")


def test_a_tilde_path_is_expanded_before_it_is_judged_relative(
    tmp_path: Path, _home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review p3-r7: `walk=~/...` is the operator's home, not `<repo>/~/...`."""
    root = _owed_good(tmp_path)
    _forged(root, _home)
    _session(tmp_path, monkeypatch, "fr verification walk --run w1 --model m")
    state = load_run_state(root, RUN)
    owed = run_cmd._walk_obligation("step/deliver", root, state)

    got = run_cmd._verify_walk(
        "step/deliver", f"~/.cache/fr/walks/{RUN}/forged.log", root, state, owed, opened=_OPENED
    )

    assert got.startswith("forged.log@")


# --- the command-match predicate: an allowlist (security review of p3-r1) ---------


@pytest.mark.parametrize(
    "command",
    [
        "fr verification walk --run w1 --model m",
        "uv run fr verification walk --run=w1 --model m",
        "uv run --project /w fr verification walk --model m --run w1",
        "FR_X=1 /opt/bin/fr verification walk --run w1 --model m",
        "cd /w && uv run fr verification walk --run w1 --model m",
        "cd '/w space' && FR_X=1 fr verification walk --run w1",
    ],
)
def test_the_two_allowed_shapes_are_a_walk(command: str) -> None:
    from fr.run.observed import walks_run

    assert walks_run(command, "w1")


@pytest.mark.parametrize(
    "command",
    [
        "echo fr verification walk --run w1",
        'echo "fr verification walk --run w1"',
        "'fr verification walk --run w1'",
        "fr isolation exec -- 'fr verification walk --run w1'",
        "sh -c 'fr verification walk --run w1'",
        "# fr verification walk --run w1",
        "fr verification walk --run w1 # trailing",
        "fr verification walk --run w1-other",
        "fr verification walk --run=w1x",
        "fr verification walks --run w1",
        "fr verification --run w1 walk",
        "fr verification walk --run w1 --run w2",
        "fr verification walk --run w1 --run=w1",
        "fr verification walk --model m --run",
        "fr verification walk --run w1; cp /tmp/forged /x.log",
        "fr verification walk --run w1 && cp /tmp/forged /x.log",
        "cd /w && cd /v && fr verification walk --run w1",
        "cd /w x && fr verification walk --run w1",
        "true && fr verification walk --run w1",
        "fr verification walk --run w1 || true",
        "fr verification walk --run w1 > /x.log",
        "fr verification walk --run w1 2> /x.log",
        "fr verification walk --run w1 &> /x.log",
        "fr verification walk --run w1 < /dev/null",
        "fr verification walk --run w1 | tee /x.log",
        "fr verification walk --run $(echo w1)",
        "fr verification walk --run `echo w1`",
        "fr verification walk --run w1 &",
        "(fr verification walk --run w1)",
        "{ fr verification walk --run w1; }",
        "fr verification walk --run w1 <<EOF\nx\nEOF",
        "fr verification walk --run w1\ncp /tmp/f /x.log",
        "fr verification walk --run 'w1",
        "uv run python fr verification walk --run w1",
        "./fr-wrapper verification walk --run w1",
    ],
)
def test_every_other_shape_is_not_a_walk(command: str) -> None:
    from fr.run.observed import walks_run

    assert not walks_run(command, "w1")


def test_the_gate_refuses_a_walk_command_that_copies_a_forgery_onto_the_log(
    tmp_path: Path, _home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _owed_good(tmp_path)
    log = _forged(root, _home)
    _session(
        tmp_path,
        monkeypatch,
        f"fr verification walk --run w1 --model m; cp {tmp_path / 'f.log'} {log}",
    )

    with pytest.raises(Exit):
        _gate(root, log)


def test_a_symlinked_log_is_refused(
    tmp_path: Path, _home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The log must be a regular file under the run's walk dir — a link
    placed there, pointing anywhere, is not a log the walk wrote."""
    root = _owed_good(tmp_path)
    real = _forged(root, _home)
    link = real.parent / "link.log"
    link.symlink_to(real)
    _session(tmp_path, monkeypatch, "fr verification walk --run w1 --model m")

    with pytest.raises(Exit):
        _gate(root, link)

    assert "symlink" in capsys.readouterr().err


def test_a_symlink_out_of_the_walk_dir_is_refused(
    tmp_path: Path, _home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _owed_good(tmp_path)
    outside = _forged(root, _home, where=tmp_path / "elsewhere" / "walk.log")
    walks = _home / ".cache/fr/walks" / RUN
    walks.parent.mkdir(parents=True, exist_ok=True)
    walks.symlink_to(outside.parent)  # the walk dir itself points elsewhere
    _session(tmp_path, monkeypatch, "fr verification walk --run w1 --model m")

    with pytest.raises(Exit):
        _gate(root, walks / "walk.log")
