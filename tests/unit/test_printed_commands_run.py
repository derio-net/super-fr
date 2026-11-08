"""Every `fr` command the gate and backfill flows print runs as printed (spec 2026-11-08 R6)."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.commands import gate_cmd
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.gatebackfill_fixtures import ME, STRANGER, commit_at, row, write_matrix
from tests.unit.test_merge_evidence import _write_plan

REPO = "example-org/widgets"
PLAN = "2026-10-20-ops"
SPEC = "2026-10-20-widget"
SPEC_FILE = "docs/superpowers/specs/2026-10-20-widget-design.md"


def _fixture_repo(tmp_path: Path) -> Path:
    """One repo holding each owed key kind: a row, a plan phase, a spec step, a journal key."""
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path, owed_body

    root = tmp_path / "widgets"
    root.mkdir()
    for args in (
        ["init", "-q", "-b", "main"],
        ["remote", "add", "origin", f"https://github.com/{REPO}.git"],
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    write_matrix(
        root,
        [row(i, "walk-owed") for i in ("r-live", "r-journal", "r-na", "r-adopt")]
        + [row("r-later", "not-implemented", verify="live")],
    )
    spec = root / SPEC_FILE
    spec.parent.mkdir(parents=True)
    spec.write_text("# Widget\n\n## Test Plan\n\n1. step one\n2. step two\n")
    _write_plan(root, PLAN, [("manual", False), ("manual", False), ("manual", False)])
    entry = JournalEntry(
        kind="owed", scope="spec", id="owed-1", created="2026-10-11T10:00:00+00:00",
        title="owed", body=owed_body(what="w", why="y", how="h", key="row:r-journal"),
    )  # fmt: skip
    append_journal_entry(journal_path(root, "spec", "some-slug"), "some-slug", entry)
    commit_at(root, "seed", "2026-10-30T00:00:00+00:00")
    return root


# --- extraction ---------------------------------------------------------------------------

_FR_VERBS = ("acceptance", "plan", "journal", "closeout", "gate", "ops")
_START = re.compile(r"(?<![\w/.\-])fr (?:" + "|".join(_FR_VERBS) + r") ")
_PLACEHOLDER = re.compile(r"<[^<>]+>")
_FLAG_VALUES = {
    "--walk": "walk.log", "--harness": "claude-code", "--model": "model-x",
    "--strategy": "live", "--notes": "ran it", "--note": "ran it", "--evidence": "ran it",
    "--reason": "not applicable", "--id": "r-live", "--spec": SPEC_FILE,
}  # fmt: skip


def extract_commands(text: str) -> list[str]:
    """Every `fr <verb> ...` in *text*: on its own line, inside a backtick span, or inline after
    a colon, ending at the end of the line, the closing backtick or a `;` outside quotes."""
    out = []
    for line in text.splitlines():
        for m in _START.finditer(line):
            rest = line[m.start() :]
            tick = line.count("`", 0, m.start()) % 2 == 1
            if tick:
                rest = rest.split("`", 1)[0]
            lex = shlex.shlex(rest, posix=True, punctuation_chars=";")
            lex.whitespace_split = True
            toks = []
            for tok in lex:
                if tok == ";":
                    break
                toks.append(tok)
            if any(t.endswith(":") for t in toks[1:3]):
                continue  # an error prefix (`fr gate backfill: ...`), not a command
            out.append(shlex.join(toks))
    return out


def fill(command: str) -> list[str]:
    """argv of *command* with every `<placeholder>` replaced by a value valid for its flag."""
    argv, prev = [], ""
    for tok in shlex.split(command):
        if _PLACEHOLDER.search(tok):
            tok = _PLACEHOLDER.sub(_FLAG_VALUES.get(prev, "ran it"), tok)
        argv.append(tok)
        prev = tok
    return argv


# --- the world ----------------------------------------------------------------------------


class World:
    """The fixture repo, the faked forge, and a runner that executes a printed command in a
    throwaway copy of the repo, so no command sees another's writes."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp = tmp_path
        self.root = _fixture_repo(tmp_path)
        self.fake = FakeGhClient()
        self.fake.comment_author = ME
        monkeypatch.setattr(gate_cmd, "client_for_url", lambda url: self.fake)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.chdir(self.root)
        self.plan_file = tmp_path / "home/.cache/fr/gate-backfill/example-org--widgets/plan.yaml"
        self.seen: dict[str, str] = {}  # command -> where it was printed
        self._n = 0

    def invoke(self, *args: str) -> Any:
        return CliRunner().invoke(app, list(args))

    def collect(self, where: str, text: str) -> None:
        for cmd in extract_commands(text):
            self.seen.setdefault(cmd, where)

    def run_all(self) -> list[str]:
        """Run every collected `fr` command (`--yes` stripped); the failures, as text."""
        failures = []
        here = Path.cwd()
        for cmd, where in self.seen.items():
            argv = [a for a in fill(cmd)[1:] if a != "--yes"]
            self._n += 1
            copy = self.tmp / f"copy{self._n}"
            shutil.copytree(self.root, copy)
            os.chdir(copy)
            try:
                result = CliRunner().invoke(app, argv)
            finally:
                os.chdir(here)
            if result.exit_code != 0:
                failures.append(f"[{where}] {cmd}\n    exit {result.exit_code}: {result.output}")
        return failures


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    return World(tmp_path, monkeypatch)


def _manifest(w: World) -> Path:
    keys = [
        ("row:r-live", "tester"), ("row:r-journal", "tester"), ("row:r-na", "tester"),
        ("row:r-adopt", "tester"),
        (f"plan:{PLAN}#p1", "devops"), (f"plan:{PLAN}#p2", "devops"), (f"plan:{PLAN}#p3", "devops"),
        (f"spec:{SPEC}#step1", "tester"), (f"spec:{SPEC}#step2", "tester"),
    ]  # fmt: skip
    items: list[dict[str, Any]] = [
        {"key": k, "pr": 12, "gate": g}
        | ({} if k.startswith("row:") else {"kind": "audit-gap", "title": k})
        for k, g in keys
    ]
    path = w.tmp / "m.yaml"
    path.write_text(yaml.safe_dump({"schema": 1, "items": items}))
    return path


def _decide(w: World, decisions: dict[str, tuple[str, str]]) -> None:
    data = yaml.safe_load(w.plan_file.read_text())
    for e in data["entries"]:
        if e["key"] in decisions:
            e["decision"], e["note"] = decisions[e["key"]]
    w.plan_file.write_text(yaml.safe_dump(data))


def test_every_command_the_gate_and_backfill_flows_print_runs(world: World) -> None:
    w = world
    w.fake.add_pr(REPO, 12, state="MERGED", head_ref="feat/x", labels=[])
    w.fake.add_issue(REPO, 5, labels={"fr:owed"}, body="filed by hand")
    w.fake.issue_authors[(REPO, 5)] = STRANGER
    manifest = _manifest(w)
    backfill = ["gate", "backfill", "--from", str(manifest)]

    # 1. the dry-run block and its refusal hints
    first = w.invoke(*backfill)
    assert first.exit_code == 0, first.output
    w.collect("first dry run", first.output)
    _decide(w, {
        "row:r-na": ("na", "manual by nature"),
        f"plan:{PLAN}#p1": ("tick", ""),
        f"plan:{PLAN}#p2": ("na", "not needed"),
        f"spec:{SPEC}#step1": ("na", "not needed"),
        f"spec:{SPEC}#step2": ("tick", ""),
    })  # fmt: skip
    refused = w.invoke(*backfill)
    assert refused.exit_code == 2 and "record it ran: fr closeout" in refused.output
    w.collect("dry-run", refused.output)

    # 2. the --yes report, the tracker bodies and the adopt comment
    _decide(w, {f"spec:{SPEC}#step2": ("owed", ""), "row:r-adopt": (f"adopt {REPO}#5", "")})
    applied = w.invoke(*backfill, "--yes")
    assert applied.exit_code == 0, applied.output
    w.collect("--yes report", applied.output)
    for (_, number), issue in w.fake.issues.items():
        w.collect(f"tracker #{number} body", issue.body)
    for (_, number), comments in w.fake.issue_comments.items():
        for c in comments:
            w.collect(f"comment on #{number}", c["body"])
    again = w.invoke(*backfill)
    w.collect("dry-run after --yes", again.output)

    # 3. `fr gate pass`: the dry run, then a pass whose first tracker close fails (the retry line)
    pass_args = ["gate", "pass", "--repo", REPO, "--pr", "12", "--gate", "tester", "--notes", "ok"]
    dry = w.invoke(*pass_args)
    assert dry.exit_code == 0, dry.output
    w.collect("gate pass", dry.output)
    [adopted_close] = [
        ln.strip() for ln in dry.output.splitlines() if ln.strip().startswith("gh issue close")
    ]
    close_argv = shlex.split(adopted_close)  # `gh` is not fr's to execute: shape-checked only
    assert close_argv[:6] == ["gh", "issue", "close", "5", "--repo", REPO]
    assert close_argv[6] == "--comment" and len(close_argv) == 8
    dev = ["gate", "pass", "--repo", REPO, "--pr", "12", "--gate", "devops", "--notes", "ok"]
    w.collect("gate pass devops", w.invoke(*dev, "--no-run-evidence").output)
    w.fake.fail_on_mutation = w.fake.attempted_mutations + 3
    failed = w.invoke(*pass_args, "--yes")
    assert "to retry the close" in failed.output, failed.output
    w.collect("gate pass retry", failed.output)
    w.fake.fail_on_mutation = None
    retried = w.invoke(*pass_args, "--yes")
    w.collect("gate pass after retry", retried.output)

    assert len(w.seen) >= 8, sorted(w.seen)
    failures = w.run_all()
    assert not failures, "\n".join(f[:400] for f in failures)


# --- the guard against a new emitter ------------------------------------------------------

EMITTERS = (
    "packages/fr/src/fr/gatebackfill/render.py",
    "packages/fr/src/fr/gatebackfill/trackers.py",
    "packages/fr/src/fr/gatebackfill/close.py",
    "packages/fr/src/fr/commands/gate_cmd.py",
)
# Every `fr <verb>` these modules mention. The executing test above covers the ones that print
# a command; a literal added here must be reached by that test (a fixture and a flow) first.
COVERED_VERBS = {
    "fr acceptance set-status",
    "fr closeout outcome",
    "fr gate",  # prose: `fr gate backfill` / `fr gate pass` are named below
    "fr gate backfill",
    "fr gate pass",
    "fr journal resolve",
    "fr ops gate",  # named in a refusal, not printed as a command to run
    "fr plan edit",
}


def test_a_new_fr_command_literal_in_an_emitter_must_be_covered() -> None:
    from fr.cli import app
    from typer.main import get_command

    tops = "|".join(sorted(get_command(app).commands))  # type: ignore[attr-defined]
    pattern = re.compile(rf"(?<![\w/.\-])fr ((?:{tops})(?: [a-z][a-z-]*)?)")
    repo = Path(__file__).resolve().parents[2]
    found = {
        f"fr {m.group(1)}" for rel in EMITTERS for m in pattern.finditer((repo / rel).read_text())
    }
    assert found <= COVERED_VERBS, (
        f"new `fr` command literal(s) {sorted(found - COVERED_VERBS)} in an emitter: extend "
        "test_every_command_the_gate_and_backfill_flows_print_runs to reach them, then add them "
        "to COVERED_VERBS"
    )
