"""`scripts/ci_lane.py`: which lane a CI run takes, and whether `ci-ok` passes it
(spec 2026-11-24-ci-economy R5, R15, R17).

The fixture repos live under `tmp_path`; the forge payloads are captures
(`tests/fixtures/ci_lane/README.md`). Nothing here reads this checkout's git state.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.own_artifacts

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import ci_lane  # noqa: E402

# ── Task 1: lane_for and classify (R15) ───────────────────────────────────


@pytest.mark.parametrize(
    "paths",
    [
        ["docs/x.md"],
        [".changes/a.yaml"],
        ["README.md"],
        [".test_durations"],
        ["docs/superpowers/runs/r.yaml", "AGENTS.md", ".changes/b.yaml"],
    ],
)
def test_a_change_with_nothing_installable_tested_or_in_ci_is_light(paths: list[str]) -> None:
    assert ci_lane.lane_for(paths) == "light"


@pytest.mark.parametrize(
    "paths",
    [
        ["packages/fr/src/fr/x.py"],
        ["scripts/x.py"],
        ["plugins/super-fr/skills/a/SKILL.md"],
        ["tests/unit/test_x.py"],
        [".github/workflows/ci.yml"],
        ["docs/x.md", "packages/fr/src/fr/x.py"],
        ["docs/x.md", "tests/conftest.py"],
        [],
    ],
)
def test_an_installable_tested_or_ci_path_or_no_path_is_full(paths: list[str]) -> None:
    assert ci_lane.lane_for(paths) == "full"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _write_commit(repo: Path, rel: str, message: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(message + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


@pytest.fixture
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return tmp_path


def _pr_checkout(tmp: Path, pr_path: str, *, base_moves: str | None = None) -> Path:
    """A clone checked out the way `pull_request` checks out: HEAD is a merge commit
    whose first parent is the base tip and second parent the PR head."""
    origin = tmp / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _write_commit(origin, "packages/fr/src/fr/x.py", "base")
    _git(origin, "checkout", "-q", "-b", "feat/x")
    _write_commit(origin, pr_path, "pr change")
    _git(origin, "checkout", "-q", "main")
    if base_moves:
        _write_commit(origin, base_moves, "base moves")
    clone = tmp / "clone"
    _git(tmp, "clone", "-q", str(origin), str(clone))
    _git(clone, "fetch", "-q", "origin", "feat/x")
    _git(clone, "merge", "-q", "--no-ff", "-m", "merge", "FETCH_HEAD")
    return clone


def _outputs(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if line)


def test_classify_reads_a_docs_only_pull_request_as_light(isolated_git: Path) -> None:
    clone = _pr_checkout(isolated_git, "docs/guide.md")
    out = isolated_git / "github_output"
    code = ci_lane.main(["classify", "--base", "main"], cwd=clone, env={"GITHUB_OUTPUT": str(out)})
    assert code == 0
    assert _outputs(out) == {"lane": "light"}


def test_classify_diffs_against_the_merge_base_not_the_moved_base_tip(isolated_git: Path) -> None:
    # The base moved an installable path after the PR branched: that is not the PR's change.
    clone = _pr_checkout(isolated_git, "docs/guide.md", base_moves="scripts/y.py")
    out = isolated_git / "github_output"
    ci_lane.main(["classify", "--base", "main"], cwd=clone, env={"GITHUB_OUTPUT": str(out)})
    assert _outputs(out) == {"lane": "light"}


def test_classify_reads_an_installable_pull_request_as_full(isolated_git: Path) -> None:
    clone = _pr_checkout(isolated_git, "packages/fr/src/fr/y.py")
    out = isolated_git / "github_output"
    ci_lane.main(["classify", "--base", "main"], cwd=clone, env={"GITHUB_OUTPUT": str(out)})
    assert _outputs(out) == {"lane": "full"}


def test_classify_reads_a_single_parent_head_against_the_merge_base(isolated_git: Path) -> None:
    clone = _pr_checkout(isolated_git, "docs/guide.md")
    _git(clone, "reset", "-q", "--hard", "HEAD^2")
    out = isolated_git / "github_output"
    ci_lane.main(["classify", "--base", "main"], cwd=clone, env={"GITHUB_OUTPUT": str(out)})
    assert _outputs(out) == {"lane": "light"}


def test_classify_is_full_when_git_cannot_read_the_diff(isolated_git: Path) -> None:
    clone = _pr_checkout(isolated_git, "docs/guide.md")
    out = isolated_git / "github_output"
    code = ci_lane.main(
        ["classify", "--base", "no-such-branch"], cwd=clone, env={"GITHUB_OUTPUT": str(out)}
    )
    assert code == 0
    assert _outputs(out) == {"lane": "full"}


def test_classify_is_full_outside_a_git_repo(isolated_git: Path) -> None:
    out = isolated_git / "github_output"
    ci_lane.main(["classify", "--base", "main"], cwd=isolated_git, env={"GITHUB_OUTPUT": str(out)})
    assert _outputs(out) == {"lane": "full"}


# ── Task 2: landed (R5) ───────────────────────────────────────────────────

FIXTURES = REPO / "tests" / "fixtures" / "ci_lane"
SHA = "d52f788b0821c2350c9736e5429bc7eca3e07cdd"
THIS_RUN = 99999999999


def _main_push_runs() -> dict:
    return json.loads((FIXTURES / "runs_main_push.json").read_text())


def _captured_ci_run(**changes: object) -> dict:
    runs = _main_push_runs()["workflow_runs"]
    run = next(r for r in runs if r["path"] == ".github/workflows/ci.yml")
    return {**run, **changes}


def _payload(*runs: dict) -> dict:
    return {"total_count": len(runs), "workflow_runs": list(runs)}


def test_a_successful_ci_push_run_on_an_fr_queue_branch_is_trusted() -> None:
    queue_run = _captured_ci_run(head_branch="fr-queue/s/slot-1", id=45430000001)
    payload = _payload(*_main_push_runs()["workflow_runs"], queue_run)
    assert ci_lane.landed_run(payload, THIS_RUN) == 45430000001


@pytest.mark.parametrize(
    "run",
    [
        pytest.param(
            json.loads((FIXTURES / "run_pull_request.json").read_text())
            | {"head_branch": "fr-queue/s/slot-1"},
            id="a pull_request run",
        ),
        pytest.param(_captured_ci_run(), id="the main push run"),
        pytest.param(
            _captured_ci_run(head_branch="fr-queue/s/slot-1", path=".github/workflows/release.yml"),
            id="another workflow's path",
        ),
        pytest.param(
            _captured_ci_run(head_branch="fr-queue/s/slot-1", conclusion="failure"), id="a failure"
        ),
        pytest.param(
            _captured_ci_run(
                head_branch="fr-queue/s/slot-1", conclusion=None, status="in_progress"
            ),
            id="still running",
        ),
        pytest.param(
            _captured_ci_run(head_branch="fr-queue/s/slot-1", id=THIS_RUN), id="this run itself"
        ),
        pytest.param(
            _captured_ci_run(head_branch="feat/fr-queue/x"), id="fr-queue/ not at the start"
        ),
    ],
)
def test_no_other_run_is_trusted(run: dict) -> None:
    assert ci_lane.landed_run(_payload(run), THIS_RUN) is None


@pytest.mark.parametrize("payload", [{}, [], "x", {"workflow_runs": "x"}, {"workflow_runs": [1]}])
def test_a_payload_of_the_wrong_shape_trusts_nothing(payload: object) -> None:
    assert ci_lane.landed_run(payload, THIS_RUN) is None


class _Gh:
    def __init__(self, stdout: str = "", returncode: int = 0, raises: bool = False) -> None:
        self.stdout, self.returncode, self.raises = stdout, returncode, raises
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        if self.raises:
            raise FileNotFoundError("gh")
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, "err")


def _landed(tmp_path: Path, gh: _Gh) -> dict[str, str]:
    out = tmp_path / "github_output"
    out.touch()
    code = ci_lane.main(
        ["landed", "--sha", SHA, "--run", str(THIS_RUN), "--repo", "derio-net/super-fr"],
        env={"GITHUB_OUTPUT": str(out)},
        runner=gh,
    )
    assert code == 0
    return _outputs(out)


def test_landed_names_the_trusted_run(tmp_path: Path) -> None:
    queue_run = _captured_ci_run(head_branch="fr-queue/s/slot-1", id=45430000001)
    gh = _Gh(json.dumps(_payload(queue_run)))
    assert _landed(tmp_path, gh) == {"lane": "landed", "trusted_run": "45430000001"}
    assert gh.calls == [
        [
            "gh",
            "api",
            f"repos/derio-net/super-fr/actions/runs?head_sha={SHA}&event=push&per_page=100",
        ]
    ]


def test_landed_is_full_when_no_run_qualifies(tmp_path: Path) -> None:
    assert _landed(tmp_path, _Gh(json.dumps(_main_push_runs()))) == {"lane": "full"}


@pytest.mark.parametrize(
    "gh",
    [_Gh("", returncode=1), _Gh("not json"), _Gh(raises=True)],
    ids=["gh fails", "non-JSON", "no gh"],
)
def test_landed_is_full_when_the_forge_cannot_be_read(tmp_path: Path, gh: _Gh) -> None:
    assert _landed(tmp_path, gh) == {"lane": "full"}


# ── Task 3: verdict (R17) ─────────────────────────────────────────────────

JOBS = (
    "classify",
    "lint",
    "typecheck",
    "plan",
    "collect",
    "test",
    "split-check",
    "coverage",
    "scoped-tests",
    "validate-artifacts",
    "opencode-plugin-test",
    "version-sync",
    "change-fragment",
    "docs-check",
    "site-build",
)
SHARDS = ("plan", "collect", "test", "split-check", "coverage")


def _needs(default: str, **results: str) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for job in JOBS:
        result = results.get(job.replace("-", "_"), default)
        out[job] = {"result": result, "outputs": {}}
    return out


def _full(**results: str) -> dict[str, dict[str, object]]:
    return _needs("success", **{"scoped_tests": "skipped", **results})


def _light(**results: str) -> dict[str, dict[str, object]]:
    shards = {job.replace("-", "_"): "skipped" for job in SHARDS}
    return _needs("success", **{**shards, **results})


def _landed_needs(**results: str) -> dict[str, dict[str, object]]:
    return _needs("skipped", **{"classify": "success", "validate_artifacts": "success", **results})


@pytest.mark.parametrize(
    ("lane", "needs"),
    [
        ("full", _full()),
        ("full", _full(change_fragment="skipped")),  # skipped by its own condition off a PR
        ("full", _full(scoped_tests="success")),
        ("light", _light()),
        ("landed", _landed_needs()),
    ],
)
def test_a_lane_whose_jobs_did_what_it_asks_passes(lane: str, needs: dict) -> None:
    ok, _ = ci_lane.verdict(lane, needs)
    assert ok


@pytest.mark.parametrize("bad", ["failure", "cancelled"])
@pytest.mark.parametrize("lane", ["full", "light", "landed"])
@pytest.mark.parametrize("job", ["lint", "validate-artifacts", "classify"])
def test_a_failed_or_cancelled_job_fails_every_lane(lane: str, job: str, bad: str) -> None:
    needs = {"full": _full, "light": _light, "landed": _landed_needs}[lane]()
    needs[job]["result"] = bad
    ok, reason = ci_lane.verdict(lane, needs)
    assert not ok
    assert job in reason


@pytest.mark.parametrize("job", ["collect", "test", "split-check", "coverage"])
def test_full_needs_the_shards_to_have_run(job: str) -> None:
    needs = _full()
    needs[job]["result"] = "skipped"
    ok, reason = ci_lane.verdict("full", needs)
    assert not ok
    assert job in reason


def test_light_needs_the_scoped_tests_to_have_run() -> None:
    ok, reason = ci_lane.verdict("light", _light(scoped_tests="skipped"))
    assert not ok
    assert "scoped-tests" in reason


@pytest.mark.parametrize("job", ["lint", "typecheck", "docs-check", "change-fragment", "classify"])
def test_light_skips_only_the_shard_jobs(job: str) -> None:
    needs = _light()
    needs[job]["result"] = "skipped"
    ok, reason = ci_lane.verdict("light", needs)
    assert not ok
    assert job in reason


@pytest.mark.parametrize("job", ["validate-artifacts", "classify"])
def test_landed_needs_the_classifier_and_the_strict_validation(job: str) -> None:
    needs = _landed_needs()
    needs[job]["result"] = "skipped"
    ok, reason = ci_lane.verdict("landed", needs)
    assert not ok
    assert job in reason


@pytest.mark.parametrize("lane", ["", "fast", None])
def test_a_missing_or_unknown_lane_fails(lane: str | None) -> None:
    ok, reason = ci_lane.verdict(lane, _full())
    assert not ok
    assert "lane" in reason


def test_an_unknown_result_fails() -> None:
    ok, reason = ci_lane.verdict("full", _full(lint="timed_out"))
    assert not ok
    assert "lint" in reason


def test_verdict_reads_its_inputs_from_the_environment(capsys: pytest.CaptureFixture[str]) -> None:
    env = {"LANE": "landed", "NEEDS": json.dumps(_landed_needs()), "TRUSTED_RUN": "45430000001"}
    assert ci_lane.main(["verdict"], env=env) == 0
    line = capsys.readouterr().out.strip()
    assert len(line.splitlines()) == 1
    assert "landed" in line and "45430000001" in line


@pytest.mark.parametrize(
    "env",
    [
        {"LANE": "full", "NEEDS": json.dumps(_full(test="failure"))},
        {"LANE": "full"},
        {"LANE": "full", "NEEDS": "not json"},
        {"LANE": "full", "NEEDS": "[]"},
        {"NEEDS": json.dumps(_full())},
    ],
    ids=["a failed job", "no NEEDS", "non-JSON NEEDS", "NEEDS not a mapping", "no LANE"],
)
def test_verdict_exits_one_with_one_line(env: dict, capsys: pytest.CaptureFixture[str]) -> None:
    assert ci_lane.main(["verdict"], env=env) == 1
    assert len(capsys.readouterr().out.strip().splitlines()) == 1


def test_a_path_with_a_ref_suffix_still_names_the_ci_workflow() -> None:
    """Review p2-r2: should GitHub report `path` as `<file>@<ref>`, the match still holds."""
    run = {
        "id": 7,
        "path": ".github/workflows/ci.yml@refs/heads/fr-queue/s/slot-1",
        "event": "push",
        "head_branch": "fr-queue/s/slot-1",
        "conclusion": "success",
    }
    assert ci_lane.landed_run({"workflow_runs": [run]}, 8) == 7


def test_the_script_parses_on_the_runners_older_python() -> None:
    """Review p2-r3: `classify` runs this script on ubuntu-latest's own python3, which is
    older than the repo's 3.14 floor, so it must parse as Python 3.10."""
    import ast
    from pathlib import Path

    for name in ("ci_lane.py", "installable.py"):
        source = (Path(__file__).resolve().parents[2] / "scripts" / name).read_text()
        ast.parse(source, feature_version=(3, 10))
