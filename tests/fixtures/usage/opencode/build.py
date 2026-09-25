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
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
