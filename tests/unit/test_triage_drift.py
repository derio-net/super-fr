"""Version drift: re-home a run on an incompatible major (spec 2026-10-07-cloud-triage
R17, R18, §G; Test Plan 12).

`fr.triage.drift` is pure (cursors, the latest release and the ledger in; requests
out); the drive pass reads each active batch's run cursor from its branch head and
the latest release through the forge client, and asks the batch's runner to re-home.
The pass tests reuse `test_triage_driver_pass`'s world, clone and state-ref fakes,
with the real `claude-cloud` runner and its mailbox.
"""

from __future__ import annotations

import json
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Any

import fr.cli  # noqa: F401 - the command modules load in the CLI's order
import pytest
import yaml
from fr.commands import triage_batch_cmd
from fr.gh import GhError
from fr.real_ghrestclient import RealGhRestClient
from fr.triage import drift, state_ref
from fr.triage.drift import Ledger, RunVersion
from fr_claude_cloud.runner import ClaudeCloudRunner

from tests.unit.github_rest_support import FixtureGh
from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    REPO,
    DriveCheckout,
    World,
    _state,
    checkout_fixture,
    world_fixture,
)
from tests.unit.test_triage_driver_pass import (  # noqa: F401 - fixtures
    CONFIG,
    HOST_ID,
    Runners,
    _batch,
    _pass,
    _record,
    _workspace,
    clock,
    remote,
    visibility,
)

ITEM = f"{REPO}/run/batch-b3"
CURSOR_PATH = "docs/superpowers/runs/2026-10-08-feat-batch-b3.yaml"


def _rv(run: str | None = "r1", version: str | None = "5.17.1", status: str = "idle") -> RunVersion:
    return RunVersion(
        batch="b3",
        item=ITEM,
        branch="feat/batch-b3",
        run=run,
        fr_version=version,
        status=status,
    )


# ------------------------------------------------------------------ the pure part


@pytest.mark.parametrize(
    ("version", "expected"),
    [("5.17.1", 5), ("v6.0.0", 6), ("10.2", 10), (None, None), ("", None), ("main", None)],
)
def test_major_reads_a_version_or_tag(version: str | None, expected: int | None) -> None:
    assert drift.major(version) == expected


def test_the_cursor_is_found_among_the_prs_files() -> None:
    files = ["README.md", "docs/superpowers/runs/x.records/implement.yaml", CURSOR_PATH]
    assert drift.cursor_path(files) == CURSOR_PATH
    assert drift.cursor_path(["docs/superpowers/runs/archive/old/y.yaml"]) is None
    assert drift.cursor_path([]) is None


def test_a_cursor_reads_its_run_and_fr_version() -> None:
    assert drift.read_cursor("run: r1\nfr_version: 5.17.1\n") == ("r1", "5.17.1")
    assert drift.read_cursor("run: r1\n") == ("r1", None)
    assert drift.read_cursor(":\n- not yaml: [") == (None, None)


def test_the_same_major_requests_nothing() -> None:
    plan = drift.plan_drift([_rv(version="6.0.3")], "v6.1.0", Ledger())
    assert plan.rehomes == () and plan.unknown == ()


def test_a_different_major_requests_one_rehome_at_the_sessions_idle() -> None:
    plan = drift.plan_drift([_rv()], "v6.0.0", Ledger())

    assert [(r.item, r.run, r.recorded, r.release) for r in plan.rehomes] == [
        (ITEM, "r1", "5.17.1", "v6.0.0")
    ]
    brief = plan.rehomes[0].brief
    assert "feat/batch-b3" in brief and "fr pickup --run r1" in brief


@pytest.mark.parametrize("status", ["working", "blocked", "unknown"])
def test_a_drifted_session_that_is_not_idle_waits_for_its_idle(status: str) -> None:
    plan = drift.plan_drift([_rv(status=status)], "v6.0.0", Ledger())
    assert plan.rehomes == ()


def test_a_run_already_rehomed_for_this_release_is_never_rehomed_twice() -> None:
    ledger = Ledger().with_rehomes(drift.plan_drift([_rv()], "v6.0.0", Ledger()).rehomes, at="t")

    assert drift.plan_drift([_rv()], "v6.0.0", ledger).rehomes == ()
    # a later release is a new (run, release) pair
    assert len(drift.plan_drift([_rv()], "v7.0.0", ledger).rehomes) == 1


def test_a_run_with_no_recorded_version_is_reported_once_and_never_rehomed() -> None:
    plan = drift.plan_drift([_rv(version=None)], "v6.0.0", Ledger())
    assert plan.rehomes == ()
    assert [u.run for u in plan.unknown] == ["r1"]

    again = drift.plan_drift([_rv(version=None)], "v6.0.0", Ledger().with_reported(plan.unknown))
    assert again.rehomes == () and again.unknown == ()


def test_no_release_known_plans_nothing() -> None:
    plan = drift.plan_drift([_rv(), _rv(run="r2", version=None)], None, Ledger())
    assert plan.rehomes == () and plan.unknown == ()


def test_the_ledger_travels_in_the_ref_so_a_restore_never_rehomes_twice(tmp_path: Path) -> None:
    assert drift.REHOMES_FILE in state_ref.REF_FILES
    first = tmp_path / "first"
    first.mkdir()
    plan = drift.plan_drift([_rv(), _rv(run="r2", version=None)], "v6.0.0", Ledger())
    drift.save_ledger(first, drift.load_ledger(first).with_rehomes(plan.rehomes, at="t")
                      .with_reported(plan.unknown))  # fmt: skip

    restored = tmp_path / "restored"  # a fresh container: only the ref's files
    restored.mkdir()
    shutil.copy(first / drift.REHOMES_FILE, restored / drift.REHOMES_FILE)

    again = drift.plan_drift([_rv(), _rv(run="r2", version=None)], "v6.0.0",
                             drift.load_ledger(restored))  # fmt: skip
    assert again.rehomes == () and again.unknown == ()


def test_an_absent_ledger_is_empty_and_a_corrupt_one_refuses(tmp_path: Path) -> None:
    assert drift.load_ledger(tmp_path) == Ledger()
    (tmp_path / drift.REHOMES_FILE).write_text("rehomes: 3\n")
    with pytest.raises(drift.TriageError):
        drift.load_ledger(tmp_path)


# ----------------------------------------------------- the forge's releases route


def test_the_rest_client_reads_the_latest_releases_tag_from_the_capture() -> None:
    gh = FixtureGh()
    assert RealGhRestClient(run=gh).latest_release(REPO) == "v5.17.1"
    assert gh.calls == [["api", f"repos/{REPO}/releases/latest"]]


def test_a_repo_with_no_release_has_none() -> None:
    def missing(argv: list[str]) -> GhError:
        return GhError("gh: Not Found (HTTP 404)")

    assert RealGhRestClient(run=FixtureGh(fail=missing)).latest_release(REPO) is None


# ------------------------------------------------------------------- the pass


def _cursor(version: str | None) -> str:
    text = "schema_version: 10\nrun: r-b3\nbranch: feat/batch-b3\n"
    return text + (f"fr_version: {version}\n" if version else "")


def _drifting(
    world: World,
    state: Path,
    *,
    cursors: dict[int, str | None],
    release: str | None = "v6.0.0",
    session_state: str = "completed",
) -> list[tuple[str, str, str]]:
    """Batches b3.. dispatched through claude-cloud, each with an open PR whose files
    carry its run cursor (recording `cursors[n]`) and a recorded idle session."""
    world.config = CONFIG
    reads: list[tuple[str, str, str]] = []
    batches, sessions = [], []
    for n, version in cursors.items():
        world.issues[n] = "open"
        world.pr(100 + n, f"feat/batch-b{n}", [n],
                 files=[f"docs/superpowers/runs/r-b{n}.yaml"])  # fmt: skip
        ev = ("      - {kind: dispatch, at: 2026-10-01T10:00:00Z, runner: claude-cloud, "
              f"handle: h, branch: feat/batch-b{n}}}\n")  # fmt: skip
        batches.append(_batch(f"b{n}", n, events=ev))
        sessions.append({"item": f"{REPO}/run/batch-b{n}", "session": f"s-b{n}",
                         "state": session_state, "branch": f"feat/batch-b{n}"})  # fmt: skip

    texts = {f"sha-{100 + n}": _cursor(v).replace("r-b3", f"r-b{n}") for n, v in cursors.items()}

    def read_file_at_ref(repo: str, path: str, ref: str) -> str:
        reads.append((repo, path, ref))
        return texts[ref]

    world.read_file_at_ref = read_file_at_ref  # type: ignore[attr-defined]
    world.latest_release = lambda repo: release  # type: ignore[attr-defined]
    state.mkdir(parents=True, exist_ok=True)
    _state(state, world, *batches)
    (state / "sessions.yaml").write_text(yaml.safe_dump({"sessions": sessions}))
    return reads


@pytest.fixture
def cloud(runners: Runners) -> ClaudeCloudRunner:
    real = ClaudeCloudRunner()
    runners.by_name["claude-cloud"] = real  # type: ignore[assignment]
    return real


@pytest.fixture
def runners(monkeypatch: pytest.MonkeyPatch) -> Runners:
    found = Runners()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", found)
    return found


@pytest.fixture
def drive(request: pytest.FixtureRequest, cloud: ClaudeCloudRunner) -> list[Any]:
    """A cloud drive pass's world: the clone, the state remote, a private repo and the
    clock (returned, so a test can move it)."""
    for name in ("checkout", "remote", "visibility"):
        request.getfixturevalue(name)
    now: list[Any] = request.getfixturevalue("clock")
    return now


def _requests(outbox: Path, kind: str) -> list[dict[str, Any]]:
    return [r for r in json.loads(outbox.read_text())["requests"] if r["kind"] == kind]


def test_a_pass_rehomes_only_the_run_on_another_major_once(
    tmp_path: Path, world: World, drive: list[Any]
) -> None:
    ws, state = _workspace(tmp_path, "ws")
    reads = _drifting(world, state, cursors={3: "5.17.1", 4: "6.0.2", 5: None})
    outbox = tmp_path / "outbox.json"

    first = _pass(state, outbox, "--workspace", str(ws), "--state-repo", REPO)

    assert first.exit_code in (0, 3), first.output
    assert {(p, ref) for _, p, ref in reads} >= {
        ("docs/superpowers/runs/r-b3.yaml", "sha-103"),
        ("docs/superpowers/runs/r-b4.yaml", "sha-104"),
    }
    rehomes = _requests(outbox, "rehome")
    assert [(r["item"], r["session"]) for r in rehomes] == [(ITEM, "s-b3")]
    assert "fr pickup --run r-b3" in rehomes[0]["prompt"]
    assert "r-b5" in first.output and "no recorded fr version" in first.output
    ledger = drift.load_ledger(state)
    assert [(e["run"], e["release"]) for e in ledger.rehomes] == [("r-b3", "v6.0.0")]
    assert ledger.reported == ("r-b5",)

    results = tmp_path / "results.json"
    results.write_text(json.dumps([{"id": rehomes[0]["id"], "session": "s-b3-new"}]))
    recorded = _record(state, outbox, results)
    assert recorded.exit_code == 0, recorded.output

    drive[0] = drive[0] + timedelta(minutes=10)
    second = _pass(state, outbox, "--workspace", str(ws), "--state-repo", REPO)

    assert second.exit_code in (0, 3), second.output
    assert _requests(outbox, "rehome") == []
    assert "r-b5" not in second.output, "an unknown version is reported once"


def test_a_working_session_is_not_rehomed_until_it_is_idle(
    tmp_path: Path, world: World, drive: list[Any]
) -> None:
    ws, state = _workspace(tmp_path, "ws")
    _drifting(world, state, cursors={3: "5.17.1"}, session_state="working")
    outbox = tmp_path / "outbox.json"

    result = _pass(state, outbox, "--workspace", str(ws), "--state-repo", REPO)

    assert result.exit_code in (0, 3), result.output
    assert _requests(outbox, "rehome") == []
    assert drift.load_ledger(state).rehomes == ()
