"""A run at `lens-review` (spec 2026-11-12-review-lenses §3.C) in a real linked
worktree whose base has a remote, so the feature has a diff.

The shape is the shipped step's own definition (`needs`, `emits`, `evidence`)
between a `plan` step and `deliver`; the branch changes `src/app.py` and
`src/auth/token.py`. Lenses are added with `lens` plan-journal entries, as a
step record or `fr journal add --kind lens` writes them.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from fr.run import units
from fr.run.model import load_run_state

PLAN = "2026-05-09-lensed"
PLAN_REL = f"docs/superpowers/plans/{PLAN}"
CHANGED = ("src/app.py", "src/auth/token.py")

LENS_SHAPE = """
workflow: lensed
schema: 1
unit: run
steps:
  - id: plan
    kind: agent
    emits: [plan]
  - id: lens-review
    kind: agent
    tier: standard
    needs: [plan]
    emits: [journal:plan]
    evidence: [lenses, review, reviewer, findings]
  - id: deliver
    kind: agent
    needs: [plan]
"""

RESOLVE = ["run", "resolve", "r1", "--step", "lens-review"]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def with_remote(repo: Path) -> None:
    """Give the worktree's base an `origin` whose `main` is the seed commit."""
    common = Path(_git(repo, "rev-parse", "--git-common-dir").strip())
    if not common.is_absolute():
        common = (repo / common).resolve()
    remote = common.parent.parent / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "fetch", "-q", "origin")
    _git(repo, "remote", "set-head", "origin", "main")


def commit_paths(repo: Path, paths: dict[str, str], message: str = "work") -> None:
    for rel, text in paths.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    _git(repo, "add", "--", *paths)
    _git(repo, "commit", "-qm", message, "--no-verify")


def plan_journal(repo: Path, *entries: dict[str, object]) -> None:
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path

    from tests.unit.requirements_support import now

    for e in entries:
        append_journal_entry(
            journal_path(repo, "plan", PLAN),
            PLAN,
            JournalEntry(scope="plan", created=now(), **e),  # type: ignore[arg-type]
        )


def lens(lens_id: str, n: int = 1, title: str = "why it matters") -> dict[str, object]:
    return {"kind": "lens", "id": f"lens-{lens_id}-{n}", "lens": lens_id, "title": title}


def finding(fid: str, scope: str, *, state: str = "fixed") -> list[dict[str, object]]:
    """A global lens finding and its resolution record."""
    return [
        {"kind": "finding", "id": fid, "title": fid, "state": "open", "review_scope": scope},
        {"kind": "finding", "id": f"{fid}-resolved", "title": f"resolves {fid}",
         "state": state, "resolves": fid},
    ]  # fmt: skip


def at_lens_review(
    tmp_path: Path,
    *,
    lenses: tuple[str, ...] = (),
    config: str | None = None,
    remote: bool = True,
    shape: str = LENS_SHAPE,
) -> tuple[Path, Path, str]:
    """`lens-review` opened (its brief printed) with `lenses` added in the plan
    journal and `config` committed as `.fr/lenses.yaml` on the branch. Returns
    `(repo, shipped, when the unit opened)`."""
    from tests.unit.test_run_cli import _FIXTURE_PLAN, _invoke, _repo, _write_shape

    repo = _repo(tmp_path)
    if remote:
        with_remote(repo)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "lensed", shape)
    files = {rel: f"# {rel}\n" for rel in CHANGED}
    if config is not None:
        files[".fr/lenses.yaml"] = config
    commit_paths(repo, files, "feature")
    plan_dir = repo / PLAN_REL
    shutil.copytree(_FIXTURE_PLAN, plan_dir)
    meta = plan_dir / "_meta.yaml"
    meta.write_text(meta.read_text().replace("2026-05-09-fixture-minimal", PLAN))
    ok = _invoke(repo, shipped, ["run", "start", "lensed", "--branch", "b", "--run-id", "r1"])
    assert ok.exit_code == 0, ok.output
    ok = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert ok.exit_code == 0, ok.output
    ok = _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "plan", "--state", "done",
         "--emitted", f"plan={PLAN_REL}"],
    )  # fmt: skip
    assert ok.exit_code == 0, ok.output
    if lenses:
        plan_journal(repo, *(lens(name) for name in lenses))
    ok = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert ok.exit_code == 0, ok.output
    attempt = units.last_attempt(load_run_state(repo, "r1"), "step/lens-review")
    assert attempt is not None
    return repo, shipped, attempt.dispatched


def lens_evidence(repo: Path) -> dict[str, str]:
    record = load_run_state(repo, "r1").steps["lens-review"]
    return units.evidence_of(record, "step/lens-review")


def review_lens_return(lens_id: str, files: tuple[str, ...], *findings: str) -> str:
    body = "\n".join(findings) if findings else "none"
    return (
        f"Reviewed through {lens_id}.\n\n```review-lens\nlens: {lens_id}\n"
        f"examined: {', '.join(files)}\n```\n\n```review-findings\n{body}\n```\n"
    )
