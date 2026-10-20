"""Capture tests/fixtures/hooks/guard-verdicts.yaml from the bash guard.

    uv run python tests/fixtures/hooks/capture_guard_verdicts.py

The verdict table is the contract between the two shell-gate engines — the
Claude Code hook `plugins/super-fr/hooks/fr-isolation-guard.sh` and the
OpenCode 2 port `packages/fr-opencode-plugin/src/guard.ts` (spec
2026-10-20-opencode-2-support §B). Its `expected`, `reason` and
`sentinel_after` columns are CAPTURED: this script builds the sandbox
(`guard-world.sh`), runs the real bash script on a synthesized PreToolUse
payload for each row's inputs, and writes down what it decided. Never edit a
verdict by hand — a hand-written row is a second opinion, not evidence. Change
the inputs here and re-capture.

`judge` is also what `tests/unit/test_hooks_guard.py` uses to re-run every row
against the script, so the table is proven to describe today's behaviour.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCRIPT = REPO / "plugins" / "super-fr" / "hooks" / "fr-isolation-guard.sh"
WORLD = HERE / "guard-world.sh"
TABLE = HERE / "guard-verdicts.yaml"
SESSION = "sess-1"

# Longest first, so {wt} is substituted before {home} and {root}.
PLACEHOLDERS = {
    "{wt}": "home/.cache/fr/worktrees/base/feat",
    "{wt_unmarked}": "base-wt-unmarked",
    "{home}": "home",
    "{base}": "base",
    "{other}": "other",
    "{plain}": "plain",
    "{scratch}": "scratch",
    "{elsewhere}": "elsewhere",
    "{root}": "",
}

FRESH = {"repo_root": "{base}"}
LIVE = {"repo_root": "{base}", "workspaces": ["worktrees/base/feat"]}
ORPHANED = {"repo_root": "{base}", "workspaces": ["worktrees/base/gone"]}

# (id, command, cwd, sentinel, env). Inputs only — verdicts are captured.
ROWS: list[tuple[str, str, str, dict[str, Any] | None, dict[str, str]]] = [
    ("no-sentinel", "git status", "{base}", None, {}),
    ("base-plain-command", "git status", "{base}", FRESH, {}),
    ("base-subdir", "ls", "{base}/sub", FRESH, {}),
    ("cwd-linked-worktree", "git status", "{wt}", FRESH, {}),
    ("cwd-outside-base", "ls", "{elsewhere}", FRESH, {}),
    ("cd-worktree-compound", "cd {wt} && git status", "{base}", FRESH, {}),
    ("cd-worktree-quoted", 'cd "{wt}" && git status', "{base}", FRESH, {}),
    ("cd-worktree-tilde", "cd ~/.cache/fr/worktrees/base/feat && git status", "{base}", FRESH, {}),
    ("cd-allowed-prefix", "cd {scratch} && rm -rf x", "{base}", FRESH, {}),
    ("cd-prefix-then-anywhere", "cd {scratch} && cd {base} && rm f", "{base}", FRESH, {}),
    ("cd-not-allowed-dir", "cd {elsewhere} && ls", "{base}", FRESH, {}),
    ("cd-other-repo-isolation-up", "cd {other} && fr isolation up --branch x", "{base}", FRESH, {}),
    ("cd-other-repo-general", "cd {other} && make", "{base}", FRESH, {}),
    ("cd-other-repo-base-ok", "cd {other} && make", "{base}", FRESH, {"FR_BASE_OK": "1"}),
    ("cd-plain-repo", "cd {plain} && ls", "{base}", FRESH, {}),
    (
        "cd-plain-subdir-rider",
        "cd {plain}/sub && fr isolation status && cat id_ed25519",
        "{base}",
        FRESH,
        {},
    ),
    ("cd-same-repo-unmarked-worktree", "cd {wt_unmarked} && ls", "{base}", FRESH, {}),
    ("cd-gone-path", "cd {root}/gone && ls", "{base}", FRESH, {}),
    ("cd-relative-subdir-then-fr", "cd sub && fr isolation down", "{base}", FRESH, {}),
    ("cd-base-then-git", "cd {base} && git status", "{base}", FRESH, {}),
    ("fr-isolation-status-rider", "fr isolation status && make", "{base}", FRESH, {}),
    (
        "fr-isolation-env-prefix",
        "FR_ISOLATION_TARGET=worktree fr isolation up --branch x",
        "{base}",
        FRESH,
        {},
    ),
    ("fr-run-start-uv", "uv run fr run start fr-goal --branch x", "{base}", FRESH, {}),
    ("fr-run-advance", "fr run advance", "{base}", FRESH, {}),
    ("fr-init", "fr init scaffold", "{base}", FRESH, {}),
    ("fr-version", "fr --version", "{base}", FRESH, {}),
    ("fr-skills", "fr skills", "{base}", FRESH, {}),
    ("fr-plan", "fr plan list", "{base}", FRESH, {}),
    ("fr-substring", "echo fr isolation status", "{base}", FRESH, {}),
    ("multiline-later-allowance", "echo hi\nfr isolation status", "{base}", FRESH, {}),
    ("sentinel-live-workspace", "ls", "{base}", LIVE, {}),
    ("sentinel-orphaned-heals", "ls", "{base}", ORPHANED, {}),
]


def expand(value: str, root: Path) -> str:
    for key, rel in PLACEHOLDERS.items():
        value = value.replace(key, str(root / rel) if rel else str(root))
    return value


def collapse(value: str, root: Path) -> str:
    for key, rel in PLACEHOLDERS.items():
        value = value.replace(str(root / rel) if rel else str(root), key)
    return value


def build_world(root: Path) -> Path:
    subprocess.run(["bash", str(WORLD), str(root)], check=True)
    return root.resolve()


def env_for(root: Path, extra: dict[str, str] | None) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"FR_BASE_OK", "KUBERNETES_SERVICE_HOST", "FR_CD_ALLOW_PREFIXES"}
    }
    env["HOME"] = str(root / "home")
    env["FR_SENTINEL_DIR"] = str(root / "sentinels")
    env["FR_CD_ALLOW_PREFIXES"] = f"{root / 'home/.cache/fr/worktrees'}:{root / 'scratch'}"
    env.update(extra or {})
    return env


def judge(row: dict[str, Any], root: Path) -> dict[str, Any]:
    """Run the bash guard on one row's inputs; return the captured columns."""
    sentinels = root / "sentinels"
    shutil.rmtree(sentinels, ignore_errors=True)
    sentinels.mkdir()
    sentinel = sentinels / f"{SESSION}.json"
    if row["sentinel"] is not None:
        data = {k: expand(v, root) if isinstance(v, str) else v for k, v in row["sentinel"].items()}
        data["skill"] = "fr-goal"
        sentinel.write_text(json.dumps(data))
    payload = {
        "session_id": SESSION,
        "cwd": expand(row["cwd"], root),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": expand(row["command"], root)},
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env_for(root, row.get("env")),
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"guard exited {result.returncode}: {result.stderr}")
    reason = None
    if result.stdout.strip():
        out = json.loads(result.stdout)["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny"
        reason = collapse(out["permissionDecisionReason"], root)
    return {
        "expected": "deny" if reason else "allow",
        "reason": reason,
        "sentinel_after": None
        if row["sentinel"] is None
        else ("present" if sentinel.exists() else "absent"),
    }


def capture() -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmp:
        root = build_world(Path(tmp) / "world")
        rows = []
        for rid, command, cwd, sentinel, env in ROWS:
            row: dict[str, Any] = {"id": rid, "command": command, "cwd": cwd, "sentinel": sentinel}
            if env:
                row["env"] = env
            row.update(judge(row, root))
            rows.append(row)
        return rows


HEADER = """\
# CAPTURED from plugins/super-fr/hooks/fr-isolation-guard.sh — do not edit by hand.
# Regenerate: uv run python tests/fixtures/hooks/capture_guard_verdicts.py
# Inputs: id, command, cwd, sentinel (the session sentinel before the call, null =
# none), env. Captured: expected, reason (the deny text, paths as placeholders),
# sentinel_after. Placeholders and the sandbox: guard-world.sh. Loaded by
# tests/unit/test_hooks_guard.py (against the bash script) and by
# packages/fr-opencode-plugin/test/guard-verdicts.test.ts (against the port).
"""


def main() -> None:
    rows = capture()
    body = yaml.safe_dump({"rows": rows}, sort_keys=False, width=100, allow_unicode=True)
    TABLE.write_text(HEADER + body)
    print(f"captured {len(rows)} rows -> {TABLE.relative_to(REPO)}")


if __name__ == "__main__":
    main()
