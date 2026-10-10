"""SYNTHETIC operation inputs; only screens replay real captured observations.

Runs the candidate's installed Typer CLI, batch writer, optional protocol and real
herdr subprocess seam. A synthetic forge adapter avoids all production forge I/O.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from fr_herdr.runner import agent_name

ITEM = "example/alpha/run/batch-scenario"
NAME = agent_name(ITEM)
PANE = "w1:p1"
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/herdr"


def pane(args):
    path = Path(os.environ["HERDR_REPLACE_STATE"])
    data = json.loads(path.read_text())
    with Path(os.environ["HERDR_REPLACE_LOG"]).open("a") as log:
        log.write(json.dumps(args) + "\n")
    if args[:2] == ["agent", "list"]:
        return {
            "result": {
                "agents": []
                if data["shell"]
                else [
                    {
                        "pane_id": PANE,
                        "name": NAME,
                        "agent": data["harness"],
                        "agent_status": "done",
                        "interactive_ready": True,
                    }
                ]
            }
        }
    if args[:2] == ["pane", "process-info"]:
        proc = {
            "argv": [data["harness"], *data.get("args", ["--model", data["model"]])],
            "pid": 2,
            "cwd": str(Path.cwd()),
        }
        if data["shell"]:
            proc = {"argv": ["zsh"], "pid": 1, "cwd": str(Path.cwd())}
        return {"result": {"process_info": {"shell_pid": 1, "foreground_processes": [proc]}}}
    if args[:2] == ["pane", "read"]:
        file = (
            "opencode/final-idle.json"
            if data["harness"] == "opencode"
            else "restart/screen-empty.json"
        )
        return json.loads((FIXTURES / file).read_text())
    if args[:2] == ["pane", "send-keys"]:
        data["shell"] = True
    if args[:2] == ["agent", "start"]:
        if os.environ.get("HERDR_REPLACE_FAIL"):
            print(
                json.dumps(
                    {
                        "error": {
                            "code": "synthetic_start_failure",
                            "message": "injected startup failure",
                        }
                    }
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        assert args[2] == NAME and args[args.index("--pane") + 1] == PANE
        assert "--resume" not in args
        harness = args[args.index("--kind") + 1]
        harness_args = args[args.index("--") + 1 :]
        assert ("--auto" in harness_args) == (harness == "opencode")
        data.update(
            shell=False,
            harness=harness,
            model=harness_args[harness_args.index("--model") + 1],
            args=harness_args,
        )
    if args[:2] == ["agent", "prompt"]:
        assert "HOLD" in args[3] and "/fr-goal" not in args[3]
        assert "--wait" in args
    path.write_text(json.dumps(data))
    return {}


def scenario():
    from fr.cli import app
    from fr.commands import triage_batch_cmd as cmd
    from fr.triage.batch import last_dispatch, save_batches
    from fr.triage.model import Batch, DispatchEvent, Facts, Issue, load_judgements
    from typer.testing import CliRunner

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
    git("checkout", "-b", "feat/scenario")
    runs = Path("docs/superpowers/runs")
    runs.mkdir(parents=True)
    (runs / "scenario.yaml").write_text(
        "run: scenario\nbranch: feat/scenario\nsteps:\n  deliver: {state: done}\n"
    )
    state = Path("state")
    state.mkdir()
    path = state / "judgements.yaml"
    path.write_text("schema: 2\ntiers: [{n: 1, title: Now}]\nissues:\n  alpha#1: {tier: 1}\n")
    dispatch = DispatchEvent(
        kind="dispatch",
        at=datetime(2026, 10, 9, tzinfo=UTC),
        runner="herdr",
        handle=PANE,
        branch="feat/scenario",
        reserved_version="6.0.0",
    )
    b = Batch(
        id="scenario",
        title="scenario",
        ids=["alpha#1"],
        launch={"runner": "herdr", "harness": "opencode", "model": "openai/old"},
        events=[dispatch],
    )
    save_batches(path, [b], read=[])
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
    Path(os.environ["HERDR_REPLACE_STATE"]).write_text(
        json.dumps({"shell": False, "harness": "opencode", "model": "openai/old"})
    )

    class Forge:
        def list_prs_by_head(self, repo, branch):
            return []

    class Checkout:
        path = Path.cwd()

        def origin_repo(self):
            return "example/alpha"

        def main_worktree(self):
            return self.path

    cmd.make_client = lambda url: Forge()
    cmd.make_checkout = lambda path: Checkout()
    base = [
        "triage",
        "batch",
        "replace",
        "scenario",
        "--repo",
        "example/alpha",
        "--dir",
        str(state.resolve()),
        "--checkout",
        str(Path.cwd()),
        "--reason",
        "candidate scenario",
    ]

    def invoke(*args, code=0):
        result = CliRunner().invoke(app, [*base, *args])
        assert result.exit_code == code, result.output
        return result

    os.environ["FR_SKIP_MIGRATION"] = "1"  # intentionally minimal synthetic cursor
    before = path.read_bytes()
    invoke("--harness", "claude", "--model", "sonnet")
    assert path.read_bytes() == before
    log = Path(os.environ["HERDR_REPLACE_LOG"])
    assert not any(x in log.read_text() for x in ("send-text", "send-keys", "start", "prompt"))
    invoke("--harness", "claude", "--model", "sonnet", "--yes")
    assert last_dispatch(load_judgements(path).batches[0]) == dispatch
    invoke("--harness", "opencode", "--model", "openai/new", "--yes")
    invoke("--model", "openai/newer", "--yes")
    os.environ["HERDR_REPLACE_FAIL"] = "1"
    invoke("--model", "openai/failure", "--yes", code=1)
    assert load_judgements(path).batches[0].launch.model == "openai/newer"
    del os.environ["HERDR_REPLACE_FAIL"]
    count = log.read_text().count('"start"')
    invoke("--repair", "--yes")
    assert log.read_text().count('"start"') == count
    assert load_judgements(path).batches[0].events[-1].reconciled
    assert '"close"' not in log.read_text()


if __name__ == "__main__":
    if sys.argv[1] == "scenario-run":
        scenario()
    else:
        print(json.dumps(pane(sys.argv[1:])))
