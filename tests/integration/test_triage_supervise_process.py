"""The supervisor as a real process around a fake driver (spec 2026-11-19-batch-train-truth
R11-R13). Real children and signals; every wait is a bounded poll."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import yaml
from fr.triage.driver_record import load_ledger, load_record

DRIVER = textwrap.dedent(
    """
    import os, signal, sys, time
    d = sys.argv[1]
    with open(d + "/pids", "a") as f:
        f.write(str(os.getpid()) + "\\n")
    if os.path.exists(d + "/ignore-term"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        ctl = open(d + "/control").read().strip() if os.path.exists(d + "/control") else "run"
        if ctl.startswith("exit:"):
            sys.exit(int(ctl[5:]))
        time.sleep(0.05)
    """
)
SUPERVISOR = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    from fr.triage.supervise import Supervisor
    import os
    d = Path(sys.argv[1])
    (d / f"supervisor-{os.getpid()}").write_text("")
    parent = os.environ.get("RIG_PARENT")
    sup = Supervisor(
        lambda pid: [sys.executable, str(d / "driver.py"), str(d)],
        d / "state", base_delay=0.3, grace=1.0, poll=0.2,
        parent=int(parent) if parent else None,
    )
    raise SystemExit(sup.run())
    """
)
PARENT = textwrap.dedent(
    """
    import os, subprocess, sys, time
    # name ourselves as the parent: on a loaded host this process may be gone before the
    # supervisor has even imported fr, and the supervisor must still end (R12)
    env = {**os.environ, "RIG_PARENT": str(os.getpid())}
    subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2]], env=env)
    deadline = time.monotonic() + 15  # exit only once the supervisor has started its driver
    while not os.path.exists(sys.argv[2] + "/pids") and time.monotonic() < deadline:
        time.sleep(0.05)
    """
)


def wait_for(pred: Callable[[], bool], timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.05)
    return pred()


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class Rig:
    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "driver.py").write_text(DRIVER)
        (root / "supervisor.py").write_text(SUPERVISOR)
        (root / "parent.py").write_text(PARENT)
        (root / "state").mkdir()
        self.procs: list[subprocess.Popen[bytes]] = []

    def pids(self) -> list[int]:
        path = self.root / "pids"
        return [int(x) for x in path.read_text().split()] if path.exists() else []

    def start(self) -> subprocess.Popen[bytes]:
        proc = subprocess.Popen(
            [sys.executable, str(self.root / "supervisor.py"), str(self.root)],
            stderr=(self.root / "supervisor.err").open("ab"),
        )
        self.procs.append(proc)
        return proc

    def cleanup(self) -> None:
        for proc in self.procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        for pid in self.pids():
            if alive(pid):
                os.kill(pid, signal.SIGKILL)


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.cleanup()


def test_a_killed_driver_is_restarted_and_the_crash_is_recorded(rig: Rig) -> None:
    sup = rig.start()
    assert wait_for(lambda: len(rig.pids()) == 1)
    first = rig.pids()[0]
    os.kill(first, signal.SIGKILL)
    assert wait_for(lambda: len(rig.pids()) == 2), "no new child within the backoff"
    assert rig.pids()[1] != first
    state = rig.root / "state"
    assert wait_for(lambda: "crash:SIGKILL" in load_ledger(state).causes)
    assert load_ledger(state).causes["crash:SIGKILL"].kind == "crash"
    assert wait_for(lambda: (load_record(state) or object()) is not None and
                    getattr(load_record(state), "restarts", 0) == 1)  # fmt: skip
    # the restarted child is recorded a moment after the crash is: wait for it
    assert wait_for(lambda: getattr(load_record(state), "pid", 0) == rig.pids()[1])
    record = load_record(state)
    assert record is not None
    assert (record.supervised, record.last_crash) == (sup.pid, "SIGKILL")
    log = (state / "drive.log").read_text()
    assert " restart " in log and "SIGKILL" in log


def test_a_refusal_exit_stops_the_supervisor_with_that_code_and_no_restart(rig: Rig) -> None:
    (rig.root / "control").write_text("exit:2")
    sup = rig.start()
    assert sup.wait(timeout=15) == 2
    assert len(rig.pids()) == 1
    assert "crash:2" not in load_ledger(rig.root / "state").causes


def test_the_supervisor_and_its_driver_end_with_the_supervisors_parent(rig: Rig) -> None:
    subprocess.run([sys.executable, str(rig.root / "parent.py"), str(rig.root / "supervisor.py"),
                    str(rig.root)], check=True)  # fmt: skip
    assert wait_for(lambda: len(rig.pids()) == 1)
    child = rig.pids()[0]
    # the supervisor names itself on start: reading the child's ppid instead races the
    # supervisor ending it, which it may already have done
    (sup,) = (int(p.name.split("-")[1]) for p in rig.root.glob("supervisor-*"))
    assert wait_for(lambda: not alive(sup) and not alive(child), timeout=15)


def test_a_supervisor_whose_parent_ended_before_it_ran_starts_no_driver(rig: Rig) -> None:
    # the parent is named, and gone, before the supervisor runs: the adopter must not be
    # mistaken for it, or the supervisor outlives its session (R12)
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    env = {**os.environ, "RIG_PARENT": str(gone.pid)}
    proc = subprocess.run([sys.executable, str(rig.root / "supervisor.py"), str(rig.root)],
                          env=env, timeout=15)  # fmt: skip
    assert proc.returncode == 0
    assert rig.pids() == []
    assert (
        "parent ended before the driver started" in (rig.root / "state" / "drive.log").read_text()
    )


def test_sigterm_to_the_supervisor_stops_the_driver_and_exits(rig: Rig) -> None:
    sup = rig.start()
    assert wait_for(lambda: len(rig.pids()) == 1)
    child = rig.pids()[0]
    sup.send_signal(signal.SIGTERM)
    assert sup.wait(timeout=15) == 0
    assert wait_for(lambda: not alive(child))
    assert len(rig.pids()) == 1  # a stop is never a crash to restart
    assert not any(k.startswith("crash:") for k in load_ledger(rig.root / "state").causes)


def test_a_driver_that_ignores_sigterm_is_killed_after_the_grace(rig: Rig) -> None:
    (rig.root / "ignore-term").write_text("")
    sup = rig.start()
    assert wait_for(lambda: len(rig.pids()) == 1)
    child = rig.pids()[0]
    time.sleep(0.3)  # let the driver install its handler
    started = time.monotonic()
    sup.send_signal(signal.SIGTERM)
    assert sup.wait(timeout=15) == 0
    assert wait_for(lambda: not alive(child))
    assert time.monotonic() - started >= 0.9  # it waited the (shortened) grace first
    assert "SIGKILL" in (rig.root / "state" / "drive.log").read_text()


def test_the_supervisor_stays_in_its_callers_process_group(rig: Rig) -> None:
    sup = rig.start()
    assert wait_for(lambda: len(rig.pids()) == 1)
    assert os.getpgid(sup.pid) == os.getpgid(0)
    assert os.getpgid(rig.pids()[0]) == os.getpgid(0)


def test_a_crash_loop_stops_the_supervisor_as_a_refusal(rig: Rig) -> None:
    (rig.root / "control").write_text("exit:1")
    sup = rig.start()
    # base 0.3 s doubling: 0.3+0.6+1.2+2.4+4.8 s of waits before the sixth crash
    assert sup.wait(timeout=60) == 2
    assert len(rig.pids()) == 6
    ledger = load_ledger(rig.root / "state")
    assert ledger.causes["crash-loop"].kind == "refusal"
    assert ledger.causes["crash:1"].count == 6  # the last crash is ledgered too (p2a-r6)
    data = yaml.safe_load((rig.root / "state" / "driver.yaml").read_text())
    assert data["restarts"] == 5
    # the refusal is on driver.yaml, so the board's driver-stopped need shows it (R8)
    assert data["last_refusal"]["cause"] == "crash-loop"
    assert data["last_refusal"]["resume"]
    # and said on stderr with the pointer to file it, as everything the supervisor logs is
    err = (rig.root / "supervisor.err").read_text()
    assert "fr triage drive failures --file --yes" in err
    assert "restart 1 in" in err and "crash-loop" in err
    log = (rig.root / "state" / "drive.log").read_text()
    assert "crash-loop" in log


def test_sighup_to_the_supervisor_stops_the_driver_and_exits_cleanly(rig: Rig) -> None:
    sup = rig.start()
    assert wait_for(lambda: len(rig.pids()) == 1)
    child = rig.pids()[0]
    sup.send_signal(signal.SIGHUP)
    assert sup.wait(timeout=15) == 0
    assert wait_for(lambda: not alive(child))
    assert len(rig.pids()) == 1
    assert "SIGHUP received" in (rig.root / "state" / "drive.log").read_text()
