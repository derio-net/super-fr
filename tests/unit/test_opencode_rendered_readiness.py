"""Synthetic startup timing replay with captured input screens; never live verdicts.

Real diagnostic: title readiness at +4.406s, eligible rendered textarea at +9.741s.
All three entry points must wait before a single prompt; no uncertain replay.
"""

import base64
import gzip
import hashlib
import json
from pathlib import Path

import pytest
from fr_dispatch.protocols import ReplacementRequest
from fr_dispatch.testing import run_item
from fr_herdr import managed, opencode, replacement, runner

FIXTURES = Path(__file__).parents[1] / "fixtures/herdr"


@pytest.fixture
def timeline(tmp_path, monkeypatch, native_herdr_cache):
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("HERDR_PANE_ID", "caller")
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "socket"))
    monkeypatch.setattr(runner, "stable_checkout", lambda p: p)
    monkeypatch.setattr(replacement, "stable_checkout", lambda p: p)
    monkeypatch.setattr(managed, "reconstruct", lambda d: "HOLD, never replay the goal")
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    monkeypatch.setattr(opencode, "_sleep", sleep)
    monkeypatch.setattr(opencode, "_clock", lambda: now[0])
    monkeypatch.setattr(
        opencode,
        "create_session",
        lambda model, checkout: "ses-" + model.replace("/", "-"),
    )
    created = json.loads((FIXTURES / "tab-create.json").read_text())
    pane = created["result"]["root_pane"]["pane_id"]
    screen = json.loads((FIXTURES / "opencode/final-idle.json").read_text())["raw"]
    d = managed.Descriptor(
        server=managed.server_identity(),
        pane=pane,
        name="b-test",
        item="example/alpha/run/batch-test",
        role="batch",
        branch="feat/test",
        checkout=str(tmp_path),
        harness="opencode",
        model="openai/old",
    )

    class Timeline:
        phase = "source"
        reads = 0
        name = d.name
        model = d.model
        calls = []
        refusal_screen = None
        startup_screen = ""
        ready_screen = screen
        wrong_model = False

        def __init__(self):
            self.calls = []
            self.argv = ["--model", self.model]

        def __call__(self, args, **kwargs):
            self.calls.append(args)
            if args[:2] == ["tab", "create"]:
                return created
            if args[:2] == ["agent", "list"]:
                return {
                    "result": {
                        "agents": [
                            {
                                "pane_id": pane,
                                "name": self.name,
                                "agent": "opencode",
                                "agent_status": "idle",
                                "interactive_ready": True,
                            }
                        ]
                    }
                }
            if args[:2] == ["pane", "process-info"]:
                argv = ["opencode", *self.argv]
                if self.wrong_model:
                    if "--session" in argv:
                        argv[argv.index("--session") + 1] = "ses-other"
                    else:
                        argv[argv.index("--model") + 1] = "other/model"
                proc = {
                    "pid": 2,
                    "argv": argv,
                    "cwd": d.checkout,
                }
                if self.phase == "shell":
                    proc = {"pid": 1, "argv": ["zsh"], "cwd": d.checkout}
                return {
                    "result": {"process_info": {"shell_pid": 1, "foreground_processes": [proc]}}
                }
            if args[:2] == ["pane", "read"]:
                if self.phase == "startup":
                    self.reads += 1
                    return {
                        "raw": self.refusal_screen
                        if self.refusal_screen is not None
                        else self.startup_screen
                        if self.reads < 3
                        else self.ready_screen
                    }
                return {"raw": screen}
            if args[:2] == ["pane", "send-keys"]:
                self.phase = "shell"
            if args[:2] == ["agent", "start"]:
                self.name = args[2]
                self.argv = args[args.index("--") + 1 :]
                if "--model" in self.argv:
                    self.model = self.argv[self.argv.index("--model") + 1]
                self.phase = "startup"
            if args[:2] == ["agent", "prompt"] and self.reads < 3:
                raise runner.HerdrError(
                    "title ready but input not rendered", code="agent_prompt_stalled"
                )
            return {}

    fake = Timeline()
    for module in (runner, opencode, replacement):
        monkeypatch.setattr(module, "_run_herdr", fake)
    return d, fake


def test_initial_dispatch_waits_for_rendered_prompt_before_single_submission(timeline):
    d, fake = timeline
    item = run_item(
        "example/alpha",
        "batch-test",
        harness="opencode",
        model=d.model,
        checkout=d.checkout,
        branch=d.branch,
        brief="HOLD",
    )
    assert runner.HerdrRunner("w2").dispatch(item) == d.pane
    assert fake.reads >= 3
    assert sum(c[:2] == ["agent", "prompt"] for c in fake.calls) == 1
    assert not any(c[:2] in (["agent", "send-keys"], ["pane", "send-keys"]) for c in fake.calls)


def test_managed_restart_waits_for_new_rendered_prompt(timeline):
    d, fake = timeline
    managed.save(d)
    assert opencode.restart_pane(d.pane, yes=True, exclude=set())[0] == "ok"
    assert fake.reads >= 3
    assert sum(c[:2] == ["agent", "prompt"] for c in fake.calls) == 1


def test_replacement_target_waits_for_rendered_prompt(timeline):
    d, fake = timeline
    managed.save(d)
    request = ReplacementRequest(
        d.item,
        d.pane,
        d.name,
        d.branch,
        d.checkout,
        d.harness,
        d.model,
        "opencode",
        "openai/new",
        "attempt",
    )
    op = replacement.Operation(request)
    with op.ownership():
        op.prepare()
        assert op.execute().ok
    assert fake.reads >= 3
    assert sum(c[:2] == ["agent", "prompt"] for c in fake.calls) == 1
    start = next(c for c in fake.calls if c[:2] == ["agent", "start"])
    assert start[start.index("--") + 1 :] == [
        "--session",
        "ses-openai-new",
        "--auto",
    ]


@pytest.mark.parametrize("failure", ["timeout", "draft", "dialog", "model", "name"])
def test_startup_readiness_refuses_unsafe_or_unrendered_target_without_prompt(timeline, failure):
    d, fake = timeline
    fake.phase = "startup"
    if failure == "timeout":
        fake.refusal_screen = ""
    elif failure in {"draft", "dialog"}:
        fake.refusal_screen = json.loads((FIXTURES / f"opencode/{failure}.json").read_text())["raw"]
    elif failure == "model":
        fake.wrong_model = True
    else:
        fake.name = "different-name"
    pending = d.model_copy(update={"checkpoint": "prepared"})
    managed.save(pending)
    with pytest.raises((managed.ManagedError, runner.HerdrError)):
        opencode.wait_ready(pending)
    assert managed.load(d.pane) == pending
    assert not any(c[:2] in (["agent", "prompt"], ["pane", "send-keys"]) for c in fake.calls)


def metadata_capture(kind):
    name = "startup-metadata" if kind == "startup" else "metadata-ready"
    data = json.loads((FIXTURES / f"opencode/v2-2.1.4-{name}.json").read_text())
    raw = gzip.decompress(base64.b64decode(data["raw_gzip_base64"]))
    assert hashlib.sha256(raw).hexdigest() == data["sha256"]
    return raw.decode()


def test_captured_metadata_sequence_never_admits_the_incomplete_screen():
    assert opencode.input_reason(metadata_capture("startup")) == "dialog-or-unfocused"
    assert opencode.input_reason(metadata_capture("ready")) is None


def test_dispatch_waits_for_captured_startup_metadata_before_single_submission(timeline):
    d, fake = timeline
    fake.startup_screen = metadata_capture("startup")
    fake.ready_screen = metadata_capture("ready")
    item = run_item(
        "example/alpha",
        "batch-test",
        harness="opencode",
        model=d.model,
        checkout=d.checkout,
        branch=d.branch,
        brief="HOLD",
    )
    assert runner.HerdrRunner("w2").dispatch(item) == d.pane
    assert fake.reads == 3
    assert sum(c[:2] == ["agent", "prompt"] for c in fake.calls) == 1
    create = next(c for c in fake.calls if c[:2] == ["tab", "create"])
    assert "--no-focus" in create
    start = next(c for c in fake.calls if c[:2] == ["agent", "start"])
    assert start[start.index("--") + 1 :] == ["--session", "ses-openai-old", "--auto"]
    assert not any(c[:2] in (["pane", "send-keys"], ["agent", "focus"]) for c in fake.calls)


def test_permanent_captured_startup_metadata_times_out_without_submission(timeline):
    d, fake = timeline
    fake.phase = "startup"
    fake.refusal_screen = metadata_capture("startup")
    pending = d.model_copy(update={"checkpoint": "prepared"})
    managed.save(pending)
    with pytest.raises(runner.HerdrError, match="rendered-input-timeout; no prompt sent"):
        opencode.wait_ready(pending, run=fake)
    assert 1 < fake.reads <= 31
    assert managed.load(d.pane) == pending
    assert not any(c[:2] == ["agent", "prompt"] for c in fake.calls)


@pytest.mark.parametrize("when", ["initial", "after-pending"])
@pytest.mark.parametrize("unsafe", ["draft", "permission", "palette", "unknown", "resolved-grey"])
def test_grey_startup_with_draft_or_overlay_is_a_refusal(timeline, unsafe, when):
    d, fake = timeline
    fake.phase = "startup"
    startup = metadata_capture("startup")
    if unsafe == "draft":
        # Synthetic negative: insert a draft in the real grey prompt's blank input row.
        screen = startup.replace("┃", "┃  unsent draft", 1)
    elif unsafe == "permission":
        screen = startup.replace("New session -", "permission required · New session -")
    elif unsafe == "palette":
        # The real captured Commands overlay replaces the upper blank viewport;
        # preserve the incomplete grey prompt below it. This composition is synthetic.
        dialog = json.loads((FIXTURES / "opencode/dialog.json").read_text())["raw"]
        rows = startup.splitlines()
        rows[10] = dialog.splitlines()[0]
        screen = "\n".join(rows)
    elif unsafe == "unknown":
        screen = startup.replace("New session -", "Unrecognized overlay · New session -")
    else:
        screen = metadata_capture("ready").replace("38;2;92;156;245m", "38;2;72;72;72m")
    original = fake.__call__

    def observe(args, **kwargs):
        answer = original(args, **kwargs)
        if args[:2] == ["pane", "read"]:
            return {"raw": startup if when == "after-pending" and fake.reads == 1 else screen}
        return answer

    with pytest.raises(managed.ManagedError):
        opencode.wait_ready(d.model_copy(update={"checkpoint": "prepared"}), run=observe)
    assert fake.reads == (2 if when == "after-pending" else 1)
    assert not any(c[:2] == ["agent", "prompt"] for c in fake.calls)


@pytest.mark.parametrize(
    "change", ["name", "status", "readiness", "model", "cwd", "session", "auto", "pid"]
)
def test_metadata_wait_revalidates_guards_after_each_pending_observation(timeline, change):
    d, fake = timeline
    d = d.model_copy(update={"session": "ses-pinned"})
    fake.argv = ["--session", d.session, "--auto"]
    fake.phase = "startup"
    fake.startup_screen = metadata_capture("startup")
    original = fake.__call__

    def observe(args, **kwargs):
        answer = original(args, **kwargs)
        if fake.reads >= 1:
            if args[:2] == ["agent", "list"]:
                agent = answer["result"]["agents"][0]
                if change == "name":
                    agent["name"] = "different-name"
                elif change == "status":
                    agent["agent_status"] = "working"
                elif change == "readiness":
                    agent["interactive_ready"] = False
            if args[:2] == ["pane", "process-info"]:
                proc = answer["result"]["process_info"]["foreground_processes"][0]
                if change == "model":
                    proc["argv"] = ["opencode", "--model", "other/model"]
                elif change == "cwd":
                    proc["cwd"] = "/other"
                elif change == "session":
                    proc["argv"] = ["opencode", "--session", "ses-other", "--auto"]
                elif change == "auto":
                    proc["argv"] = ["opencode", "--session", "ses-pinned"]
                elif change == "pid":
                    proc["pid"] = 3
        return answer

    with pytest.raises(managed.ManagedError, match="mismatch|unknown or changed|process changed"):
        opencode.wait_ready(d.model_copy(update={"checkpoint": "prepared"}), run=observe)
    assert fake.reads == 1  # The second observation refuses before reading another screen.
    assert not any(c[:2] == ["agent", "prompt"] for c in fake.calls)


def test_incomplete_metadata_is_not_active_restart_admission(timeline):
    d, fake = timeline
    fake.phase = "startup"
    fake.refusal_screen = metadata_capture("startup")
    with pytest.raises(managed.ManagedError, match="dialog-or-unfocused"):
        opencode.eligible(d, set(), run=fake, restart=False)
