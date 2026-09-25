"""`fr triage batch merge --yes` against real git (spec 2026-09-25-triage-batches
§3.F; Test Plan 14).

A local bare origin stands in for the forge's git side, with real multi-file
version manifests (TOML, JSON and a lockfile) and three batch PR branches. The
forge's API side is faked (`GitForge`): a bare repo cannot answer `gh pr view`
or required checks, so the fake reads each PR head from the bare origin and
"merges" by merging the branch into main in a worker clone and pushing. Every
git operation merge itself performs is real, in the checkout and in scratch
worktrees under the triage state directory.

- `one` is up to date at its slot (1.0.1): merged as it is.
- `two` (1.0.2) is then behind main with a conflict in the version files only:
  resolved by `checkout --theirs`, `set` run with the scratch worktree as cwd,
  pushed, and merged.
- `three` (1.0.3) also conflicts in `a.txt`, which `one` changed: the queue
  stops naming it and keeps the scratch worktree. A re-run resumes at `three`.

Separate worlds (review r3-f2, r3-f10): a PR that bumped the version AND added
a dependency to `pyproject.toml` stops the queue rather than losing the
dependency to `--theirs`; an up-to-date PR off its slot is re-slotted (step
3b); and a kept worktree holding a manual fix is never replaced (r3-f6).
Every `set` leaves an untracked `setv.log` behind, which must never be
committed (r3-f7).
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.triage.gitseam import Checkout
from fr.triage.model import Facts, Issue, PullRequest, TriageConfig
from typer.testing import CliRunner

REPO = "example-org/demo"
VERSION_FILES = ["pyproject.toml", "package.json", "uv.lock"]

SETV = """\
import json, pathlib, re, sys
v = sys.argv[1]
root = pathlib.Path(".")
for name in ("pyproject.toml", "uv.lock"):
    p = root / name
    p.write_text(re.sub(r'^version = "[^"]*"', f'version = "{v}"', p.read_text(), flags=re.M))
p = root / "package.json"
data = json.loads(p.read_text())
data["version"] = v
p.write_text(json.dumps(data, indent=2) + "\\n")
(root / "setv.log").write_text(f"set {v}\\n")  # build output: never committed
"""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _identity(repo: Path) -> None:
    for key, value in (
        ("user.name", "test"),
        ("user.email", "test@example.com"),
        ("commit.gpgsign", "false"),
    ):
        _git(repo, "config", key, value)


def _manifests(root: Path, version: str, extra: str = "") -> None:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "demo"\nversion = "{version}"\n{extra}'
    )
    (root / "package.json").write_text(
        json.dumps({"name": "demo", "version": version}, indent=2) + "\n"
    )
    (root / "uv.lock").write_text(
        f'lock-version = 1\n\n[[package]]\nname = "demo"\nversion = "{version}"\n'
    )


def _branch(seed: Path, name: str, version: str, files: dict[str, str], extra: str = "") -> None:
    _git(seed, "checkout", "--quiet", "-b", name, "main")
    _manifests(seed, version, extra)
    for path, text in files.items():
        (seed / path).write_text(text)
    _git(seed, "add", "--all")
    _git(seed, "commit", "--quiet", "-m", f"{name}: bump to {version}")
    _git(seed, "push", "--quiet", "origin", name)
    _git(seed, "checkout", "--quiet", "main")


class GitForge:
    """The forge's API side over a bare origin: PR heads come from its refs."""

    def __init__(self, origin: Path, worker: Path, prs: dict[int, str]) -> None:
        self.origin, self.worker, self.prs = origin, worker, prs
        self.merged: list[int] = []

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        branch = self.prs[number]
        return {
            "state": "MERGED" if number in self.merged else "OPEN",
            "draft": False,
            "head_oid": _git(self.origin, "rev-parse", f"refs/heads/{branch}"),
            "head_ref": branch,
            "mergeable": "MERGEABLE",
            "merge_state": "CLEAN",
        }

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        return [{"name": "test", "bucket": "pass", "state": "SUCCESS"}]

    def wait_required_checks(self, repo: str, number: int, **kw: Any) -> list[dict[str, Any]]:
        return self.pr_required_checks(repo, number)

    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        branch = self.prs[number]
        assert self.pr_view(repo, number)["head_oid"] == head_sha, "--match-head-commit"
        _git(self.worker, "fetch", "--quiet", "origin")
        _git(self.worker, "checkout", "--quiet", "-B", "main", "origin/main")
        # GitHub refuses a PR that is not mergeable; so does this fake.
        _git(
            self.worker, "merge", "--quiet", "--no-ff", "-m", f"Merge #{number}", f"origin/{branch}"
        )
        _git(self.worker, "push", "--quiet", "origin", "main")
        self.merged.append(number)

    def closing_ref(self, repo: str, number: int) -> str:
        return f"Closes {repo}#{number}"

    def repo_merge_methods(self, repo: str) -> dict[str, Any]:
        return {"default": "merge", "allowed": ["merge"]}


class DemoCheckout(Checkout):
    """A real clone whose origin is a local path: it names the batch's repo."""

    def origin_repo(self) -> str | None:
        return REPO


def _pr(number: int, bid: str, head: str, files: list[str]) -> PullRequest:
    return PullRequest(
        repo=REPO,
        number=number,
        title=bid,
        state="OPEN",
        is_draft=False,
        url=f"https://github.com/{REPO}/pull/{number}",
        head_ref=f"feat/batch-{bid}",
        head_oid=head,
        files=files,
        created_at="2026-09-25T11:00:00+00:00",
    )


# (batch id, PR number, reserved version, {path: text}, extra pyproject lines)
Spec = tuple[str, int, str, dict[str, str], str]


def _build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    specs: list[Spec],
    *,
    main_after: str | None = None,
) -> dict[str, Any]:
    """A bare origin at 1.0.0, one branch per spec cut from it, then (with
    *main_after*) an outside release bumping main after the branches exist."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
    seed = tmp_path / "seed"
    _git(tmp_path, "clone", "--quiet", str(origin), str(seed))
    _identity(seed)
    _git(seed, "checkout", "--quiet", "-b", "main")
    _manifests(seed, "1.0.0")
    (seed / "a.txt").write_text("alpha\n")
    (seed / "scripts").mkdir()
    (seed / "scripts" / "setv.py").write_text(SETV)
    set_cmd = f"{shlex.quote(sys.executable)} scripts/setv.py {{version}}"
    config = {
        "version": {
            "source": {"file": "pyproject.toml", "key": "project.version"},
            "files": VERSION_FILES,
            "set": set_cmd,
        }
    }
    (seed / ".fr").mkdir()
    (seed / ".fr" / "triage.yaml").write_text(yaml.safe_dump(config))
    _git(seed, "add", "--all")
    _git(seed, "commit", "--quiet", "-m", "seed")
    _git(seed, "push", "--quiet", "origin", "main")
    for bid, _, version, files, extra in specs:
        _branch(seed, f"feat/batch-{bid}", version, files, extra)
    if main_after is not None:
        _manifests(seed, main_after)
        _git(seed, "commit", "--quiet", "-am", f"release {main_after}")
        _git(seed, "push", "--quiet", "origin", "main")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "--quiet", str(origin), str(clone))
    _identity(clone)
    worker = tmp_path / "worker"
    _git(tmp_path, "clone", "--quiet", str(origin), str(worker))
    _identity(worker)

    forge = GitForge(origin, worker, {n: f"feat/batch-{b}" for b, n, *_ in specs})
    judgements = (
        "schema: 2\ntiers:\n  - {n: 1, title: Now}\nissues:\n"
        + "".join(f"  demo#{n}: {{tier: 1}}\n" for _, n, *_ in specs)
        + "batches:\n"
        + "".join(
            f'  - id: {b}\n    title: {b}\n    ids: ["demo#{n}"]\n    bump: patch\n'
            f"    events:\n      - {{kind: dispatch, at: 2026-09-25T10:00:00Z, runner: herdr,"
            f" handle: h, branch: feat/batch-{b}, reserved_version: {v}}}\n"
            for b, n, v, *_ in specs
        )
    )
    facts = Facts(
        schema=3,
        scope="example-org--demo",
        kind="repo",
        collected_at="2026-09-26T12:00:00+00:00",
        repos=[REPO],
        issues=[
            Issue(
                repo=REPO,
                number=n,
                title=b,
                state="open",
                url=f"https://github.com/{REPO}/issues/{n}",
            )
            for b, n, *_ in specs
        ],
        prs=[
            _pr(
                n,
                b,
                _git(origin, "rev-parse", f"refs/heads/feat/batch-{b}"),
                [*files, *VERSION_FILES],
            )
            for b, n, _, files, _ in specs
        ],
        config={REPO: TriageConfig.model_validate(config)},
    )
    state = tmp_path / "state"
    state.mkdir()
    (state / "judgements.yaml").write_text(judgements, encoding="utf-8")
    (state / "facts.json").write_text(json.dumps(facts.to_json()), encoding="utf-8")
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: forge)
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: DemoCheckout(clone))
    return {"origin": origin, "forge": forge, "state": state, "worker": worker}


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    return _build(
        tmp_path,
        monkeypatch,
        [
            ("one", 11, "1.0.1", {"a.txt": "alpha from one\n", "one.txt": "1\n"}, ""),
            ("two", 12, "1.0.2", {"two.txt": "2\n"}, ""),
            ("three", 13, "1.0.3", {"a.txt": "alpha from three\n"}, ""),
        ],
    )


def _merge(state: Path) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "batch", "merge", "--yes", "--repo", REPO, "--dir", str(state)]
    )
    return result.exit_code, " ".join(result.output.split())


def _main_file(world: dict[str, Any], path: str) -> str:
    return _git(world["origin"], "show", f"main:{path}")


def test_the_queue_merges_resolves_version_conflicts_and_stops_on_a_real_one(
    world: dict[str, Any],
) -> None:
    code, out = _merge(world["state"])

    assert code == 1, out
    assert world["forge"].merged == [11, 12]
    # one merged as it was; two was brought up to date and kept its slot.
    for path in VERSION_FILES:
        text = _main_file(world, path)
        assert "1.0.2" in text, (path, text)
        assert "<<<<<<<" not in text and ">>>>>>>" not in text
    assert _main_file(world, "one.txt") == "1"
    assert _main_file(world, "two.txt") == "2"
    log = _git(world["origin"], "log", "--format=%s", "feat/batch-two")
    assert "chore: take reserved version 1.0.2 after batch one" in log.splitlines()
    # three stopped on a.txt, with its scratch worktree kept for inspection.
    assert "a.txt" in out and "PR #13" in out
    kept = world["state"] / "merge" / "feat" / "batch-three"
    assert kept.is_dir()
    assert (kept / "a.txt").read_text() == "alpha from three\n"  # the merge was aborted
    # two's scratch worktree was removed after its successful merge.
    assert not (world["state"] / "merge" / "feat" / "batch-two").exists()
    # the forge-side head of three is untouched: nothing was pushed for it.
    assert "alpha from three" in _git(world["origin"], "show", "feat/batch-three:a.txt")


def test_a_re_run_resumes_at_the_first_unmerged_pr(world: dict[str, Any]) -> None:
    assert _merge(world["state"])[0] == 1

    code, out = _merge(world["state"])

    assert code == 1, out
    assert world["forge"].merged == [11, 12]  # nothing merged twice
    assert "one: already merged" in out and "two: already merged" in out
    assert "1. batch three" in out and "slot 1.0.3" in out
    assert "a.txt" in out


def test_the_version_update_commits_no_untracked_build_output(world: dict[str, Any]) -> None:
    """Review r3-f7: `set` left `setv.log` in the scratch worktree of `two`."""
    _merge(world["state"])
    files = _git(world["origin"], "ls-tree", "-r", "--name-only", "main").split()
    assert "setv.log" not in files
    assert (
        "setv.log"
        not in _git(world["origin"], "ls-tree", "-r", "--name-only", "feat/batch-two").split()
    )


def test_a_kept_worktree_with_a_manual_fix_is_never_replaced(world: dict[str, Any]) -> None:
    """Review r3-f6: the operator started fixing `three` in the kept worktree."""
    assert _merge(world["state"])[0] == 1
    kept = world["state"] / "merge" / "feat" / "batch-three"
    (kept / "a.txt").write_text("alpha, resolved by hand\n")

    code, out = _merge(world["state"])

    assert code == 2, out
    assert str(kept) in out and "git worktree remove --force" in out
    assert (kept / "a.txt").read_text() == "alpha, resolved by hand\n"
    assert world["forge"].merged == [11, 12]


def test_a_pr_that_changed_a_version_file_beyond_the_version_stops_the_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review r3-f2: the PR bumped the version AND added a dependency to
    `pyproject.toml`; main bumped the version too. `--theirs` would take main's
    whole file and drop the dependency, so the queue stops naming the file."""
    dep = 'dependencies = ["requests>=2"]\n'
    world = _build(
        tmp_path,
        monkeypatch,
        [("dep", 21, "1.0.2", {"dep.txt": "d\n"}, dep)],
        main_after="1.0.1",
    )

    code, out = _merge(world["state"])

    assert code == 1, out
    assert "PR #21" in out and "pyproject.toml" in out
    assert world["forge"].merged == []
    # the dependency is not lost: nothing was pushed, and main never took the file
    assert dep.strip() in _git(world["origin"], "show", "feat/batch-dep:pyproject.toml")
    assert "1.0.1" in _main_file(world, "pyproject.toml")
    kept = world["state"] / "merge" / "feat" / "batch-dep"
    assert dep.strip() in (kept / "pyproject.toml").read_text()  # the merge was aborted


def test_an_up_to_date_pr_off_its_slot_is_re_slotted_against_real_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Step 3b (review r3-f10): up to date with main but carrying 1.0.5 where
    its slot is 1.0.1: `set` runs in the scratch worktree, the re-slot commit is
    pushed, and the PR merges at its slot without any `git merge` of main."""
    world = _build(tmp_path, monkeypatch, [("solo", 31, "1.0.5", {"solo.txt": "s\n"}, "")])

    code, out = _merge(world["state"])

    assert code == 0, out
    assert world["forge"].merged == [31]
    for path in VERSION_FILES:
        assert "1.0.1" in _main_file(world, path), path
        assert "1.0.5" not in _main_file(world, path), path
    log = _git(world["origin"], "log", "--format=%s", "feat/batch-solo").splitlines()
    assert log[0] == "chore: re-slot version to 1.0.1"
    assert not any(line.startswith("Merge") for line in log)  # 3b: no update from main
    assert not (world["state"] / "merge" / "feat" / "batch-solo").exists()
