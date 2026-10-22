"""`fr ops apply` (spec 2026-10-22-fr-ops R4, R11, R19): the engine over fakes, then the CLI."""

from __future__ import annotations

import os
import pty
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest
from fr.ops.apply import ALREADY_DONE, APPLIED_UNCHECKED, ApplyRefused, apply_ops
from fr.ops.engine import OrderError, order
from fr.ops.evidence import OpEvidence
from fr.ops.identity import IdentityError
from fr.ops.load import LoadedOp
from fr.ops.model import Op

SRC = Path("ops.yaml")


def lo(oid: str, **fields: object) -> LoadedOp:
    data: dict[str, object] = {"id": oid, "summary": f"do {oid}", "phase": "pre-merge"}
    data.update(fields)
    return LoadedOp(Op.model_validate(data), SRC, 1)  # type: ignore[arg-type]


class World:
    """A fake system: `done` ops pass their check; applying an op makes it done
    unless it is in `broken`. Records every command run."""

    def __init__(self, done: set[str] = frozenset(), broken: set[str] = frozenset()) -> None:  # type: ignore[assignment]
        self.done = set(done)
        self.broken = set(broken)
        self.ran: list[tuple[str, str, bool]] = []
        self.written: list[dict[str, object]] = []
        self.ready_ok = True

    def runner(self, command: str, env: Mapping[str, str]) -> tuple[int, str]:
        kind, _, oid = command.partition(":")
        if kind == "check":
            return (0, "") if oid in self.done else (1, f"{oid} is not done")
        if kind == "ready":
            return (0, "") if self.ready_ok else (1, "not live yet")
        return 1, ""

    def apply(self, op: LoadedOp, env: Mapping[str, str], interactive: bool) -> tuple[int, str]:
        self.ran.append((op.op.id, "apply", interactive))
        if op.op.id in self.broken:
            return 1, "boom"
        self.done.add(op.op.id)
        return 0, "ok"

    def record(self, **kw: object) -> None:
        self.written.append(kw)


class FakePrompt:
    def __init__(self, terminal: bool = True, answers: list[bool] | None = None) -> None:
        self.terminal = terminal
        self.answers = list(answers or [])
        self.asked: list[str] = []

    def has_terminal(self) -> bool:
        return self.terminal

    def confirm(self, text: str) -> bool:
        self.asked.append(text)
        return self.answers.pop(0) if self.answers else True


class NoJournal:
    def latest(self, op_id: str, *, runbook: bool) -> OpEvidence | None:
        return None


class Idents:
    def __call__(self, name: str) -> Mapping[str, str]:
        if name == "bad":
            raise IdentityError("identity 'bad': TOKEN could not be read (exit 1)")
        return {"TOKEN": f"secret-{name}"}


def run(ops: list[LoadedOp], world: World, prompt: FakePrompt | None = None, **kw: object):
    return apply_ops(
        ops,
        runner=world.runner,
        applier=world.apply,
        identities=Idents(),
        journal=NoJournal(),
        prompt=prompt or FakePrompt(),
        record=world.record,
        **kw,  # type: ignore[arg-type]
    )


def op(oid: str, **kw: object) -> LoadedOp:
    kw.setdefault("check", f"check:{oid}")
    kw.setdefault("apply", f"apply:{oid}")
    return lo(oid, **kw)


def test_order_is_dependency_order_and_a_cycle_is_refused_before_anything_runs() -> None:
    a, b = op("a", needs=["b"]), op("b")
    assert [x.op.id for x in order([a, b])] == ["b", "a"]
    w = World()
    cyc = [op("a", needs=["b"]), op("b", needs=["a"])]
    with pytest.raises(OrderError):
        order(cyc)
    assert w.ran == []


def test_done_ops_are_skipped_and_nothing_is_written() -> None:
    w = World(done={"a"})
    res = run([op("a")], w)
    assert res.ok and w.ran == [] and w.written == []
    assert "already done, nothing written" in res.steps[0].message


def test_na_ops_are_skipped() -> None:
    w = World()
    w.runner = lambda c, e: (0, "")  # type: ignore[method-assign]
    res = run([op("a", na_if="na:a")], w)
    assert res.ok and w.ran == [] and w.written == []
    assert ALREADY_DONE in res.steps[0].message


def test_apply_runs_in_order_and_records_the_recheck() -> None:
    w = World()
    res = run([op("a", needs=["b"]), op("b")], w, yes=True)
    assert res.ok
    assert [r[0] for r in w.ran] == ["b", "a"]
    assert [(r["op"], r["result"]) for r in w.written] == [("b", "done"), ("a", "done")]


def test_a_mutating_prompt_names_side_effects_and_undo() -> None:
    w = World()
    p = FakePrompt()
    run([op("m", mutating=True, side_effects=["drops the cache"], undo="restore-cache")], w, p)
    assert "drops the cache" in p.asked[0] and "restore-cache" in p.asked[0]


def test_an_undo_none_is_named_with_its_reason() -> None:
    w = World()
    p = FakePrompt()
    run([op("m", mutating=True, undo={"none": "irreversible"})], w, p)
    assert "irreversible" in p.asked[0]


def test_declining_stops_without_running() -> None:
    w = World()
    res = run([op("a"), op("b")], w, FakePrompt(answers=[False]))
    assert not res.ok and w.ran == [] and "declined" in res.steps[-1].message


def test_no_terminal_needs_yes_and_mutating_also_needs_yes_mutating() -> None:
    w = World()
    with pytest.raises(ApplyRefused, match="--yes"):
        run([op("a")], w, FakePrompt(terminal=False))
    assert w.ran == []
    with pytest.raises(ApplyRefused, match="--yes-mutating"):
        run([op("a", mutating=True)], w, FakePrompt(terminal=False), yes=True)
    assert w.ran == []
    assert run(
        [op("a", mutating=True)], w, FakePrompt(terminal=False), yes=True, yes_mutating=True
    ).ok


def test_stops_at_the_first_failure_naming_op_and_undo() -> None:
    w = World(broken={"a"})
    res = run([op("a", undo="revert-a"), op("b")], w, yes=True)
    assert not res.ok
    assert [r[0] for r in w.ran] == ["a"]
    assert "a" in res.steps[-1].message and "revert-a" in res.steps[-1].message
    assert w.written[0]["result"] == "failed"


def test_a_recheck_that_stays_open_is_recorded_open() -> None:
    w = World()
    w.apply = lambda o, e, i: (0, "ok")  # type: ignore[method-assign]
    res = apply_ops(
        [op("a")], runner=w.runner, applier=w.apply, identities=Idents(), journal=NoJournal(),
        prompt=FakePrompt(), record=w.record, yes=True,
    )  # fmt: skip
    assert not res.ok and w.written[0]["result"] == "open"


def test_a_second_run_over_a_done_phase_writes_nothing() -> None:
    w = World()
    run([op("a"), op("b")], w, yes=True)
    n = len(w.written)
    res = run([op("a"), op("b")], w, yes=True)
    assert res.ok and len(w.written) == n and all("nothing written" in s.message for s in res.steps)


def test_post_merge_op_with_failing_ready_is_refused() -> None:
    w = World()
    w.ready_ok = False
    res = run([op("a", phase="post-merge", ready="ready:a")], w, yes=True)
    assert not res.ok and w.ran == [] and "ready" in res.steps[-1].message


def test_post_merge_op_with_passing_ready_applies() -> None:
    w = World()
    assert run([op("a", phase="post-merge", ready="ready:a")], w, yes=True).ok


def test_a_pre_merge_op_ignores_ready() -> None:
    w = World()
    w.ready_ok = False
    assert run([op("a", ready="ready:a")], w, yes=True).ok


def test_an_op_without_apply_stops_and_says_do_it_by_hand() -> None:
    w = World()
    res = run([lo("ui", check="check:ui", commands=["click the button"])], w, yes=True)
    assert not res.ok and "no apply" in res.steps[-1].message


def test_identity_failure_names_the_identity_and_nothing_is_applied() -> None:
    w = World()
    res = run([op("a", identities=["bad"])], w, yes=True)
    assert not res.ok and w.ran == [] and "bad" in res.steps[-1].message


def test_apply_loops_over_identities_with_the_same_list_as_check() -> None:
    w = World()
    envs: list[Mapping[str, str]] = []

    def applier(o: LoadedOp, env: Mapping[str, str], interactive: bool) -> tuple[int, str]:
        envs.append(dict(env))
        w.done.add(o.op.id)
        return 0, "ok"

    res = apply_ops(
        [op("a", identities=["x", "y"])], runner=w.runner, applier=applier, identities=Idents(),
        journal=NoJournal(), prompt=FakePrompt(), record=w.record, yes=True,
    )  # fmt: skip
    assert res.ok and [e["TOKEN"] for e in envs] == ["secret-x", "secret-y"]


def test_apply_output_is_masked() -> None:
    w = World()

    def applier(o: LoadedOp, env: Mapping[str, str], interactive: bool) -> tuple[int, str]:
        return 1, f"denied for {env['TOKEN']}"

    res = apply_ops(
        [op("a", identities=["x"])], runner=w.runner, applier=applier, identities=Idents(),
        journal=NoJournal(), prompt=FakePrompt(), record=w.record, yes=True,
    )  # fmt: skip
    text = res.steps[-1].message + str(w.written)
    assert "secret-x" not in text and "***" in text


def test_an_interactive_op_needs_a_terminal_and_runs_attached() -> None:
    w = World()
    with pytest.raises(ApplyRefused, match="terminal"):
        run([op("i", interactive=True)], w, FakePrompt(terminal=False), yes=True)
    assert run([op("i", interactive=True)], w, FakePrompt(), yes=True).ok
    assert w.ran == [("i", "apply", True)]


def test_run_interactive_attaches_the_terminal_and_run_probe_does_not(tmp_path: Path) -> None:
    from fr.ops.probe import run_interactive, run_probe

    master, slave = pty.openpty()
    try:
        tty = os.ttyname(slave)
        assert run_interactive("test -t 0 && test -t 1", tmp_path, tty=tty) == 0
        run_interactive("echo hi-from-op", tmp_path, tty=tty)
        assert b"hi-from-op" in os.read(master, 1024)
        assert run_probe("test -t 0", tmp_path)[0] != 0
    finally:
        os.close(master)
        os.close(slave)
    assert run_interactive("true", tmp_path, tty=str(tmp_path / "nope")) == 127


def test_run_interactive_uses_the_minimal_env(tmp_path: Path, monkeypatch) -> None:
    from fr.ops.probe import run_interactive

    monkeypatch.setenv("LEAK_ME", "x")
    master, slave = pty.openpty()
    try:
        assert run_interactive('test -z "${LEAK_ME:-}"', tmp_path, tty=os.ttyname(slave)) == 0
    finally:
        os.close(master)
        os.close(slave)


class ScriptedPrompt(FakePrompt):
    """`has_terminal` answers from a script, then repeats the last answer."""

    def __init__(self, seq: list[bool], answers: list[bool] | None = None) -> None:
        super().__init__(True, answers)
        self.seq = list(seq)

    def has_terminal(self) -> bool:
        return self.seq.pop(0) if len(self.seq) > 1 else self.seq[0]


class RecordedJournal:
    """A journal port that answers from what `World.record` wrote (latest wins)."""

    def __init__(self, world: World) -> None:
        self.world = world

    def latest(self, op_id: str, *, runbook: bool) -> OpEvidence | None:
        rows = [w for w in self.world.written if w["op"] == op_id]
        if not rows:
            return None
        w = rows[-1]
        return OpEvidence(
            result=str(w["result"]),
            created="2026-10-22T10:00:00+00:00",
            reason=w.get("reason"),  # type: ignore[arg-type]
        )


def run_j(ops: list[LoadedOp], world: World, prompt: FakePrompt, **kw: object):
    return apply_ops(
        ops, runner=world.runner, applier=world.apply, identities=Idents(),
        journal=RecordedJournal(world), prompt=prompt, record=world.record, **kw,
    )  # type: ignore[arg-type]  # fmt: skip


def test_p2_r2_a_refusal_after_work_carries_what_already_ran() -> None:
    w = World()
    prompt = ScriptedPrompt([True, False])  # preflight skipped; b finds no terminal
    with pytest.raises(ApplyRefused) as e:
        run([op("a"), op("b", interactive=True, needs=["a"])], w, prompt, yes=True)
    assert e.value.result is not None and [s.op_id for s in e.value.result.steps] == ["a"]
    assert w.ran == [("a", "apply", False)]


def test_p2_r2_preflight_refuses_before_the_first_apply() -> None:
    w = World()
    with pytest.raises(ApplyRefused, match="--yes-mutating"):
        run([op("a"), op("b", mutating=True, needs=["a"])], w, FakePrompt(terminal=False), yes=True)
    assert w.ran == [] and w.written == []
    with pytest.raises(ApplyRefused, match="terminal"):
        run([op("a"), op("b", interactive=True)], w, FakePrompt(terminal=False), yes=True)
    assert w.ran == []


def test_p2_r3_an_apply_without_a_check_is_flagged_not_recorded_done() -> None:
    w = World()
    u = lo("u", apply="apply:u")
    res = run_j([u], w, FakePrompt(), yes=True)
    assert res.ok and res.needs_attestation == ["u"]
    assert w.written[0]["result"] == "open" and w.written[0]["reason"] == APPLIED_UNCHECKED
    assert res.steps[0].outcome == "needs-attestation"


def test_p2_r3_a_rerun_does_not_silently_reapply() -> None:
    w = World()
    u = lo("u", apply="apply:u")
    run_j([u], w, FakePrompt(), yes=True)
    res = run_j([u], w, FakePrompt(terminal=False), yes=True)
    assert len(w.ran) == 1 and res.needs_attestation == ["u"]
    assert "already applied" in res.steps[0].message
    p = FakePrompt(answers=[True])
    run_j([u], w, p, yes=True)
    assert "ALREADY APPLIED" in p.asked[0] and len(w.ran) == 2
    p2 = FakePrompt(answers=[False])
    run_j([u], w, p2, yes=True)
    assert len(w.ran) == 2


def test_p2_r6_yes_mutating_alone_does_not_confirm_a_mutating_op() -> None:
    w = World()
    with pytest.raises(ApplyRefused, match="--yes"):
        run([op("m", mutating=True)], w, FakePrompt(terminal=False), yes_mutating=True)
    assert w.ran == []
    p = FakePrompt()
    run([op("m", mutating=True)], w, p, yes_mutating=True)
    assert p.asked  # with a terminal it is still asked


def test_p2_r7_a_need_outside_the_selection_must_be_done() -> None:
    w = World()
    need = op("n", phase="pre-merge")
    with pytest.raises(ApplyRefused, match="'n'"):
        run([op("a", phase="post-merge", needs=["n"])], w, yes=True, outside=[need], known={"n"})
    assert w.ran == []
    w.done.add("n")
    assert run(
        [op("a", phase="post-merge", needs=["n"])], w, yes=True, outside=[need], known={"n"}
    ).ok


def test_p2_r13_the_applier_falls_back_to_stderr(tmp_path: Path) -> None:
    from fr.ops.apply import ShellApplier

    ap = ShellApplier(tmp_path)
    assert ap(lo("x", apply="echo oops >&2; exit 2"), {}, False) == (2, "oops")
    assert ap(lo("x", apply="echo out; echo err >&2; exit 2"), {}, False) == (2, "out")


# --- the CLI ------------------------------------------------------------------

from fr.cli import app  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

runner = CliRunner()
PLAN_REL = "docs/superpowers/plans/p"
OPS = """schema_version: 1
ops:
  - id: first
    summary: first
    phase: pre-merge
    check: 'test -f made-first'
    apply: 'touch made-first'
  - id: second
    summary: second
    phase: pre-merge
    needs: [first]
    check: 'test -f made-second'
    apply: 'touch made-second'
  - id: later
    summary: later
    phase: post-merge
    check: 'test -f made-later'
    apply: 'touch made-later'
"""


def marks(root: Path) -> Path:
    """Where the fixture ops leave their marks: outside the repo, because a probe that
    names a file inside it is hashed into the trust (and creating it would untrust)."""
    return root.parent / "marks"


def ops_text(root: Path, text: str = OPS) -> str:
    return text.replace("made-", f"{marks(root)}/made-")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("FR_OPS_TRUST_DIR", str(tmp_path / "trust"))
    root = tmp_path / "r"
    (root / PLAN_REL).mkdir(parents=True)
    (root / PLAN_REL / "ops.yaml").write_text(ops_text(root))
    (root / ".gitignore").write_text("made-*\n")
    _git(root, "init", "-q", "-b", "feat/x")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed")
    from fr.ops.load import load_ops, load_ops_config
    from fr.ops.trust import fingerprint, grant_trust, head_tree, tree_digest

    tree = head_tree(root)
    ops = load_ops(root / PLAN_REL, root).ops
    fp = fingerprint(ops, load_ops_config(root), root, code_tree=tree_digest(tree))
    grant_trust(root, "p", fp, tree=tree)
    marks(root).mkdir()
    monkeypatch.chdir(root)
    return root


@pytest.fixture()
def in_profile(monkeypatch):
    monkeypatch.setattr("fr.ops.profile.in_ops_profile", lambda *a, **k: True)


def _apply(*args: str):
    return runner.invoke(app, ["ops", "apply", *args, "--plan", PLAN_REL])


def test_cli_refuses_outside_an_ops_profile(repo: Path) -> None:
    res = _apply("--phase", "pre-merge", "--yes")
    assert res.exit_code == 2
    assert "fr isolation up --profile" in res.output and "chore/ops-p" in res.output
    assert not (marks(repo) / "made-first").exists()


def test_cli_apply_phase_twice_second_writes_nothing(repo: Path, in_profile) -> None:
    res = _apply("--phase", "pre-merge", "--yes")
    assert res.exit_code == 0, res.output
    assert (marks(repo) / "made-first").exists() and (marks(repo) / "made-second").exists()
    assert not (marks(repo) / "made-later").exists()
    journal = next((repo / "docs/superpowers/journals").rglob("*.md"))
    before = journal.read_bytes()
    res2 = _apply("--phase", "pre-merge", "--yes")
    assert res2.exit_code == 0, res2.output
    assert "already done, nothing written" in res2.output
    assert journal.read_bytes() == before


def test_cli_single_op_pulls_its_needs(repo: Path, in_profile) -> None:
    res = _apply("second", "--yes")
    assert res.exit_code == 0, res.output
    assert (marks(repo) / "made-first").exists() and (marks(repo) / "made-second").exists()


def test_cli_without_a_terminal_and_without_yes_refuses(repo: Path, in_profile) -> None:
    res = _apply("--phase", "pre-merge")
    assert res.exit_code == 2 and "--yes" in res.output
    assert not (marks(repo) / "made-first").exists()


def test_cli_apply_refuses_an_untrusted_op_set(repo: Path, in_profile) -> None:
    (repo / PLAN_REL / "ops.yaml").write_text(
        ops_text(repo, OPS.replace("touch made-first", "touch made-1st"))
    )
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "edit")
    res = _apply("--phase", "pre-merge", "--yes")
    assert res.exit_code == 2 and "fr ops trust" in res.output
    assert not (marks(repo) / "made-first").exists() and not (marks(repo) / "made-1st").exists()


def test_cli_a_cycle_is_refused_before_any_run(repo: Path, in_profile) -> None:
    ops = OPS.replace(
        "check: 'test -f made-first'", "needs: [second]\n    check: 'test -f made-first'"
    )
    (repo / PLAN_REL / "ops.yaml").write_text(ops)
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "cyc")
    from fr.ops.load import load_ops, load_ops_config
    from fr.ops.trust import fingerprint, grant_trust, head_tree, tree_digest

    tree = head_tree(repo)
    fp = fingerprint(
        load_ops(repo / PLAN_REL, repo).ops,
        load_ops_config(repo),
        repo,
        code_tree=tree_digest(tree),
    )
    grant_trust(repo, "p", fp, tree=tree)
    res = _apply("--phase", "pre-merge", "--yes")
    assert res.exit_code == 2 and "cycle" in res.output
    assert not (marks(repo) / "made-first").exists()


def test_cli_a_failing_apply_exits_1_and_names_the_op(repo: Path, in_profile) -> None:
    (repo / PLAN_REL / "ops.yaml").write_text(
        ops_text(repo, OPS.replace("touch made-first", "exit 3"))
    )
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "bad")
    from fr.ops.load import load_ops, load_ops_config
    from fr.ops.trust import fingerprint, grant_trust, head_tree, tree_digest

    tree = head_tree(repo)
    fp = fingerprint(
        load_ops(repo / PLAN_REL, repo).ops,
        load_ops_config(repo),
        repo,
        code_tree=tree_digest(tree),
    )
    grant_trust(repo, "p", fp, tree=tree)
    res = _apply("--phase", "pre-merge", "--yes")
    assert res.exit_code == 1 and "first" in res.output
    assert not (marks(repo) / "made-second").exists()


def test_p2_r1_an_unknown_op_is_refused_naming_it(repo: Path, in_profile) -> None:
    res = _apply("nope", "--yes")
    assert res.exit_code == 2 and "'nope'" in res.output
    res = _apply("first", "ghost", "--yes") if False else _apply("ghost", "--yes")
    assert res.exit_code == 2


def test_p2_r1_a_runbook_only_op_says_runbook(repo: Path, in_profile) -> None:
    (repo / ".fr").mkdir(exist_ok=True)
    (repo / ".fr/ops.yaml").write_text("runbook: book.yaml\n")
    (repo / "book.yaml").write_text(
        "- id: rb\n  summary: rb\n  phase: post-merge\n  commands: [x]\n"
    )
    res = _apply("rb", "--yes")
    assert res.exit_code == 2 and "--runbook" in res.output


def test_p2_r2_the_cli_prints_what_ran_before_a_refusal(
    repo: Path, in_profile, monkeypatch
) -> None:
    from fr.ops.apply import ApplyResult, ApplyStep

    res_ = ApplyResult([ApplyStep("first", "applied", "first: applied; DONE (checked)")])

    def boom(*a, **k):
        raise ApplyRefused("op 'second' is interactive and needs a terminal", res_)

    monkeypatch.setattr("fr.ops.apply.apply_ops", boom)
    res = _apply("--phase", "pre-merge", "--yes")
    assert res.exit_code == 2
    assert res.output.index("first: applied") < res.output.index("interactive")
