"""Which lane a CI run takes, and whether `ci-ok` passes it (spec 2026-11-24-ci-economy).

`ci.yml`'s first job, `classify`, picks one lane per run:

- `landed` (R5): a push to `main` whose sha already has a successful run of this CI
  workflow, triggered by a push to an `fr-queue/` branch. Only `validate-artifacts`
  runs again.
- `light` (R15, R16): a pull request whose diff changes nothing installable
  (`installable.is_installable`), nothing under `tests/` and nothing under `.github/`.
  The scoped tests run instead of the shards.
- `full`: everything else, and every answer this script cannot reach for sure.

`ci-ok` then asks `verdict` whether the needed jobs' results satisfy the lane (R17).

Subcommands:

    ci_lane.py classify --base <ref>                      (pull_request)
    ci_lane.py landed --sha <sha> --run <id> --repo <o/r> (push to main)
    ci_lane.py verdict                                    (ci-ok; reads LANE, NEEDS)

`classify` and `landed` append `lane=<lane>` (and `trusted_run=<id>`) to
`$GITHUB_OUTPUT`. Stdlib only, so it runs under `uv run --no-project`, like the other
scripts.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from installable import is_installable  # noqa: E402

FULL = "full"
LIGHT = "light"
LANDED = "landed"

# Paths outside the installable set that still change what the suite tests or how
# CI runs it (R15): a light lane over them would skip the very tests they change.
FULL_PREFIXES = ("tests/", ".github/")

Runner = Callable[..., subprocess.CompletedProcess[Any]]


def lane_for(paths: Sequence[str]) -> str:
    """`light` when every path is non-installable and outside `tests/` and `.github/`;
    `full` otherwise, and for an empty list (a diff that names nothing proves nothing)."""
    if not paths:
        return FULL
    for path in paths:
        if is_installable(path) or path.startswith(FULL_PREFIXES):
            return FULL
    return LIGHT


def _git(args: Sequence[str], cwd: Path | None, env: Mapping[str, str] | None) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, env=_git_env(env)
    ).stdout


def _git_env(env: Mapping[str, str] | None) -> dict[str, str] | None:
    # The output file is ours; git sees the process environment otherwise.
    return None if env is None else {**os.environ, **env}


def pull_request_lane(
    base: str, *, cwd: Path | None = None, env: Mapping[str, str] | None = None
) -> str:
    """The lane of the pull request checked out at *cwd*.

    A `pull_request` checkout's HEAD is a merge commit whose second parent is the PR
    head; with one parent, HEAD is the head. The diff runs from the merge base with
    `origin/<base>` to that head, so a later change on the base is not the PR's. Any
    git failure reads `full`.
    """
    try:
        try:
            _git(["rev-parse", "--verify", "--quiet", "HEAD^2"], cwd, env)
            head = "HEAD^2"
        except subprocess.CalledProcessError:
            head = "HEAD"
        merge_base = _git(["merge-base", f"origin/{base}", head], cwd, env).decode().strip()
        diff = _git(["diff", "--no-renames", "--name-only", "-z", merge_base, head, "--"], cwd, env)
    except subprocess.CalledProcessError as exc:
        return _fallback(f"git {' '.join(map(str, exc.cmd[1:3]))} failed (exit {exc.returncode})")
    except OSError as exc:
        return _fallback(f"git could not run: {exc}")
    return lane_for([os.fsdecode(p) for p in diff.split(b"\0") if p])


def _fallback(cause: str) -> str:
    """The full lane, saying why on stderr: a fallback the job log does not name reads
    as a lane that was chosen (lens review l-errors-r1)."""
    print(f"ci_lane: {cause}; taking the full lane", file=sys.stderr)
    return FULL


CI_WORKFLOW = ".github/workflows/ci.yml"
QUEUE_BRANCH_PREFIX = "fr-queue/"


def landed_run(runs_json: object, this_run: int | str, sha: str) -> int | None:
    """The id of a run that already proved this sha, or None (R5).

    *runs_json* is a `GET repos/{repo}/actions/runs` payload. A run qualifies when it is
    this CI workflow (by `path`, which a workflow cannot rename; an `@<ref>` suffix, should
    GitHub ever report one, is ignored: review p2-r2), triggered by a push
    (`event`) to an `fr-queue/` branch (`head_branch`), finished `success` (every job,
    `ci-ok` included, succeeded or skipped by its own condition), ran on *sha* itself
    (`head_sha`, never trusting the query's filter alone), and is not this run.
    A payload of any other shape trusts nothing.
    """
    runs = runs_json.get("workflow_runs") if isinstance(runs_json, dict) else None
    if not isinstance(runs, list):
        return None
    for run in runs:
        if not isinstance(run, dict):
            continue
        if (
            str(run.get("path") or "").split("@", 1)[0] == CI_WORKFLOW
            and run.get("event") == "push"
            and str(run.get("head_branch") or "").startswith(QUEUE_BRANCH_PREFIX)
            and run.get("conclusion") == "success"
            and run.get("head_sha") == sha
            and isinstance(run.get("id"), int)
            and str(run["id"]) != str(this_run)
        ):
            return int(run["id"])
    return None


def landed_lane(sha: str, this_run: str, repo: str, *, runner: Runner) -> dict[str, str]:
    """`lane=landed` and the run it trusts, or `lane=full` when none qualifies or the
    forge cannot be read: a skip needs proof, and no answer is no proof."""
    argv = ["gh", "api", f"repos/{repo}/actions/runs?head_sha={sha}&event=push&per_page=100"]
    try:
        proc = runner(argv, capture_output=True, text=True, check=False)
    except OSError as exc:
        return {"lane": _fallback(f"gh could not run: {exc}")}
    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()
        return {
            "lane": _fallback(f"gh api exit {proc.returncode}: {err[-1] if err else 'no output'}")
        }
    try:
        payload = json.loads(proc.stdout)
    except ValueError:
        return {"lane": _fallback("gh api returned no JSON")}
    except TypeError:
        return {"lane": _fallback("gh api returned no JSON")}
    trusted = landed_run(payload, this_run, sha)
    if trusted is None:
        print(
            f"ci_lane: no successful fr-queue push run of {CI_WORKFLOW} on {sha}; full lane",
            file=sys.stderr,
        )
        return {"lane": FULL}
    return {"lane": LANDED, "trusted_run": str(trusted)}


# R17. The shard jobs the `full` lane must have run, and the only jobs the `light` lane
# may skip. The classifier must succeed in every lane: without it there is no lane.
FULL_REQUIRED = ("collect", "test", "split-check", "coverage")
LIGHT_SKIPPABLE = frozenset({"plan", "collect", "test", "split-check", "coverage"})
LIGHT_REQUIRED = ("scoped-tests",)
LANDED_REQUIRED = ("validate-artifacts",)
CLASSIFIER = "classify"


def verdict(lane: str | None, needs: Mapping[str, Any]) -> tuple[bool, str]:
    """Whether `ci-ok` passes: (ok, one-line reason).

    *needs* is `toJSON(needs)`: `{job: {"result": ..., "outputs": {...}}}`. A failed or
    cancelled job fails every lane, and so does any result but success and skipped.
    Then each lane names the jobs that must have succeeded and the jobs that may be
    skipped: `full` any job by its own condition, `light` only the shard jobs, `landed`
    every job but the classifier and `validate-artifacts`.
    """
    if lane not in (FULL, LIGHT, LANDED):
        return False, f"no known lane ({lane!r}): the classify job did not choose one"
    results = {job: str((v or {}).get("result")) for job, v in needs.items()}
    bad = sorted(job for job, r in results.items() if r not in ("success", "skipped"))
    if bad:
        detail = ", ".join(f"{job}={results[job]}" for job in bad)
        return False, f"lane {lane}: {detail}"
    required = {FULL: FULL_REQUIRED, LIGHT: LIGHT_REQUIRED, LANDED: LANDED_REQUIRED}[lane]
    missing = [job for job in (CLASSIFIER, *required) if results.get(job) != "success"]
    if lane == LIGHT:
        missing += sorted(
            job
            for job, r in results.items()
            if r == "skipped" and job not in LIGHT_SKIPPABLE and job not in missing
        )
    if missing:
        return False, f"lane {lane}: did not run: {', '.join(missing)}"
    return True, f"lane {lane}: every needed job did what the lane asks"


def _verdict_from_env(env: Mapping[str, str]) -> tuple[bool, str]:
    try:
        needs = json.loads(env.get("NEEDS", ""))
    except ValueError:
        return False, "NEEDS is not JSON"
    if not isinstance(needs, dict):
        return False, "NEEDS is not a mapping of job results"
    ok, reason = verdict(env.get("LANE"), needs)
    trusted = env.get("TRUSTED_RUN")
    if ok and env.get("LANE") == LANDED and trusted:
        reason += f"; trusts run {trusted}"
    return ok, reason


def _emit(pairs: Mapping[str, str], env: Mapping[str, str]) -> None:
    lines = "".join(f"{key}={value}\n" for key, value in pairs.items())
    target = env.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(lines)
    sys.stdout.write(lines)


def main(
    argv: Sequence[str] | None = None,
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    runner: Runner = subprocess.run,
) -> int:
    parser = argparse.ArgumentParser(prog="ci_lane.py")
    sub = parser.add_subparsers(dest="command", required=True)
    classify = sub.add_parser("classify", help="the lane of a pull request")
    classify.add_argument("--base", required=True)
    landed = sub.add_parser("landed", help="whether a push to main already landed green")
    landed.add_argument("--sha", required=True)
    landed.add_argument("--run", required=True)
    landed.add_argument("--repo", required=True)
    sub.add_parser("verdict", help="whether ci-ok passes (reads LANE, NEEDS, TRUSTED_RUN)")
    args = parser.parse_args(argv)
    environ: Mapping[str, Any] = os.environ if env is None else env

    if args.command == "classify":
        _emit({"lane": pull_request_lane(args.base, cwd=cwd, env=env)}, environ)
        return 0
    if args.command == "landed":
        _emit(landed_lane(args.sha, args.run, args.repo, runner=runner), environ)
        return 0
    if args.command == "verdict":
        ok, reason = _verdict_from_env(environ)
        print(("ci-ok: pass: " if ok else "ci-ok: FAIL: ") + reason)
        return 0 if ok else 1
    return 2  # pragma: no cover - argparse refuses an unknown command first


if __name__ == "__main__":
    raise SystemExit(main())
