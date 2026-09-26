#!/usr/bin/env python3
"""The CI time-budget watcher (spec 2026-09-26-ci-time-budget-design.md §3.B, §5).

Split into a pure core (this module's top half — `wall_clock`, `counted`,
`budget_for`, `decide`, `parse_body`/`render_body`) and a thin `gh` adapter
(`GhAdapter`, `main`) so the decisions can be unit-tested against captured
fixtures without a network call. Stdlib + PyYAML only, so it runs under
`uv run --no-project --with pyyaml`.

Run with `--run-id <id>` (from `workflow_run` or a manual `workflow_dispatch`)
and an optional `--budget-seconds` override (the Test Plan's forced-breach
knob). GH_TOKEN / GITHUB_REPOSITORY come from the workflow environment.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_BUDGET_CONFIG_PATH = REPO_ROOT / ".github" / "ci-budget.yaml"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
CI_BUDGET_WORKFLOW_FILE = "ci-budget.yml"
LABEL = "ci-budget"
LABEL_COLOR = "d73a4a"
LABEL_DESCRIPTION = "CI time budget breach (scripts/ci_budget.py)"
DEFAULT_BUDGET_SECONDS = 240.0
COUNTED_CONCLUSIONS = ("success", "failure")


class Excluded:
    """Sentinel returned by `budget_for` for a file with `exclude: true`."""

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return "EXCLUDED"


EXCLUDED = Excluded()


# ── wall clock / slowest job ────────────────────────────────────────────


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _ran(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Jobs that actually ran: excludes `conclusion == "skipped"`.

    GitHub DOES stamp skipped jobs with `started_at`/`completed_at` (observed
    on run 36247922786: `change-fragment` started 14:16:03Z and completed
    14:16:02Z, a moment *before* it "started" — the workflow's skip window,
    not real work). Filtering on those timestamps being present or absent
    would therefore wrongly include a skipped job; `conclusion` is the test.
    """
    return [j for j in jobs if j.get("conclusion") != "skipped"]


def wall_clock(jobs: list[dict[str, Any]]) -> float | None:
    """Max `completed_at` minus min `started_at` over jobs that ran, in seconds.

    `None` when every job was skipped (nothing ran).
    """
    ran = _ran(jobs)
    if not ran:
        return None
    starts = [_parse_ts(j["started_at"]) for j in ran]
    ends = [_parse_ts(j["completed_at"]) for j in ran]
    return (max(ends) - min(starts)).total_seconds()


def slowest_job(jobs: list[dict[str, Any]]) -> tuple[str, float] | None:
    """The (name, seconds) of the longest-running job that ran, or None."""
    ran = _ran(jobs)
    if not ran:
        return None
    scored = [
        (j["name"], (_parse_ts(j["completed_at"]) - _parse_ts(j["started_at"])).total_seconds())
        for j in ran
    ]
    return max(scored, key=lambda pair: pair[1])


# ── counted: which runs of a watched file count toward its budget ──────


def workflow_on(workflow: dict[Any, Any]) -> Any:
    """The `on:` block's value. PyYAML parses the bare key `on` as `True`."""
    if "on" in workflow:
        return workflow["on"]
    return workflow.get(True)


def _push_spec(on_value: Any) -> Any | None:
    """The `push:` trigger's own value, or None if there is no push trigger."""
    if isinstance(on_value, dict):
        return on_value.get("push") if "push" in on_value else None
    if isinstance(on_value, list):
        return {} if "push" in on_value else None
    if on_value == "push":
        return {}
    return None


def _push_targets_main(push_spec: Any) -> bool:
    """True when the push trigger has no branch filter, `**`, or lists `main`."""
    if not isinstance(push_spec, dict) or not push_spec:
        return True
    branches = push_spec.get("branches")
    if branches is None:
        return True
    return "**" in branches or "main" in branches


def counted(on_value: Any, run: dict[str, Any]) -> bool:
    """Whether `run` of a workflow whose `on:` block is `on_value` counts.

    If the workflow triggers on `push` to `main` (no branch filter, a `**`
    filter, or `main` listed), only `event == push` runs on `main` are
    counted. Otherwise every event (including `workflow_dispatch`) counts.
    """
    push_spec = _push_spec(on_value)
    if push_spec is not None and _push_targets_main(push_spec):
        return run.get("event") == "push" and run.get("head_branch") == "main"
    return True


# ── budget_for: per-file budget / exclusion from .github/ci-budget.yaml ──


def budget_for(config: dict[str, Any] | None, file: str) -> float | Excluded:
    config = config or {}
    entry = (config.get("workflows") or {}).get(file) or {}
    if entry.get("exclude"):
        return EXCLUDED
    if "budget_seconds" in entry:
        return float(entry["budget_seconds"])
    return float(config.get("default_seconds", DEFAULT_BUDGET_SECONDS))


def load_config(path: Path = CI_BUDGET_CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


# ── Measurement: one run, reduced to what the state machine needs ──────


@dataclass(frozen=True)
class Measurement:
    file: str
    run_id: int
    run_url: str
    sha: str
    event: str
    head_branch: str
    conclusion: str
    budget_seconds: float
    wall_clock_seconds: float | None
    slowest_job_name: str | None
    slowest_job_seconds: float | None

    @property
    def over_budget(self) -> bool:
        return self.wall_clock_seconds is not None and self.wall_clock_seconds > self.budget_seconds


def measure(
    file: str, run: dict[str, Any], jobs: list[dict[str, Any]], budget_seconds: float
) -> Measurement:
    wc = wall_clock(jobs)
    slow = slowest_job(jobs)
    return Measurement(
        file=file,
        run_id=run["id"],
        run_url=run["html_url"],
        sha=run["head_sha"][:7],
        event=run["event"],
        head_branch=run["head_branch"],
        conclusion=run["conclusion"],
        budget_seconds=budget_seconds,
        wall_clock_seconds=wc,
        slowest_job_name=slow[0] if slow else None,
        slowest_job_seconds=slow[1] if slow else None,
    )


# ── Row / ParsedBody: the issue body's data, in and out of Markdown ────

MAX_ROWS = 10


@dataclass(frozen=True)
class Row:
    run_id: int
    run_url: str
    sha: str
    wall_clock_seconds: float
    slowest_job_name: str
    slowest_job_seconds: float


@dataclass(frozen=True)
class ParsedBody:
    file: str
    budget_seconds: float
    rows: tuple[Row, ...] = ()
    streak: int = 0
    green_rows: tuple[Row, ...] = ()
    regression_of: int | None = None


def _num(value: float) -> str:
    return f"{value:g}"


MARKER_RE = re.compile(r"<!-- ci-budget:(?P<file>\S+) -->")
BUDGET_RE = re.compile(r"budget: (?P<seconds>[\d.]+)s", re.IGNORECASE)
GREEN_RE = re.compile(r"<!-- ci-budget-green:(?P<n>\d+) -->")
GREEN_ROW_RE = re.compile(r"<!-- ci-budget-green-row:(?P<data>[^>]*) -->")
REGRESSION_RE = re.compile(r"regressed again; previously #(?P<n>\d+)", re.IGNORECASE)
ROW_RE = re.compile(
    r"\|\s*\[#(?P<run_id>\d+)\]\((?P<url>[^)]+)\)\s*\|\s*`(?P<sha>[^`]+)`\s*\|\s*"
    r"(?P<wall>[\d.]+)s\s*\|\s*(?P<job>.+?)\s*\((?P<job_seconds>[\d.]+)s\)\s*\|"
)


def _row_line(row: Row) -> str:
    return (
        f"| [#{row.run_id}]({row.run_url}) | `{row.sha}` | {_num(row.wall_clock_seconds)}s | "
        f"{row.slowest_job_name} ({_num(row.slowest_job_seconds)}s) |"
    )


def _green_row_comment(row: Row) -> str:
    fields = (
        row.run_id,
        row.run_url,
        row.sha,
        _num(row.wall_clock_seconds),
        row.slowest_job_name,
        _num(row.slowest_job_seconds),
    )
    return "<!-- ci-budget-green-row:" + "|".join(str(f) for f in fields) + " -->"


def _parse_green_row(data: str) -> Row:
    run_id, url, sha, wall, job, job_seconds = data.split("|", 5)
    return Row(
        run_id=int(run_id),
        run_url=url,
        sha=sha,
        wall_clock_seconds=float(wall),
        slowest_job_name=job,
        slowest_job_seconds=float(job_seconds),
    )


def render_body(parsed: ParsedBody) -> str:
    """A stable, idempotent issue body: `render_body(parse_body(x)) == x`."""
    lines = [
        f"<!-- ci-budget:{parsed.file} -->",
        f"## `{parsed.file}` is over its {_num(parsed.budget_seconds)}s CI time budget",
        "",
    ]
    if parsed.regression_of is not None:
        lines.append(f"Regressed again; previously #{parsed.regression_of}.")
        lines.append("")
    lines.append("| Run | SHA | Wall clock | Slowest job |")
    lines.append("| --- | --- | --- | --- |")
    for row in parsed.rows:
        lines.append(_row_line(row))
    lines.append("")
    lines.append(f"<!-- ci-budget-green:{parsed.streak} -->")
    for row in parsed.green_rows:
        lines.append(_green_row_comment(row))
    return "\n".join(lines) + "\n"


def _marker_file(body: str) -> str | None:
    match = MARKER_RE.search(body or "")
    return match.group("file") if match else None


def parse_body(body: str) -> ParsedBody:
    """The inverse of `render_body`. Unparseable rows are dropped (spec §5);
    a missing streak marker parses as streak 0."""
    file = _marker_file(body)
    if file is None:
        raise ValueError("body has no <!-- ci-budget:<file> --> marker")

    budget_match = BUDGET_RE.search(body)
    budget_seconds = (
        float(budget_match.group("seconds")) if budget_match else DEFAULT_BUDGET_SECONDS
    )

    regression_match = REGRESSION_RE.search(body)
    regression_of = int(regression_match.group("n")) if regression_match else None

    green_match = GREEN_RE.search(body)
    streak = int(green_match.group("n")) if green_match else 0

    rows = tuple(
        Row(
            run_id=int(m.group("run_id")),
            run_url=m.group("url"),
            sha=m.group("sha"),
            wall_clock_seconds=float(m.group("wall")),
            slowest_job_name=m.group("job"),
            slowest_job_seconds=float(m.group("job_seconds")),
        )
        for m in ROW_RE.finditer(body)
    )
    green_rows = tuple(_parse_green_row(m.group("data")) for m in GREEN_ROW_RE.finditer(body))

    return ParsedBody(
        file=file,
        budget_seconds=budget_seconds,
        rows=rows,
        streak=streak,
        green_rows=green_rows,
        regression_of=regression_of,
    )


# ── decide: the §3.B state machine ──────────────────────────────────────


class ActionKind(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    CLOSE = "close"
    NOOP = "noop"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    title: str | None = None
    body: str | None = None
    close_comment: str | None = None


def _measurement_row(measurement: Measurement) -> Row:
    assert measurement.wall_clock_seconds is not None
    assert measurement.slowest_job_name is not None
    assert measurement.slowest_job_seconds is not None
    return Row(
        run_id=measurement.run_id,
        run_url=measurement.run_url,
        sha=measurement.sha,
        wall_clock_seconds=measurement.wall_clock_seconds,
        slowest_job_name=measurement.slowest_job_name,
        slowest_job_seconds=measurement.slowest_job_seconds,
    )


def _close_comment(rows: tuple[Row, ...]) -> str:
    lines = ["3 consecutive runs under budget:"]
    for row in rows:
        lines.append(f"- [#{row.run_id}]({row.run_url}) — {_num(row.wall_clock_seconds)}s")
    return "\n".join(lines)


def decide(
    state: ParsedBody | None, measurement: Measurement, *, regression_of: int | None = None
) -> Action:
    """The §3.B table, per watched file, counted runs only."""
    if measurement.wall_clock_seconds is None:
        return Action(kind=ActionKind.NOOP)

    if state is None:
        if not measurement.over_budget:
            return Action(kind=ActionKind.NOOP)
        body = render_body(
            ParsedBody(
                file=measurement.file,
                budget_seconds=measurement.budget_seconds,
                rows=(_measurement_row(measurement),),
                streak=0,
                regression_of=regression_of,
            )
        )
        title = f"CI budget: {measurement.file} over {_num(measurement.budget_seconds)}s"
        return Action(kind=ActionKind.CREATE, title=title, body=body)

    if measurement.over_budget:
        rows = (*state.rows, _measurement_row(measurement))[-MAX_ROWS:]
        new_state = replace(
            state, rows=rows, streak=0, green_rows=(), budget_seconds=measurement.budget_seconds
        )
        return Action(kind=ActionKind.UPDATE, body=render_body(new_state))

    if measurement.conclusion != "success":
        return Action(kind=ActionKind.NOOP)

    green_rows = (*state.green_rows, _measurement_row(measurement))
    streak = state.streak + 1
    if streak >= 3:
        return Action(kind=ActionKind.CLOSE, close_comment=_close_comment(green_rows))
    new_state = replace(
        state, streak=streak, green_rows=green_rows, budget_seconds=measurement.budget_seconds
    )
    return Action(kind=ActionKind.UPDATE, body=render_body(new_state))


# ── watch-list tripwire (spec §7.3) ──────────────────────────────────────


def watched_workflows(ci_budget_workflow: dict[str, Any]) -> set[str]:
    """The `name:`s in the watcher's own `workflow_run.workflows` list."""
    on_value = workflow_on(ci_budget_workflow)
    if not isinstance(on_value, dict):
        return set()
    workflow_run = on_value.get("workflow_run") or {}
    return set(workflow_run.get("workflows") or [])


def check_watch_list(
    workflows_dir: Path, ci_budget_workflow_path: Path, config: dict[str, Any]
) -> list[str]:
    """Every workflow file must be watched (by `name:`) or `exclude: true`'d,
    with the watcher itself the one built-in exception. Every config key
    must name a real workflow file. Returns a list of error strings (empty
    means the tripwire passes)."""
    ci_budget_workflow = yaml.safe_load(ci_budget_workflow_path.read_text())
    watched = watched_workflows(ci_budget_workflow)
    excluded = {
        file
        for file, entry in (config.get("workflows") or {}).items()
        if (entry or {}).get("exclude")
    }

    errors: list[str] = []
    workflow_files = sorted(p for p in workflows_dir.glob("*.yml"))
    names_by_file: dict[str, str] = {}
    for path in workflow_files:
        doc = yaml.safe_load(path.read_text()) or {}
        names_by_file[path.name] = doc.get("name", path.name)

    for path in workflow_files:
        if path.name == ci_budget_workflow_path.name:
            continue
        name = names_by_file[path.name]
        if name not in watched and path.name not in excluded:
            errors.append(
                f"{path.name} (name: {name!r}) is neither watched (ci-budget.yml's "
                f"workflow_run.workflows) nor excluded (.github/ci-budget.yaml)"
            )

    for key in config.get("workflows") or {}:
        if key not in names_by_file:
            errors.append(f".github/ci-budget.yaml names {key!r}, which is not a workflow file")

    return errors


# ── gh adapter ───────────────────────────────────────────────────────────


def _gh_run(argv: list[str]) -> str:
    result = subprocess.run(["gh", *argv], capture_output=True, text=True, check=True)
    return result.stdout


class GhAdapter:
    """Thin wrapper over `gh`, with the subprocess call injectable for tests."""

    def __init__(self, repo: str, run: Callable[[list[str]], str] | None = None) -> None:
        self.repo = repo
        self._run = run or _gh_run

    def ensure_label(self) -> None:
        raw = self._run(["label", "list", "--repo", self.repo, "--json", "name", "--limit", "200"])
        labels = json.loads(raw or "[]")
        if not any(item["name"] == LABEL for item in labels):
            self._run(
                [
                    "label",
                    "create",
                    LABEL,
                    "--repo",
                    self.repo,
                    "--color",
                    LABEL_COLOR,
                    "--description",
                    LABEL_DESCRIPTION,
                ]
            )

    def _issues(self, state: str) -> list[dict[str, Any]]:
        raw = self._run(
            [
                "issue",
                "list",
                "--repo",
                self.repo,
                "--label",
                LABEL,
                "--state",
                state,
                "--json",
                "number,body",
                "--limit",
                "100",
            ]
        )
        return cast(list[dict[str, Any]], json.loads(raw or "[]"))

    def find_open_issue(self, file: str) -> tuple[int, str] | None:
        for item in self._issues("open"):
            if _marker_file(item.get("body") or "") == file:
                return item["number"], item["body"]
        return None

    def find_latest_closed_issue(self, file: str) -> int | None:
        matches = [
            item["number"]
            for item in self._issues("closed")
            if _marker_file(item.get("body") or "") == file
        ]
        return max(matches) if matches else None

    def _body_file(self, body: str) -> Path:
        tmp = NamedTemporaryFile(mode="w", suffix=".md", delete=False)
        tmp.write(body)
        tmp.close()
        return Path(tmp.name)

    def create_issue(self, title: str, body: str) -> int:
        path = self._body_file(body)
        out = self._run(
            [
                "issue",
                "create",
                "--repo",
                self.repo,
                "--title",
                title,
                "--body-file",
                str(path),
                "--label",
                LABEL,
            ]
        )
        match = re.search(r"/issues/(\d+)", out)
        if not match:
            raise RuntimeError(
                f"could not parse an issue number from `gh issue create` output: {out!r}"
            )
        return int(match.group(1))

    def edit_issue_body(self, number: int, body: str) -> None:
        path = self._body_file(body)
        self._run(["issue", "edit", str(number), "--repo", self.repo, "--body-file", str(path)])

    def close_issue(self, number: int, comment: str) -> None:
        self._run(["issue", "close", str(number), "--repo", self.repo, "--comment", comment])

    def fetch_workflow_text(self, path: str, ref: str) -> str | None:
        try:
            raw = self._run(["api", f"repos/{self.repo}/contents/{path}", "-f", f"ref={ref}"])
        except subprocess.CalledProcessError:
            return None
        data = json.loads(raw)
        return base64.b64decode(data["content"]).decode()

    def fetch_run(self, run_id: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            json.loads(self._run(["api", f"repos/{self.repo}/actions/runs/{run_id}"])),
        )

    def fetch_jobs(self, run_id: str) -> list[dict[str, Any]]:
        raw = json.loads(self._run(["api", f"repos/{self.repo}/actions/runs/{run_id}/jobs"]))
        return cast(list[dict[str, Any]], raw["jobs"])


# ── main ─────────────────────────────────────────────────────────────────


def apply_action(gh: GhAdapter, action: Action, open_issue_number: int | None) -> None:
    if action.kind is ActionKind.NOOP:
        return
    if action.kind is ActionKind.CREATE:
        assert action.title is not None and action.body is not None
        gh.ensure_label()
        gh.create_issue(action.title, action.body)
        return
    if action.kind is ActionKind.UPDATE:
        assert open_issue_number is not None and action.body is not None
        gh.edit_issue_body(open_issue_number, action.body)
        return
    if action.kind is ActionKind.CLOSE:
        assert open_issue_number is not None and action.close_comment is not None
        gh.close_issue(open_issue_number, action.close_comment)
        return


def run_once(
    gh: GhAdapter, run_id: str, config: dict[str, Any], budget_override: float | None
) -> str:
    """Runs one watcher invocation; returns a human log line."""
    run = gh.fetch_run(run_id)
    if run.get("conclusion") not in COUNTED_CONCLUSIONS:
        return f"run {run_id} concluded {run.get('conclusion')!r}; not measured"

    file = Path(run["path"]).name
    if file == CI_BUDGET_WORKFLOW_FILE:
        return "refusing to watch ci-budget.yml itself"

    workflow_text = gh.fetch_workflow_text(run["path"], run["head_sha"])
    if workflow_text is None:
        return f"{run['path']} not found at {run['head_sha'][:7]}; skipping (renamed?)"
    workflow = yaml.safe_load(workflow_text) or {}

    if not counted(workflow_on(workflow), run):
        return f"run {run_id} ({run['event']} on {run['head_branch']}) is not counted for {file}"

    budget = budget_override if budget_override is not None else budget_for(config, file)
    if isinstance(budget, Excluded):
        return f"{file} is excluded from the CI time budget"

    jobs = gh.fetch_jobs(run_id)
    measurement = measure(file, run, jobs, budget)

    found = gh.find_open_issue(file)
    state = parse_body(found[1]) if found else None
    regression_of = None
    if state is None and measurement.over_budget:
        regression_of = gh.find_latest_closed_issue(file)

    action = decide(state, measurement, regression_of=regression_of)
    apply_action(gh, action, found[0] if found else None)
    return f"{file} run {run_id}: {action.kind.value}"


def main(argv: list[str] | None = None, *, run: Callable[[list[str]], str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CI time-budget watcher")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--budget-seconds", type=float, default=None)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        print("ci_budget: GITHUB_REPOSITORY is not set", file=sys.stderr)
        return 1

    gh = GhAdapter(repo, run=run)
    config = load_config()
    print(f"ci_budget: {run_once(gh, args.run_id, config, args.budget_seconds)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
