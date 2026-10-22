"""Build `two-sessions.db` — the OpenCode 2 store fixture (see README.md).

The DDL of `session_v2`, `session_message`, `session`, `message` and `part` is
VERBATIM from a 2026-10-20 `sqlite3 .schema` of a live OpenCode 2.1.0 store
(read from a read-only copy). The `data` JSON shapes follow live rows of the
same capture. Every identity — directory, title, prompt, model, provider,
figure — is fictional: the shape was captured live and the identity redacted
(`.claude/rules/third-party-privacy.md`).

Run: `uv run --no-project python tests/fixtures/opencode/build.py`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

OUT = Path(__file__).with_name("two-sessions.db")

DDL = [
    """CREATE TABLE `session_v2` (
          `id` text PRIMARY KEY,
          `project_id` text NOT NULL,
          `workspace_id` text,
          `parent_id` text,
          `fork_session_id` text,
          `fork_boundary` text,
          `slug` text NOT NULL,
          `directory` text NOT NULL,
          `path` text,
          `title` text,
          `version` text NOT NULL,
          `share_url` text,
          `summary_additions` integer,
          `summary_deletions` integer,
          `summary_files` integer,
          `summary_diffs` text,
          `metadata` text,
          `cost` real DEFAULT 0 NOT NULL,
          `tokens_input` integer DEFAULT 0 NOT NULL,
          `tokens_output` integer DEFAULT 0 NOT NULL,
          `tokens_reasoning` integer DEFAULT 0 NOT NULL,
          `tokens_cache_read` integer DEFAULT 0 NOT NULL,
          `tokens_cache_write` integer DEFAULT 0 NOT NULL,
          `revert` text,
          `permission` text,
          `agent` text,
          `model` text,
          `time_created` integer NOT NULL,
          `time_updated` integer NOT NULL,
          `time_compacting` integer,
          `time_archived` integer,
          `time_suspended` integer, `resume_attempts` integer DEFAULT 0 NOT NULL, `time_idle` integer, `time_viewed` integer, `idle_outcome` text,
          CONSTRAINT `fk_session_v2_project_id_project_id_fk` FOREIGN KEY (`project_id`) REFERENCES `project`(`id`) ON DELETE CASCADE
        )""",  # noqa: E501
    """CREATE TABLE "session_message" (
          `id` text PRIMARY KEY,
          `session_id` text NOT NULL,
          `type` text NOT NULL,
          `seq` integer NOT NULL,
          `time_created` integer NOT NULL,
          `time_updated` integer NOT NULL,
          `data` text NOT NULL,
          CONSTRAINT `fk_session_message_session_id_session_v2_id_fk` FOREIGN KEY (`session_id`) REFERENCES `session_v2`(`id`) ON DELETE CASCADE
        )""",  # noqa: E501
    """CREATE TABLE `session` (
          `id` text PRIMARY KEY,
          `project_id` text NOT NULL,
          `workspace_id` text,
          `parent_id` text,
          `slug` text NOT NULL,
          `directory` text NOT NULL,
          `path` text,
          `title` text NOT NULL,
          `version` text NOT NULL,
          `share_url` text,
          `summary_additions` integer,
          `summary_deletions` integer,
          `summary_files` integer,
          `summary_diffs` text,
          `metadata` text,
          `cost` real DEFAULT 0 NOT NULL,
          `tokens_input` integer DEFAULT 0 NOT NULL,
          `tokens_output` integer DEFAULT 0 NOT NULL,
          `tokens_reasoning` integer DEFAULT 0 NOT NULL,
          `tokens_cache_read` integer DEFAULT 0 NOT NULL,
          `tokens_cache_write` integer DEFAULT 0 NOT NULL,
          `revert` text,
          `permission` text,
          `agent` text,
          `model` text,
          `time_created` integer NOT NULL,
          `time_updated` integer NOT NULL,
          `time_compacting` integer,
          `time_archived` integer,
          CONSTRAINT `fk_session_project_id_project_id_fk` FOREIGN KEY (`project_id`) REFERENCES `project`(`id`) ON DELETE CASCADE
        )""",  # noqa: E501
    """CREATE TABLE `message` (
          `id` text PRIMARY KEY,
          `session_id` text NOT NULL,
          `time_created` integer NOT NULL,
          `time_updated` integer NOT NULL,
          `data` text NOT NULL,
          CONSTRAINT `fk_message_session_id_session_id_fk` FOREIGN KEY (`session_id`) REFERENCES `session`(`id`) ON DELETE CASCADE
        )""",  # noqa: E501
    """CREATE TABLE `part` (
          `id` text PRIMARY KEY,
          `message_id` text NOT NULL,
          `session_id` text NOT NULL,
          `time_created` integer NOT NULL,
          `time_updated` integer NOT NULL,
          `data` text NOT NULL,
          CONSTRAINT `fk_part_message_id_message_id_fk` FOREIGN KEY (`message_id`) REFERENCES `message`(`id`) ON DELETE CASCADE
        )""",  # noqa: E501
]

T0 = 1792400000000  # 2026-10-20, epoch ms (fictional instant)
V2 = "ses_v2demo"
CHILD = "ses_v2child"
V1 = "ses_v1only"
MIGRATED = "ses_v1migrated"
CAPTURE = Path(__file__).with_name("migrated-1x-session.json")
"""Rows of ONE real migrated 1.x session (version 1.18.x, in both `session` and
`session_v2`), copied from a read-only copy of a live 2.1.0 store and redacted:
see README.md for exactly which parts are captured."""
MODEL = {"id": "example-model", "providerID": "example-provider", "variant": "default"}
TOKENS = {"input": 1200, "output": 300, "reasoning": 50, "cache": {"read": 4000, "write": 600}}
CHILD_TOKENS = {"input": 200, "output": 40, "reasoning": 0, "cache": {"read": 0, "write": 0}}


def tool(call: str, name: str, at: int, state: dict, *, ran: bool = True) -> dict:
    times = {"created": at, "completed": at + 900}
    if ran:
        times["ran"] = at + 100
    return {"type": "tool", "id": call, "name": name, "time": times, "state": state}


def text(body: str) -> list[dict]:
    return [{"type": "text", "text": body}]


def v2_session(sid: str, parent: str | None, title: str) -> tuple:
    return (sid, "prj_demo", parent, f"slug-{sid}", "/home/u/work/demo", title, "2.1.0", T0, T0)


def main() -> None:
    OUT.unlink(missing_ok=True)
    con = sqlite3.connect(OUT)
    for ddl in DDL:
        con.execute(ddl)
    con.executemany(
        "INSERT INTO session_v2 (id, project_id, parent_id, slug, directory, title, version, "
        "time_created, time_updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [v2_session(V2, None, "demo session"), v2_session(CHILD, V2, "demo subagent")],
    )
    first = {
        "agent": "build",
        "model": MODEL,
        "content": [
            {"type": "reasoning", "text": "thinking about the demo"},
            tool(
                "call_skill",
                "skill",
                T0 + 1000,
                {
                    "status": "completed",
                    "input": {"name": "fr-goal"},
                    "metadata": {"name": "fr-goal", "dir": "/home/u/skills/fr-goal"},
                    "content": text("skill loaded"),
                },
            ),
            tool(
                "call_question",
                "question",
                T0 + 2000,
                {
                    "status": "completed",
                    "input": {
                        "questions": [
                            {
                                "header": "Pick one",
                                "question": "Which demo option?",
                                "options": [{"label": "A", "description": "first"}],
                            }
                        ]
                    },
                    "metadata": {"answers": [["A"]]},
                    "content": text("answered"),
                },
            ),
            tool(
                "call_shell",
                "shell",
                T0 + 3000,
                {
                    "status": "completed",
                    "input": {"command": "echo demo > /home/u/work/demo/out.log"},
                    "metadata": {"exit": 0, "status": "completed", "truncated": False},
                    "content": text("demo\n"),
                },
            ),
            tool(
                "call_subagent",
                "subagent",
                T0 + 4000,
                {
                    "status": "completed",
                    "input": {"agent": "general", "description": "demo", "prompt": "do the demo"},
                    "metadata": {"sessionID": CHILD, "status": "completed"},
                    "content": text("child done"),
                },
            ),
            {"type": "text", "text": "demo finished"},
        ],
        "cost": 0.0123,
        "tokens": TOKENS,
        "time": {"created": T0 + 500, "completed": T0 + 6000},
        "finish": "tool-calls",
    }
    migrated = {
        "agent": "build",
        "model": MODEL,
        "content": [
            tool(
                "call_bash_v1",
                "bash",
                T0 + 7000,
                {
                    "status": "completed",
                    "input": {"command": "ls /home/u/work/demo"},
                    "metadata": {"exit": 0, "output": "out.log\n"},
                    "content": text("out.log\n"),
                },
                ran=False,
            )
        ],
        "cost": 0,
        "tokens": {"input": 10, "output": 5, "reasoning": 0, "cache": {"read": 0, "write": 0}},
        "time": {"created": T0 + 6500, "completed": T0 + 8000},
    }
    child = {
        "agent": "general",
        "model": MODEL,
        "content": [{"type": "text", "text": "child final answer"}],
        "cost": 0.002,
        "tokens": CHILD_TOKENS,
        "time": {"created": T0 + 4200, "completed": T0 + 4800},
        "finish": "stop",
    }
    rows = [
        ("msg_u1", V2, "user", 0, T0, T0, {"text": "start the demo", "time": {"created": T0}}),
        ("msg_a1", V2, "assistant", 1, T0 + 500, T0 + 6000, first),
        ("msg_a2", V2, "assistant", 2, T0 + 6500, T0 + 8000, migrated),
        ("msg_c1", CHILD, "assistant", 0, T0 + 4200, T0 + 4800, child),
    ]
    con.executemany(
        "INSERT INTO session_message VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(*r[:6], json.dumps(r[6])) for r in rows],
    )
    # A 1.x session: legacy tables only, never migrated into session_v2.
    con.execute(
        "INSERT INTO session (id, project_id, parent_id, slug, directory, title, version, "
        "time_created, time_updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (V1, "prj_demo", None, "slug-v1", "/home/u/work/old", "old session", "1.18.32", T0, T0),
    )
    con.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        (
            "msg_v1",
            V1,
            T0,
            T0,
            json.dumps(
                {
                    "role": "assistant",
                    "agent": "build",
                    "modelID": "example-model",
                    "providerID": "example-provider",
                    "cost": 0.5,
                    "tokens": TOKENS,
                    "time": {"created": T0, "completed": T0 + 1000},
                }
            ),
        ),
    )
    con.execute(
        "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
        (
            "prt_v1",
            "msg_v1",
            V1,
            T0,
            T0,
            json.dumps(
                {
                    "type": "tool",
                    "tool": "bash",
                    "callID": "call_v1",
                    "state": {
                        "status": "completed",
                        "input": {"command": "true"},
                        "metadata": {"exit": 0},
                        "time": {"start": T0, "end": T0 + 10},
                    },
                }
            ),
        ),
    )
    # A real migrated 1.x session (R13's "migration lost nothing"): captured rows.
    captured = json.loads(CAPTURE.read_text())
    born = captured[0]["time_created"] - 24
    for table in ("session_v2", "session"):
        con.execute(
            f"INSERT INTO {table} (id, project_id, parent_id, slug, directory, title, version, "
            "time_created, time_updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (MIGRATED, "prj_demo", None, "slug-migrated", "/home/u/work/legacy",
             "migrated session", "1.18.10", born, captured[-1]["time_updated"]),
        )  # fmt: skip
    con.executemany(
        "INSERT INTO session_message VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (r["id"], MIGRATED, r["type"], r["seq"], r["time_created"], r["time_updated"],
             json.dumps(r["data"]))
            for r in captured
        ],
    )  # fmt: skip
    con.commit()
    con.execute("VACUUM")
    con.close()


if __name__ == "__main__":
    main()
