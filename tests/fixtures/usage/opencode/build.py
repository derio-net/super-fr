"""Build `opencode.db` — the OpenCode reader's fixture (see ../NOTE.md).

The DDL is the subset of the LIVE schema the reader touches, copied from a
2026-09-25 `sqlite3 .schema` of OpenCode's own database (columns the reader
never reads are omitted; types and names are verbatim). The `data` JSON shapes
follow live rows of the same capture (assistant `message.data`: role, modelID,
providerID, agent, cost, tokens{input,output,reasoning,cache{read,write}},
time{created,completed}; `part.data` of type `tool`: tool, callID,
state{status,input}). All identities are fictional.

Run: `uv run --no-project python tests/fixtures/usage/opencode/build.py`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

OUT = Path(__file__).with_name("opencode.db")

DDL = [
    """CREATE TABLE `session` (
          `id` text PRIMARY KEY,
          `parent_id` text,
          `directory` text NOT NULL,
          `title` text NOT NULL,
          `time_created` integer NOT NULL
        )""",
    """CREATE TABLE `message` (
          `id` text PRIMARY KEY,
          `session_id` text NOT NULL,
          `time_created` integer NOT NULL,
          `time_updated` integer NOT NULL,
          `data` text NOT NULL
        )""",
    """CREATE TABLE `part` (
          `id` text PRIMARY KEY,
          `message_id` text NOT NULL,
          `session_id` text NOT NULL,
          `time_created` integer NOT NULL,
          `time_updated` integer NOT NULL,
          `data` text NOT NULL
        )""",
]

T0 = 1790328511802  # 2026-09-25, epoch ms (a live row's time.created)


def assistant(model: str, provider: str, cost: float, tokens: dict, at: int) -> str:
    return json.dumps(
        {
            "role": "assistant",
            "mode": "build",
            "agent": "build",
            "cost": cost,
            "tokens": tokens,
            "modelID": model,
            "providerID": provider,
            "time": {"created": at, "completed": at + 5000},
            "finish": "tool-calls",
        }
    )


def main() -> None:
    OUT.unlink(missing_ok=True)
    con = sqlite3.connect(OUT)
    for ddl in DDL:
        con.execute(ddl)
    con.executemany(
        "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
        [
            ("ses_paid", None, "/work/example", "paid session", T0),
            ("ses_free", None, "/work/example", "free session", T0),
            ("ses_copilot", None, "/work/example", "copilot session", T0),
            ("ses_mixed", None, "/work/example", "mixed session", T0),
        ],
    )
    paid_tokens = {
        "total": 12600,
        "input": 200,
        "output": 300,
        "reasoning": 100,
        "cache": {"write": 2000, "read": 10000},
    }
    free_tokens = {
        "total": 5050,
        "input": 50,
        "output": 0,
        "reasoning": 0,
        "cache": {"write": 0, "read": 5000},
    }
    copilot_tokens = {
        "total": 24163,
        "input": 2,
        "output": 514,
        "reasoning": 0,
        "cache": {"write": 3735, "read": 19912},
    }
    user = json.dumps({"role": "user", "time": {"created": T0 - 1000}})
    con.executemany(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        [
            ("msg_u1", "ses_paid", T0 - 1000, T0 - 1000, user),
            (
                "msg_a1",
                "ses_paid",
                T0,
                T0 + 5000,
                assistant("claude-sonnet-5", "anthropic", 0.0123, paid_tokens, T0),
            ),
            (
                "msg_a2",
                "ses_free",
                T0,
                T0 + 5000,
                assistant("free-model", "opencode", 0, free_tokens, T0),
            ),
            # Copilot-routed: OpenCode records a non-zero `cost` that is its OWN
            # estimate (Copilot bills by subscription, not per token). The
            # providerID and the token/cost shape follow a live github-copilot
            # row of the same 2026-09-25 capture; the figures are that row's.
            (
                "msg_a3",
                "ses_copilot",
                T0,
                T0 + 5000,
                assistant("claude-sonnet-5", "github-copilot", 0.0184639, copilot_tokens, T0),
            ),
            # one exact + one Copilot-estimated message: the session is estimated
            (
                "msg_a4",
                "ses_mixed",
                T0,
                T0 + 5000,
                assistant("claude-sonnet-5", "anthropic", 0.0123, paid_tokens, T0),
            ),
            (
                "msg_a5",
                "ses_mixed",
                T0 + 6000,
                T0 + 11000,
                assistant(
                    "claude-sonnet-5", "github-copilot", 0.0184639, copilot_tokens, T0 + 6000
                ),
            ),
        ],
    )
    tool = json.dumps(
        {
            "type": "tool",
            "tool": "bash",
            "callID": "call_1",
            "state": {
                "status": "completed",
                "input": {"command": "uv run pytest -q", "description": "tests"},
            },
        }
    )
    # A `task` dispatch: the part shape (state.input.prompt, state.metadata.
    # sessionId = the child session) follows a live task part of the same
    # 2026-09-25 capture; the prompt is a same-length placeholder (1009 chars,
    # that row's size) and the ids are fictional.
    task = json.dumps(
        {
            "type": "tool",
            "tool": "task",
            "callID": "call_task_1",
            "state": {
                "status": "completed",
                "input": {
                    "description": "<redacted>",
                    "subagent_type": "general",
                    "prompt": "x" * 1009,
                },
                "metadata": {"parentSessionId": "ses_mixed", "sessionId": "ses_child"},
            },
        }
    )
    text = json.dumps({"type": "text", "text": "<redacted>"})
    con.executemany(
        "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("prt_1", "msg_a1", "ses_paid", T0 + 1000, T0 + 1000, text),
            ("prt_2", "msg_a1", "ses_paid", T0 + 2000, T0 + 2000, tool),
            ("prt_3", "msg_a4", "ses_mixed", T0 + 3000, T0 + 3000, task),
        ],
    )
    run_tree(con)
    con.commit()
    con.close()


# --- the run tree (spec 2026-10-02-opencode-observe-2 §H) ---------------------
#
# Shapes follow a live OpenCode 1.18.33 capture of 2026-09-29 (read-only,
# shapes only, no content copied): a `task` subagent is a child `session` row
# (`parent_id` = its dispatcher); a `task` part carries `state.input.
# {subagent_type,prompt,description}`, `state.metadata.{parentSessionId,
# sessionId,model}`, `state.time.{start,end}`, `state.status` and
# `state.output` = `<task id="ses_…" state="completed"><task_result>…
# </task_result></task>`; the child's own last `text` part holds the same final
# message; `question` carries `state.input.questions[].{question,header,
# options[].{label,description}}` — answered `status: completed` with
# `state.metadata.answers: [[str]]`, declined `status: error` with `error`, a
# pending call `status: running`; `read` carries `state.input.filePath`. Every
# id, path and text below is fictional.

TR = T0 + 3_600_000  # the run tree starts an hour after the usage rows

RUN_DIR = "/work/example/wt"
SHOT = f"{RUN_DIR}/shots/a.png"
LOG = "/tmp/example/full-suite.log"

REVIEW_RETURN = """schema_version: 7
journal:
  - kind: review
    id: review-1
    title: spec review, round 1
    body: |
      Reviewed the spec; nothing blocks the plan.
"""

GEN1_RETURN = """Reviewed phase 2.

```review-findings
p2a-r1 | in | x
p2a-r2 | out | y
```
"""

GEN2_RETURN = "Reviewed phase 2 and found nothing to raise."


def _question(text: str, header: str) -> dict:
    return {
        "question": text,
        "header": header,
        "options": [
            {"label": "Yes", "description": "go ahead"},
            {"label": "No", "description": "stop here"},
        ],
    }


def _tool(tool: str, call: str, state: dict) -> str:
    return json.dumps({"type": "tool", "tool": tool, "callID": call, "state": state})


def _done(start: int, end: int, **state: object) -> dict:
    return {"status": "completed", "time": {"start": start, "end": end}, **state}


def _task(
    child: str, subagent: str, start: int, end: int | None, text: str | None, *, parent: str
) -> dict:
    state: dict = {
        "input": {
            "description": f"dispatch {child}",
            "subagent_type": subagent,
            "prompt": "x" * 64,
        },
        "metadata": {"parentSessionId": parent, "sessionId": child, "model": "example-model"},
    }
    if end is None:
        state.update(status="running", time={"start": start})
    else:
        state.update(
            status="completed",
            time={"start": start, "end": end},
            output=f'<task id="{child}" state="completed"><task_result>{text}</task_result></task>',
        )
    return state


def _bash(command: str, start: int, end: int, exit_code: int = 0) -> dict:
    return _done(
        start,
        end,
        input={"command": command, "description": "run"},
        output="",
        metadata={"exit": exit_code, "output": "", "truncated": False},
    )


def run_tree(con: sqlite3.Connection) -> None:
    con.executemany(
        "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
        [
            ("ses_run", None, RUN_DIR, "example run", TR),
            ("ses_rev", "ses_run", RUN_DIR, "spec review", TR + 90_000),
            ("ses_gen1", "ses_run", RUN_DIR, "phase review a", TR + 130_000),
            ("ses_gen2", "ses_run", RUN_DIR, "phase review b", TR + 150_000),
            ("ses_exec", "ses_run", RUN_DIR, "phase executor", TR + 170_000),
            ("ses_other", None, "/work/example/other", "another run", TR),
            ("ses_stray", "ses_other", "/work/example/other", "other's child", TR + 70_000),
        ],
    )
    tokens = {
        "total": 1500,
        "input": 100,
        "output": 200,
        "reasoning": 0,
        "cache": {"write": 200, "read": 1000},
    }
    messages = [
        ("msg_run", "ses_run", TR, 0.25),
        ("msg_rev", "ses_rev", TR + 90_000, 0.125),
        ("msg_gen1", "ses_gen1", TR + 130_000, 0.0625),
        ("msg_gen2", "ses_gen2", TR + 150_000, 0.0625),
        ("msg_exec", "ses_exec", TR + 170_000, 0.5),
        ("msg_other", "ses_other", TR, 0.5),
        ("msg_stray", "ses_stray", TR + 70_000, 0.5),
    ]
    con.executemany(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        [
            (mid, sid, at, at + 5000, assistant("example-model", "anthropic", cost, tokens, at))
            for mid, sid, at, cost in messages
        ],
    )
    t = TR
    run_parts = [
        _tool(
            "question",
            "call_q1",
            _done(
                t + 1_000,
                t + 20_000,
                input={"questions": [_question("Ship the first half?", "Scope")]},
                metadata={"answers": [["Yes"]]},
                output="User answered: Yes",
            ),
        ),
        _tool(
            "todowrite",
            "call_todo",
            _done(
                t + 21_000,
                t + 21_500,
                input={"todos": [{"content": "plan", "status": "pending"}]},
            ),
        ),
        _tool(
            "question",
            "call_q2",
            _done(
                t + 22_000,
                t + 30_000,
                input={"questions": [_question("Keep the old flag?", "Compat")]},
                metadata={"answers": [["No"]]},
                output="User answered: No",
            ),
        ),
        _tool(
            "read",
            "call_read_spec",
            _done(t + 31_000, t + 31_200, input={"filePath": f"{RUN_DIR}/docs/spec.md"}),
        ),
        _tool(
            "question",
            "call_q3",
            {
                "status": "error",
                "input": {"questions": [_question("Add a third mode?", "Modes")]},
                "error": "The user dismissed this question",
                "time": {"start": t + 32_000, "end": t + 32_500},
            },
        ),
        _tool(
            "question",
            "call_q4",
            {
                "status": "running",
                "input": {"questions": [_question("Rename the command?", "Naming")]},
                "time": {"start": t + 33_000},
            },
        ),
        _tool("read", "call_read_png", _done(t + 40_000, t + 40_100, input={"filePath": SHOT})),
        _tool("bash", "call_shots", _bash("node shots.cjs", t + 41_000, t + 45_000)),
        _tool(
            "bash",
            "call_suite",
            _bash(f"uv run pytest -q > {LOG} 2>&1; echo exit=$? >> {LOG}", t + 50_000, t + 80_000),
        ),
        _tool(
            "task",
            "call_task_rev",
            _task(
                "ses_rev",
                "fr-spec-reviewer-hard",
                t + 90_000,
                t + 120_000,
                REVIEW_RETURN,
                parent="ses_run",
            ),
        ),
        _tool(
            "task",
            "call_task_gen1",
            _task("ses_gen1", "general", t + 130_000, t + 145_000, GEN1_RETURN, parent="ses_run"),
        ),
        _tool(
            "task",
            "call_task_gen2",
            _task("ses_gen2", "general", t + 150_000, t + 165_000, GEN2_RETURN, parent="ses_run"),
        ),
        _tool(
            "task",
            "call_task_exec",
            _task(
                "ses_exec", "fr-phase-executor-standard", t + 170_000, None, None, parent="ses_run"
            ),
        ),
        # Names ses_run as the parent, but ses_stray's own row says ses_other:
        # the two keys disagree, so the dispatch is not ses_run's.
        _tool(
            "task",
            "call_task_stray",
            _task("ses_stray", "general", t + 175_000, t + 176_000, "stray", parent="ses_run"),
        ),
    ]
    rows: list[tuple[str, str, str, int, int, str]] = []
    for n, data in enumerate(run_parts, start=1):
        start = json.loads(data)["state"]["time"]["start"]
        rows.append((f"prt_run_{n:02d}", "msg_run", "ses_run", start, start + 1, data))

    def text_part(pid: str, mid: str, sid: str, at: int, text: str) -> tuple:
        return (pid, mid, sid, at, at, json.dumps({"type": "text", "text": text}))

    rows += [
        text_part("prt_rev_1", "msg_rev", "ses_rev", t + 95_000, "Reading the spec."),
        text_part("prt_rev_2", "msg_rev", "ses_rev", t + 119_000, REVIEW_RETURN),
        (
            "prt_gen1_1",
            "msg_gen1",
            "ses_gen1",
            t + 135_000,
            t + 135_100,
            _tool(
                "read", "call_g1_read", _done(t + 135_000, t + 135_100, input={"filePath": SHOT})
            ),
        ),
        text_part("prt_gen1_2", "msg_gen1", "ses_gen1", t + 144_000, GEN1_RETURN),
        text_part("prt_gen2_1", "msg_gen2", "ses_gen2", t + 164_000, GEN2_RETURN),
        text_part("prt_exec_1", "msg_exec", "ses_exec", t + 171_000, "Starting phase 1."),
        text_part("prt_stray_1", "msg_stray", "ses_stray", t + 175_500, "stray"),
        (
            "prt_other_1",
            "msg_other",
            "ses_other",
            t + 60_000,
            t + 60_001,
            _tool(
                "bash",
                "call_other_suite",
                _bash(f"uv run pytest -q > {LOG} 2>&1", t + 60_000, t + 65_000),
            ),
        ),
        (
            "prt_other_2",
            "msg_other",
            "ses_other",
            t + 70_000,
            t + 70_001,
            _tool(
                "task",
                "call_other_task",
                _task("ses_stray", "general", t + 70_000, t + 176_000, "stray", parent="ses_other"),
            ),
        ),
    ]
    con.executemany("INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)", rows)


if __name__ == "__main__":
    main()
