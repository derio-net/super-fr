"""`fr verification walk` — the candidate install, the smoke, each row's scenario
and the log (spec 2026-10-06-verification-strategies §C, R8-R10).

Every test runs against a tmp repo with a FAKE install contract: a shell script
that writes `{prefix}/bin/fakefr`. Nothing here installs a real `fr`, and the
operator's own is fingerprinted by the walk itself.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml
from fr.cli import app
from fr.run.model import RunState, StepRecord, save_run_state
from typer.testing import CliRunner

runner = CliRunner()
RUN = "w1"
SPEC = "docs/superpowers/specs/s.md"
SPEC_REF = f"proj:{SPEC}"

INSTALL = """#!/bin/sh
prefix="$1"
mkdir -p "$prefix/bin"
cat > "$prefix/bin/fakefr" <<'EOS'
#!/bin/sh
if [ "$1" = "--version" ]; then echo "fakefr 1.2.3"; else echo "status in $(pwd)"; fi
EOS
chmod +x "$prefix/bin/fakefr"
echo "tools: $UV_TOOL_DIR $UV_TOOL_BIN_DIR"
echo fakefr
"""


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def _script(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _repo(
    tmp_path: Path,
    *,
    install: str | None = INSTALL,
    strategy: str = "candidate",
    rows: dict[str, str | None] | None = None,
) -> Path:
    """A committed repo: contract, spec, matrix, a run, and a scenario per row
    (`rows` maps row id -> scenario body, `None` for a row naming none)."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    if install is not None:
        path = root / ".fr" / "candidate-install"
        path.parent.mkdir()
        path.write_text(install)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    rows = {"ok": "echo fine", "bad": "echo broke; exit 3"} if rows is None else rows
    (root / "docs/superpowers/specs").mkdir(parents=True)
    (root / SPEC).write_text(f"# S\n\n## Verification\n\nstrategy: {strategy}\n")
    matrix_rows = []
    for rid, body in rows.items():
        row: dict[str, object] = {
            "id": rid,
            "capability": "c",
            "acceptance": f"{rid} works",
            "origin": [f"{SPEC_REF}#R1"],
            "status": "not-implemented",
        }
        if body is not None:
            _script(root, f"scenarios/{rid}.sh", body)
            row["scenario"] = f"scenarios/{rid}.sh"
        matrix_rows.append(row)
    (root / "docs/acceptance").mkdir(parents=True)
    (root / "docs/acceptance/matrix.yaml").write_text(
        yaml.safe_dump({"schema_version": 4, "org": "o", "repo": "proj", "rows": matrix_rows})
    )
    save_run_state(
        root,
        RunState(
            run=RUN,
            workflow="fr-goal@1",
            branch="b",
            started="2026-10-06T11:00:00+00:00",
            cursor="deliver",
            steps={
                "spec": StepRecord(
                    state="done", at="2026-10-06T12:00:00+00:00", emitted={"spec": SPEC}
                )
            },
        ),
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init", "--no-verify")
    return root


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _walk(root: Path, *args: str, model: str | None = "m-1"):
    argv = ["verification", "walk", "--run", RUN, *args]
    if model is not None:
        argv += ["--model", model]
    return runner.invoke(app, argv, env={**os.environ, "VK_REPO_ROOT": str(root)})


def _logs(home: Path) -> list[Path]:
    return sorted((home / ".cache/fr/walks" / RUN).glob("*.log"))


def _header(log: Path) -> dict:
    text = log.read_text()
    return yaml.safe_load(text.split("---\n")[1])


def test_the_walk_refuses_a_repo_without_the_install_contract_naming_it(tmp_path: Path) -> None:
    root = _repo(tmp_path, install=None)

    result = _walk(root)

    assert result.exit_code == 2
    assert ".fr/candidate-install" in result.output


def test_the_walk_requires_a_model(tmp_path: Path) -> None:
    result = _walk(_repo(tmp_path), model=None)

    assert result.exit_code == 2
    assert "--model" in result.output


def test_a_passing_walk_installs_into_a_prefix_and_writes_the_log(
    tmp_path: Path, _home: Path
) -> None:
    root = _repo(tmp_path, rows={"ok": "echo fine; echo $FR_WALK_PREFIX > prefix.txt"})
    from fr.run.code_tree import code_tree

    result = _walk(root, "--harness", "claude-code")

    assert result.exit_code == 0, result.output
    (log,) = _logs(_home)
    header = _header(log)
    assert header["fr-walk"] == 1
    assert (header["run"], header["strategy"], header["harness"], header["model"]) == (
        RUN,
        "candidate",
        "claude-code",
        "m-1",
    )
    assert header["code_tree"] == code_tree(root)
    names = [s["name"] for s in header["steps"]]
    assert names == ["install", "smoke:fixture", "smoke:version", "smoke:status", "row:ok"]
    assert all(s["exit"] == 0 for s in header["steps"])
    text = log.read_text()
    assert "fakefr 1.2.3" in text  # the smoke ran the INSTALLED tool
    prefix = text.split("tools: ", 1)[1].split()[0]
    assert prefix.endswith("/uv-tools") and "fr-walk-" in prefix
    assert not prefix.startswith(str(root))  # outside the repo
    assert "fr-walk-" in text.split("tools: ", 1)[1].split()[1]  # UV_TOOL_BIN_DIR too
    # The repo is exactly as the walk found it: scenarios ran in a fixture copy.
    assert _git(root, "status", "--porcelain") == ""


def test_a_failing_scenario_exits_non_zero_and_is_in_the_log(tmp_path: Path, _home: Path) -> None:
    result = _walk(_repo(tmp_path))

    assert result.exit_code == 1
    steps = {s["name"]: s["exit"] for s in _header(_logs(_home)[0])["steps"]}
    assert steps["row:ok"] == 0 and steps["row:bad"] == 3
    assert "broke" in _logs(_home)[0].read_text()


def test_scenarios_run_on_the_installed_tool_in_a_fresh_fixture_copy(
    tmp_path: Path, _home: Path
) -> None:
    root = _repo(tmp_path, rows={"ok": 'fakefr status; test -d .git; echo "$FR_WALK_PREFIX"'})

    assert _walk(root).exit_code == 0

    text = _logs(_home)[0].read_text()
    assert "status in" in text and "work-ok" in text  # PATH has {bin}, cwd is the row's copy


def test_client_runs_scenarios_with_that_cwd(tmp_path: Path, _home: Path) -> None:
    client = tmp_path / "client"
    client.mkdir()
    root = _repo(tmp_path, rows={"ok": "pwd"})

    assert _walk(root, "--client", str(client)).exit_code == 0

    assert str(client.resolve()) in _logs(_home)[0].read_text()


def test_row_narrows_the_walk_and_an_unknown_row_is_refused(tmp_path: Path, _home: Path) -> None:
    root = _repo(tmp_path)

    assert _walk(root, "--row", "ok").exit_code == 0
    assert [s["name"] for s in _header(_logs(_home)[0])["steps"]][-1] == "row:ok"
    refused = _walk(root, "--row", "nope")
    assert refused.exit_code == 2 and "nope" in refused.output


def test_a_row_with_no_scenario_is_refused_by_id(tmp_path: Path) -> None:
    result = _walk(_repo(tmp_path, rows={"ok": "true", "unscripted": None}))

    assert result.exit_code == 2
    assert "unscripted" in result.output and "scenario" in result.output


def test_an_uncommitted_code_path_is_refused(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "extra.py").write_text("x = 1\n")

    result = _walk(root)

    assert result.exit_code == 2 and "extra.py" in result.output


def test_a_post_merge_strategy_has_nothing_to_walk(tmp_path: Path) -> None:
    result = _walk(_repo(tmp_path, strategy="live"))

    assert result.exit_code == 2 and "post-merge" in result.output


def test_an_install_that_touches_the_operators_fr_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _home: Path
) -> None:
    pinned = tmp_path / "operator" / "fr"
    pinned.parent.mkdir()
    pinned.write_text("#!/bin/sh\necho operator\n")
    monkeypatch.setenv("FR_HARNESS_FR", str(pinned))
    # An install that scribbles on the pinned fr (what an unisolated `uv tool
    # install` does to ~/.local/bin/fr).
    root = _repo(tmp_path, install=INSTALL + f'echo tampered >> "{pinned}"\necho fakefr\n')

    result = _walk(root)

    assert result.exit_code == 2
    assert "operator's own fr" in result.output.replace("\n", " ")
    # Review p3-r3: every step of that log passed, so the log itself must say
    # the operator's fr moved — or a later `deliver` would accept it.
    from fr.verification.walk import WalkOwed, check_walk_log, parse_walk_log

    log = parse_walk_log(_logs(_home)[0].read_text())
    assert ("operator-fr-unchanged", 1) in [(s.name, s.exit) for s in log.steps]
    problems = check_walk_log(log, WalkOwed(), log.code_tree, run=RUN)
    assert any("operator-fr-unchanged" in p for p in problems)
    assert not any(s.name.startswith("row:") for s in log.steps)  # stopped at the install


def test_a_scenario_that_touches_the_operators_fr_fails_the_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _home: Path
) -> None:
    """The guard runs at the end too: a row's scenario is a child as well."""
    pinned = tmp_path / "operator" / "fr"
    pinned.parent.mkdir()
    pinned.write_text("#!/bin/sh\necho operator\n")
    monkeypatch.setenv("FR_HARNESS_FR", str(pinned))
    root = _repo(tmp_path, rows={"ok": f'echo tampered >> "{pinned}"'})

    assert _walk(root, "--row", "ok").exit_code == 2

    from fr.verification.walk import parse_walk_log

    steps = parse_walk_log(_logs(_home)[0].read_text()).steps
    assert steps[-1].name == "operator-fr-unchanged" and steps[-1].exit != 0


def test_the_throwaway_prefix_is_removed_after_the_walk(tmp_path: Path, _home: Path) -> None:
    """Review p3-r8: the candidate install is throwaway — nothing stays behind."""
    root = _repo(tmp_path, rows={"ok": 'echo "prefix=$FR_WALK_PREFIX"'})

    assert _walk(root, "--row", "ok").exit_code == 0

    text = _logs(_home)[0].read_text()
    prefix = Path(text.split("prefix=", 1)[1].split("\n", 1)[0])
    assert prefix.name.startswith("fr-walk-") and not prefix.exists()


def test_the_candidate_never_sees_the_operators_identity_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _home: Path
) -> None:
    pinned = tmp_path / "operator-fr"
    pinned.write_text("#!/bin/sh\n")
    monkeypatch.setenv("FR_HARNESS_FR", str(pinned))
    root = _repo(tmp_path, rows={"ok": 'echo "pin=[$FR_HARNESS_FR]"'})

    assert _walk(root).exit_code == 0

    assert "pin=[]" in _logs(_home)[0].read_text()


# --- the log, judged ---------------------------------------------------------------


def test_check_walk_log_names_each_cause() -> None:
    from fr.acceptance.model import Row
    from fr.verification.walk import WalkLog, WalkOwed, WalkStep, check_walk_log

    def row(rid: str) -> Row:
        return Row(
            id=rid, capability="c", acceptance="a", origin=("p:x.md",), status="not-implemented"
        )

    steps = (
        WalkStep("install", 0, 1.0),
        WalkStep("smoke:version", 0, 0.1),
        WalkStep("smoke:status", 0, 0.1),
        WalkStep("row:a", 1, 0.1),
    )
    log = WalkLog("r", "candidate", "t" * 64, "h", "m", steps)
    owed = WalkOwed(rows=(row("a"), row("b")))

    problems = " | ".join(check_walk_log(log, owed, "u" * 64, run="r"))

    assert "code tree" in problems  # stale
    assert "'row:a' failed" in problems
    assert "'b' is not covered" in problems
    assert check_walk_log(log, WalkOwed(), "t" * 64, run="r") == ["step 'row:a' failed (exit 1)"]


def test_check_walk_log_refuses_another_runs_or_another_strategys_log() -> None:
    """Review p3-r2: a passing log of ANOTHER run, or of a strategy this run
    does not owe, is not this run's walk — the header must match both."""
    from fr.verification.walk import WalkLog, WalkOwed, WalkStep, check_walk_log

    steps = (
        WalkStep("install", 0, 1.0),
        WalkStep("smoke:version", 0, 0.1),
        WalkStep("smoke:status", 0, 0.1),
    )
    tree = "t" * 64
    owed = WalkOwed(run_strategy="candidate", strategy="candidate")

    assert (
        check_walk_log(WalkLog("r", "candidate", tree, "h", "m", steps), owed, tree, run="r") == []
    )
    other_run = " | ".join(
        check_walk_log(WalkLog("x", "candidate", tree, "h", "m", steps), owed, tree, run="r")
    )
    assert "run 'x'" in other_run
    other_strategy = " | ".join(
        check_walk_log(WalkLog("r", "client-live", tree, "h", "m", steps), owed, tree, run="r")
    )
    assert "strategy 'client-live'" in other_strategy and "'candidate'" in other_strategy


def test_walk_owed_names_the_rows_common_strategy(tmp_path: Path) -> None:
    """With no run-level strategy owed, the expected strategy is the owed rows'
    own (p3-r2)."""
    from fr.requirements import load_spec_matrix
    from fr.verification.rows import SpecVerification
    from fr.verification.spec_section import parse_section
    from fr.verification.walk import walk_owed

    root = _repo(tmp_path, strategy="live", rows={"ok": "true"})
    matrix, spec_ref = load_spec_matrix(root, SPEC)
    section = parse_section("## Verification\n\nstrategy: live\n- ok: candidate\n")
    owed = walk_owed(matrix, spec_ref, SpecVerification(root, section), root)

    assert owed.run_strategy is None and owed.strategy == "candidate"


def test_a_log_with_no_header_is_not_a_walk_log() -> None:
    from fr.verification.walk import WalkError, parse_walk_log

    with pytest.raises(WalkError, match="not a walk log"):
        parse_walk_log("all green, trust me\n")
