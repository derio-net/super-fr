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
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
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


def _manifests(root: Path, version: str) -> None:
    (root / "pyproject.toml").write_text(f'[project]\nname = "demo"\nversion = "{version}"\n')
    (root / "package.json").write_text(
        json.dumps({"name": "demo", "version": version}, indent=2) + "\n"
    )
    (root / "uv.lock").write_text(
        f'lock-version = 1\n\n[[package]]\nname = "demo"\nversion = "{version}"\n'
    )


def _branch(seed: Path, name: str, version: str, files: dict[str, str]) -> None:
    _git(seed, "checkout", "--quiet", "-b", name, "main")
    _manifests(seed, version)
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


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
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
    _git(seed, "add", "--all")
    _git(seed, "commit", "--quiet", "-m", "seed")
    _git(seed, "push", "--quiet", "origin", "main")
    _branch(seed, "feat/batch-one", "1.0.1", {"a.txt": "alpha from one\n", "one.txt": "1\n"})
    _branch(seed, "feat/batch-two", "1.0.2", {"two.txt": "2\n"})
    _branch(seed, "feat/batch-three", "1.0.3", {"a.txt": "alpha from three\n"})

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "--quiet", str(origin), str(clone))
    _identity(clone)
    worker = tmp_path / "worker"
    _git(tmp_path, "clone", "--quiet", str(origin), str(worker))
    _identity(worker)

    numbers = {"one": 11, "two": 12, "three": 13}
    forge = GitForge(origin, worker, {n: f"feat/batch-{b}" for b, n in numbers.items()})
    touched = {"one": ["a.txt", "one.txt"], "two": ["two.txt"], "three": ["a.txt"]}
    reserved = {"one": "1.0.1", "two": "1.0.2", "three": "1.0.3"}
    judgements = (
        "schema: 2\ntiers:\n  - {n: 1, title: Now}\nissues:\n"
        + "".join(f"  demo#{n}: {{tier: 1}}\n" for n in numbers.values())
        + "batches:\n"
        + "".join(
            f'  - id: {b}\n    title: {b}\n    ids: ["demo#{n}"]\n    bump: patch\n'
            f"    events:\n      - {{kind: dispatch, at: 2026-09-25T10:00:00Z, runner: herdr,"
            f" handle: h, branch: feat/batch-{b}, reserved_version: {reserved[b]}}}\n"
            for b, n in numbers.items()
        )
    )
    set_cmd = f"{shlex.quote(sys.executable)} scripts/setv.py {{version}}"
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
            for b, n in numbers.items()
        ],
        prs=[
            _pr(
                n,
                b,
                _git(origin, "rev-parse", f"refs/heads/feat/batch-{b}"),
                [*touched[b], *VERSION_FILES],
            )
            for b, n in numbers.items()
        ],
        config={
            REPO: TriageConfig.model_validate(
                {
                    "version": {
                        "source": {"file": "pyproject.toml", "key": "project.version"},
                        "files": VERSION_FILES,
                        "set": set_cmd,
                    }
                }
            )
        },
    )
    state = tmp_path / "state"
    state.mkdir()
    (state / "judgements.yaml").write_text(judgements, encoding="utf-8")
    (state / "facts.json").write_text(json.dumps(facts.to_json()), encoding="utf-8")
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: forge)
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: DemoCheckout(clone))
    return {"origin": origin, "forge": forge, "state": state, "worker": worker}


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
