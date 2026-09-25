"""Build `state.db` — the Hermes reader's fixture (see ../NOTE.md).

The tables are created from `schema.sql`, a verbatim copy of the three tables
of Hermes' own `SCHEMA_SQL` the reader touches. No Hermes host was available
to capture rows from, so the ROWS are constructed against that schema — the
plan's stated source (P1.T2.S1) — and `messages.tool_calls` assumes the
OpenAI chat-completions shape Hermes stores (`[{id, type, function{name,
arguments}}]`, arguments a JSON string). Not live-verified; see the journal.

Sessions: `h_actual` (actual_cost_usd set, one delegate child), `h_estimated`
(estimated only), `h_acp` (an ACP session: zero tokens everywhere,
hermes-agent#6775). Identities are fictional.

Run: `uv run --no-project python tests/fixtures/usage/hermes/build.py`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "state.db"
T0 = 1790328500.0  # 2026-09-25, epoch seconds


def call(name: str, **arguments: str) -> dict:
    return {
        "id": f"call_{name}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def main() -> None:
    OUT.unlink(missing_ok=True)
    con = sqlite3.connect(OUT)
    con.executescript((HERE / "schema.sql").read_text())
    sessions = [
        # id, source, model, parent, started, in, out, cr, cw, estimated, actual
        (
            "h_actual",
            "cli",
            "anthropic/claude-sonnet-5",
            None,
            T0,
            1200,
            300,
            8000,
            500,
            0.051,
            0.048,
        ),
        (
            "h_actual_child",
            "cli",
            "anthropic/claude-sonnet-5",
            "h_actual",
            T0 + 30,
            100,
            50,
            0,
            0,
            0.002,
            0.002,
        ),
        ("h_estimated", "cli", "openrouter/some-model", None, T0, 400, 100, 0, 0, 0.0071, None),
        ("h_acp", "acp", "anthropic/claude-sonnet-5", None, T0, 0, 0, 0, 0, None, None),
    ]
    con.executemany(
        "INSERT INTO sessions (id, source, model, parent_session_id, started_at, input_tokens, "
        "output_tokens, cache_read_tokens, cache_write_tokens, estimated_cost_usd, "
        "actual_cost_usd) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        sessions,
    )
    messages = [
        # session, role, content, tool_calls, timestamp, token_count
        ("h_actual", "user", "<redacted>", None, T0 + 1, 40),
        (
            "h_actual",
            "assistant",
            "<redacted>",
            json.dumps([call("terminal", command="uv run pytest -q")]),
            T0 + 5,
            900,
        ),
        ("h_actual", "tool", "<redacted>", None, T0 + 6, 200),
        (
            "h_actual",
            "assistant",
            "<redacted>",
            json.dumps(
                [
                    call("read_file", path="docs/superpowers/specs/x.md"),
                    call("write_file", path="packages/fr/src/fr/x.py"),
                ]
            ),
            T0 + 10,
            600,
        ),
        ("h_actual", "assistant", "<redacted>", None, T0 + 20, 100),
        (
            "h_actual_child",
            "assistant",
            "<redacted>",
            json.dumps([call("terminal", command="git status --short")]),
            T0 + 31,
            150,
        ),
        ("h_estimated", "assistant", "<redacted>", None, T0 + 2, 500),
        ("h_acp", "user", "<redacted>", None, T0 + 1, 0),
        (
            "h_acp",
            "assistant",
            "<redacted>",
            json.dumps([call("terminal", command="ls")]),
            T0 + 2,
            0,
        ),
    ]
    con.executemany(
        "INSERT INTO messages (session_id, role, content, tool_calls, timestamp, token_count) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        messages,
    )
    con.executemany(
        "INSERT INTO session_model_usage (session_id, model, input_tokens, output_tokens, "
        "estimated_cost_usd, actual_cost_usd) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("h_actual", "anthropic/claude-sonnet-5", 1200, 300, 0.051, 0.048),
            ("h_actual_child", "anthropic/claude-sonnet-5", 100, 50, 0.002, 0.002),
            ("h_estimated", "openrouter/some-model", 400, 100, 0.0071, 0),
        ],
    )
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
