"""`deliver` stamps this feature's `local` rows (spec 2026-11-14-acceptance-local-status
R4, §D).

The stamps are planned right after the leftovers gate and written only after the
resolve's last refusal, in the resolve's own commit: a refused resolve writes none.
Every repo here is a local sandbox with no CI (no workflow file, no `ci:` service).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
import yaml
from fr.run.model import load_run_state

from tests.unit.record_support import (
    RUN,
    commit_all,
    fr,
    git,
    implement_record,
    resolve_empty_lens_review,
    write_record,
)
from tests.unit.test_deliver_pr_body import PR, account_seeded_row

ROW = "loc-1"
TEST = "tests/test_x.py"
LEVEL = f"unit=t:{TEST}#test_y"
FRAGMENT = Path("docs/acceptance/features/spec.yaml")


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    import fr.gh

    served: dict[str, str] = {"body": "never read before the render"}

    def view_pr_body(ref: str, *, cwd: Path | None = None) -> str:
        return served["body"]

    monkeypatch.setattr(fr.gh, "view_pr_body", view_pr_body)
    return served


def _at_deliver(tmp_path: Path, *, phase_log: bool = False) -> Path:
    """A run briefed `deliver` with `tests/test_x.py` committed before phase 1 resolved
    (so a phase suite log covers it), the seeded row accounted for."""
    from tests.unit.record_support import started_run

    root = started_run(tmp_path)
    (root / "tests").mkdir(exist_ok=True)
    (root / TEST).write_text("def test_y():\n    assert True\n")
    commit_all(root, "test: x")
    evidence = None
    if phase_log:
        log = tmp_path / "phase.log"  # outside the checkout: never a code path
        log.write_text("1 passed\n")
        evidence = {"tests": str(log)}
    impl = implement_record(evidence=evidence)
    step = ["run", "resolve", RUN, "--step"]
    rec = write_record(root, impl)
    out = fr(root, [*step, "implement-phase", "--item", "phase/1", "--record", str(rec)])
    assert out.exit_code == 0, out.output
    review = {
        "run": RUN, "step": "review-phase", "item": "phase/1", "outcome": "done",
        "journal": [{"kind": "review", "id": "r-p1", "title": "review", "body": "clean"}],
        "evidence": {"review": "r-p1", "reviewer": "reviewer-1"},
    }  # fmt: skip
    rec = write_record(root, review)
    out = fr(root, [*step, "review-phase", "--item", "phase/1", "--record", str(rec)])
    assert out.exit_code == 0, out.output
    resolve_empty_lens_review(root)
    assert load_run_state(root, RUN).steps["deliver"].state == "running"
    account_seeded_row(root)
    commit_all(root, "at deliver")
    if not phase_log:
        (root / "suite.log").write_text("n passed\n")
    return root


def _add_local(root: Path) -> None:
    """Row `loc-1`, added `local` by this feature: it lands in the feature's fragment."""
    out = fr(
        root,
        [
            *("acceptance", "add", "--id", ROW, "--capability", "Widget"),
            *("--acceptance", "loc-1 holds", "--origin", "spec:spec#R1", "--status", "local"),
            *("--level", LEVEL, "--notes", "tests/test_x.py::test_y verifies it"),
        ],
    )
    assert out.exit_code == 0, out.output
    commit_all(root, "local")


def _set_local(root: Path, row: str) -> None:
    out = fr(
        root,
        [
            *("acceptance", "set-status", "--id", row, "--status", "local", "--feature", "spec"),
            *("--level", LEVEL, "--notes", "tests/test_x.py::test_y verifies it"),
        ],
    )
    assert out.exit_code == 0, out.output
    commit_all(root, "local")


def _deliver_record(root: Path, tests: str = "suite.log"):
    data = {
        "run": RUN, "step": "deliver", "outcome": "done",
        "emitted": {"pr": PR}, "evidence": {"tests": tests},
    }  # fmt: skip
    rec = write_record(root, data)
    return fr(root, ["run", "resolve", RUN, "--step", "deliver", "--record", str(rec)])


def _deliver_flags(root: Path, tests: str = "suite.log"):
    return fr(
        root,
        [
            *("run", "resolve", RUN, "--step", "deliver", "--state", "done"),
            *("--emitted", f"pr={PR}", "--evidence", f"tests={tests}"),
        ],
    )


def _body(root: Path) -> Path:
    return root / "docs" / "superpowers" / "runs" / f"{RUN}.records" / "pr-body.md"


def _deliver_twice(root: Path, live: dict[str, str], deliver=_deliver_record):  # type: ignore[no-untyped-def]
    """The first resolve renders the PR body and is refused by the PR gate (a refusal
    after the stamp is planned); the second delivers."""
    first = deliver(root)
    assert first.exit_code == 2, first.output
    assert _body(root).is_file(), first.output
    live["body"] = _body(root).read_text()
    return deliver(root)


def _fragment(root: Path) -> dict:
    return yaml.safe_load((root / FRAGMENT).read_text())


def _row(root: Path, row: str = ROW) -> dict:
    return next(r for r in _fragment(root)["rows"] if r["id"] == row)


def _blob(root: Path, path: str) -> str:
    return git(root, "rev-parse", f"HEAD:{path}").strip()


def _code_tree(root: Path) -> str:
    from fr.run.code_tree import code_tree

    return code_tree(root)


def _today() -> str:
    return dt.datetime.now(dt.UTC).date().isoformat()


def test_a_local_row_is_stamped_in_the_deliver_commit(tmp_path: Path, live: dict[str, str]) -> None:
    root = _at_deliver(tmp_path)
    _add_local(root)

    out = _deliver_twice(root, live)

    assert out.exit_code == 0, out.output
    stamp = _row(root)["local"]
    assert stamp["at"] == _today()
    assert stamp["tree"] == _code_tree(root)
    assert stamp["log"].startswith("suite.log@")
    assert stamp["files"] == {TEST: _blob(root, TEST)}
    assert load_run_state(root, RUN).steps["deliver"].state == "done"
    # In the resolve's own commit, nothing left uncommitted.
    assert git(root, "status", "--porcelain", "--", str(FRAGMENT)).strip() == ""
    touched = git(root, "show", "--name-only", "--format=%s", "HEAD").splitlines()
    assert "deliver" in touched[0] and str(FRAGMENT) in touched


def test_the_flag_form_stamps_too(tmp_path: Path, live: dict[str, str]) -> None:
    root = _at_deliver(tmp_path)
    _add_local(root)

    out = _deliver_twice(root, live, _deliver_flags)

    assert out.exit_code == 0, out.output
    assert _row(root)["local"]["files"] == {TEST: _blob(root, TEST)}
    assert git(root, "status", "--porcelain", "--", str(FRAGMENT)).strip() == ""


@pytest.mark.parametrize("deliver", [_deliver_record, _deliver_flags], ids=["record", "flags"])
def test_a_later_refusal_writes_no_stamp(tmp_path: Path, live: dict[str, str], deliver) -> None:  # type: ignore[no-untyped-def]
    root = _at_deliver(tmp_path)
    _add_local(root)
    before = (root / FRAGMENT).read_bytes()
    head = git(root, "rev-parse", "HEAD").strip()

    out = deliver(root)  # the PR gate refuses: the live body lacks every section

    assert out.exit_code == 2, out.output
    assert (root / FRAGMENT).read_bytes() == before
    changed = git(root, "diff", "--name-only", head, "HEAD").split()
    assert str(FRAGMENT) not in changed
    assert load_run_state(root, RUN).steps["deliver"].state == "running"


def test_a_local_row_outside_the_features_fragment_is_left_alone(
    tmp_path: Path, live: dict[str, str]
) -> None:
    """The seeded row lives in `legacy.yaml`: set `local` there, it is no row this
    feature's fragment added or amended, so `deliver` does not stamp it."""
    from tests.unit.record_support import SEEDED_ROW

    root = _at_deliver(tmp_path)
    _set_local(root, SEEDED_ROW)
    legacy = root / "docs/acceptance/features/legacy.yaml"
    before = legacy.read_bytes()

    out = _deliver_twice(root, live)

    assert out.exit_code == 0, out.output
    assert legacy.read_bytes() == before
    assert not (root / FRAGMENT).exists()


def test_a_fresh_log_over_an_uncommitted_code_path_refuses_naming_the_row(
    tmp_path: Path, live: dict[str, str]
) -> None:
    root = _at_deliver(tmp_path)
    _add_local(root)
    (root / TEST).write_text("def test_y():\n    assert 1\n")
    before = (root / FRAGMENT).read_bytes()

    out = _deliver_record(root)

    assert out.exit_code == 2, out.output
    flat = " ".join(out.output.split())
    assert ROW in flat and TEST in flat
    assert (root / FRAGMENT).read_bytes() == before
    assert not _body(root).exists(), "refused before the PR gate"


def test_tests_reuse_stamps_with_the_witness_tree(tmp_path: Path, live: dict[str, str]) -> None:
    root = _at_deliver(tmp_path, phase_log=True)
    _add_local(root)

    out = _deliver_twice(root, live, lambda r: _deliver_record(r, "reuse"))

    assert out.exit_code == 0, out.output
    stamp = _row(root)["local"]
    from fr.run import units

    reused = units.evidence_of(load_run_state(root, RUN).steps["deliver"], "step/deliver")
    log, _, tree = reused["tests"].rpartition(";tree=")
    assert log.startswith("reused:") and log.endswith(stamp["log"].rpartition(":")[2])
    assert stamp["log"] == log and "phase.log@" in log
    assert stamp["tree"] == tree == _code_tree(root)
    assert stamp["files"] == {TEST: _blob(root, TEST)}


def _merged_row(tmp_path: Path, root: Path) -> None:
    """Row `m-1`, another feature's, merged on the default ref and merged into the
    branch: it changes here only by an amendment in this feature's fragment."""
    base = tmp_path / "base"
    folder = base / "docs" / "acceptance" / "features"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "other.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "feature": "other",
                "repo": "t/t",
                "rows": [
                    {
                        "id": "m-1",
                        "capability": "Widget",
                        "acceptance": "m-1 holds",
                        "origin": ["spec:other#R1"],
                        "status": "unwired",
                    }
                ],
            },
            sort_keys=False,
        )
    )
    git(base, "add", "-A")
    git(base, "commit", "-qm", "other feature")
    git(base, "push", "-q", "origin", "main")
    git(root, "fetch", "-q", "origin")
    git(root, "merge", "-q", "--no-edit", "origin/main")


def _set_status_of(root: Path, row: str) -> list[dict]:
    return [a for a in _fragment(root)["amendments"] if a["row"] == row and a["op"] == "set-status"]


def test_a_pending_set_status_amendment_is_stamped_in_place(
    tmp_path: Path, live: dict[str, str]
) -> None:
    root = _at_deliver(tmp_path)
    _merged_row(tmp_path, root)
    _set_local(root, "m-1")
    (amendment,) = _set_status_of(root, "m-1")
    assert amendment["status"] == "local" and "local" not in amendment

    out = _deliver_twice(root, live)

    assert out.exit_code == 0, out.output
    (amendment,) = _set_status_of(root, "m-1")
    assert amendment["local"]["files"] == {TEST: _blob(root, TEST)}
    other = yaml.safe_load((root / "docs/acceptance/features/other.yaml").read_text())
    assert "local" not in other["rows"][0], "the merged row's definition is untouched"


# --- the witness ----------------------------------------------------------------------


def test_only_a_local_suite_log_or_a_reuse_can_stamp(tmp_path: Path) -> None:
    from fr.commands.run_cmd import _local_stamp_witness

    root = tmp_path
    git_init = ["init", "-q", str(root)]
    import subprocess

    subprocess.run(["git", *git_init], check=True)
    for refused in (None, "ci", "ci:abc+def;tree=0123", "unobserved"):
        assert isinstance(_local_stamp_witness(root, refused), str), refused
    assert _local_stamp_witness(root, "reused:phase/1/x:p.log@0123456789ab;tree=feed") == (
        "reused:phase/1/x:p.log@0123456789ab",
        "feed",
    )
    assert isinstance(_local_stamp_witness(root, "reused:phase/1/x:p.log@0123456789ab"), str)


# --- quiet placement --------------------------------------------------------------------


def test_under_quiet_the_fragment_is_written_in_the_artifact_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fragment is read and written in the feature root of the `fr` worktree and
    committed there; the blobs come from the product checkout."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    from fr.acceptance.fold import clear_fold_cache
    from fr.artifacts.paths import KIND_DIRS, artifact_root
    from fr.commands import run_cmd

    from tests.unit.test_placement_quiet import quiet_repo

    root = quiet_repo(tmp_path)
    (root / "tests").mkdir()
    (root / TEST).write_text("def test_y():\n    assert True\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "test: x")
    froot = artifact_root(root)
    assert froot.resolve() != root.resolve()
    frag = froot / KIND_DIRS["acceptance-fragment"] / "spec.yaml"
    frag.parent.mkdir(parents=True, exist_ok=True)
    frag.write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "feature": "spec",
                "repo": "derio-net/widgets",
                "rows": [
                    {
                        "id": "q-1",
                        "capability": "widgets",
                        "acceptance": "q-1 holds",
                        "origin": ["spec:spec#R1"],
                        "status": "local",
                        "levels": {"unit": [f"widgets:{TEST}#test_y"]},
                    }
                ],
            },
            sort_keys=False,
        )
    )
    clear_fold_cache()

    plan = run_cmd._local_stamp_plan(root, "spec", "suite.log@0123456789ab", today="2026-11-14")

    assert plan is not None and plan.path == frag and plan.rows == ("q-1",)
    assert not (root / KIND_DIRS["acceptance-fragment"]).exists()
    writes = run_cmd._RunWrites(verb="resolve")
    token = run_cmd._RUN_WRITES.set(writes)
    try:
        run_cmd._deliver_local_stamp_write(root, plan)
        outcome = writes.commit()
    finally:
        run_cmd._RUN_WRITES.reset(token)
    assert outcome is not None and outcome.committed, outcome
    assert git(froot, "status", "--porcelain", "--", ".").strip() == ""
    assert frag.name in git(froot, "show", "--name-only", "--format=", "HEAD")
    stamp = yaml.safe_load(frag.read_text())["rows"][0]["local"]
    assert stamp == {
        "at": "2026-11-14",
        "tree": _code_tree(root),
        "log": "suite.log@0123456789ab",
        "files": {TEST: _blob(root, TEST)},
    }
    assert git(root, "status", "--porcelain").strip() == "", "the product checkout is untouched"


def test_a_fragment_with_no_local_row_never_folds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review p2-r1: deliver with no `local` row behaves exactly as before; the plan
    returns before the fold, so no fold failure can refuse it in the stamp's name."""
    from fr.acceptance import fold as fold_mod
    from fr.commands import run_cmd

    root = _at_deliver(tmp_path)
    out = fr(
        root,
        [
            *("acceptance", "add", "--id", ROW, "--capability", "Widget"),
            *("--acceptance", "loc-1 holds", "--origin", "spec:spec#R1", "--status", "unwired"),
            *("--level", LEVEL, "--notes", "a test exists"),
        ],
    )
    assert out.exit_code == 0, out.output
    commit_all(root, "unwired")
    assert (root / FRAGMENT).is_file()

    def boom(*_a: object, **_k: object) -> object:
        raise AssertionError("the stamp plan folded a fragment with no local row")

    monkeypatch.setattr(fold_mod, "effective", boom)
    assert run_cmd._local_stamp_plan(root, "spec", "suite.log", today="2026-11-14") is None


# --- tests-lens gaps (l-tests-r1, l-tests-r4) ------------------------------------------


def _deliver_record_no_pr(root: Path):
    data = {"run": RUN, "step": "deliver", "outcome": "done", "evidence": {"tests": "suite.log"}}
    rec = write_record(root, data)
    return fr(root, ["run", "resolve", RUN, "--step", "deliver", "--record", str(rec)])


def _deliver_flags_no_pr(root: Path):
    return fr(
        root,
        [
            *("run", "resolve", RUN, "--step", "deliver", "--state", "done"),
            *("--evidence", "tests=suite.log"),
        ],
    )


@pytest.mark.parametrize(
    "deliver", [_deliver_record_no_pr, _deliver_flags_no_pr], ids=["record", "flags"]
)
def test_the_last_refusal_missing_emits_writes_no_stamp(
    tmp_path: Path, live: dict[str, str], deliver
) -> None:  # type: ignore[no-untyped-def]
    """l-tests-r1: the PR gate passes (the live body carries every section) and the
    exit guard and label sync pass too; `_refuse_missing_emits`, the resolve's last
    refusal, refuses a `done` naming no `pr`. The stamp, planned before every one of
    them, is never written."""
    root = _at_deliver(tmp_path)
    _add_local(root)
    first = _deliver_flags(root)  # renders the body; the PR gate refuses
    assert first.exit_code == 2, first.output
    live["body"] = _body(root).read_text()
    before = (root / FRAGMENT).read_bytes()

    out = deliver(root)

    assert out.exit_code == 2, out.output
    assert "without the artifact(s) it declares: pr" in " ".join(out.output.split())
    assert (root / FRAGMENT).read_bytes() == before
    assert "local" not in _row(root)
    assert load_run_state(root, RUN).steps["deliver"].state == "running"


def test_the_exit_guard_refusal_writes_no_stamp(
    tmp_path: Path, live: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """l-tests-r1: a refusal by `_deliver_exit_guard`, after the PR gate passes."""
    import fr.verification.baseline as baseline

    root = _at_deliver(tmp_path)
    _add_local(root)
    first = _deliver_flags(root)
    assert first.exit_code == 2, first.output
    live["body"] = _body(root).read_text()
    before = (root / FRAGMENT).read_bytes()
    monkeypatch.setattr(baseline, "unaccounted_lowerings", lambda *_a, **_k: ["R1 lowered"])

    out = _deliver_flags(root)

    assert out.exit_code == 2, out.output
    assert "R1 lowered" in out.output
    assert (root / FRAGMENT).read_bytes() == before
    assert "local" not in _row(root)


def test_a_level_ref_not_committed_at_head_refuses_naming_the_row(
    tmp_path: Path, live: dict[str, str]
) -> None:
    """l-tests-r4: the row's test file is in the working tree (ignored, so no code path
    is dirty) but not in HEAD: deliver refuses, naming the row and the path."""
    root = _at_deliver(tmp_path)
    (root / ".gitignore").write_text("tests/test_new.py\n")
    commit_all(root, "ignore")
    (root / "tests" / "test_new.py").write_text("def test_z():\n    assert True\n")
    out = fr(
        root,
        [
            *("acceptance", "add", "--id", ROW, "--capability", "Widget"),
            *("--acceptance", "loc-1 holds", "--origin", "spec:spec#R1", "--status", "local"),
            *("--level", "unit=t:tests/test_new.py#test_z", "--notes", "test_z verifies it"),
        ],
    )
    assert out.exit_code == 0, out.output
    commit_all(root, "local")
    assert git(root, "ls-files", "tests/test_new.py").strip() == ""
    before = (root / FRAGMENT).read_bytes()

    out = _deliver_flags(root)

    assert out.exit_code == 2, out.output
    flat = " ".join(out.output.split())
    assert f"row {ROW}: tests/test_new.py is not committed at HEAD" in flat
    assert (root / FRAGMENT).read_bytes() == before
    assert not _body(root).exists(), "refused before the PR gate"


def test_git_unable_to_read_head_refuses_naming_the_row(
    tmp_path: Path, live: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """l-tests-r4: `head_blobs` answering None (git cannot read HEAD) refuses deliver,
    naming every row, before the PR gate."""
    from fr.acceptance import local as local_mod

    root = _at_deliver(tmp_path)
    _add_local(root)
    before = (root / FRAGMENT).read_bytes()
    monkeypatch.setattr(local_mod, "head_blobs", lambda *_a, **_k: None)

    out = _deliver_flags(root)

    assert out.exit_code == 2, out.output
    assert f"row {ROW}: git cannot read HEAD" in " ".join(out.output.split())
    assert (root / FRAGMENT).read_bytes() == before
    assert not _body(root).exists(), "refused before the PR gate"


def test_a_tests_witness_that_is_no_local_run_refuses_through_deliver(
    tmp_path: Path, live: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """l-tests-r4: a `tests: ci` witness the forge vouched for is neither a fresh log
    nor a reuse: deliver refuses to stamp, naming the row. The forge's answer is the
    one thing faked (this sandbox has no forge)."""
    from fr.run import ci_evidence

    root = _at_deliver(tmp_path)
    _add_local(root)
    before = (root / FRAGMENT).read_bytes()
    witness = "ci:abc+def;tree=0123"
    monkeypatch.setattr(ci_evidence, "verify_ci", lambda *_a, **_k: witness)

    out = _deliver_flags(root, tests="ci")

    assert out.exit_code == 2, out.output
    flat = " ".join(out.output.split())
    assert f"row {ROW}: tests: {witness} is not a local suite log" in flat
    assert not _body(root).exists(), "refused before the PR gate"
    assert (root / FRAGMENT).read_bytes() == before
    assert "local" not in _row(root)
