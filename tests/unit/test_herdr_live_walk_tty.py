"""PTY verdict-contract tests, not a real herdr client-live acceptance walk.

Like verification.walk._run, the child captures scenario stdout/stderr. A private
controlling terminal must still display instructions/prompts and accept the verdict.
"""

import json
import os
import pty
import select
import signal
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scenarios/herdr-opencode-live.sh"


def run_with_operator_tty(tmp_path, args, verdict, evidence):
    captured = tmp_path / "captured.json"
    pid, terminal = pty.fork()
    if pid == 0:
        try:
            done = subprocess.run(
                ["bash", str(SCRIPT), *args],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=15,
            )
            captured.write_text(
                json.dumps({"code": done.returncode, "stdout": done.stdout, "stderr": done.stderr})
            )
            os._exit(0)
        except BaseException:
            os._exit(99)
    screen = b""
    answered_verdict = answered_evidence = False
    reaped = False
    deadline = time.monotonic() + 20
    try:
        while time.monotonic() < deadline:
            if select.select([terminal], [], [], 0.1)[0]:
                try:
                    screen += os.read(terminal, 65536)
                except OSError:
                    pass  # PTY EOF on Linux is EIO; still reap/check the child below
            if not answered_verdict and b"Type PASS or FAIL:" in screen:
                os.write(terminal, (verdict + "\n").encode())
                answered_verdict = True
            if not answered_evidence and b"Path to the redacted observation log:" in screen:
                os.write(terminal, (str(evidence) + "\n").encode())
                answered_evidence = True
            ended, status = os.waitpid(pid, os.WNOHANG)
            if ended:
                reaped = True
                assert os.waitstatus_to_exitcode(status) == 0
                break
        assert reaped, "operator verdict interaction timed out"
    finally:
        if not reaped:
            os.killpg(pid, signal.SIGKILL)  # only this fork's private PTY session
            os.waitpid(pid, 0)
        os.close(terminal)
    return screen.decode(errors="replace"), json.loads(captured.read_text())


@pytest.mark.parametrize("args", [[], ["--record-verdict"]])
@pytest.mark.parametrize(
    "verdict,evidence_kind,code",
    [
        ("PASS", "nonempty", 0),
        ("PASS", "missing", 2),
        ("PASS", "empty", 2),
        ("FAIL", "nonempty", 1),
    ],
)
def test_documented_no_argument_walk_and_explicit_mode_use_tty_with_captured_output(
    tmp_path, args, verdict, evidence_kind, code
):
    evidence = tmp_path / "redacted-observations.log"
    if evidence_kind != "missing":
        evidence.write_text(
            "Synthetic PTY fixture; NOT client-live evidence.\n"
            if evidence_kind == "nonempty"
            else ""
        )
    screen, captured = run_with_operator_tty(tmp_path, args, verdict, evidence)
    assert "Use a disposable repository" in screen
    assert "Observe working/blocked refusal" in screen
    assert "Type PASS or FAIL:" in screen
    assert "Path to the redacted observation log:" in screen
    assert captured["code"] == code, captured
    assert "Type PASS or FAIL:" not in captured["stderr"]
    if code == 0:
        assert "operator verdict: PASS" in captured["stdout"]
        assert str(evidence) in captured["stdout"]
    else:
        assert "operator verdict: PASS" not in captured["stdout"]


@pytest.mark.parametrize("args,code", [([], 3), (["--record-verdict"], 2)])
def test_noninteractive_default_still_reports_owed_and_never_passes(tmp_path, args, code):
    evidence = tmp_path / "synthetic-observations.log"
    evidence.write_text("Synthetic input, not a client-live walk.\n")
    done = subprocess.run(
        ["bash", str(SCRIPT), *args],
        start_new_session=True,
        input=f"PASS\n{evidence}\n",  # piped answers never count as an operator TTY
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert done.returncode == code
    assert "OWED" in done.stdout
    assert "operator verdict: PASS" not in done.stdout
