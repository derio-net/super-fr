"""`fr triage batch merge`: order, plan, reconcile and refusals
(spec 2026-09-25-triage-batches §3.D Reconcile, §3.F; Test Plan 11, 12, 13).

The forge is `MergeForge` (through `triage_batch_cmd.make_client`) and the clone
is `FakeCheckout` (through `triage_batch_cmd.make_checkout`), whose scratch
worktrees record what merge asked git to do. Real git is exercised by
`tests/integration/test_triage_batch_merge_git.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.gh import GhError
from fr.triage.batch import merge_order
from fr.triage.model import Facts, Issue, PullRequest, TriageConfig
from typer.testing import CliRunner

REPO = "derio-net/super-fr"


def _toml(version: str) -> str:
    return f'[project]\nname = "super-fr"\nversion = "{version}"\n'


CONFIG = {
    "version": {
        "source": {"file": "pyproject.toml", "key": "project.version"},
        "files": ["pyproject.toml", "uv.lock"],
        "set": "python scripts/bump.py {version}",
    }
}


# ------------------------------------------------------------------ fakes


class MergeForge:
    """The adapter's merge operations over an in-memory set of PRs."""

    def __init__(self) -> None:
        self.prs: dict[int, dict[str, Any]] = {}
        self.checks: dict[int, list[dict[str, Any]]] = {}
        self.refuse: dict[int, str] = {}
        self.merged: list[tuple[int, str, str]] = []
        self.waits: list[int] = []

    def add(self, number: int, head: str, **kw: Any) -> None:
        self.prs[number] = {
            "state": "OPEN",
            "draft": False,
            "head_oid": head,
            "head_ref": kw.pop("head_ref", f"feat/batch-{number}"),
            "mergeable": "MERGEABLE",
            "merge_state": "CLEAN",
            **kw,
        }

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        return dict(self.prs[number])

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        return list(self.checks.get(number, [{"name": "test", "bucket": "pass"}]))

    def wait_required_checks(self, repo: str, number: int, **kw: Any) -> list[dict[str, Any]]:
        self.waits.append(number)
        return self.pr_required_checks(repo, number)

    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        if number in self.refuse:
            raise GhError(self.refuse[number], returncode=1)
        assert self.prs[number]["head_oid"] == head_sha
        self.merged.append((number, head_sha, method))
        self.prs[number]["state"] = "MERGED"

    def closing_ref(self, repo: str, number: int) -> str:
        return f"Closes {repo}#{number}"


class FakeWorktree:
    def __init__(self, checkout: FakeCheckout, path: Path, ref: str) -> None:
        self.checkout, self.path, self.ref = checkout, path, ref
        self.files = {f: t for (r, f), t in checkout.files.items() if r == ref}
        self.log: list[str] = []

    def merge(self, ref: str) -> list[str]:
        self.log.append(f"merge {ref}")
        return list(self.checkout.conflicts.get(self.ref, []))

    def take_theirs(self, paths: list[str]) -> None:
        self.log.append(f"theirs {' '.join(paths)}")

    def abort_merge(self) -> None:
        self.log.append("abort")

    def read(self, file: str) -> str | None:
        return self.files.get(file)

    def run(self, command: str, **fields: str) -> None:
        self.log.append(f"run {command.format(**fields)}")
        if "version" in fields:
            self.files["pyproject.toml"] = _toml(fields["version"])

    def commit_all(self, message: str) -> str | None:
        self.log.append(f"commit {message}")
        sha = f"new-{len(self.checkout.worktrees)}"
        for f, t in self.files.items():
            self.checkout.files[(sha, f)] = t
        self.new = sha
        return sha

    def push(self, branch: str) -> None:
        self.log.append(f"push {branch}")
        self.checkout.up_to_date.add(self.new)
        self.checkout.on_push(branch, self.new)


class FakeCheckout:
    def __init__(self, path: Path, forge: MergeForge) -> None:
        self.path = path
        self.files: dict[tuple[str, str], str] = {
            ("origin/main", "pyproject.toml"): _toml("4.21.1")
        }
        self.up_to_date: set[str] = set()
        self.conflicts: dict[str, list[str]] = {}
        self.worktrees: list[FakeWorktree] = []
        self.removed: list[Path] = []
        self.forge = forge

    def origin_repo(self) -> str | None:
        return REPO

    def default_branch(self) -> str:
        return "main"

    def fetch(self) -> None:
        pass

    def show(self, ref: str, file: str) -> str | None:
        return self.files.get((ref, file))

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return descendant in self.up_to_date

    def add_worktree(self, where: Path, ref: str) -> FakeWorktree:
        wt = FakeWorktree(self, where, ref)
        self.worktrees.append(wt)
        return wt

    def remove_worktree(self, where: Path) -> None:
        self.removed.append(where)

    def on_push(self, branch: str, sha: str) -> None:
        for pr in self.forge.prs.values():
            if pr["head_ref"] == branch:
                pr["head_oid"] = sha


def _batch_yaml(bid: str, n: int, *, order: int | None = None, bump: str = "patch", v: str) -> str:
    extra = f"    order: {order}\n" if order is not None else ""
    return (
        f'  - id: {bid}\n    title: {bid}\n    ids: ["super-fr#{n}"]\n    bump: {bump}\n{extra}'
        f"    events:\n      - {{kind: dispatch, at: 2026-09-25T10:00:00Z, runner: herdr,"
        f" handle: h, branch: feat/batch-{bid}, reserved_version: {v}}}\n"
    )


def _pr(n: int, bid: str, head: str, files: list[str]) -> PullRequest:
    return PullRequest(
        repo=REPO,
        number=n,
        title=bid,
        state="OPEN",
        is_draft=False,
        url=f"https://github.com/{REPO}/pull/{n}",
        head_ref=f"feat/batch-{bid}",
        head_oid=head,
        files=files,
        created_at="2026-09-25T11:00:00+00:00",
    )


def _setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    batches: list[tuple[str, int, int | None, str, str, list[str]]],
    *,
    tiers: dict[int, int] | None = None,
    config: dict[str, Any] | None = CONFIG,
) -> tuple[MergeForge, FakeCheckout]:
    """*batches*: (id, issue/PR number, order, bump, reserved version, files)."""
    tiers = tiers or {}
    issues = "".join(f"  super-fr#{n}: {{tier: {tiers.get(n, 2)}}}\n" for _, n, *_ in batches)
    judgements = (
        "schema: 2\ntiers:\n  - {n: 1, title: Now}\n  - {n: 2, title: Next}\nissues:\n"
        + issues
        + "batches:\n"
        + "".join(_batch_yaml(b, n, order=o, bump=bump, v=v) for b, n, o, bump, v, _ in batches)
    )
    forge = MergeForge()
    checkout = FakeCheckout(tmp_path / "clone", forge)
    prs = []
    for bid, n, _, _, v, files in batches:
        head = f"head-{bid}"
        prs.append(_pr(n + 1000, bid, head, files))
        forge.add(n + 1000, head, head_ref=f"feat/batch-{bid}")
        checkout.files[(head, "pyproject.toml")] = _toml(v)
        checkout.up_to_date.add(head)
    facts = Facts(
        schema=3,
        scope="derio-net--super-fr",
        kind="repo",
        collected_at="2026-09-26T12:00:00+00:00",
        repos=[REPO],
        issues=[
            Issue(
                repo=REPO,
                number=n,
                title=f"issue {n}",
                state="open",
                url=f"https://github.com/{REPO}/issues/{n}",
            )
            for _, n, *_ in batches
        ],
        prs=prs,
        config={REPO: TriageConfig.model_validate(config)} if config else {},
    )
    (tmp_path / "judgements.yaml").write_text(judgements, encoding="utf-8")
    (tmp_path / "facts.json").write_text(json.dumps(facts.to_json()), "utf-8")
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: forge)
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: checkout)
    return forge, checkout


def _merge(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "batch", "merge", *args, "--repo", REPO, "--dir", str(tmp_path)]
    )
    return result.exit_code, result.output


def _order(out: str) -> list[str]:
    return [line.split()[2] for line in out.splitlines() if line.lstrip()[:2].rstrip(".").isdigit()]


# ------------------------------------------------------------------ order (§3.F)


def _entry(bid: str, files: list[str], *, order: int | None = None, tier: int = 2) -> Any:
    from fr.triage.batch import QueueEntry
    from fr.triage.model import Batch

    batch = Batch.model_validate({"id": bid, "title": bid, "ids": ["super-fr#1"], "order": order})
    return QueueEntry(batch=batch, pr=_pr(1, bid, "h", files), tier=tier)


def test_explicit_order_is_a_hard_constraint() -> None:
    entries = [
        _entry("zeta", ["a.py"], order=1),
        _entry("alpha", ["b.py"]),
        _entry("mid", ["a.py", "c.py"], order=2),
    ]
    assert [e.batch.id for e in merge_order(entries)] == ["zeta", "mid", "alpha"]


def test_overlapping_batches_are_not_adjacent_when_avoidable() -> None:
    entries = [_entry("a", ["x.py"]), _entry("b", ["x.py"]), _entry("c", ["y.py"])]
    order = [e.batch.id for e in merge_order(entries)]
    assert order == ["a", "c", "b"]


def test_ties_break_on_fewest_overlaps_then_lowest_tier_then_id() -> None:
    entries = [
        _entry("d", ["p.py"], tier=2),
        _entry("c", ["q.py"], tier=1),
        _entry("b", ["r.py"], tier=2),
        _entry("a", ["p.py"], tier=1),
    ]
    # a and d share p.py (1 overlap each) -> they go after b, c, which have none;
    # c before b on tier; a before d on tier; a and d are kept apart where possible.
    assert [e.batch.id for e in merge_order(entries)] == ["c", "a", "b", "d"]


def test_the_order_is_deterministic() -> None:
    entries = [_entry(x, ["f.py"]) for x in "edcba"]
    once = [e.batch.id for e in merge_order(entries)]
    assert once == [e.batch.id for e in merge_order(list(reversed(entries)))]


# -------------------------------------------------------------- plan (§3.F)


def test_the_printed_plan_names_shared_files_per_step_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _setup(
        tmp_path,
        monkeypatch,
        [
            ("one", 1, None, "patch", "4.21.2", ["shared.py", "a.py"]),
            ("two", 2, None, "patch", "4.21.3", ["shared.py", "b.py"]),
        ],
    )
    code, out = _merge(tmp_path)
    assert code == 0, out
    assert _order(out) == ["one", "two"]
    first = next(line for line in out.splitlines() if " one " in line)
    assert "shared.py" in first and "a.py" not in first
    assert "re-run with --yes" in out
    assert forge.merged == [] and checkout.worktrees == []


def test_reconcile_re_slots_after_a_reorder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`late` was dispatched second (4.21.3) but must merge first (order 1): the
    slots follow merge order, so each PR is re-versioned to its slot."""
    forge, checkout = _setup(
        tmp_path,
        monkeypatch,
        [
            ("early", 1, None, "patch", "4.21.2", ["a.py"]),
            ("late", 2, 1, "patch", "4.21.3", ["b.py"]),
        ],
    )
    code, out = _merge(tmp_path)
    assert code == 0, out
    assert _order(out) == ["late", "early"]
    late = next(line for line in out.splitlines() if " late " in line)
    assert "4.21.3 -> slot 4.21.2" in late
    early = next(line for line in out.splitlines() if " early " in line)
    assert "4.21.2 -> slot 4.21.3" in early


def test_an_up_to_date_pr_holding_the_wrong_slot_is_re_versioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Step 3b: up to date with main but carrying the wrong number."""
    forge, checkout = _setup(
        tmp_path, monkeypatch, [("solo", 1, None, "patch", "4.21.5", ["a.py"])]
    )
    code, out = _merge(tmp_path, "--yes")
    assert code == 0, out
    (wt,) = checkout.worktrees
    assert wt.log == [
        "run python scripts/bump.py 4.21.2",
        "commit chore: re-slot version to 4.21.2",
        "push feat/batch-solo",
    ]
    assert forge.waits == [1001]
    assert forge.merged == [(1001, "new-1", "squash")]
    assert checkout.removed == [wt.path]  # step 4: removed after the merge


def test_an_up_to_date_pr_at_its_slot_merges_with_its_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _setup(
        tmp_path, monkeypatch, [("solo", 1, None, "minor", "4.22.0", ["a.py"])]
    )
    code, out = _merge(tmp_path, "--yes", "--method", "merge")
    assert code == 0, out
    assert checkout.worktrees == []
    assert forge.merged == [(1001, "head-solo", "merge")]


def test_nothing_merges_at_a_version_not_above_mains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _setup(
        tmp_path, monkeypatch, [("solo", 1, None, "patch", "4.21.2", ["a.py"])]
    )
    real_fetch = checkout.fetch
    fetches = []

    def _main_moves() -> None:  # an outside release lands after the plan is printed
        fetches.append(1)
        if len(fetches) > 1:
            checkout.files[("origin/main", "pyproject.toml")] = _toml("4.21.2")
        real_fetch()

    checkout.fetch = _main_moves  # type: ignore[method-assign]
    code, out = _merge(tmp_path, "--yes")
    assert code == 1
    assert "not above" in out and "4.21.2" in out
    assert forge.merged == []


def test_a_merged_pr_is_skipped_so_a_re_run_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _setup(
        tmp_path,
        monkeypatch,
        [
            ("one", 1, None, "patch", "4.21.2", ["a.py"]),
            ("two", 2, None, "patch", "4.21.2", ["b.py"]),
        ],
    )
    forge.prs[1001]["state"] = "MERGED"
    checkout.files[("origin/main", "pyproject.toml")] = _toml("4.21.2")
    code, out = _merge(tmp_path)
    assert code == 0, out
    assert _order(out) == ["two"]
    assert "one: already merged" in out
    two = next(line for line in out.splitlines() if " two " in line)
    assert "slot 4.21.3" in two


def test_a_named_batch_that_is_not_pr_open_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch, [("one", 1, None, "patch", "4.21.2", ["a.py"])])
    code, out = _merge(tmp_path, "nope")
    assert code == 2


# ----------------------------------------------------------- refusals (§3.F)


@pytest.mark.parametrize(
    ("mutate", "words"),
    [
        (lambda f: f.prs[1001].update(draft=True), "draft"),
        (
            lambda f: f.checks.__setitem__(1001, [{"name": "lint", "bucket": "fail"}]),
            "lint",
        ),
        (lambda f: f.prs[1001].update(head_oid="someone-pushed"), "head moved"),
    ],
    ids=["draft", "failing-check", "moved-head"],
)
def test_each_refusal_stops_the_queue_with_its_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutate: Any, words: str
) -> None:
    forge, checkout = _setup(
        tmp_path,
        monkeypatch,
        [
            ("one", 1, None, "patch", "4.21.2", ["a.py"]),
            ("two", 2, None, "patch", "4.21.3", ["b.py"]),
        ],
    )
    real_view = forge.pr_view
    views: list[int] = []

    def _changes_after_plan(repo: str, number: int) -> dict[str, Any]:
        views.append(number)
        if views.count(1001) == 2:  # the step-1 re-read, after the plan was printed
            mutate(forge)
        return real_view(repo, number)

    forge.pr_view = _changes_after_plan  # type: ignore[method-assign]
    code, out = _merge(tmp_path, "--yes")
    assert code == 1
    assert words in out
    assert forge.merged == []  # the queue stopped: `two` never merged either


def test_a_protection_refusal_is_reported_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _setup(tmp_path, monkeypatch, [("one", 1, None, "patch", "4.21.2", ["a.py"])])
    words = "X Pull request #1001 is not mergeable: At least 1 approving review is required."
    forge.refuse[1001] = words
    code, out = _merge(tmp_path, "--yes")
    assert code == 1
    assert words in " ".join(out.split())


def test_an_unsupported_backend_stops_with_its_declared_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.real_glabclient import RealGlabClient

    _setup(tmp_path, monkeypatch, [("one", 1, None, "patch", "4.21.2", ["a.py"])])
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: RealGlabClient())
    code, out = _merge(tmp_path, "--yes")
    assert code == 2
    assert "gh#611" in out and "pr_view" in out


def test_a_conflict_outside_the_version_files_stops_and_keeps_the_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _setup(tmp_path, monkeypatch, [("one", 1, None, "patch", "4.21.2", ["a.py"])])
    checkout.up_to_date.clear()  # behind main
    checkout.conflicts["head-one"] = ["uv.lock", "src/a.py"]
    code, out = _merge(tmp_path, "--yes")
    assert code == 1
    assert "src/a.py" in out and "uv.lock" not in out.split("src/a.py")[0].split("\n")[-1]
    (wt,) = checkout.worktrees
    assert wt.log == ["merge origin/main", "abort"]
    assert checkout.removed == []
    assert str(wt.path) in " ".join(out.split()).replace(" ", "") or "kept" in out


def test_a_version_only_conflict_takes_mains_side_then_sets_the_slot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _setup(
        tmp_path,
        monkeypatch,
        [
            ("one", 1, None, "patch", "4.21.2", ["a.py"]),
        ],
    )
    checkout.up_to_date.clear()
    checkout.conflicts["head-one"] = ["pyproject.toml", "uv.lock"]
    real_add = checkout.add_worktree

    def _add(where: Path, ref: str) -> FakeWorktree:
        wt = real_add(where, ref)
        wt.files["pyproject.toml"] = _toml("4.21.1")  # main's side after --theirs
        return wt

    checkout.add_worktree = _add  # type: ignore[method-assign]
    code, out = _merge(tmp_path, "--yes")
    assert code == 0, out
    (wt,) = checkout.worktrees
    assert wt.log == [
        "merge origin/main",
        "theirs pyproject.toml uv.lock",
        "run python scripts/bump.py 4.21.2",
        "commit chore: take reserved version 4.21.2 after main",
        "push feat/batch-one",
    ]
    assert forge.merged == [(1001, "new-1", "squash")]
