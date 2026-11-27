"""The derived delivery witnesses: proportionality and docs (spec 2026-11-27-run-verdict R7).

Moved from `fr.commands.run_cmd` in slice 1. Both diff against one base,
`witness_base`'s; each returns a `Verdict[str]`, its refusal lines exactly the lines the
old command printed, and `run_cmd`'s `derive` settles it inside its `try`.

Engine code: no `typer`, no `rich` but `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

from rich.markup import escape

from fr.artifacts.paths import emitted_path
from fr.run.model import RunState
from fr.run.steps import emitted_plan
from fr.run.verdict import RunRefusal, Say, Verdict, Warn


def proportionality_witness(key: str, repo_root: Path, state: RunState) -> Verdict[str]:
    """`<merge-base-sha>:<sha256-of-report>` for this run's plan — or a refusal.

    The report itself never blocks (spec §C, report first); what fails closed
    is only the witness. A report with no merge-base is the single line naming
    `--base`, and hashing it would record "proportionality checked" over a
    diff nobody computed, so the resolve is refused with that line instead.
    """
    from fr.parser import PlanSchemaError, parse
    from fr.proportionality import run_report

    plan_rel = emitted_plan(state)
    if plan_rel is None:
        return Verdict(
            None,
            refusal=(
                Say(
                    f"[red]{key}: cannot derive proportionality evidence — no plan recorded "
                    "yet (resolve the step that emits `plan` first)[/red]",
                    soft_wrap=True,
                ),
            ),
        )
    try:
        plan = parse(emitted_path(repo_root, plan_rel))
    except PlanSchemaError as e:
        return Verdict(
            None,
            refusal=(
                Say(
                    f"[red]{key}: cannot derive proportionality evidence — plan {plan_rel} "
                    f"does not parse: {escape(str(e))}[/red]",
                    soft_wrap=True,
                ),
            ),
        )
    warnings: list[Say] = []
    try:
        base = witness_base(
            key, repo_root, "proportionality", announce=True, warn=warnings.append, state=state
        )
    except RunRefusal as r:
        return Verdict(None, refusal=r.lines, exit_code=r.exit_code, warnings=tuple(warnings))
    report = run_report(repo_root, plan, base)
    if report.merge_base is None:
        return Verdict(
            None,
            refusal=(
                Say(
                    f"{key}: cannot derive proportionality evidence — {report.text.strip()}",
                    markup=False,
                    soft_wrap=True,
                ),
            ),
            warnings=tuple(warnings),
        )
    digest = hashlib.sha256(report.text.encode()).hexdigest()
    return Verdict(f"{report.merge_base}:{digest}", warnings=tuple(warnings))


def docs_witness(
    key: str, repo_root: Path, *, announce: bool, state: RunState | None = None
) -> Verdict[str]:
    """`<merge-base-sha>:<sha256>` of the current pages, `none` with no
    `.fr/docs.yaml` — or a refusal with the check's own findings (R9).

    The base is `witness_base`'s, so both derived witnesses diff
    against the same commit, the isolation start commit included; a fallback
    base is named once, by proportionality when the step declares both.
    """
    from fr.docs import render
    from fr.docs.gate import evaluate
    from fr.docs.load import DocsEnvError, load_config, merge_base_of

    warnings: list[Say] = []
    try:
        config = load_config(repo_root)
        if config is None:
            return Verdict("none")
        base = witness_base(
            key, repo_root, "docs", announce=announce, warn=warnings.append, state=state
        )
        outcome = evaluate(repo_root, config, base)
        merge_base = merge_base_of(repo_root, base)
    except RunRefusal as r:
        return Verdict(None, refusal=r.lines, exit_code=r.exit_code, warnings=tuple(warnings))
    except DocsEnvError as e:
        lines = derived_refusal_lines(key, [f"cannot derive docs evidence — fr docs: {e}"])
        return Verdict(None, refusal=lines, warnings=tuple(warnings))
    if outcome.findings:
        lines = derived_refusal_lines(
            key,
            [
                f"refused — `fr docs check` fails ({len(outcome.findings)} finding(s)):",
                *render.findings_text(outcome.findings).splitlines(),
            ],
        )
        return Verdict(None, refusal=lines, warnings=tuple(warnings))
    current = render.status_json(outcome.pages, [])
    digest = hashlib.sha256(current.encode()).hexdigest()
    return Verdict(f"{merge_base}:{digest}", warnings=tuple(warnings))


def witness_base(
    key: str,
    repo_root: Path,
    name: str,
    *,
    announce: bool,
    warn: Warn,
    state: RunState | None = None,
) -> str:
    """The base a derived delivery witness diffs against, or `RunRefusal` naming why.

    `proportionality` and `docs` share it, so both diff against one commit.
    `announce` sends `warn` the fallback used when the remote default branch did not
    resolve.
    """
    from fr.run.target import TargetError, target_ref

    if state is not None and state.base_branch is not None:
        try:
            explicit = target_ref(repo_root, state.base_branch)
        except TargetError as error:
            raise RunRefusal(
                derived_refusal_lines(key, [f"cannot derive {name} evidence — {error}"])
            ) from None
        assert explicit is not None
        return explicit
    base, label = proportionality_base(repo_root)
    if base is None:
        raise RunRefusal(
            (
                Say(
                    f"{key}: cannot derive {name} evidence — no base: {label}. Fetch the "
                    "remote so its default branch resolves, or create the local default branch.",
                    markup=False,
                    soft_wrap=True,
                ),
            )
        )
    if announce and label is not None:
        warn(
            Say(
                f"{key}: {name}: no remote default branch; using base {label}",
                markup=False,
                soft_wrap=True,
            )
        )
    return base


def proportionality_base(repo_root: Path) -> tuple[str | None, str | None]:
    """The base `deliver`'s proportionality witness diffs against (gh#768).

    `fr run resolve` takes no `--base`, so a repo whose remote default branch
    does not resolve could never resolve `deliver`. In order: the remote
    default branch (`(ref, None)` — the ordinary case, nothing printed); the
    commit `fr isolation up` cut this branch from; the local default branch.
    `(ref, label)` names a fallback; `(None, why)` means none is left.
    """
    from fr.git import GitRefusal, GitUnavailableError, git_answer, remote_default_ref
    from fr.isolation.types import load_state

    try:
        found = remote_default_ref(repo_root)
        if found is not None and not isinstance(found, GitRefusal):
            return found, None
        head = git_answer(repo_root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        try:
            recorded = load_state(repo_root, head)
        except OSError, ValueError:
            recorded = None
        if recorded is not None and recorded.base_sha:
            ok = git_answer(repo_root, "cat-file", "-e", f"{recorded.base_sha}^{{commit}}")
            if ok.returncode == 0:
                return recorded.base_sha, f"{recorded.base_sha[:12]} (isolation start commit)"
        for name in ("main", "master"):
            if name == head:
                continue
            ok = git_answer(repo_root, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}")
            if ok.returncode == 0:
                return name, f"{name} (local default branch)"
    except GitUnavailableError as e:
        return None, f"git could not answer ({e}); retry"
    return None, (
        "no remote default branch, no isolation start commit, and no local default branch"
    )


def derived_refusal_lines(key: str, lines: Sequence[str]) -> tuple[Say, ...]:
    """A derived witness's refusal: its first line after the unit key, the
    rest indented beneath it."""
    first = Say(f"{key}: {lines[0]}", markup=False, soft_wrap=True)
    return (first, *(Say(f"  {line}", markup=False, soft_wrap=True) for line in lines[1:]))
