"""`fr ops gate` — the DevOps stage's sequencer (spec 2026-10-22-fr-ops R15, §I).

Every port is a fake: the host (`fr isolation up/exec/verify-merge`), the ops workspace
(git and this `fr` there), the forge and the operator's terminal. The ops workspace's
files are real, so the ledger, the op evidence and the Test Plan are the real readers.
"""

from __future__ import annotations

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
from fr.ops.gate import Gate, GateTarget, HostGateState, JournalLedger, preview, run
from fr.run.model import RunState, StepRecord, save_run_state

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
            entry = JournalEntry(
                kind=kind,
                scope="spec",
                id=sid,
                created="2026-10-22T10:00:00+00:00",
                title=f"step {n}",
                body="x" if kind == "discovery" else "why: later\nhow: later",
            )
            append_journal_entry(journal_path(self.path, "spec", SPEC_SLUG), SPEC_SLUG, entry)
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

    def commit_paths(self, paths: list[str], message: str) -> str | None:
        self.calls.append(("commit", message))
        return "c" * 40

    def rebase_onto(self, new_base: str, upstream: str) -> None:
        self.calls.append(("rebase", (new_base, upstream)))
        if self.rebase_error:
            raise RuntimeError(self.rebase_error)

    def push(self, branch: str, lease: str | None = None) -> None:
        self.calls.append(("push", branch))
        self.leases.append(lease)
        if self.push_error:
            raise RuntimeError(self.push_error)


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
        self.how: dict[str, str] = {}
        self.materialised: list[Path] = []
        # `fr ops status <id> --json`, scripted per op: each call pops (exit, rows | text)
        self.by_id: dict[str, list[tuple[int, Any]]] = {}

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
    def __init__(self, *, state: str = "OPEN", unsupported: bool = False) -> None:
        self.pr = {"state": state, "head_oid": HEAD, "head_ref": "feat/x", "base_ref": "main",
                   "labels": ["gate:devops", "gate:tester"]}  # fmt: skip
        self.required: list[dict[str, Any]] = [{"name": "ci", "bucket": "pass"}]
        self.calls: list[tuple[str, Any]] = []
        self.unsupported = unsupported
        self.open_prs: dict[str, int] = {}
        self.default = "main"

    def default_branch(self, *, cwd: Path, run: Any = None) -> str | None:
        return self.default

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        assert (repo, number) == (REPO, 5)
        return dict(self.pr)

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        return list(self.required)

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        return list(self.required)

    def repo_merge_methods(self, repo: str) -> dict[str, Any]:
        return {"default": "squash", "allowed": ["squash"]}

    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        if self.unsupported:
            raise UnsupportedForgeOperation("pr_merge", "gitlab")
        self.calls.append(("merge", (number, head_sha, method)))
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
    forge = forge or FakeForge()
    prompt = prompt or FakePrompt()
    said: list[str] = []
    target = GateTarget(run=_state(), repo=REPO, pr=5, plan_rel=PLAN, profile="ops",
                        primary=PRIMARY)  # fmt: skip
    if up:  # a workspace stage 1 cut from the verified head (p4-r5)
        _host(ops_root).set_cut(HEAD)
    gate = Gate(target, host, forge, prompt, said.append, _host(ops_root))
    return gate, host, tree, forge, prompt, said


def _host(root: Path) -> HostGateState:
    """The operator's host-side stage state, outside the ops workspace (p4-gate-state)."""
    return HostGateState(root.parent / "gate-state" / "run-1.json")


def _record_stages(root: Path, *ns: int, head: str = HEAD) -> None:
    for n in ns:
        _host(root).mark(n, head=head if n == 1 else None)


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
    _record_stages(ops_root, 1, 2)
    gate, *_ = _gate(ops_root, up=True)
    text = "\n".join(preview(gate))
    assert "[done] 1." in text and "[done] 2." in text and "[next] 3." in text


# ----------------------------------------------------------------------- the full run


def test_a_full_run_walks_every_stage_in_order(ops_root: Path) -> None:
    gate, host, tree, forge, prompt, said = _gate(ops_root)
    result = run(gate)
    assert result.ok, said
    assert result.ran == (1, 2, 3, 4, 5, 6, 7, 8)
    assert _host(ops_root).stages() == set(range(1, 9))

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
    # stage 2: its own confirmation names the PR, the head sha and the pre-merge state
    merge_q = next(a for a in prompt.asked if a.startswith("MERGE"))
    assert "#5" in merge_q and HEAD in merge_q and "pre-merge state" in merge_q
    assert ("merge", (5, HEAD, "squash")) in forge.calls
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
    for n in range(1, 9):
        assert any(f"DevOps stage {n}" in m for m in commits), commits


# --------------------------------------------------------------------- the merge


def test_the_merge_refuses_while_a_pre_merge_op_is_open(ops_root: Path) -> None:
    _record_stages(ops_root, 1)  # recorded, but no op evidence closes them
    gate, host, tree, forge, prompt, _ = _gate(ops_root, up=True)
    result = run(gate)
    assert result.failed == 2 and "pre-merge ops are still open" in result.why
    assert not [c for c in forge.calls if c[0] == "merge"]
    assert not any(a.startswith("MERGE") for a in prompt.asked)


def test_the_merge_refuses_on_red_required_checks(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    forge = FakeForge()
    forge.required = [{"name": "ci", "bucket": "fail"}]
    gate, *_ = _gate(ops_root, up=True, live_closed=True, forge=forge)
    result = run(gate)
    assert result.failed == 2 and "failing" in result.why and "ci" in result.why
    assert not [c for c in forge.calls if c[0] == "merge"]


def test_a_declined_merge_merges_nothing(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, host, tree, forge, prompt, _ = _gate(
        ops_root, up=True, live_closed=True, prompt=FakePrompt([False])
    )
    result = run(gate)
    assert result.failed == 2 and "not confirmed" in result.why
    assert not [c for c in forge.calls if c[0] == "merge"]
    assert 2 not in _host(ops_root).stages()


def test_a_non_github_forge_names_the_manual_merge(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, *_ = _gate(ops_root, up=True, live_closed=True, forge=FakeForge(unsupported=True))
    result = run(gate)
    assert result.failed == 2
    assert "by hand" in result.why and "#5" in result.why and HEAD in result.why


def test_a_forge_merged_pr_counts_as_stage_2_done(ops_root: Path) -> None:
    _record_stages(ops_root, 1)
    gate, host, tree, forge, prompt, _ = _gate(ops_root, up=True, forge=FakeForge(state="MERGED"))
    result = run(gate)
    assert result.ok and 2 not in result.ran and result.ran[0] == 3
    assert not any(a.startswith("MERGE") for a in prompt.asked)
    assert not [c for c in forge.calls if c[0] == "merge"]


# ------------------------------------------------------------- resume and failure


def test_a_rerun_resumes_at_the_first_unrecorded_stage(ops_root: Path) -> None:
    _record_stages(ops_root, 1, 2, 3)
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
    assert _host(ops_root).stages() == {1, 2, 3}
    host.fail_apply = set()
    gate2 = Gate(gate.target, host, forge, FakePrompt(), [].append, _host(ops_root))
    second = run(gate2)
    assert second.ok and second.ran == (4, 5, 6, 7, 8)
    assert len([c for c in forge.calls if c[0] == "merge"]) == 1


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
    assert not [c for c in forge.calls if c[0] == "merge"]
    assert not any(a.startswith("MERGE") for a in prompt.asked)


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
    assert ("merge", (5, HEAD, "squash")) in forge.calls
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
    assert ("merge", (5, HEAD, "squash")) in forge.calls


def test_a_malformed_recorded_sha_is_refused(ops_root: Path) -> None:
    path = ops_root.parent / "gate-state" / "run-1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"stages": [1], "head": "--exec=x"}))
    for op in ("pre", "mut"):
        record_op(ops_root, "p", op=op, result="done", phase="pre-merge")
    gate, host, tree, forge, *_ = _gate(ops_root, up=True, live_closed=True)
    result = run(gate)
    assert result.failed == 2 and result.code == 2 and "sha" in result.why
    assert not [c for c in forge.calls if c[0] == "merge"]


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
