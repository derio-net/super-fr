"""Installed public CLI with real persistence and explicitly derived fake herdr state.

Wire keys come from recovery-capture and existing agent/process/screen captures.
No network, actual client, actual pane, user cache or real triage scope is used.
"""

from __future__ import annotations

import copy
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from fr.cli import app
from fr.commands import triage_batch_cmd as cmd
from fr.run.model import RunState, current_run_schema_version, dump_run_state
from fr.triage.batch import effective_handle, last_dispatch, save_batches
from fr.triage.model import Batch, DispatchEvent, Facts, Issue, load_judgements
from fr_herdr import managed, opencode, recovery, replacement
from fr_herdr.runner import HerdrRunner, agent_name
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[2] / "fixtures/herdr"
ITEM = "example/alpha/run/batch-fixture"
NAME = agent_name(ITEM)
PANE = "w1T:pNEW"
SESSION = "ses_fixture"
opencode.create_session = lambda model, checkout: SESSION
effects = []
timed_observations = []
started = False
fail_prompt = False
panes = json.loads((ROOT / "recovery-capture/pane-list.json").read_text())
tabs = json.loads((ROOT / "recovery-capture/tab-list.json").read_text())
screen = json.loads((ROOT / "opencode/final-idle.json").read_text())


def herdr(argv, *, timeout=None):
    global started
    if timeout is not None:
        assert 0 < timeout <= 30
        assert argv[:2] in (["agent", "list"], ["pane", "process-info"], ["pane", "read"])
        timed_observations.append((argv[:2], timeout))
    if argv[:2] == ["pane", "list"]:
        return copy.deepcopy(panes)
    if argv[:2] == ["tab", "list"]:
        return copy.deepcopy(tabs)
    if argv[:2] == ["agent", "list"]:
        return {
            "result": {
                "agents": []
                if not started
                else [
                    {
                        "pane_id": PANE,
                        "tab_id": "w1T:tNEW",
                        "name": NAME,
                        "agent": "opencode",
                        "agent_status": "done",
                        "interactive_ready": True,
                        "agent_session": {
                            "agent": "opencode",
                            "kind": "id",
                            "value": SESSION,
                        },
                    }
                ]
            }
        }
    if argv[:2] == ["tab", "create"]:
        intent = recovery.load_intent(ITEM, effective_handle(load_judgements(path).batches[0]))
        assert intent and intent.checkpoint == "allocation-pending"
        effects.append("allocate")
        pane = copy.deepcopy(panes["result"]["panes"][-2])
        pane.update(pane_id=PANE, tab_id="w1T:tNEW")
        tab = copy.deepcopy(tabs["result"]["tabs"][-2])
        tab.update(tab_id="w1T:tNEW", label=ITEM)
        panes["result"]["panes"].append(pane)
        tabs["result"]["tabs"].append(tab)
        return {"result": {"root_pane": pane, "tab": tab}}
    if argv[:2] == ["agent", "start"]:
        assert argv[2] == NAME and "--auto" in argv
        assert argv[argv.index("--session") + 1] == SESSION
        effects.append("launch")
        started = True
        return {}
    if argv[:2] == ["agent", "prompt"]:
        assert argv[3].startswith("HOLD") and "acknowledge/report" in argv[3]
        assert "claim --abandoned" not in argv[3] and "fr run advance" not in argv[3]
        effects.append("prompt")
        if fail_prompt:
            raise managed.ManagedError("synthetic uncertain submission")
        return {}
    if argv[:2] == ["pane", "process-info"]:
        return {
            "result": {
                "process_info": {
                    "foreground_processes": [
                        {
                            "argv": ["opencode", "--session", SESSION, "--auto"],
                            "pid": 5,
                            "cwd": str(Path.cwd()),
                        }
                    ]
                }
            }
        }
    if argv[:2] == ["pane", "read"]:
        return screen
    raise AssertionError(argv)


def git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True)


git(
    "-c",
    "user.name=scenario",
    "-c",
    "user.email=scenario@example.invalid",
    "commit",
    "--allow-empty",
    "-m",
    "fixture",
)
git("checkout", "-b", "feat/fixture")
runs = Path("docs/superpowers/runs")
runs.mkdir(parents=True)
cursor = runs / "fixture.yaml"
cursor.write_text(
    dump_run_state(
        RunState(
            schema_version=current_run_schema_version(),
            run="fixture",
            workflow="fr-goal@1",
            branch="feat/fixture",
            started="2026-10-14T00:00:00Z",
            cursor="brainstorm",
            steps={"brainstorm": {"state": "running"}},
        )
    )
)
Path("dirty.txt").write_text("preserve this uncommitted work")
state = Path("state")
state.mkdir()
path = state / "judgements.yaml"
path.write_text("schema: 2\ntiers: [{n: 1, title: Now}]\nissues:\n  alpha#1: {tier: 1}\n")
original = DispatchEvent(
    kind="dispatch",
    at=datetime(2026, 10, 9, tzinfo=UTC),
    runner="herdr",
    handle="closed",
    branch="feat/fixture",
    reserved_version="6.0.0",
)
batch = Batch(
    id="fixture",
    title="fixture",
    ids=["alpha#1"],
    launch={"runner": "herdr", "harness": "opencode", "model": "openai/fixture"},
    events=[original],
)
save_batches(path, [batch], read=[])
facts = Facts(
    scope="example--alpha",
    kind="repo",
    collected_at="2026-10-10T00:00:00Z",
    repos=["example/alpha"],
    issues=[
        Issue(
            repo="example/alpha",
            number=1,
            title="fixture",
            state="open",
            url="https://github.com/example/alpha/issues/1",
        )
    ],
)
(state / "facts.json").write_text(json.dumps(facts.to_json()))


class Checkout:
    path = Path.cwd()

    def main_worktree(self):
        return self.path


class Forge:
    def list_prs_by_head(self, *args):
        return []


cmd._open_checkout = lambda *a: Checkout()
cmd.make_client = lambda *a: Forge()
cmd.load_runner = lambda *a: HerdrRunner()
recovery._run_herdr = herdr
replacement._run_herdr = herdr
args = [
    "triage",
    "batch",
    "replace",
    "fixture",
    "--repo",
    "example/alpha",
    "--dir",
    str(state.resolve()),
    "--checkout",
    str(Path.cwd()),
    "--reason",
    "disposable fixture",
]
recover_args = ["--recover", "--harness", "opencode", "--model", "openai/fixture"]


def invoke(extra, code=0):
    result = CliRunner().invoke(app, [*args, *extra])
    assert result.exit_code == code, (result.output, result.exception)
    return result


before, cursor_before = path.read_bytes(), cursor.read_bytes()
invoke(recover_args)
assert path.read_bytes() == before and effects == []
assert not list(managed.cache_dir().glob("*.json"))
invoke(["--recover", "--repair"], 2)
invoke(["--recover", "--model", "openai/fixture"], 2)
old_label = tabs["result"]["tabs"][-2]["label"]
tabs["result"]["tabs"][-2]["label"] = ITEM
invoke([*recover_args, "--yes"], 2)
assert effects == [] and path.read_bytes() == before
tabs["result"]["tabs"][-2]["label"] = old_label

# Batch outcome write failure: actual durable uptake exists, but owner is not yet effective.
save = cmd.save_batches


def fail_outcome(path, batches, **kw):
    if batches[0].events[-1].kind == "replacement" and batches[0].events[-1].result == "success":
        raise OSError("synthetic outcome disk failure")
    return save(path, batches, **kw)


cmd.save_batches = fail_outcome
failed = invoke([*recover_args, "--yes"], 1)
assert effective_handle(load_judgements(path).batches[0]) == "closed"
assert managed.load(PANE).checkpoint == "uptake-confirmed", (
    failed.output,
    effects,
    managed.load(PANE),
)
cmd.save_batches = save
before_effects = list(effects)
before_observations = list(timed_observations)
invoke(["--repair", "--yes"])
assert effects == before_effects == ["allocate", "launch", "prompt"]
assert timed_observations == before_observations
assert [args for args, _ in timed_observations] == [
    ["agent", "list"],
    ["pane", "process-info"],
    ["pane", "read"],
]
final = load_judgements(path).batches[0]
assert last_dispatch(final) == original and effective_handle(final) == PANE
assert managed.load(PANE).recovery_hold and managed.load(PANE).checkpoint == "active"
assert final.events[-1].session == "ses_fixture"
assert (
    cursor.read_bytes() == cursor_before
    and Path("dirty.txt").read_text() == "preserve this uncommitted work"
)
invoke([*recover_args, "--yes"], 2)
assert effects == before_effects

# A second EXPLICIT act after fake source closure: batch success precedes intent activation.
old_pane = PANE
panes["result"]["panes"] = [p for p in panes["result"]["panes"] if p["pane_id"] != old_pane]
tabs["result"]["tabs"] = [t for t in tabs["result"]["tabs"] if t["label"] != ITEM]
started = False
PANE, SESSION = "w1T:pNEW2", "ses_fixture2"
save_intent = recovery.save_intent


def fail_activation(intent):
    if intent.checkpoint == "active":
        raise OSError("synthetic activation disk failure")
    save_intent(intent)


recovery.save_intent = fail_activation
invoke([*recover_args, "--yes"], 1)
assert effective_handle(load_judgements(path).batches[0]) == PANE
assert managed.load(PANE).checkpoint == "active"
assert HerdrRunner().replacement_pending(ITEM, PANE).pane == old_pane
recovery.save_intent = save_intent
before_effects = list(effects)
invoke(["--repair", "--yes"])
assert effects == before_effects == ["allocate", "launch", "prompt"] * 2
assert recovery.load_intent(ITEM, old_pane).checkpoint == "active"
assert last_dispatch(load_judgements(path).batches[0]) == original
assert [args for args, _ in timed_observations] == [
    ["agent", "list"],
    ["pane", "process-info"],
    ["pane", "read"],
] * 2
for offset in (0, 3):
    budgets = [timeout for _, timeout in timed_observations[offset : offset + 3]]
    assert budgets == sorted(budgets, reverse=True)
print(
    "installed recovery: preview, refusal, same-model, cross-store repair, "
    "immutable lifecycle and HOLD passed"
)
