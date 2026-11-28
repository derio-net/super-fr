"""`fr ops gate` — the DevOps stage's sequencer (spec 2026-10-22-fr-ops R15, §I).

Every port is a fake: the host (`fr isolation up/exec/verify-merge`), the ops workspace
(git and this `fr` there), the forge and the operator's terminal. The ops workspace's
files are real, so the ledger, the op evidence and the Test Plan are the real readers.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from fr.ghclient import UnsupportedForgeOperation
from fr.journal.model import (
    JournalEntry,
    append_journal_entry,
    archived_journal_path,
    journal_path,
)
from fr.ops import gate as gate_mod
from fr.ops.evidence import record_op
from fr.ops.gate import (
    Gate,
    GateResult,
    GateTarget,
    HostGateState,
    JournalLedger,
    preview,
    run,
)
from fr.run.model import RunState, StepRecord, save_run_state
from fr.triage.approval import release_marker

from tests.unit.requirements_support import row, write_matrix

REPO = "derio-net/super-fr"
SPEC = "docs/superpowers/specs/2026-10-22-s-design.md"
SPEC_SLUG = "2026-10-22-s"
PLAN = "docs/superpowers/plans/p"
HEAD = "a" * 40
TIP = "c" * 40  # the default branch's tip, where a merged PR's ops workspace is cut
OPS = """schema_version: 1
ops:
  - {id: pre, summary: create the thing, phase: pre-merge, check: 'false', apply: 'true'}
  - id: mut
    summary: rewrite the other thing
    phase: pre-merge
    mutating: true
    side_effects: [rewrites it]
    undo: 'true'
    check: 'false'
    apply: 'true'
  - {id: post, summary: after merge, phase: post-merge, check: 'false', apply: 'true',
     ready: 'true'}
"""
PRIMARY = Path("/base")


def _state() -> RunState:
    return RunState(
        run="run-1",
        workflow="fr-goal@1",
        branch="feat/x",
        started="2026-10-22T00:00:00+00:00",
        cursor="deliver",
        steps={
            "brainstorm": StepRecord(state="done", emitted={"spec": SPEC}),
            "plan": StepRecord(state="done", emitted={"plan": PLAN}),
            "deliver": StepRecord(
                state="done", emitted={"pr": f"https://github.com/{REPO}/pull/5"}
            ),
        },
    )


@pytest.fixture
def ops_root(tmp_path: Path) -> Path:
    root = tmp_path / "ops"
    (root / "docs/superpowers/specs").mkdir(parents=True)
    (root / SPEC).write_text(
        "# S\n\n## Verification\n\nstrategy: none\ngate: developer\n\n## Test Plan\n\n"
        "- [devops] walk the stage\n- [tester] click the page\n"
    )
    write_matrix(root, [row(SPEC, rid="r1")])
    (root / PLAN).mkdir(parents=True)
    (root / PLAN / "ops.yaml").write_text(OPS)
    save_run_state(root, _state())
    return root


class FakeTree:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.calls: list[tuple[str, Any]] = []
        self.gate_pass_code: int | None = None
        self.rebase_error: str | None = None
        self.push_error: str | None = None
        self.leases: list[str | None] = []
        self.head_files: dict[str, str] = {}  # what the PR head carries, by path
        self.merge_conflict: tuple[str, ...] = ()  # paths a merge_commit conflicts on
        self.on_merge: Any = None  # called on a clean merge: what the merge brings in
        self.contains: set[str] = set()  # commits the ops branch already holds

    def snapshot_head(self) -> None:
        """Freeze the tree's current journals as what the PR head carries (p4-r2)."""
        for path in self.path.glob("docs/superpowers/journals/**/*.md"):
            self.head_files[path.relative_to(self.path).as_posix()] = path.read_text()

    def show(self, ref: str, path: str) -> str | None:
        assert ref in (HEAD, TIP)  # the cut: the PR head, or main's tip after the merge
        return self.head_files.get(path)

    def head(self) -> str:
        return HEAD

    def fr(self, args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        args = list(args)
        self.calls.append(("fr", (args, terminal)))
        if args[:2] == ["closeout", "outcome"]:
            n = int(args[args.index("--step") + 1])
            kind = "owed" if "--owed" in args else "discovery"
            jp = journal_path(self.path, "spec", SPEC_SLUG)
            taken = jp.read_text() if jp.exists() else ""
            sid, k = f"test-plan-step-{n}", 1
            while f"id={sid} " in taken:
                k += 1
                sid = f"test-plan-step-{n}-{k}"
            said = "owed" if kind == "owed" else "n/a" if "--na" in args else "ran"
            entry = JournalEntry(
                kind=kind,
                scope="spec",
                id=sid,
                created="2026-10-22T10:00:00+00:00",
                title=f"Test Plan step {n}: {said}",  # as `fr closeout outcome` titles it
                body="x" if kind == "discovery" else "why: later\nhow: later",
            )
            append_journal_entry(journal_path(self.path, "spec", SPEC_SLUG), SPEC_SLUG, entry)
            if "--ran" in args:
                self._walk_named_rows(n, args)
        if args[:2] == ["gate", "pass"]:
            from fr.ops.holds import devops_blockers

            if self.gate_pass_code is not None:
                return self.gate_pass_code, "fr gate pass: still held"
            steps = [b for b in devops_blockers(self.path, _state()) if b.startswith("Test Plan")]
            if steps:
                return 2, "fr gate pass: still held by its recorded evidence"
        if args[:1] == ["archive"]:
            dest = self.path / "docs/superpowers/implemented/plans/p"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(self.path / PLAN), dest)
            live = journal_path(self.path, "plan", "p")
            if live.exists():
                arch = archived_journal_path(self.path, "plan", "p")
                arch.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(live), arch)
        return 0, ""

    def _walk_named_rows(self, n: int, args: list[str]) -> None:
        """What the real `fr closeout outcome --ran` writes (R9): a passing walk on each
        row step *n* names, `walked` once no harness the row names is still owed."""
        import yaml
        from fr.spec import test_plan_steps

        steps = test_plan_steps((self.path / SPEC).read_text())
        named = set(steps[n - 1].rows) if n <= len(steps) else set()
        harness = args[args.index("--harness") + 1] if "--harness" in args else "operator"
        model = args[args.index("--model") + 1] if "--model" in args else "human"
        for frag in (self.path / "docs/acceptance/features").glob("*.yaml"):
            data = yaml.safe_load(frag.read_text())
            for r in data.get("rows") or []:
                if r["id"] not in named:
                    continue
                walk = {"strategy": "live", "harness": harness, "model": model,
                        "outcome": "pass", "at": "2026-10-22T10:00:00Z",
                        "evidence": f"Test Plan step {n}"}  # fmt: skip
                r["walks"] = [*(r.get("walks") or []), walk]
                passing = {w["harness"] for w in r["walks"] if w["outcome"] == "pass"}
                if all(h in passing for h in r.get("harnesses") or []):
                    r["status"] = "walked"
            frag.write_text(yaml.safe_dump(data, sort_keys=False))

    def commit_paths(self, paths: list[str], message: str) -> str | None:
        self.calls.append(("commit", message))
        return "c" * 40

    def rebase_onto(self, new_base: str, upstream: str) -> None:
        self.calls.append(("rebase", (new_base, upstream)))
        if self.rebase_error:
            raise RuntimeError(self.rebase_error)

    def is_ancestor(self, sha: str) -> bool:
        return sha in self.contains

    def merge_commit(self, ref: str, message: str) -> str:
        self.calls.append(("merge", (ref, message)))
        if self.merge_conflict:
            raise gate_mod.MergeConflict(self.merge_conflict)
        if self.on_merge is not None:
            self.on_merge()
        return HEAD

    def push(self, branch: str, lease: str | None = None) -> None:
        self.calls.append(("push", branch))
        self.leases.append(lease)
        if self.push_error:
            raise RuntimeError(self.push_error)


def _write_edits(root: Path, edits: dict[str, str | None]) -> None:
    for rel, text in edits.items():
        target = root / rel
        if text is None:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink(missing_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)


class FakeHost:
    def __init__(self, tree: FakeTree, *, up: bool = False) -> None:
        self.tree = tree
        self.up = up
        self.calls: list[tuple[list[str], bool]] = []
        self.live: dict[str, str] = {"pre": "OPEN", "mut": "OPEN", "post": "OPEN"}
        self.fail_apply: set[str] = set()
        self.ready_code = 0
        self.changed: list[str] = []  # ops-profile files the PR head changes (p4-r1)
        # files whose content differs from the default branch's tip, per compared rev
        self.stale: dict[str, list[str]] = {}
        self.tip: str | None = TIP
        self.origin_default: str | None = "main"
        self.queue = True  # `.fr/triage.yaml` declares a `queue:` block
        self.patch: str | None = "ab12cd"  # the verified head's patch-id; None: unreadable
        self.how: dict[str, str] = {}
        self.materialised: list[Path] = []
        # `fr ops status <id> --json`, scripted per op: each call pops (exit, rows | text)
        self.by_id: dict[str, list[tuple[int, Any]]] = {}
        # what origin/<default> carries beyond the ops workspace: path -> text (None: absent)
        self.default_edits: dict[str, str | None] = {}

    def materialise(self, ref: str, paths: Sequence[str]) -> Path:
        """*paths* as the PR head carries them: copied from the fake's own tree."""
        import tempfile

        self.calls.append((["materialise", ref, *paths], False))
        out = Path(tempfile.mkdtemp(prefix="fr-gate-head-"))
        self.materialised.append(out)
        for rel in paths:
            src = self.tree.path / rel
            if src.is_dir():
                shutil.copytree(src, out / rel)
            elif src.is_file():
                (out / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, out / rel)
        _write_edits(out, self.default_edits)
        return out

    def changed_paths(self, base: str, head: str, paths: Sequence[str]) -> list[str]:
        self.calls.append((["diff", base, head, *paths], False))
        return [c for c in self.changed if any(c.startswith(p) for p in paths)]

    def differing_paths(self, base: str, head: str, paths: Sequence[str]) -> list[str]:
        self.calls.append((["diff-tip", base, head, *paths], False))
        return [c for c in self.stale.get(head, []) if any(c.startswith(p) for p in paths)]

    def rev_parse(self, ref: str) -> str | None:
        self.calls.append((["rev-parse", ref], False))
        return self.tip

    def origin_head(self) -> str | None:
        return self.origin_default

    def patch_id(self, head: str, default: str) -> str | None:
        return self.patch

    def queue_configured(self, default: str) -> bool:
        return self.queue

    def fetch(self, ref: str) -> None:
        self.calls.append((["fetch", ref], False))

    def workspace(self, branch: str) -> FakeTree | None:
        assert branch == "chore/ops-p"
        return self.tree if self.up else None

    def fr(self, args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        args = list(args)
        self.calls.append((args, terminal))
        if args[:2] == ["isolation", "up"]:
            self.up = True
            return 0, ""
        if args[:2] == ["isolation", "exec"]:
            inner = args[args.index("--") + 1 :]
            assert inner[0] == "fr"
            verb = inner[1:3]
            if verb == ["ops", "status"] and "--ready" in inner:
                return self.ready_code, "READY post"
            if verb == ["ops", "status"] and "--phase" not in inner:
                op = inner[3]
                code, payload = self.by_id[op].pop(0)
                return code, payload if isinstance(payload, str) else json.dumps(payload)
            if verb == ["ops", "status"]:
                phase = inner[inner.index("--phase") + 1]
                rows = [
                    {"op": o, "state": s, "label": s, "reason": "", "summary": o,
                     "identity": None, "how": self.how.get(o, "checked" if s == "DONE" else None)}
                    for o, s in self.live.items()
                    if (o == "post") == (phase == "post-merge")
                ]  # fmt: skip
                return 1, json.dumps(rows)
            if verb == ["ops", "apply"]:
                op = inner[3]
                if op in self.fail_apply:
                    return 1, f"{op}: failed"
                phase = "post-merge" if op == "post" else "pre-merge"
                record_op(self.tree.path, "p", op=op, result="done", phase=phase)
                self.live[op] = "DONE"
                return 0, f"{op}: applied"
        return 0, ""


class FakeForge:
    def __init__(
        self, *, state: str = "OPEN", unsupported: bool = False, queue_lands: bool = True
    ) -> None:
        # `queue_lands`: the merge queue lands a released PR before the stage next reads the
        # forge, so one run goes on to stage 3; False leaves it to `land()` between two runs.
        self.queue_lands = queue_lands
        self.pr = {"state": state, "head_oid": HEAD, "head_ref": "feat/x", "base_ref": "main",
                   "labels": ["gate:devops", "gate:tester"]}  # fmt: skip
        self.required: list[dict[str, Any]] = [{"name": "ci", "bucket": "pass"}]
        self.calls: list[tuple[str, Any]] = []
        self.unsupported = unsupported
        self.open_prs: dict[str, int] = {}
        self.default = "main"
        self.comments: list[dict[str, Any]] = []

    def default_branch(self, *, cwd: Path, run: Any = None) -> str | None:
        return self.default

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        assert (repo, number) == (REPO, 5)
        return dict(self.pr)

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        return list(self.required)

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        return list(self.required)

    def pr_merge(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("the DevOps stage calls no pr_merge: the merge queue lands the PR")

    def ensure_labels(self, repo: str, labels: list[Any]) -> None:
        if self.unsupported:
            raise UnsupportedForgeOperation("ensure_labels", "gitlab")
        self.calls.append(("ensure_labels", [label.name for label in labels]))

    def edit_pr_labels(
        self, repo: str, pr: int, *, add: frozenset[str], remove: frozenset[str]
    ) -> None:
        self.calls.append(("labels", (pr, sorted(add), sorted(remove))))
        self.pr["labels"] = [*self.pr["labels"], *sorted(add)]
        if self.queue_lands and "fr-queue:release" in add:
            self.land()

    def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]:
        return [dict(c) for c in self.comments]

    def comment_pr(self, repo: str, pr: int, body: str) -> None:
        self.calls.append(("comment", body))
        self.comments.append({"association": "OWNER", "id": len(self.comments) + 1, "body": body})

    def edit_issue_comment(self, repo: str, comment_id: int, body: str) -> None:
        self.calls.append(("edit_comment", body))
        for c in self.comments:
            if c["id"] == comment_id:
                c["body"] = body

    def land(self) -> None:
        """What the merge queue does between two runs of the stage."""
        self.pr["state"] = "MERGED"

    def open_pr_for_head(self, repo: str, branch: str) -> dict[str, Any] | None:
        n = self.open_prs.get(branch)
        return {"number": n, "url": "u"} if n else None

    def pr_create(self, repo: str, *, head: str, base: str, title: str, body: str) -> int:
        self.calls.append(("pr_create", {"head": head, "base": base}))
        self.open_prs[head] = 9
        return 9


class FakePrompt:
    def __init__(self, confirms: Sequence[bool] = (), answers: Sequence[str] = ()) -> None:
        self.confirms = list(confirms)
        self.answers = list(answers)
        self.asked: list[str] = []

    def confirm(self, text: str) -> bool:
        self.asked.append(text)
        return self.confirms.pop(0) if self.confirms else True

    def ask(self, text: str) -> str:
        self.asked.append(text)
        return self.answers.pop(0) if self.answers else "ran it worked"


def _gate(
    ops_root: Path,
    *,
    up: bool = False,
    forge: FakeForge | None = None,
    prompt: FakePrompt | None = None,
    live_closed: bool = False,
) -> tuple[Gate, FakeHost, FakeTree, FakeForge, FakePrompt, list[str]]:
    tree = FakeTree(ops_root)
    host = FakeHost(tree, up=up)
    if live_closed:  # the pre-merge ops' LIVE status rows read DONE (p4-r2)
        host.live.update(pre="DONE", mut="DONE")
    # a recorded stage 3 means the PR merged: the queue landed it, which only the forge says
    forge = forge or FakeForge(state="MERGED" if 3 in _host(ops_root).stages() else "OPEN")
    prompt = prompt or FakePrompt()
    said: list[str] = []
    target = GateTarget(run=_state(), repo=REPO, pr=5, plan_rel=PLAN, profile="ops",
                        primary=PRIMARY)  # fmt: skip
    if up:  # a workspace stage 1 cut from the verified head (p4-r5)
        _host(ops_root).set_cut(HEAD)
    gate = Gate(target, host, forge, prompt, said.append, _host(ops_root))
    return gate, host, tree, forge, prompt, said


def _labelled(forge: FakeForge, label: str) -> bool:
    return ("labels", (5, [label], [])) in forge.calls


def _through_the_queue(
    ops_root: Path, gate: Gate, forge: FakeForge, host: FakeHost
) -> tuple[GateResult, GateResult]:
    """Run the stage to its stop at stage 2, let the queue land the PR, and run it again
    on a fresh gate (a new command run reads the forge afresh)."""
    first = run(gate)
    forge.land()
    again = Gate(gate.target, host, forge, FakePrompt(), [].append, _host(ops_root))
    return first, run(again)


def _host(root: Path) -> HostGateState:
    """The operator's host-side stage state, outside the ops workspace (p4-gate-state)."""
    return HostGateState(root.parent / "gate-state" / "run-1.json")


def _record_stages(root: Path, *ns: int, head: str = HEAD) -> None:
    for n in ns:
        _host(root).mark(n, head=head if n == 1 else None)


def _pre_merge_closed(root: Path) -> None:
    """Stage 1's evidence, for a test that records stage 1 without running it: stage 6
    folds every op before it runs the pass (ops-gate-truth R14)."""
    for op in ("pre", "mut"):
        record_op(root, "p", op=op, result="done", phase="pre-merge")


def _exec(*inner: str) -> list[str]:
    return ["isolation", "exec", "--repo", str(PRIMARY), "--branch", "chore/ops-p", "--", "fr",
            *inner]  # fmt: skip


# ----------------------------------------------------------------------------- preview


def test_preview_lists_the_eight_stages_and_changes_nothing(ops_root: Path) -> None:
    gate, host, tree, forge, prompt, _ = _gate(ops_root)
    lines = preview(gate)
    text = "\n".join(lines)
    for n in range(1, 9):
        assert f" {n}. " in text
    assert "[next] 1." in text and "nothing done" in text
    assert host.calls == [] and tree.calls == [] and prompt.asked == []
    assert forge.calls == []


def test_preview_marks_recorded_stages_done(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    gate, *_ = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))  # stage 2: the forge's
    text = "\n".join(preview(gate))
    assert "[done] 1." in text and "[done] 2." in text and "[next] 3." in text


# ----------------------------------------------------------------------- the full run


def test_a_full_run_walks_every_stage_in_order(ops_root: Path) -> None:
    gate, host, tree, forge, prompt, said = _gate(ops_root, forge=FakeForge(queue_lands=False))
    first, result = _through_the_queue(ops_root, gate, forge, host)
    assert first.waiting and first.ran == (1, 2) and not first.ok and first.code == 0
    assert result.ok, said
    assert result.ran == (3, 4, 5, 6, 7, 8)
    assert _host(ops_root).stages() == {1, 3, 4, 5, 6, 7, 8}  # stage 2 is never recorded

    argvs = [a for a, _ in host.calls]
    # stage 1: the ops workspace is cut from the PR head on the ops profile
    up = next(a for a in argvs if a[:2] == ["isolation", "up"])
    assert up == ["isolation", "up", "--repo", str(PRIMARY), "--profile", "ops", "--branch",
                  "chore/ops-p", "--base", HEAD]  # fmt: skip
    # each op is confirmed on the host, then runs through `fr isolation exec`
    assert _exec("ops", "apply", "pre", "--plan", PLAN, "--yes") in argvs
    assert _exec("ops", "apply", "mut", "--plan", PLAN, "--yes", "--yes-mutating") in argvs
    assert _exec("ops", "apply", "post", "--plan", PLAN, "--yes") in argvs
    assert any("MUTATING" in a and "rewrites it" in a for a in prompt.asked)
    # stage 2: its own confirmation names the PR, the head sha and the pre-merge state; it
    # adds the release label and merges nothing (R26)
    release_q = next(a for a in prompt.asked if a.startswith("RELEASE"))
    assert "#5" in release_q and HEAD in release_q and "pre-merge state" in release_q
    assert ("ensure_labels", ["fr-queue:release"]) in forge.calls
    assert _labelled(forge, "fr-queue:release")
    # stage 4's completion lifts the queue's barrier
    assert _labelled(forge, "fr-queue:postmerge-done")
    # stage 3: verify-merge, then the ops branch rebased onto the default branch
    assert ["isolation", "verify-merge", "--repo", str(PRIMARY), "--branch", "feat/x",
            "--default-branch", "main"] in argvs  # fmt: skip
    assert ("rebase", ("origin/main", HEAD)) in tree.calls
    assert _exec("ops", "status", "--plan", PLAN, "--phase", "post-merge", "--ready") in argvs
    # stage 6 from the ops workspace; stage 8 archives and opens the housekeeping PR
    tree_args = [a for k, (a, _) in ((k, v) for k, v in tree.calls if k == "fr")]
    gp = next(a for a in tree_args if a[:2] == ["gate", "pass"])
    assert gp[gp.index("--gate") + 1] == "devops" and gp[gp.index("--run") + 1] == "run-1"
    assert ["archive", "--branch", "feat/x", "--no-issues"] in tree_args
    assert ("pr_create", {"head": "chore/ops-p", "base": "main"}) in forge.calls


def test_trust_is_granted_on_the_host_before_any_probe(ops_root: Path) -> None:
    gate, host, tree, *_ = _gate(ops_root, up=True)
    order: list[str] = []
    real_tree_fr, real_host_fr = tree.fr, host.fr

    def tree_fr(args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        if list(args[:2]) == ["ops", "trust"]:
            assert terminal, "trust needs the operator's terminal"
            order.append("trust")
        return real_tree_fr(args, terminal=terminal)

    def host_fr(args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        if "status" in args:
            order.append("status")
        return real_host_fr(args, terminal=terminal)

    tree.fr = tree_fr  # type: ignore[method-assign]
    host.fr = host_fr  # type: ignore[method-assign]
    run(gate)
    assert order[:2] == ["trust", "status"]


def test_an_untrusted_set_stops_stage_1_before_any_probe(ops_root: Path) -> None:
    gate, host, tree, *_ = _gate(ops_root, up=True)
    real = tree.fr

    def refuse(args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        return (1, "") if list(args[:2]) == ["ops", "trust"] else real(args, terminal=terminal)

    tree.fr = refuse  # type: ignore[method-assign]
    result = run(gate)
    assert result.failed == 1 and "not trusted" in result.why
    assert not any(a[:2] == ["isolation", "exec"] for a, _ in host.calls)


def test_pre_merge_evidence_is_never_pushed_to_the_pr_head(ops_root: Path) -> None:
    gate, host, tree, *_ = _gate(ops_root)
    run(gate)
    pushes = [b for k, b in tree.calls if k == "push"]
    assert pushes and set(pushes) == {"chore/ops-p"}
    assert not any("push" in a for a, _ in host.calls)


def test_each_stage_commits_its_evidence_on_the_ops_branch(ops_root: Path) -> None:
    gate, host, tree, *_ = _gate(ops_root)
    run(gate)
    commits = [m for k, m in tree.calls if k == "commit"]
    for n in (1, 3, 4, 5, 6, 7, 8):
        assert any(f"DevOps stage {n}" in m for m in commits), commits
    assert not any("DevOps stage 2" in m for m in commits)  # stage 2 records nothing (R26)


# --------------------------------------------------------------------- the merge


def test_the_merge_refuses_while_a_pre_merge_op_is_open(ops_root: Path) -> None:
    _record_stages(ops_root, 1)  # recorded, but no op evidence closes them
    gate, host, tree, forge, prompt, _ = _gate(ops_root, up=True)
    result = run(gate)
    assert result.failed == 2 and "pre-merge ops are still open" in result.why
    assert not _labelled(forge, "fr-queue:release")
    assert not any(a.startswith("RELEASE") for a in prompt.asked)


def test_the_merge_refuses_on_red_required_checks(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    forge = FakeForge()
    forge.required = [{"name": "ci", "bucket": "fail"}]
    gate, *_ = _gate(ops_root, up=True, live_closed=True, forge=forge)
    result = run(gate)
    assert result.failed == 2 and "failing" in result.why and "ci" in result.why
    assert not _labelled(forge, "fr-queue:release")


def test_a_declined_merge_merges_nothing(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, host, tree, forge, prompt, _ = _gate(
        ops_root, up=True, live_closed=True, prompt=FakePrompt([False])
    )
    result = run(gate)
    assert result.failed == 2 and "not confirmed" in result.why and "nothing released" in result.why
    assert not _labelled(forge, "fr-queue:release")
    assert 2 not in _host(ops_root).stages()


def test_a_forge_that_cannot_label_names_the_manual_label(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, *_ = _gate(ops_root, up=True, live_closed=True, forge=FakeForge(unsupported=True))
    result = run(gate)
    assert result.failed == 2
    assert "by hand" in result.why and "#5" in result.why and "fr-queue:release" in result.why


def test_a_forge_merged_pr_counts_as_stage_2_done(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    _pre_merge_closed(ops_root)
    gate, host, tree, forge, prompt, _ = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    result = run(gate)
    assert result.ok and 2 not in result.ran and result.ran[0] == 3
    assert not any(a.startswith("RELEASE") for a in prompt.asked)
    assert not _labelled(forge, "fr-queue:release")


def test_stage_2_never_merges_and_waits_for_the_queue(ops_root: Path) -> None:
    """R26: the stage adds `fr-queue:release` and stops; `pr_merge` raises if it is called."""
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    forge = FakeForge(queue_lands=False)
    gate, host, tree, forge, prompt, said = _gate(ops_root, up=True, live_closed=True, forge=forge)
    result = run(gate)
    assert result.waiting and not result.ok and result.code == 0 and result.ran == (2,)
    assert _labelled(forge, "fr-queue:release") and 2 not in _host(ops_root).stages()
    assert not any(a[:2] == ["isolation", "verify-merge"] for a, _ in host.calls)  # no stage 3
    assert any("waits for the PR to be merged" in line for line in said)
    # p6-r2: the marker names what stage 2 verified, written before the label
    assert forge.calls.index(("comment", release_marker(HEAD, "ab12cd"))) < forge.calls.index(
        ("labels", (5, ["fr-queue:release"], []))
    )


def test_forge_labels_off_refuses_the_release_and_names_the_label(
    ops_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R9: the queue is told by label, so `forge.labels: off` stops the stage."""
    monkeypatch.setattr(
        "fr.settings.ledger_block",
        lambda root, kind: "forge.labels is off" if kind == "labels" else None,
    )
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, host, tree, forge, *_ = _gate(ops_root, up=True, live_closed=True)
    result = run(gate)
    assert result.failed == 2 and "forge.labels is off" in result.why
    assert "fr-queue:release" in result.why and not [c for c in forge.calls if c[0] == "labels"]


def test_a_rerun_while_released_asks_nothing_and_waits_again(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    forge = FakeForge(queue_lands=False)
    forge.pr["labels"].append("fr-queue:release")
    forge.comments.append({"association": "OWNER", "id": 1, "body": release_marker(HEAD, "ab12cd")})
    gate, host, tree, forge, prompt, _ = _gate(ops_root, up=True, live_closed=True, forge=forge)
    result = run(gate)
    assert result.waiting and prompt.asked == []
    assert not [c for c in forge.calls if c[0] == "labels"]


def test_a_released_pr_whose_marker_names_another_diff_is_released_again(ops_root: Path) -> None:
    """p6-r2: a label whose marker is not what the stage verified now is not a release."""
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    forge = FakeForge(queue_lands=False)
    forge.pr["labels"].append("fr-queue:release")
    forge.comments.append({"association": "OWNER", "id": 1, "body": release_marker("0ld", "0ld")})
    gate, host, tree, forge, prompt, _ = _gate(ops_root, up=True, live_closed=True, forge=forge)
    result = run(gate)
    assert result.waiting and len(prompt.asked) == 1
    assert ("edit_comment", release_marker(HEAD, "ab12cd")) in forge.calls  # in place
    assert not [c for c in forge.calls if c[0] == "labels"]  # the label is already on


def test_an_unreadable_patch_id_releases_nothing(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, host, tree, forge, prompt, _ = _gate(ops_root, up=True, live_closed=True)
    host.patch = None
    result = run(gate)
    assert result.failed == 2 and "patch-id" in result.why and forge.calls == []


def test_a_repo_with_no_queue_is_told_to_merge_by_hand_and_a_hand_merge_completes_stage_2(
    ops_root: Path,
) -> None:
    """p6-r4: the gate never merges; with no `queue:` it says so and waits for the forge."""
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    forge = FakeForge(queue_lands=False)
    gate, host, tree, forge, prompt, said = _gate(ops_root, up=True, live_closed=True, forge=forge)
    host.queue = False
    result = run(gate)
    assert result.waiting and prompt.asked == [] and forge.calls == []
    assert any("does not serve" in line and "merge PR #5 by hand" in line for line in said)
    forge.land()  # the operator merges it
    again = Gate(gate.target, host, forge, FakePrompt(), [].append, _host(ops_root))
    assert run(again).ran[0] == 3 and 2 not in run(again).ran


def test_stage_4_under_labels_off_finishes_when_the_label_was_added_by_hand(
    ops_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p6-r3: the label already on is enough; nothing is written, so labels off cannot refuse."""
    monkeypatch.setattr(
        "fr.settings.ledger_block",
        lambda root, kind: "forge.labels is off" if kind == "labels" else None,
    )
    forge = FakeForge(state="MERGED")
    forge.pr["labels"].append("fr-queue:postmerge-done")
    gate, host, tree, forge, *_ = _gate(ops_root, forge=forge)
    result = run(gate)
    assert 4 in result.ran and 4 in _host(ops_root).stages()
    assert not [c for c in forge.calls if c[0] == "labels"]


def test_stage_4_writes_the_postmerge_marker_before_the_label(ops_root: Path) -> None:
    """l-security-r2: the label alone lifts nothing, so the marker comes first."""
    from fr.triage.approval import postmerge_marker

    forge = FakeForge(state="MERGED")
    gate, host, tree, forge, *_ = _gate(ops_root, forge=forge)
    result = run(gate)
    assert 4 in result.ran
    assert forge.calls.index(("comment", postmerge_marker(HEAD))) < forge.calls.index(
        ("labels", (5, ["fr-queue:postmerge-done"], []))
    )


def test_a_marker_is_edited_only_when_it_is_trusted_and_its_own_form(ops_root: Path) -> None:
    """l-security-r3: a stranger's comment that starts like the marker is never overwritten;
    the stage posts a new one."""
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    forge = FakeForge(queue_lands=False)
    forge.comments.append({"association": "NONE", "id": 1, "body": release_marker("0ld", "0ld")})
    forge.comments.append(
        {"association": "OWNER", "id": 2, "body": "see " + release_marker("x", "y")}
    )
    gate, host, tree, forge, *_ = _gate(ops_root, up=True, live_closed=True, forge=forge)
    run(gate)
    assert not [c for c in forge.calls if c[0] == "edit_comment"]
    assert ("comment", release_marker(HEAD, "ab12cd")) in forge.calls


def test_a_recorded_stage_2_no_longer_skips_the_wait(ops_root: Path) -> None:
    """A host record from before the queue named stage 2 done: the forge's word is the only
    one, so an unmerged PR is released again rather than rebased and post-merge-applied."""
    _record_stages(ops_root, 1, 2)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, host, tree, forge, *_ = _gate(
        ops_root, up=True, live_closed=True, forge=FakeForge(queue_lands=False)
    )
    result = run(gate)
    assert result.waiting and not any(c[0] == "rebase" for c in tree.calls)


# ------------------------------------------------------------- resume and failure


def test_a_rerun_resumes_at_the_first_unrecorded_stage(ops_root: Path) -> None:
    _record_stages(ops_root, 1, 2, 3)
    _pre_merge_closed(ops_root)
    gate, host, tree, forge, *_ = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    result = run(gate)
    assert result.ran == (4, 5, 6, 7, 8)
    argvs = [a for a, _ in host.calls]
    assert not any(a[:2] in (["isolation", "up"], ["isolation", "verify-merge"]) for a in argvs)


def test_it_stops_at_the_first_failure_naming_the_stage_then_resumes(ops_root: Path) -> None:
    gate, host, tree, forge, *_ = _gate(ops_root)
    host.fail_apply = {"post"}
    first = run(gate)
    assert not first.ok and first.failed == 4
    assert "stage 4 (post-merge ops) failed" in first.why and "op post" in first.why
    assert _host(ops_root).stages() == {1, 3}  # stage 2 is the forge's MERGED, never recorded
    host.fail_apply = set()
    gate2 = Gate(gate.target, host, forge, FakePrompt(), [].append, _host(ops_root))
    second = run(gate2)
    assert second.ok and second.ran == (4, 5, 6, 7, 8)
    assert sum(c[0] == "labels" and "fr-queue:release" in c[1][1] for c in forge.calls) == 1


def test_a_ready_probe_that_fails_stops_stage_3(ops_root: Path) -> None:
    gate, host, *_ = _gate(ops_root)
    host.ready_code = 1
    result = run(gate)
    assert result.failed == 3 and "ready" in result.why


def test_a_rerun_of_a_complete_stage_does_nothing(ops_root: Path) -> None:
    gate, host, tree, forge, *_ = _gate(ops_root)
    assert run(gate).ok
    n_host, n_tree = len(host.calls), len(tree.calls)
    again = run(Gate(gate.target, host, forge, FakePrompt(), [].append, _host(ops_root)))
    assert again.ok and again.ran == ()
    assert len(host.calls) == n_host and len(tree.calls) == n_tree


# ------------------------------------------------------- devops steps, the hand-off


def test_an_owed_devops_step_is_refused_at_stage_6(ops_root: Path) -> None:
    gate, host, tree, forge, *_ = _gate(ops_root, prompt=FakePrompt(answers=["owed not yet"]))
    tree.gate_pass_code = 2
    result = run(gate)
    assert result.failed == 6 and "gate pass" in result.why
    assert 5 in _host(ops_root).stages()


def test_an_unanswered_devops_step_stops_stage_5(ops_root: Path) -> None:
    gate, *_ = _gate(ops_root, prompt=FakePrompt(answers=["", "", ""]))
    result = run(gate)
    assert result.failed == 5 and "Not understood: ''" in result.why


def test_stage_7_keeps_gate_tester_and_the_pass_comment_lists_its_steps(ops_root: Path) -> None:
    gate, host, tree, forge, prompt, said = _gate(ops_root)
    assert run(gate).ok
    tree_args = [a for k, (a, _) in ((k, v) for k, v in tree.calls if k == "fr")]
    gp = next(a for a in tree_args if a[:2] == ["gate", "pass"])
    notes = gp[gp.index("--notes") + 1]
    assert "Tester gate owns" in notes and "click the page" in notes
    assert any("gate:tester stays" in line for line in said)
    assert not any("tester" in a for a in tree_args if a[:2] != ["gate", "pass"])


def test_stage_8_reuses_an_open_housekeeping_pr(ops_root: Path) -> None:
    _record_stages(ops_root, 1, 2, 3, 4, 5, 6, 7)
    forge = FakeForge(state="MERGED")
    forge.open_prs["chore/ops-p"] = 7
    gate, host, tree, *_ = _gate(ops_root, up=True, forge=forge)
    assert run(gate).ok
    assert not [c for c in forge.calls if c[0] == "pr_create"]


def test_pr_number_reads_a_url_or_a_number() -> None:
    assert gate_mod.pr_number("https://github.com/o/r/pull/12") == 12
    assert gate_mod.pr_number("12") == 12
    assert gate_mod.pr_number(None) is None


# ------------------------------------------- p4-merge-head-pinned: the verified head


def test_stage_1_records_the_head_it_was_cut_from(ops_root: Path) -> None:
    gate, *_ = _gate(ops_root)
    run(gate)
    assert _host(ops_root).head() == HEAD


def test_a_head_that_moved_after_stage_1_is_refused_and_nothing_merges(ops_root: Path) -> None:
    old = "b" * 40
    _record_stages(ops_root, 1, head=old)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, host, tree, forge, prompt, _ = _gate(ops_root, up=True, live_closed=True)
    result = run(gate)
    assert result.failed == 2 and result.code == 2
    assert old in result.why and HEAD in result.why and "fr isolation down" in result.why
    assert not _labelled(forge, "fr-queue:release")
    assert not any(a.startswith("RELEASE") for a in prompt.asked)


def test_the_merge_and_the_rebase_carry_the_recorded_head(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, host, tree, forge, *_ = _gate(ops_root, up=True, live_closed=True)
    calls: list[str] = []
    real_view = forge.pr_view

    def view(repo: str, number: int) -> dict[str, Any]:
        v = real_view(repo, number)
        calls.append(v["head_oid"])
        return v

    forge.pr_view = view  # type: ignore[method-assign]
    assert run(gate).ok
    assert _labelled(forge, "fr-queue:release")
    assert ("rebase", ("origin/main", HEAD)) in tree.calls


def test_a_reused_workspace_not_cut_from_the_live_head_is_refused(ops_root: Path) -> None:
    """p4-r5: a workspace cut from any other commit (a descendant included) is refused."""
    gate, host, tree, forge, *_ = _gate(ops_root, up=True)
    _host(ops_root).set_cut("b" * 40)
    result = run(gate)
    assert result.failed == 1 and "fr isolation down" in result.why
    assert "b" * 40 in result.why and HEAD in result.why
    assert not any(a[:2] == ["isolation", "exec"] for a, _ in host.calls)


def test_a_reused_workspace_with_no_recorded_cut_is_refused(ops_root: Path) -> None:
    gate, host, tree, forge, *_ = _gate(ops_root, up=True)
    path = ops_root.parent / "gate-state" / "run-1.json"
    path.unlink()
    result = run(gate)
    assert result.failed == 1 and "unknown" in result.why


# ------------------------- p4-gate-state-host-side: nothing the PR carries is read


def _plant(root: Path, n: int, body: str) -> None:
    JournalLedger(root, "p").record(n, f"stage {n}", body)


def test_journal_planted_stages_skip_nothing(ops_root: Path) -> None:
    for n in range(1, 6):
        _plant(ops_root, n, f"head: {HEAD}" if n == 1 else "forged")
    gate, host, tree, forge, *_ = _gate(ops_root, up=True)
    result = run(gate)
    assert result.ran[0] == 1
    argvs = [a for a, _ in host.calls]
    assert _exec("ops", "apply", "pre", "--plan", PLAN, "--yes") in argvs


def test_a_journal_planted_head_is_ignored(ops_root: Path) -> None:
    _host(ops_root).mark(1, head=HEAD)
    _plant(ops_root, 1, "head: " + "e" * 40)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, host, tree, forge, *_ = _gate(ops_root, up=True, live_closed=True)
    assert run(gate).ok
    assert _labelled(forge, "fr-queue:release")


def test_a_malformed_recorded_sha_is_refused(ops_root: Path) -> None:
    path = ops_root.parent / "gate-state" / "run-1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"stages": [1], "head": "--exec=x"}))
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, host, tree, forge, *_ = _gate(ops_root, up=True, live_closed=True)
    result = run(gate)
    assert result.failed == 2 and result.code == 2 and "sha" in result.why
    assert not _labelled(forge, "fr-queue:release")


def test_stage_1_refuses_a_malformed_forge_head(ops_root: Path) -> None:
    forge = FakeForge()
    forge.pr["head_oid"] = "--upload-pack=x"
    gate, host, *_ = _gate(ops_root, forge=forge)
    result = run(gate)
    assert result.failed == 1 and result.code == 2
    assert not any(a[:2] == ["isolation", "up"] for a, _ in host.calls)


def test_stage_3_refuses_when_the_merged_head_differs(ops_root: Path) -> None:
    _record_stages(ops_root, 1, 2)
    forge = FakeForge(state="MERGED")
    forge.pr["head_oid"] = "f" * 40
    gate, host, tree, *_ = _gate(ops_root, up=True, forge=forge)
    result = run(gate)
    assert result.failed == 3 and result.code == 2 and HEAD in result.why
    assert not [c for c in tree.calls if c[0] == "rebase"]


def test_host_state_lives_outside_every_checkout(monkeypatch, tmp_path: Path) -> None:
    from fr.ops.gate import gate_state_path

    monkeypatch.setenv("FR_OPS_GATE_DIR", str(tmp_path / "gs"))
    monkeypatch.setattr("fr.ops.trust.repo_key", lambda root: "derio-net--super-fr")
    assert gate_state_path(tmp_path / "repo", "run-1") == (
        tmp_path / "gs" / "derio-net--super-fr" / "run-1.json"
    )
    monkeypatch.delenv("FR_OPS_GATE_DIR")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    assert gate_state_path(tmp_path / "repo", "r").parent.parent == tmp_path / "xdg/fr/ops-gate"
    HostGateState(tmp_path / "s" / "r.json").mark(1, head=HEAD)
    assert oct((tmp_path / "s" / "r.json").stat().st_mode & 0o777) == "0o600"


# ------------------------------------- spec 2026-11-01-ops-gate-probes R5: the ops gap


def _gapped(ops_root: Path, ops_yaml: str | None = None) -> None:
    """A devops-gated spec with a command step, and a plan with no op."""
    (ops_root / SPEC).write_text(
        "# S\n\n## Verification\n\nstrategy: none\ngate: devops\n\n## Test Plan\n\n"
        "- run `pulumi up` on the stack\n- [tester] click the page\n"
    )
    (ops_root / PLAN / "ops.yaml").unlink()
    if ops_yaml is not None:
        (ops_root / PLAN / "ops.yaml").write_text(ops_yaml)


def test_stage_1_refuses_an_ops_gap_before_anything_is_brought_up(ops_root: Path) -> None:
    _gapped(ops_root)
    gate, host, *_ = _gate(ops_root)
    with pytest.raises(gate_mod.StageFailed) as exc:
        gate_mod.stage_1(gate)
    assert exc.value.code == 2
    for needle in ("step 1", "pulumi up", "fr ops stub", "none:", "PR #5"):
        assert needle in exc.value.why, (needle, exc.value.why)
    assert not any(a[:2] == ["isolation", "up"] for a, _ in host.calls)
    assert any(a[:2] == ["materialise", HEAD] for a, _ in host.calls)
    assert host.materialised and not any(p.exists() for p in host.materialised)
    assert _host(ops_root).head() is None  # nothing recorded


def test_stage_1_reads_a_merged_prs_gap_from_the_default_branch_tip(ops_root: Path) -> None:
    """review p1-r1 (gh#1266 family): a merged PR gains no commits, so the gap is read
    from the default branch's tip, where a follow-up fix lands, and the refusal says so."""
    _gapped(ops_root)
    gate, host, *_ = _gate(ops_root, forge=FakeForge(state="MERGED"))
    with pytest.raises(gate_mod.StageFailed) as exc:
        gate_mod.stage_1(gate)
    assert exc.value.code == 2
    assert any(a[:2] == ["materialise", TIP] for a, _ in host.calls)
    assert not any(a[:2] == ["materialise", HEAD] for a, _ in host.calls)
    assert "follow-up PR" in exc.value.why and "on the PR branch" not in exc.value.why
    assert not any(a[:2] == ["isolation", "up"] for a, _ in host.calls)


def test_stage_1_passes_a_merged_pr_once_the_tip_carries_the_fix(ops_root: Path) -> None:
    """review p1-r1: the way out — `none:` (or ops) landed on the default branch."""
    _gapped(ops_root, "schema_version: 2\nnone: converged by hand\n")
    gate, host, *_ = _gate(ops_root, forge=FakeForge(state="MERGED"))
    gate_mod.stage_1(gate)
    assert any(a[:2] == ["materialise", TIP] for a, _ in host.calls)
    assert any(a[:2] == ["isolation", "up"] for a, _ in host.calls)


def test_stage_1_reports_a_git_failure_in_the_gap_read_as_not_checked(
    ops_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """review p1-r3: the advisory read never escapes the stage as a raw GitError."""
    from fr.triage.gitseam import GitError

    _gapped(ops_root)
    gate, host, *_ = _gate(ops_root)
    said: list[str] = []
    monkeypatch.setattr(gate, "say", said.append)

    def boom(ref: str, paths: object) -> Path:
        raise GitError("archive failed")

    monkeypatch.setattr(host, "materialise", boom)
    gate_mod.stage_1(gate)
    assert any("not checked" in line for line in said)


def test_stage_1_passes_the_gap_check_with_a_none_acknowledgement(ops_root: Path) -> None:
    _gapped(ops_root, "schema_version: 2\nnone: converged by hand\n")
    gate, host, *_ = _gate(ops_root)
    result = run(gate)
    assert "ops gap" not in result.why
    assert any(a[:2] == ["isolation", "up"] for a, _ in host.calls)


# ----------------------------------------------- R10: the answer grammar (stage 5)


def _run5(ops_root: Path, answers: list[str]) -> tuple[Any, FakePrompt, FakeTree]:
    _record_stages(ops_root, 1, 2, 3, 4)
    gate, host, tree, forge, prompt, _ = _gate(
        ops_root, up=True, prompt=FakePrompt(answers=answers)
    )
    return run(gate), prompt, tree


def _outcome_args(tree: FakeTree) -> list[list[str]]:
    return [c[1][0] for c in tree.calls if c[0] == "fr" and c[1][0][:2] == ["closeout", "outcome"]]


@pytest.mark.parametrize(
    ("answer", "flag", "text"),
    [
        ("ran: x", "--ran", "x"),
        ("ran:x", "--ran", "x"),
        ("na - y", "--na", "y"),
        ("na- y", "--na", "y"),
        ("owed x", "--owed", "x"),
        ("N/A: z", "--na", "z"),
    ],
)
def test_the_answer_grammar_accepts(ops_root: Path, answer: str, flag: str, text: str) -> None:
    result, prompt, tree = _run5(ops_root, [answer])
    assert result.failed != 5
    (args,) = _outcome_args(tree)
    assert args[args.index(flag) + 2] == text and len(prompt.asked) == 1


@pytest.mark.parametrize("bad", ["rancid", "na-ive", "ran", "", "ran:", "retry"])
def test_a_non_matching_answer_is_reprompted_with_an_echo(ops_root: Path, bad: str) -> None:
    result, prompt, tree = _run5(ops_root, [bad, "ran: walked"])
    assert len(prompt.asked) == 2
    assert repr(bad) in prompt.asked[1] and "`ran <evidence>`" in prompt.asked[1]
    (args,) = _outcome_args(tree)
    assert args[args.index("--evidence") + 1] == "walked"


def test_three_non_matches_in_a_row_fail_the_stage_with_the_echo(ops_root: Path) -> None:
    result, prompt, tree = _run5(ops_root, ["rancid", "ran", "na-ive"])
    assert result.failed == 5 and "'na-ive'" in result.why and len(prompt.asked) == 3
    assert "`ran <evidence>`" in result.why  # review p2-r3: the grammar is echoed too
    assert _outcome_args(tree) == []


# ------------------------------------------------ R8: a pointed step is probed


def _row(op: str, state: str, how: str | None = None, **kw: Any) -> dict[str, Any]:
    row = {"op": op, "state": state, "label": state, "how": how, "reason": "", "output": None,
           "evidence": None}  # fmt: skip
    return {**row, **kw}


def _point(ops_root: Path, op: str = "post") -> None:
    spec = ops_root / SPEC
    spec.write_text(spec.read_text().replace("[devops] walk", f"[devops] (op: {op}) walk"))


def _probe(ops_root: Path, script: list[tuple[int, Any]], answers: list[str] | None = None):
    _point(ops_root)
    _record_stages(ops_root, 1, 2, 3, 4)
    gate, host, tree, forge, prompt, said = _gate(
        ops_root, up=True, prompt=FakePrompt(answers=answers or [])
    )
    host.by_id["post"] = list(script)
    return run(gate), host, tree, prompt, said


def test_a_passing_probe_records_ran_with_its_evidence_and_asks_nothing(ops_root: Path) -> None:
    done = [_row("post", "DONE", "checked", output="a\nb", evidence="a; b")]
    result, host, tree, prompt, said = _probe(ops_root, [(0, done)])
    assert result.failed != 5 and prompt.asked == []
    (args,) = _outcome_args(tree)
    assert args[args.index("--ran") :][:3] == ["--ran", "--evidence", "post: check passed — a; b"]
    trusts = [c for c in tree.calls if c[0] == "fr" and c[1][0][:2] == ["ops", "trust"]]
    assert len(trusts) == 1 and any("a\nb" in line for line in said)


def test_trust_is_granted_before_the_first_probe_runs(ops_root: Path) -> None:
    """review p2-r3: R8's `gate.trust(tree)` precedes the first `fr ops status <id>`."""
    order: list[str] = []
    done = [_row("post", "DONE", "checked", evidence="ok")]
    _point(ops_root)
    _record_stages(ops_root, 1, 2, 3, 4)
    gate, host, tree, forge, prompt, said = _gate(ops_root, up=True)
    host.by_id["post"] = [(0, done)]
    real_trust, real_fr = gate.trust, host.fr

    def trust(t: Any) -> None:
        order.append("trust")
        real_trust(t)

    def fr(args: Any, *, terminal: bool = False) -> tuple[int, str]:
        if "status" in list(args):
            order.append("status")
        return real_fr(args, terminal=terminal)

    gate.trust = trust  # type: ignore[method-assign]
    host.fr = fr  # type: ignore[method-assign]
    run(gate)
    assert "status" in order and order.index("trust") < order.index("status")


@pytest.mark.parametrize("state", ["UNVERIFIABLE", "CANNOT-VERIFY", "ESCALATE"])
def test_a_failing_state_offers_only_retry_na_owed(ops_root: Path, state: str) -> None:
    """review p2-r3: every not-done state is treated as OPEN is (R8)."""
    script = [(1, [_row("post", state, reason="why")])]
    result, host, tree, prompt, _ = _probe(ops_root, script, ["ran x", "owed chase it"])
    assert "`retry`" in prompt.asked[0] and "`ran <evidence>`" not in prompt.asked[0]
    assert "Not understood: 'ran x'" in prompt.asked[1]
    (args,) = _outcome_args(tree)
    assert "--owed" in args


@pytest.mark.parametrize("how", ["proof", "legacy", "attested"])
def test_a_done_that_ran_no_check_asks_the_usual_question(ops_root: Path, how: str) -> None:
    """review p2-r3: no probe ran, so fr records no `ran` on its own (R8)."""
    script = [(0, [_row("post", "DONE", how)])]
    result, host, tree, prompt, _ = _probe(ops_root, script, ["ran: walked it"])
    assert len(prompt.asked) == 1 and "`ran <evidence>`" in prompt.asked[0]
    (args,) = _outcome_args(tree)
    assert args[args.index("--evidence") + 1] == "walked it"


def test_an_open_probe_offers_retry_na_owed_and_retry_reruns_it(ops_root: Path) -> None:
    script = [(1, [_row("post", "OPEN", reason="HTTP 404")]),
              (1, [_row("post", "OPEN", reason="HTTP 404")]),
              (0, [_row("post", "DONE", "checked", evidence="ok")])]  # fmt: skip
    result, host, tree, prompt, _ = _probe(ops_root, script, ["retry", "ran x", "retry"])
    assert len(prompt.asked) == 3 and "`retry`" in prompt.asked[0]
    assert "Not understood: 'ran x'" in prompt.asked[2]
    (args,) = _outcome_args(tree)
    assert "post: check passed — ok" in args


def test_an_escalate_probe_is_handled_like_open(ops_root: Path) -> None:
    result, host, tree, prompt, _ = _probe(
        ops_root, [(3, [_row("post", "ESCALATE", reason="p1")])], ["owed later"]
    )
    (args,) = _outcome_args(tree)
    assert "--owed" in args and "`retry`" in prompt.asked[0]


@pytest.mark.parametrize("row", [_row("post", "N/A"), _row("post", "DONE", "attested")])
def test_na_and_attested_ask_the_usual_question_and_record_no_ran_on_their_own(
    ops_root: Path, row: dict[str, Any]
) -> None:
    result, host, tree, prompt, _ = _probe(ops_root, [(0, [row])], ["ran: by hand"])
    assert "`ran <evidence>`" in prompt.asked[0] and "retry" not in prompt.asked[0]
    (args,) = _outcome_args(tree)
    assert args[args.index("--evidence") + 1] == "by hand"


def test_a_refused_status_fails_the_stage_with_its_output(ops_root: Path) -> None:
    result, host, tree, prompt, _ = _probe(ops_root, [(2, "untrusted op set")])
    assert result.failed == 5 and "untrusted op set" in result.why and prompt.asked == []
    assert _outcome_args(tree) == []


def test_stage_1_refuses_a_near_miss_test_plan_heading(ops_root: Path) -> None:
    """super-fr#1315: a numbered Test Plan heading hides every devops step, so stage 1
    refuses it before anything comes up — never `not checked`."""
    _gapped(ops_root)
    spec = ops_root / SPEC
    spec.write_text(spec.read_text().replace("## Test Plan", "## 6. Test Plan (post-merge)"))
    gate, host, *_ = _gate(ops_root)
    with pytest.raises(gate_mod.StageFailed) as exc:
        gate_mod.stage_1(gate)
    assert exc.value.code == 2
    assert 'rename it to "## Test Plan"' in exc.value.why
    assert not any(a[:2] == ["isolation", "up"] for a, _ in host.calls)


def test_a_stage_that_meets_a_near_miss_heading_fails_cleanly(
    ops_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A later stage reading the steps (`gated_steps`) refuses through the runner, not a
    traceback (super-fr#1315)."""
    from fr.spec import TestPlanHeading, TestPlanHeadingError

    def boom(gate: object) -> None:
        raise TestPlanHeadingError(TestPlanHeading(4, "## 6. Test Plan", False), SPEC)

    first = gate_mod.STAGES[0]
    monkeypatch.setattr(
        gate_mod, "STAGES", (dataclasses.replace(first, act=boom), *gate_mod.STAGES[1:])
    )
    gate, *_ = _gate(ops_root)
    result = gate_mod.run(gate)
    assert not result.ok and result.code == 2
    assert 'rename it to "## Test Plan"' in result.why


def test_gh1293_an_op_already_done_live_is_recorded_not_skipped(ops_root: Path) -> None:
    """gh#1293: an op whose live check already reads DONE at stage 4 still goes through
    `fr ops apply --yes`, which records the closure it observed (R7). Skipped instead, it
    leaves no `op` evidence, so `fr gate pass` reads it as 'never checked' and refuses."""
    from fr.ops.holds import devops_blockers

    gate, host, tree, _, prompt, _ = _gate(ops_root, up=True)
    host.live["post"] = "DONE"  # checked live, nothing recorded yet

    gate_mod.apply_phase(gate, "post-merge")

    applies = [a for a, _ in host.calls if a[:2] == ["isolation", "exec"] and "apply" in a]
    assert [a[a.index("--") + 1 :] for a in applies] == [
        ["fr", "ops", "apply", "post", "--plan", PLAN, "--yes"]
    ]
    assert prompt.asked == []  # a closed op runs nothing: nothing to confirm
    assert not [b for b in devops_blockers(ops_root, _state()) if b.startswith("op post")]


def _devops_only_spec(ops_root: Path, rows: str = "") -> None:
    """A spec whose every Test Plan step is devops-gated (gh#1275's run)."""
    (ops_root / SPEC).write_text(
        f"# S\n\n## Verification\n\nstrategy: none\ngate: devops\n{rows}\n## Test Plan\n\n"
        "- [devops] walk the stage\n"
    )


def _gate_passes(tree: FakeTree) -> list[list[str]]:
    calls = [v[0] for k, v in tree.calls if k == "fr"]
    return [a for a in calls if a[:2] == ["gate", "pass"]]


def test_gh1275_stage_7_passes_a_gate_tester_nothing_owns(ops_root: Path) -> None:
    _devops_only_spec(ops_root)
    gate, host, tree, forge, _, said = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    tree.fr(["closeout", "outcome", "--run", "run-1", "--step", "1", "--ran"])  # stage 5's

    gate_mod.stage_7(gate)

    (gp,) = _gate_passes(tree)
    assert gp[gp.index("--gate") + 1] == "tester" and gp[-1] == "--yes"
    assert "no Test Plan step or unwalked row" in gp[gp.index("--notes") + 1]
    assert 7 in _host(ops_root).stages()


def test_gh1275_stage_7_keeps_gate_tester_for_an_unwalked_tester_row(ops_root: Path) -> None:
    _devops_only_spec(ops_root, "- r1: live — needs the merged build\n")
    write_matrix(ops_root, [row(SPEC, rid="r1", status="walk-owed")])
    gate, host, tree, forge, _, said = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))

    gate_mod.stage_7(gate)

    assert _gate_passes(tree) == []
    assert any("gate:tester stays" in line for line in said)
    assert any("row r1" in line for line in said)


def test_gh1275_stage_7_passes_nothing_when_the_pr_has_no_gate_tester(ops_root: Path) -> None:
    _devops_only_spec(ops_root)
    forge = FakeForge(state="MERGED")
    forge.pr["labels"] = ["gate:devops-passed"]
    gate, host, tree, *_ = _gate(ops_root, up=True, forge=forge)

    gate_mod.stage_7(gate)

    assert _gate_passes(tree) == []
    assert 7 in _host(ops_root).stages()


def test_the_merges_check_read_reports_a_cancelled_check_pending_not_failed() -> None:
    """Spec 2026-11-24-ci-economy R3: `_checks_green` reads the `cancel` bucket as pending."""
    from types import SimpleNamespace

    from fr.ops.gate import StageFailed, _checks_green

    class Forge:
        def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
            return [{"name": "ci", "bucket": "cancel"}, {"name": "x", "bucket": "pass"}]

        def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
            return []

    gate = SimpleNamespace(target=SimpleNamespace(repo=REPO, pr=5), forge=Forge())
    with pytest.raises(StageFailed) as exc:
        _checks_green(gate)  # type: ignore[arg-type]
    assert "failing" not in str(exc.value)


@pytest.mark.parametrize("required", [False, True])
def test_the_merges_check_read_names_cancelled_unreplaced_checks(required: bool) -> None:
    """Review #1647: nothing still runs and a check was cancelled with no newer run: the
    stage says so by name, with the remedy, never "checks are pending"."""
    from types import SimpleNamespace

    from fr.ops.gate import StageFailed, _checks_green

    checks = [{"name": "test (1)", "bucket": "cancel"}, {"name": "x", "bucket": "pass"}]

    class Forge:
        def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
            return checks

        def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
            return checks if required else []

    gate = SimpleNamespace(target=SimpleNamespace(repo=REPO, pr=5), forge=Forge())
    with pytest.raises(StageFailed) as exc:
        _checks_green(gate)  # type: ignore[arg-type]
    assert str(exc.value) == (
        "PR #5's checks were cancelled with no newer run: test (1); re-run the workflow"
    )


def test_the_merges_check_read_says_pending_while_a_check_still_runs() -> None:
    from types import SimpleNamespace

    from fr.ops.gate import StageFailed, _checks_green

    class Forge:
        def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
            return [{"name": "a", "bucket": "cancel"}, {"name": "b", "bucket": "pending"}]

        def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
            return []

    gate = SimpleNamespace(target=SimpleNamespace(repo=REPO, pr=5), forge=Forge())
    with pytest.raises(StageFailed) as exc:
        _checks_green(gate)  # type: ignore[arg-type]
    assert "checks are pending" in str(exc.value)


class LoginPageForge(FakeForge):
    """A forge whose default-branch read meets an SSO login page (gh#1554)."""

    def default_branch(self, *, cwd: Path, run: Any = None) -> str | None:
        from fr.tea import TeaError

        raise TeaError(
            "HTTP 200 with an HTML body, not the forge's JSON: an SSO or forward-auth "
            "login page, most likely; exempt the instance's /api/ paths or use an internal URL"
        )


def test_a_forge_error_on_the_default_branch_read_is_a_refusal_naming_it(
    ops_root: Path,
) -> None:
    """R7 (spec 2026-11-19-consumer-followups): a raised forge error is the gate's
    exit-2 refusal, naming the cause, never a traceback."""
    gate, *_ = _gate(ops_root, forge=LoginPageForge())
    with pytest.raises(gate_mod.StageFailed) as exc:
        _ = gate.default
    assert exc.value.code == 2
    assert "cannot read the default branch from the forge" in exc.value.why
    assert "SSO or forward-auth login page" in exc.value.why


# ------------------------------------- ops-gate-truth R6: ops a refresh reopened


def test_the_host_state_keeps_reopened_ops_and_the_entries_before_them(ops_root: Path) -> None:
    state = _host(ops_root)
    assert state.reopened() == (frozenset(), frozenset())
    state.set_reopened({"post", "new"}, {"e1", "e2"})
    assert state.reopened() == (frozenset({"post", "new"}), frozenset({"e1", "e2"}))
    state.clear_reopened()
    assert state.reopened() == (frozenset(), frozenset())


def test_forget_drops_the_stages_from_n_and_keeps_the_rest(ops_root: Path) -> None:
    state = _host(ops_root)
    for n in (1, 3, 4, 5, 6):
        state.mark(n, head=HEAD if n == 1 else None)
    state.set_cut(HEAD)
    state.set_pushed(TIP)
    state.set_reopened({"post"}, {"e1"})
    state.forget(4)
    assert state.stages() == {1, 3}
    assert (state.head(), state.cut(), state.pushed()) == (HEAD, HEAD, TIP)
    assert state.reopened() == (frozenset({"post"}), frozenset({"e1"}))


def _post_applies(host: FakeHost) -> list[list[str]]:
    applies = [a for a, _ in host.calls if a[:2] == ["isolation", "exec"] and "apply" in a]
    return [a[a.index("--") + 1 :] for a in applies]


def test_a_reopened_op_whose_old_evidence_closes_it_is_applied_again(ops_root: Path) -> None:
    gate, host, tree, _, prompt, _ = _gate(ops_root, up=True)
    old = record_op(ops_root, "p", op="post", result="done", phase="post-merge")
    host.live["post"] = "DONE"
    gate_mod.apply_phase(gate, "post-merge")
    assert _post_applies(host) == []  # recorded and live: nothing to do

    _host(ops_root).set_reopened({"post"}, {old.id})
    host.calls.clear()
    gate_mod.apply_phase(gate, "post-merge")
    assert _post_applies(host) == [["fr", "ops", "apply", "post", "--plan", PLAN, "--yes"]]
    assert prompt.asked == []  # live DONE: it records, runs nothing

    host.live["post"] = "OPEN"
    host.calls.clear()
    _host(ops_root).set_reopened({"post"}, {old.id, *_entry_ids(ops_root)})
    gate_mod.apply_phase(gate, "post-merge")
    assert _post_applies(host) == [["fr", "ops", "apply", "post", "--plan", PLAN, "--yes"]]
    assert len(prompt.asked) == 1 and "post" in prompt.asked[0]  # it runs: confirmed


def _entry_ids(root: Path) -> set[str]:
    from fr.journal.model import parse_journal

    return {e.id for e in parse_journal(journal_path(root, "plan", "p").read_text())}


def test_a_closure_from_before_the_refresh_does_not_close_a_reopened_op(ops_root: Path) -> None:
    gate, host, tree, *_ = _gate(ops_root, up=True)
    host.live["post"] = "DONE"
    host.how["post"] = "attested"  # closed by its journal entry, not by a live check
    old = record_op(ops_root, "p", op="post", result="done", phase="post-merge")
    ops = gate_mod._ops(tree, PLAN, "post-merge")
    rows = gate_mod._status_rows(gate, "post-merge")
    assert gate_mod._unclosed(gate, tree, ops, rows) == []

    _host(ops_root).set_reopened({"post"}, {old.id})
    assert gate_mod._unclosed(gate, tree, ops, rows) == ["post: DONE"]
    record_op(ops_root, "p", op="post", result="done", phase="post-merge")  # after the refresh
    assert gate_mod._unclosed(gate, tree, ops, rows) == []


def test_stage_4_clears_the_reopened_ops(ops_root: Path) -> None:
    _record_stages(ops_root, 1, 3)
    gate, *_ = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    _host(ops_root).set_reopened({"post"}, set())
    gate_mod.stage_4(gate)
    assert 4 in _host(ops_root).stages()
    assert _host(ops_root).reopened() == (frozenset(), frozenset())


# -------------------------- ops-gate-truth R1–R6: stages 4–7 refresh the ops workspace

FIXED_OPS = OPS.replace("phase: post-merge, check: 'false', apply: 'true',",
                        "phase: post-merge, check: 'false', apply: 'echo fixed',")  # fmt: skip
NEW_OP = "  - {id: extra, summary: n, phase: pre-merge, check: 'false', apply: 'true'}\n"


def _drifted(
    ops_root: Path,
    *stages: int,
    ops: str | None = FIXED_OPS,
    spec: str | None = None,
    confirms: Sequence[bool] = (),
) -> tuple[Gate, FakeHost, FakeTree, FakePrompt]:
    """A run with *stages* recorded whose default branch moved since stage 3: its ops
    (*ops*) and/or its Test Plan (*spec*). A clean merge brings the change in."""
    _record_stages(ops_root, *stages)
    gate, host, tree, _, prompt, _ = _gate(
        ops_root, up=True, forge=FakeForge(state="MERGED"), prompt=FakePrompt(confirms)
    )
    edits: dict[str, str | None] = {}
    if ops is not None:
        edits[f"{PLAN}/ops.yaml"] = ops
    if spec is not None:
        edits[SPEC] = spec
    host.default_edits = edits
    tree.on_merge = lambda: _write_edits(ops_root, edits)
    return gate, host, tree, prompt


def _refresh_q(prompt: FakePrompt) -> list[str]:
    return [a for a in prompt.asked if a.startswith("REFRESH")]


def test_no_drift_asks_nothing_merges_nothing_and_the_stage_acts(ops_root: Path) -> None:
    gate, host, tree, prompt = _drifted(ops_root, 1, 3, ops=None)
    gate_mod.stage_4(gate)
    assert _refresh_q(prompt) == [] and not [c for c in tree.calls if c[0] == "merge"]
    assert ["fetch", "main"] in [a for a, _ in host.calls]
    assert 4 in _host(ops_root).stages()
    assert host.materialised and not any(p.exists() for p in host.materialised)


def test_a_declined_refresh_fails_the_stage_and_changes_nothing(ops_root: Path) -> None:
    gate, host, tree, prompt = _drifted(ops_root, 1, 3, confirms=[False])
    before = _host(ops_root).path.read_text()
    with pytest.raises(gate_mod.StageFailed, match="declined"):
        gate_mod.stage_4(gate)
    assert [c[0] for c in tree.calls] == []  # no commit, no merge, no push
    assert _host(ops_root).path.read_text() == before
    assert not _post_applies(host)


def test_a_confirmed_refresh_commits_merges_pushes_then_trusts_before_any_apply(
    ops_root: Path,
) -> None:
    gate, host, tree, prompt = _drifted(ops_root, 1, 3)
    order: list[str] = []
    tree_fr, host_fr = tree.fr, host.fr

    def tfr(args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        order.append(" ".join(args[:2]))
        return tree_fr(args, terminal=terminal)

    def hfr(args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        if "apply" in args:
            order.append("ops apply")
        return host_fr(args, terminal=terminal)

    tree.fr, host.fr = tfr, hfr  # type: ignore[method-assign]
    gate_mod.stage_4(gate)
    kinds = [k for k, _ in tree.calls if k in ("commit", "merge", "push")]
    assert kinds[:3] == ["commit", "merge", "push"]
    assert tree.calls[[k for k, _ in tree.calls].index("merge")][1][0] == TIP
    assert order.index("ops trust") < order.index("ops apply")
    assert _host(ops_root).pushed() == HEAD
    (q,) = _refresh_q(prompt)
    assert "changed: post" in q and "Test Plan" not in q


def test_the_confirmation_names_every_op_and_a_changed_test_plan(ops_root: Path) -> None:
    spec = (ops_root / SPEC).read_text().replace("walk the stage", "walk it twice")
    ops = FIXED_OPS.replace("  - id: mut\n", NEW_OP + "  - id: mut\n").replace(
        "  - {id: pre, summary: create the thing, phase: pre-merge, check: 'false', "
        "apply: 'true'}\n",
        "",
    )
    gate, host, tree, prompt = _drifted(ops_root, 1, 3, ops=ops, spec=spec)
    gate_mod.stage_4(gate)
    (q,) = _refresh_q(prompt)
    for part in ("added: extra", "removed: pre", "changed: post", "Test Plan changed",
                 "origin/main"):  # fmt: skip
        assert part in q, q


def test_a_conflicting_refresh_names_the_paths_and_the_manual_merge(ops_root: Path) -> None:
    gate, host, tree, prompt = _drifted(ops_root, 1, 3)
    tree.merge_conflict = (f"{PLAN}/ops.yaml", "docs/x.md")
    with pytest.raises(gate_mod.StageFailed) as exc:
        gate_mod.stage_4(gate)
    why = exc.value.why
    assert f"{PLAN}/ops.yaml" in why and "docs/x.md" in why
    assert f"git -C {ops_root} merge {TIP}" in why
    assert not [c for c in tree.calls if c[0] == "push"]
    assert 4 not in _host(ops_root).stages()


def test_a_refresh_at_stage_5_goes_back_to_stage_4_and_reapplies(ops_root: Path) -> None:
    gate, host, tree, prompt = _drifted(ops_root, 1, 3, 4)
    _pre_merge_closed(ops_root)
    record_op(ops_root, "p", op="post", result="done", phase="post-merge")
    host.live["post"] = "DONE"
    result = run(gate)
    assert result.ok, result.why
    assert result.ran == (4, 5, 6, 7, 8)
    assert _post_applies(host) == [["fr", "ops", "apply", "post", "--plan", PLAN, "--yes"]]
    assert _host(ops_root).reopened() == (frozenset(), frozenset())
    assert len(_refresh_q(prompt)) == 1


def test_a_test_plan_only_refresh_at_stage_5_reopens_and_forgets_nothing(ops_root: Path) -> None:
    spec = (ops_root / SPEC).read_text().replace("click the page", "click it twice")
    gate, host, tree, prompt = _drifted(ops_root, 1, 3, 4, ops=None, spec=spec)
    gate_mod.stage_5(gate)
    assert len(_refresh_q(prompt)) == 1 and [k for k, _ in tree.calls if k == "merge"]
    assert _host(ops_root).reopened() == (frozenset(), frozenset())
    assert {1, 3, 4, 5} <= _host(ops_root).stages()


@pytest.mark.parametrize("at", [6, 7])
def test_a_test_plan_only_refresh_at_stage_6_or_7_goes_back_to_stage_5(
    ops_root: Path, at: int
) -> None:
    """p1-r3: stage 5 walks the Test Plan, so a changed one is walked again."""
    spec = (ops_root / SPEC).read_text().replace("walk the stage", "walk it twice")
    gate, host, tree, prompt = _drifted(ops_root, 1, 3, 4, 5, *range(6, at), ops=None, spec=spec)
    _pre_merge_closed(ops_root)
    record_op(ops_root, "p", op="post", result="done", phase="post-merge")  # stage 4's
    result = run(gate)
    assert result.ok, result.why
    assert result.ran == (5, 6, 7, 8)
    assert _host(ops_root).reopened() == (frozenset(), frozenset())
    assert not _post_applies(host)  # stage 4 is not forgotten: no op changed
    assert any("walk it twice" in a for a in prompt.asked)  # stage 5 asked the new step


def test_a_default_branch_without_the_plan_dir_is_refused(ops_root: Path) -> None:
    gate, host, tree, prompt = _drifted(ops_root, 1, 3, ops=None)
    host.default_edits = {PLAN: None}
    with pytest.raises(gate_mod.StageFailed) as exc:
        gate_mod.stage_4(gate)
    assert PLAN in exc.value.why and exc.value.code == 2
    assert _refresh_q(prompt) == [] and not tree.calls


def test_the_refresh_merges_the_sha_it_diffed_though_the_default_branch_moved(
    ops_root: Path,
) -> None:
    """Review p1-sec-r1: the drift, the question and the merge name one pinned commit."""
    gate, host, tree, prompt = _drifted(ops_root, 1, 3)
    materialise = host.materialise

    def then_move(ref: str, paths: Sequence[str]) -> Path:
        out = materialise(ref, paths)
        host.tip = "d" * 40  # origin/main moves while the operator reads the question
        return out

    host.materialise = then_move  # type: ignore[method-assign]
    gate_mod.stage_4(gate)
    assert ["materialise", TIP] == [a for a, _ in host.calls if a[0] == "materialise"][0][:2]
    assert [v[0] for k, v in tree.calls if k == "merge"] == [TIP]
    (q,) = _refresh_q(prompt)
    assert TIP[:12] in q


def test_a_default_tip_that_is_no_sha_is_refused_before_any_diff(ops_root: Path) -> None:
    gate, host, tree, prompt = _drifted(ops_root, 1, 3)
    host.tip = "origin/main"
    with pytest.raises(gate_mod.StageFailed) as exc:
        gate_mod.stage_4(gate)
    assert exc.value.code == 2 and not tree.calls and _refresh_q(prompt) == []


# ------------------------------------------------------ phase 1 review (p1-r1 … p1-r5)


def _close_pre_merge(ops_root: Path) -> None:
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")


def _passed_label(gate: Gate) -> None:
    gate.forge.pr["labels"] = [*gate.forge.pr["labels"], "gate:devops-passed"]  # type: ignore[attr-defined]


def test_after_a_restart_an_existing_pass_holds_when_nothing_blocks_it(ops_root: Path) -> None:
    """p1-r1: the label is trusted again only once the refreshed tree has no blocker."""
    gate, host, tree, prompt = _drifted(ops_root, 1, 3, 4, 5, 6)
    _passed_label(gate)
    _close_pre_merge(ops_root)
    record_op(ops_root, "p", op="post", result="done", phase="post-merge")
    host.live["post"] = "DONE"
    said: list[str] = []
    gate.say = said.append
    result = run(gate)
    assert result.ok, result.why
    assert result.ran == (4, 5, 6, 7, 8)
    assert any("the existing pass still holds after the refresh" in line for line in said)
    assert not [a for a in _gate_passes(tree) if a[a.index("--gate") + 1] == "devops"]


def test_after_a_restart_an_existing_pass_with_a_blocker_fails_stage_6(ops_root: Path) -> None:
    gate, host, tree, prompt = _drifted(ops_root, 1, 3, 4, 5, 6)
    _passed_label(gate)
    record_op(ops_root, "p", op="post", result="done", phase="post-merge")
    host.live["post"] = "DONE"
    result = run(gate)
    assert not result.ok and result.failed == 6
    assert "op pre" in result.why and "predates the refresh" in result.why
    assert "gate:devops-passed" in gate.forge.pr["labels"]  # type: ignore[attr-defined]
    assert not [c for c in gate.forge.calls if c[0] == "labels" and c[1][2]]  # type: ignore[attr-defined]


def test_an_entry_the_merge_brings_in_does_not_close_a_reopened_op(ops_root: Path) -> None:
    """p1-r2: the default branch's own journal entries are not evidence recorded here."""
    gate, host, tree, prompt = _drifted(ops_root, 1, 3)
    host.live["post"] = "DONE"
    merge = tree.on_merge

    def merge_with_an_entry() -> None:
        merge()
        record_op(ops_root, "p", op="post", result="done", phase="post-merge")

    tree.on_merge = merge_with_an_entry
    gate_mod.stage_4(gate)
    assert _post_applies(host) == [["fr", "ops", "apply", "post", "--plan", PLAN, "--yes"]]


def test_a_no_op_merge_that_still_differs_is_refused(ops_root: Path) -> None:
    """p1-r5: the pinned commit is already in the ops branch, yet the ops differ."""
    gate, host, tree, prompt = _drifted(ops_root, 1, 3, 4)
    tree.contains = {TIP}
    before = _host(ops_root).path.read_text()
    with pytest.raises(gate_mod.StageFailed) as exc:
        gate_mod.stage_5(gate)
    assert f"still differs from main at {TIP[:12]} after merging it" in exc.value.why
    assert "post" in exc.value.why and "resolve by hand" in exc.value.why
    assert not tree.calls and _refresh_q(prompt) == []
    assert _host(ops_root).path.read_text() == before


def test_a_refresh_that_reopens_on_every_pass_stops_at_the_bound(ops_root: Path) -> None:
    """p1-r4: MAX_RESTARTS bounds a default branch that never settles."""
    gate, host, tree, prompt = _drifted(ops_root, 1, 3, 4)
    tree.on_merge = None  # the merge never brings the change in: it drifts on every pass
    result = run(gate)
    assert not result.ok and result.failed == 5
    assert "keeps moving" in result.why


def test_a_push_that_fails_after_the_merge_is_retried_by_a_rerun(ops_root: Path) -> None:
    gate, host, tree, prompt = _drifted(ops_root, 1, 3)
    tree.push_error = "rejected"
    with pytest.raises(gate_mod.StageFailed, match="cannot push"):
        gate_mod.stage_4(gate)
    assert 4 not in _host(ops_root).stages() and _host(ops_root).pushed() is None
    tree.push_error = None
    gate_mod.stage_4(gate)
    assert [k for k, _ in tree.calls].count("push") == 2
    assert 4 in _host(ops_root).stages() and _host(ops_root).pushed() == HEAD


@pytest.mark.parametrize("at", [6, 7])
def test_an_ops_refresh_at_stage_6_or_7_goes_back_to_stage_4(ops_root: Path, at: int) -> None:
    gate, host, tree, prompt = _drifted(ops_root, 1, 3, 4, 5, *range(6, at))
    _pre_merge_closed(ops_root)
    record_op(ops_root, "p", op="post", result="done", phase="post-merge")
    host.live["post"] = "DONE"
    result = run(gate)
    assert result.ok, result.why
    assert result.ran == (4, 5, 6, 7, 8)
    assert _post_applies(host) == [["fr", "ops", "apply", "post", "--plan", PLAN, "--yes"]]


# ------------------------- ops-gate-truth R9, R12–R15: the stage walks its own rows


ROW_SPEC = (
    "# S\n\n## Verification\n\nstrategy: none\ngate: developer\n"
    "- rd: live — the devops stage walks it\ngate: rd=devops\n\n## Test Plan\n\n"
    "{step}\n- [tester] click the page\n"
)
FRAGMENT = f"docs/acceptance/features/{SPEC_SLUG}.yaml"
A_WALK = {"strategy": "live", "harness": "operator", "model": "human", "outcome": "pass",
          "at": "2026-10-22T09:00:00Z", "evidence": "e"}  # fmt: skip


def _row_spec(ops_root: Path, step: str = "- [devops] walk the stage", **rd: Any) -> None:
    (ops_root / SPEC).write_text(ROW_SPEC.format(step=step))
    write_matrix(ops_root, [{**row(SPEC, rid="rd", status="walk-owed"), **rd}])


def _fr_calls(tree: FakeTree, *verb: str) -> list[list[str]]:
    return [c[1][0] for c in tree.calls if c[0] == "fr" and c[1][0][: len(verb)] == list(verb)]


def _stage5(ops_root: Path, answers: list[str]) -> tuple[FakeTree, FakePrompt, list[str]]:
    _record_stages(ops_root, 1, 2, 3, 4)
    gate, host, tree, forge, prompt, said = _gate(
        ops_root, up=True, forge=FakeForge(state="MERGED"), prompt=FakePrompt(answers=answers)
    )
    gate_mod.stage_5(gate)
    return tree, prompt, said


def test_a_passing_probe_on_a_step_naming_rows_records_the_probe_identity(ops_root: Path) -> None:
    _row_spec(ops_root, "- [devops] (op: post) (rows: rd) walk the stage")
    _record_stages(ops_root, 1, 2, 3, 4)
    gate, host, tree, *_ = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    host.by_id["post"] = [(0, [_row("post", "DONE", "checked", evidence="ok")])]

    gate_mod.stage_5(gate)

    (args,) = _outcome_args(tree)
    assert args[args.index("--harness") + 1] == "fr-ops-probe"
    assert args[args.index("--model") + 1] == "op:post"


def test_stage_5_asks_about_an_unwalked_devops_row_no_ran_step_names(ops_root: Path) -> None:
    _row_spec(ops_root)
    tree, prompt, _ = _stage5(ops_root, ["ran walked the step", "ran walked the row"])

    assert any("rd" in q for q in prompt.asked[1:])
    (args,) = _fr_calls(tree, "acceptance", "set-status")
    flags = dict(zip(args[2::2], args[3::2], strict=False))
    assert flags["--id"] == "rd" and flags["--status"] == "walked"
    assert flags["--walk"] == "walked the row"
    assert (flags["--harness"], flags["--model"], flags["--strategy"]) == (
        "operator", "human", "live"
    )  # fmt: skip
    assert flags["--feature"] == SPEC_SLUG and "run-1" in flags["--notes"]


def test_an_owed_row_answer_sets_walk_owed_with_the_reason(ops_root: Path) -> None:
    _row_spec(ops_root)
    tree, *_ = _stage5(ops_root, ["ran walked the step", "owed needs the vendor"])

    (args,) = _fr_calls(tree, "acceptance", "set-status")
    flags = dict(zip(args[2::2], args[3::2], strict=False))
    assert (flags["--status"], flags["--notes"]) == ("walk-owed", "needs the vendor")
    assert "--walk" not in args and flags["--feature"] == SPEC_SLUG


def test_a_row_whose_only_step_was_na_is_asked_about(ops_root: Path) -> None:
    _row_spec(ops_root, "- [devops] (rows: rd) walk the stage")
    tree, prompt, _ = _stage5(ops_root, ["na not this time", "owed later"])

    assert len(_fr_calls(tree, "acceptance", "set-status")) == 1


def test_a_row_a_ran_step_names_is_not_asked_about(ops_root: Path) -> None:
    _row_spec(ops_root, "- [devops] (rows: rd) walk the stage")
    tree, prompt, _ = _stage5(ops_root, ["ran walked it"])

    assert _fr_calls(tree, "acceptance", "set-status") == []
    assert len(prompt.asked) == 1


def test_a_walk_the_pr_head_carries_does_not_count(ops_root: Path) -> None:
    _row_spec(ops_root, status="walked", walks=[A_WALK])
    _record_stages(ops_root, 1, 2, 3, 4)
    gate, host, tree, forge, prompt, _ = _gate(
        ops_root, up=True, forge=FakeForge(state="MERGED"),
        prompt=FakePrompt(answers=["ran the step", "ran the row"]),
    )  # fmt: skip
    tree.head_files[FRAGMENT] = (ops_root / FRAGMENT).read_text()

    gate_mod.stage_5(gate)

    assert len(_fr_calls(tree, "acceptance", "set-status")) == 1


def test_a_walk_the_ops_branch_recorded_closes_the_row(ops_root: Path) -> None:
    _row_spec(ops_root, status="walked", walks=[A_WALK])
    tree, prompt, _ = _stage5(ops_root, ["ran the step"])

    assert _fr_calls(tree, "acceptance", "set-status") == []


def test_stage_6_lists_what_the_devops_gate_owes_and_the_row_recovery(ops_root: Path) -> None:
    _row_spec(ops_root)
    _record_stages(ops_root, 1, 2, 3, 4, 5)
    for op in ("pre", "mut", "post"):
        record_op(ops_root, "p", op=op, result="done",
                  phase="post-merge" if op == "post" else "pre-merge")  # fmt: skip
    gate, host, tree, forge, prompt, said = _gate(
        ops_root, up=True, forge=FakeForge(state="MERGED")
    )
    tree.gate_pass_code = 2

    with pytest.raises(gate_mod.StageFailed) as failed:
        gate_mod.stage_6(gate)

    assert any("row rd (devops)" in line for line in said)
    why = str(failed.value)
    assert "acceptance set-status --id rd --status walked --walk" in why
    assert f"--feature {SPEC_SLUG}" in why and "--strategy live" in why


def test_stage_7_reports_the_tester_gates_rows_and_steps(ops_root: Path) -> None:
    _row_spec(ops_root)
    write_matrix(
        ops_root,
        [row(SPEC, rid="rd", status="walk-owed"), row(SPEC, rid="rt", status="walk-owed")],
    )
    (ops_root / SPEC).write_text(
        (ops_root / SPEC)
        .read_text()
        .replace("gate: rd=devops\n", "gate: rd=devops\n- rt: live — the tester walks it\n")
    )
    gate, host, tree, forge, _, said = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))

    gate_mod.stage_7(gate)

    assert any("row rt (tester)" in line for line in said)
    assert any("Test Plan step 2 (tester)" in line for line in said)
    assert not any("row rd" in line for line in said)


def test_stage_8_reports_a_held_archive_and_still_publishes(ops_root: Path) -> None:
    _record_stages(ops_root, 1, 2, 3, 4, 5, 6, 7)
    gate, host, tree, forge, _, said = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    real = tree.fr

    def held_archive(args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        if list(args)[:1] == ["archive"]:
            tree.calls.append(("fr", (list(args), terminal)))
            return 0, "  held: docs/superpowers/plans/p — phase 3 [manual] is unticked\n"
        return real(args, terminal=terminal)

    tree.fr = held_archive  # type: ignore[method-assign]
    audits: list[tuple[int, str]] = []
    real_finish = gate.finish
    gate.finish = lambda t, n, body, **k: (audits.append((n, body)), real_finish(t, n, body, **k))  # type: ignore[method-assign]

    gate_mod.stage_8(gate)

    assert any("archive held" in line for line in said)
    assert any("phase 3 [manual] is unticked" in line for line in said)
    ((n, body),) = audits
    assert n == 8 and "archive held" in body and "archived;" not in body
    assert ("pr_create", {"head": "chore/ops-p", "base": "main"}) in forge.calls


# ------------------------------------- phase 2 review: head-free row judgement (R12-R14)


B_WALK = {**A_WALK, "harness": "b", "at": "2026-10-22T09:30:00Z", "evidence": "head"}


def _head_fragment(ops_root: Path, rows: list[dict[str, Any]], rel: str = FRAGMENT) -> str:
    import yaml

    data = yaml.safe_load((ops_root / rel).read_text())
    data["rows"] = rows
    return yaml.safe_dump(data, sort_keys=False)


def test_p2_r1_a_head_written_walk_and_status_never_close_a_row(ops_root: Path) -> None:
    """The reviewer's case: a merged row owes b and has an old passing walk on a; the PR
    head adds a walk on b and sets `walked`. The stage still asks about it."""
    a_walk = {**A_WALK, "harness": "a"}
    _row_spec(ops_root, status="walked", harnesses=["a", "b"], walks=[a_walk, B_WALK])
    _record_stages(ops_root, 1, 2, 3, 4)
    gate, host, tree, forge, prompt, _ = _gate(
        ops_root, up=True, forge=FakeForge(state="MERGED"),
        prompt=FakePrompt(answers=["ran the step", "owed b is down"]),
    )  # fmt: skip
    head_row = {**row(SPEC, rid="rd", status="walked"), "harnesses": ["a", "b"],
                "walks": [B_WALK]}  # fmt: skip
    tree.head_files[FRAGMENT] = _head_fragment(ops_root, [head_row])

    gate_mod.stage_5(gate)

    assert any("rd" in q for q in prompt.asked[1:])
    assert len(_fr_calls(tree, "acceptance", "set-status")) == 1


def test_p2_r2_a_row_walked_only_by_the_head_is_asked_and_blocks_stage_6(
    ops_root: Path,
) -> None:
    """A row walked only by the PR head, named by an owed outcome later resolved fixed:
    stage 5 asks about it, and stage 6 refuses without running `fr gate pass`."""
    _row_spec(ops_root, "- [devops] (rows: rd) walk the stage", status="walked", walks=[A_WALK])
    jp = journal_path(ops_root, "spec", SPEC_SLUG)
    for e in (
        JournalEntry(kind="owed", scope="spec", id="test-plan-step-1",
                     created="2026-10-22T09:00:00+00:00", title="Test Plan step 1 owed",
                     body="why: later\nhow: later"),
        JournalEntry(kind="finding", scope="spec", id="test-plan-step-1-resolved",
                     created="2026-10-22T09:10:00+00:00", title="resolves", state="fixed",
                     resolves="test-plan-step-1", body="walked"),
    ):  # fmt: skip
        append_journal_entry(jp, SPEC_SLUG, e)
    for op in ("pre", "mut", "post"):
        record_op(ops_root, "p", op=op, result="done",
                  phase="post-merge" if op == "post" else "pre-merge")  # fmt: skip
    _record_stages(ops_root, 1, 2, 3, 4)
    gate, host, tree, forge, prompt, _ = _gate(
        ops_root, up=True, forge=FakeForge(state="MERGED"),
        prompt=FakePrompt(answers=["owed later"]),
    )  # fmt: skip
    tree.head_files[FRAGMENT] = (ops_root / FRAGMENT).read_text()

    gate_mod.stage_5(gate)
    assert any("rd" in q for q in prompt.asked)

    with pytest.raises(gate_mod.StageFailed) as failed:
        gate_mod.stage_6(gate)
    assert _gate_passes(tree) == []
    assert "row rd (devops)" in str(failed.value)
    assert "acceptance set-status --id rd" in str(failed.value)


def _second_fragment(ops_root: Path) -> str:
    """Move rd's fragment to another feature's file: rows citing the spec may live there."""
    import yaml

    rel = "docs/acceptance/features/2026-01-01-other.yaml"
    data = yaml.safe_load((ops_root / FRAGMENT).read_text())
    data["feature"] = "2026-01-01-other"
    (ops_root / rel).write_text(yaml.safe_dump(data, sort_keys=False))
    (ops_root / FRAGMENT).unlink()
    return rel


def test_p2_r3_head_walks_are_read_from_every_fragment_holding_a_judged_row(
    ops_root: Path,
) -> None:
    _row_spec(ops_root, status="walked", walks=[A_WALK])
    rel = _second_fragment(ops_root)
    _record_stages(ops_root, 1, 2, 3, 4)
    gate, host, tree, forge, prompt, _ = _gate(
        ops_root, up=True, forge=FakeForge(state="MERGED"),
        prompt=FakePrompt(answers=["ran the step", "ran the row"]),
    )  # fmt: skip
    tree.head_files[rel] = (ops_root / rel).read_text()

    gate_mod.stage_5(gate)

    assert len(_fr_calls(tree, "acceptance", "set-status")) == 1


def test_p2_r3_an_unreadable_head_fragment_is_a_refusal(ops_root: Path) -> None:
    _row_spec(ops_root)
    rel = _second_fragment(ops_root)
    _record_stages(ops_root, 1, 2, 3, 4)
    gate, host, tree, *_ = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    tree.head_files[rel] = "rows: [\n"

    with pytest.raises(gate_mod.StageFailed) as failed:
        gate_mod.stage_5(gate)
    assert failed.value.code == 2 and rel in str(failed.value)


def test_p2_r4_an_unreadable_section_fails_stage_6_with_its_message(ops_root: Path) -> None:
    _row_spec(ops_root)
    text = (ops_root / SPEC).read_text().replace("gate: developer", "gate: developer\ngate: tester")
    (ops_root / SPEC).write_text(text)
    _record_stages(ops_root, 1, 2, 3, 4, 5)
    gate, host, tree, *_ = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))

    with pytest.raises(gate_mod.StageFailed) as failed:
        gate_mod.stage_6(gate)
    assert "cannot be read" in str(failed.value)


def test_p2_r5_the_recovery_names_every_harness_a_row_still_owes(ops_root: Path) -> None:
    _row_spec(ops_root, harnesses=["a", "b"], walks=[{**A_WALK, "harness": "a"}])
    _record_stages(ops_root, 1, 2, 3, 4, 5)
    gate, host, tree, *_ = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))

    with pytest.raises(gate_mod.StageFailed) as failed:
        gate_mod.stage_6(gate)
    why = str(failed.value)
    assert "--harness b" in why and "--harness a " not in why


def test_p2_r6_stage_7s_tester_pass_names_the_run(ops_root: Path) -> None:
    _devops_only_spec(ops_root)
    gate, host, tree, *_ = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    tree.fr(["closeout", "outcome", "--run", "run-1", "--step", "1", "--ran"])

    gate_mod.stage_7(gate)

    (gp,) = _gate_passes(tree)
    assert gp[gp.index("--run") + 1] == "run-1"


# ------------------------------------------ ops-gate-truth R20: the final line reads the DoD


def _real_plan(ops_root: Path, *, manual: str | None = None) -> None:
    """The fixture plan as a real folder (`_meta.yaml`, a ticked phase 1, and optionally a
    `[manual]` phase 2 whose step is *manual*: " " unticked, "x" ticked)."""
    from tests.unit.test_run_dod import FIXTURE, MANUAL

    for name in ("_meta.yaml", "01.yaml"):
        shutil.copy(FIXTURE / name, ops_root / PLAN / name)
    phase = ops_root / PLAN / "01.yaml"
    phase.write_text(phase.read_text().replace('state: " "', "state: x"))
    if manual is not None:
        (ops_root / PLAN / "02.yaml").write_text(MANUAL.format(n=2, tick=manual))


def _all_recorded(ops_root: Path, tree: FakeTree) -> None:
    """Every op closed and both Test Plan steps recorded ran: only the plan can owe."""
    for op, phase in (("pre", "pre-merge"), ("mut", "pre-merge"), ("post", "post-merge")):
        record_op(ops_root, "p", op=op, result="done", phase=phase)
    for n in ("1", "2"):
        tree.fr(["closeout", "outcome", "--run", "run-1", "--step", n, "--ran"])


def test_r20_a_rerun_with_a_discharged_dod_says_the_stage_is_complete(ops_root: Path) -> None:
    _real_plan(ops_root, manual="x")
    _record_stages(ops_root, 1, 2, 3, 4, 5, 6, 7, 8)
    gate, host, tree, forge, _, said = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    _all_recorded(ops_root, tree)

    result = run(gate)

    assert result.ok and result.ran == ()
    assert "the DevOps stage is complete" in said, said
    assert not any("still owed" in line for line in said)


def test_r20_a_rerun_with_owed_items_lists_them_and_never_says_complete(ops_root: Path) -> None:
    _real_plan(ops_root)
    _record_stages(ops_root, 1, 2, 3, 4, 5, 6, 7, 8)
    gate, host, tree, forge, _, said = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))

    result = run(gate)

    assert result.ok and result.ran == ()
    assert "the DevOps stage is complete" not in said
    assert "every stage ran; still owed:" in said, said
    assert any(line.startswith("  gate:devops: Test Plan step 1 (devops)") for line in said)
    assert any(line.startswith("  gate:devops: op post [post-merge]") for line in said)


def test_r20_a_held_archive_leaves_its_manual_phase_owed_on_the_ran_path(ops_root: Path) -> None:
    _real_plan(ops_root, manual=" ")
    _record_stages(ops_root, 1, 2, 3, 4, 5, 6, 7)
    gate, host, tree, forge, _, said = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    _all_recorded(ops_root, tree)
    real = tree.fr

    def held_archive(args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        if list(args)[:1] == ["archive"]:
            return 0, "  held: docs/superpowers/plans/p — phase 2 [manual] is unticked\n"
        return real(args, terminal=terminal)

    tree.fr = held_archive  # type: ignore[method-assign]

    result = run(gate)

    assert result.ok and result.ran == (8,)
    assert "the DevOps stage is complete" not in said
    assert "every stage ran; still owed:" in said, said
    assert any(line.startswith("  manual phases: phase 2 [manual]: not ticked") for line in said)


def test_r20_an_unreadable_dod_never_says_complete(ops_root: Path) -> None:
    _record_stages(ops_root, 1, 2, 3, 4, 5, 6, 7, 8)  # the plan folder has no _meta.yaml
    gate, host, tree, forge, _, said = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))

    run(gate)

    assert "the DevOps stage is complete" not in said
    assert any("Definition of Done cannot be read" in line for line in said), said


def test_p3_r1_a_head_carried_owed_resolution_never_makes_the_stage_complete(
    ops_root: Path,
) -> None:
    _real_plan(ops_root, manual="x")
    _record_stages(ops_root, 1, 2, 3, 4, 5, 6, 7, 8)
    gate, host, tree, forge, _, said = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    _all_recorded(ops_root, tree)
    jp = journal_path(ops_root, "plan", "p")
    for entry in (
        JournalEntry(kind="owed", scope="plan", id="walk-the-dog",
                     created="2026-10-22T10:00:00+00:00", title="walk the dog",
                     body="what: w\nwhy: y\nhow: h\nowed_key: plan:p#p1"),
        JournalEntry(kind="finding", scope="plan", id="dog-walked", resolves="walk-the-dog",
                     state="fixed", created="2026-10-22T11:00:00+00:00", title="walked", body="b"),
    ):  # fmt: skip
        append_journal_entry(jp, "p", entry)
    tree.head_files[jp.relative_to(ops_root).as_posix()] = jp.read_text()  # the PR head wrote both

    run(gate)

    assert "the DevOps stage is complete" not in said
    assert any(line.startswith("  owed: owed walk-the-dog (plan journal)") for line in said), said


def test_p3_r1_a_manual_tick_the_head_carries_never_makes_the_stage_complete(
    ops_root: Path,
) -> None:
    _real_plan(ops_root, manual="x")
    _record_stages(ops_root, 1, 2, 3, 4, 5, 6, 7, 8)
    gate, host, tree, forge, _, said = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    _all_recorded(ops_root, tree)
    rel = f"{PLAN}/02.yaml"
    tree.head_files[rel] = (ops_root / rel).read_text()  # the tick arrived with the PR head

    run(gate)

    assert "the DevOps stage is complete" not in said
    assert any(line.startswith("  manual phases: phase 2 [manual]") for line in said), said


def test_p3_r1_a_manual_tick_made_on_the_ops_branch_counts(ops_root: Path) -> None:
    _real_plan(ops_root, manual="x")
    _record_stages(ops_root, 1, 2, 3, 4, 5, 6, 7, 8)
    gate, host, tree, forge, _, said = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    _all_recorded(ops_root, tree)
    from tests.unit.test_run_dod import MANUAL

    tree.head_files[f"{PLAN}/02.yaml"] = MANUAL.format(n=2, tick=" ")  # unticked on the head

    run(gate)

    assert "the DevOps stage is complete" in said, said
