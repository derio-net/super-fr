"""`fr.run.closeout.closeout_brief` — spec 2026-09-25-fr-goal-closeout-defects
§3.D.1.

A pure function: everything it prints is derived from the `RunState` handed
to it and the artifacts (spec, plan, journals) that state names — nothing
else, since it is read by a brand-new session that inherits none of the
delivering session's context.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.journal.model import JournalEntry, append_journal_entry, journal_path
from fr.run.closeout import CloseoutNotReadyError, closeout_brief
from fr.run.model import RunState, StepRecord
from fr.test_support import build_plan_journal

SPEC_SLUG = "2026-09-30-fixture"
SPEC_REL = f"docs/superpowers/specs/{SPEC_SLUG}-design.md"
PLAN_REL = f"docs/superpowers/plans/{SPEC_SLUG}"
PR_URL = "https://github.com/derio-net/super-fr/pull/1"
BRANCH = "feat/x"


def _spec_file(repo_root: Path, *, with_test_plan: bool) -> None:
    path = repo_root / SPEC_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "# Fixture\n\n## Background\n\ntext\n"
    if with_test_plan:
        body += "\n## Test Plan\n\n1. do the thing.\n"
    path.write_text(body)


def _plan_dir(repo_root: Path) -> None:
    (repo_root / PLAN_REL).mkdir(parents=True, exist_ok=True)


def _state(*, deliver_done: bool = True) -> RunState:
    return RunState(
        run="r1",
        workflow="fr-goal@1",
        branch=BRANCH,
        started="2026-09-30T00:00:00Z",
        cursor="deliver",
        steps={
            "brainstorm": StepRecord(state="done", emitted={"spec": SPEC_REL}),
            "plan": StepRecord(state="done", emitted={"plan": PLAN_REL}),
            "deliver": StepRecord(
                state="done" if deliver_done else "running", emitted={"pr": PR_URL}
            ),
        },
    )


def _spec_out_of_scope_finding(repo_root: Path) -> None:
    """A finding raised against the spec journal, resolved out-of-scope."""
    path = journal_path(repo_root, "spec", SPEC_SLUG)
    append_journal_entry(
        path,
        SPEC_SLUG,
        JournalEntry(
            kind="finding",
            scope="spec",
            id="sf1",
            created="2026-09-30T00:00:00",
            state="open",
            title="a spec-scope finding",
        ),
    )
    append_journal_entry(
        path,
        SPEC_SLUG,
        JournalEntry(
            kind="finding",
            scope="spec",
            id="sf1-resolved",
            created="2026-09-30T00:00:01",
            state="open",
            resolves="sf1",
            out_of_scope=True,
            title="resolves sf1: a spec-scope finding",
        ),
    )


def _plan_out_of_scope_finding(repo_root: Path) -> None:
    build_plan_journal(
        repo_root,
        SPEC_SLUG,
        [
            {"kind": "finding", "id": "pf1", "state": "open", "title": "a plan-scope finding"},
            {
                "kind": "finding",
                "id": "pf1-resolved",
                "resolves": "pf1",
                "state": "open",
                "out_of_scope": True,
                "title": "resolves pf1: a plan-scope finding",
            },
        ],
    )


def test_closeout_brief_orders_every_section_correctly(tmp_path: Path) -> None:
    _spec_file(tmp_path, with_test_plan=True)
    _plan_dir(tmp_path)
    _spec_out_of_scope_finding(tmp_path)
    _plan_out_of_scope_finding(tmp_path)

    brief = closeout_brief(tmp_path, _state())

    def idx(needle: str) -> int:
        pos = brief.find(needle)
        assert pos != -1, f"{needle!r} missing from:\n{brief}"
        return pos

    i_branch = idx(BRANCH)
    i_pr = idx(PR_URL)
    i_spec = idx(SPEC_REL)
    i_plan = idx(PLAN_REL)
    i_verify = idx(f"fr isolation verify-merge --branch {BRANCH}")
    i_stop = idx("STOP")
    i_test_plan = idx(f"Test Plan: {SPEC_REL}")
    i_status = idx("fr status")
    i_up = idx(f"fr isolation up --branch chore/archive-{SPEC_SLUG}")
    i_spec_finding = idx(f"  - spec/{SPEC_SLUG}/sf1: a spec-scope finding")
    i_plan_finding = idx(f"  - plan/{SPEC_SLUG}/pf1: a plan-scope finding")
    i_archive = idx(f"fr archive --branch {BRANCH} --issues ")
    i_housekeeping_pr = idx("housekeeping PR")
    i_down = idx(f"fr isolation down --branch {BRANCH}")

    assert (
        i_branch
        < i_pr
        < i_spec
        < i_plan
        < i_verify
        < i_stop
        < i_test_plan
        < i_status
        < i_up
        < i_spec_finding
        < i_plan_finding
        < i_archive
        < i_housekeeping_pr
        < i_down
    )


def _finding_lines(brief: str) -> list[str]:
    return [ln for ln in brief.splitlines() if ln.startswith("  - ") and "/" in ln.split(":")[0]]


def _archive_line(brief: str) -> str:
    return next(ln.strip() for ln in brief.splitlines() if "fr archive --branch" in ln)


def test_closeout_brief_lists_findings_and_files_them_inside_the_housekeeping_workspace(
    tmp_path: Path,
) -> None:
    """gh#621 (1) + R13: the brief is run from the base clone on the default
    branch, so the one `fr archive --issues` command (which writes the deferral
    records) comes after `fr isolation up --branch chore/archive-…`, and no
    per-finding `fr journal resolve` line is printed any more."""
    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)
    _spec_out_of_scope_finding(tmp_path)
    _plan_out_of_scope_finding(tmp_path)

    brief = closeout_brief(tmp_path, _state())

    i_up = brief.index("fr isolation up --branch chore/archive-")
    i_archive = brief.index(f"fr archive --branch {BRANCH} --issues ")
    assert "fr journal resolve" not in brief
    assert len(_finding_lines(brief)) == 2
    assert brief.count("fr archive --branch") == 1
    assert i_up < i_archive


def test_closeout_brief_archive_line_names_every_qid_and_the_way_to_file_none(
    tmp_path: Path,
) -> None:
    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)
    _spec_out_of_scope_finding(tmp_path)
    _plan_out_of_scope_finding(tmp_path)

    line = _archive_line(closeout_brief(tmp_path, _state()))

    assert line.startswith(
        f"fr archive --branch {BRANCH} --issues spec/{SPEC_SLUG}/sf1,plan/{SPEC_SLUG}/pf1"
    )
    assert "--no-issues" in line


def test_closeout_brief_archive_line_parses_against_the_real_cli(tmp_path: Path) -> None:
    """gh#621 (2): the printed command must be runnable as printed. Parsed
    against the real `fr archive` click signature, so a renamed option fails
    here too."""
    import shlex

    import typer
    from fr.cli import app

    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)
    _spec_out_of_scope_finding(tmp_path)
    _plan_out_of_scope_finding(tmp_path)

    line = _archive_line(closeout_brief(tmp_path, _state()))
    argv = shlex.split(line, comments=True)
    assert argv[:2] == ["fr", "archive"], line
    archive_cmd = typer.main.get_command(app).commands["archive"]  # type: ignore[attr-defined]
    ctx = archive_cmd.make_context("archive", argv[2:])
    assert ctx.params["branch"] == BRANCH
    assert ctx.params["issues"] == f"spec/{SPEC_SLUG}/sf1,plan/{SPEC_SLUG}/pf1"
    assert ctx.params["no_issues"] is False


def test_closeout_brief_under_tracking_none_keeps_the_plain_archive_line(tmp_path: Path) -> None:
    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)
    _plan_out_of_scope_finding(tmp_path)
    prof = tmp_path / ".devcontainer"
    prof.mkdir()
    (prof / "fr-profiles.yaml").write_text(
        "schema_version: 2\nprofiles:\n  dev:\n    purpose: x\ntracking: {type: none}\n"
    )

    brief = closeout_brief(tmp_path, _state())

    assert "no tracker is configured" in brief
    assert "--issues" not in brief and not _finding_lines(brief)
    assert f"fr archive --branch {BRANCH}   #" in brief


def test_closeout_brief_names_the_checkout_to_run_it_from(tmp_path: Path) -> None:
    """p4-r3: the brief itself (not just the transient handoff line the
    delivering session printed) must say where to run it from — the base
    clone, on the default branch, after merge, since the feature workspace
    the run happened in may already be reaped."""
    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)

    brief = closeout_brief(tmp_path, _state())

    assert str(tmp_path) in brief
    assert "default branch" in brief
    assert "may already be reaped" in brief or "may be reaped" in brief
    # verify-merge must be usable from that same repo root once the feature
    # workspace is gone.
    verify_idx = brief.index(f"fr isolation verify-merge --branch {BRANCH}")
    verify_line_end = brief.index("\n", verify_idx)
    assert "repo root" in brief[verify_idx:verify_line_end]


def test_closeout_brief_housekeeping_gives_exact_commands_on_a_new_branch(
    tmp_path: Path,
) -> None:
    """p4-r2: no free-floating "on a housekeeping branch" comment — an exact
    `fr isolation up --branch chore/archive-<slug>` command, run BEFORE `fr
    archive`, and an explicit warning against archiving inside the merged
    feature workspace (`state.branch`)."""
    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)

    brief = closeout_brief(tmp_path, _state())

    housekeeping_branch = f"chore/archive-{SPEC_SLUG}"
    i_up = brief.index(f"fr isolation up --branch {housekeeping_branch}")
    i_archive = brief.index(f"fr archive --branch {BRANCH}")
    assert i_up < i_archive
    # The warning names the feature branch by value, not just "this
    # workspace" — a fresh session has no notion of "this" the transcript did.
    up_line_end = brief.index("\n", i_up)
    assert BRANCH in brief[i_up:up_line_end] or BRANCH in brief[i_archive : i_archive + 200]
    assert "commit" in brief.lower() and "push" in brief.lower()


def test_closeout_brief_omits_test_plan_line_when_the_spec_has_none(tmp_path: Path) -> None:
    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)

    brief = closeout_brief(tmp_path, _state())

    assert "Test Plan" not in brief


def test_closeout_brief_refuses_a_run_whose_deliver_is_not_done(tmp_path: Path) -> None:
    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)

    with pytest.raises(CloseoutNotReadyError, match="deliver"):
        closeout_brief(tmp_path, _state(deliver_done=False))


# --- p4-r4: a resolved out-of-scope finding drops out of the brief ----------


def test_closeout_brief_excludes_a_finding_later_deferred_with_a_tracker(tmp_path: Path) -> None:
    """An out-of-scope finding, subsequently resolved `deferred --tracked-by
    <#N>` (the exact next step the brief itself tells the operator to run),
    must not still be listed — its effective state is now `deferred`, not
    `out-of-scope` (`effective_finding_states`' fold, last record wins)."""
    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)
    _plan_out_of_scope_finding(tmp_path)
    build_plan_journal(
        tmp_path,
        SPEC_SLUG,
        [
            {
                "kind": "finding",
                "id": "pf1-deferred",
                "resolves": "pf1",
                "state": "open",
                "tracked_by": "#123",
                "title": "resolves pf1: a plan-scope finding",
            },
        ],
    )

    brief = closeout_brief(tmp_path, _state())

    assert "pf1" not in brief


def test_closeout_brief_excludes_a_finding_later_fixed_by_the_operator(tmp_path: Path) -> None:
    """Same fold, the other closing state: `fixed --answered-by operator`
    (required to close an out-of-scope finding as fixed rather than
    deferred, per `unauthorized_fixes`) also drops it from the list."""
    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)
    _plan_out_of_scope_finding(tmp_path)
    build_plan_journal(
        tmp_path,
        SPEC_SLUG,
        [
            {
                "kind": "finding",
                "id": "pf1-fixed",
                "resolves": "pf1",
                "state": "fixed",
                "answered_by": "operator",
                "title": "resolves pf1: a plan-scope finding",
            },
        ],
    )

    brief = closeout_brief(tmp_path, _state())

    assert "pf1" not in brief


# --- p4-r5: PR / spec / plan fallbacks ---------------------------------------


def test_closeout_brief_reports_no_pr_recorded_when_deliver_emitted_none(tmp_path: Path) -> None:
    _spec_file(tmp_path, with_test_plan=False)
    _plan_dir(tmp_path)
    state = RunState(
        run="r1",
        workflow="fr-goal@1",
        branch=BRANCH,
        started="2026-09-30T00:00:00Z",
        cursor="deliver",
        steps={
            "brainstorm": StepRecord(state="done", emitted={"spec": SPEC_REL}),
            "plan": StepRecord(state="done", emitted={"plan": PLAN_REL}),
            "deliver": StepRecord(state="done"),  # no `pr` ever emitted
        },
    )

    brief = closeout_brief(tmp_path, state)

    assert "PR: (none recorded)" in brief


def test_closeout_brief_omits_spec_and_plan_lines_when_the_run_never_emitted_them(
    tmp_path: Path,
) -> None:
    """The `if spec_path:` / `if plan_path:` guards: a run whose `deliver`
    only emitted `pr` must still print a usable brief — no spec/plan lines,
    no Test Plan line, no out-of-scope journal lines — but the housekeeping
    block (§D: always printed) and `fr archive --branch <b>` still appear,
    named off the run id since no plan was ever emitted."""
    state = RunState(
        run="r1",
        workflow="fr-goal@1",
        branch=BRANCH,
        started="2026-09-30T00:00:00Z",
        cursor="deliver",
        steps={"deliver": StepRecord(state="done", emitted={"pr": PR_URL})},
    )

    brief = closeout_brief(tmp_path, state)

    assert "spec:" not in brief
    assert "plan:" not in brief
    assert "Test Plan" not in brief
    assert f"fr archive --branch {BRANCH}" in brief
    assert "fr isolation up --branch chore/closeout-r1" in brief
    assert "housekeeping PR" in brief
    assert "chore: close out feat/x" in brief
    assert PR_URL in brief
    assert f"fr isolation verify-merge --branch {BRANCH}" in brief
    assert "fr status" in brief
    assert f"fr isolation down --branch {BRANCH}" in brief


def test_closeout_brief_run_from_a_linked_worktree_names_the_primary_checkout(
    tmp_path: Path,
) -> None:
    """Dogfooding #610's own deliver: inside an fr workspace, repo_root is the
    LINKED feature worktree — the one closeout reaps. The brief must name the
    primary checkout (the base clone), never the worktree."""
    import subprocess

    main = tmp_path / "base"
    main.mkdir()
    git = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q", "-b", "main", str(main)], check=True)
    (main / "README.md").write_text("x\n")
    subprocess.run([*git, "-C", str(main), "add", "-A"], check=True)
    subprocess.run([*git, "-C", str(main), "commit", "-q", "-m", "init"], check=True)
    wt = tmp_path / "feature-wt"
    subprocess.run(
        [*git, "-C", str(main), "worktree", "add", "-q", "-b", "feat/x", str(wt)], check=True
    )
    _spec_file(wt, with_test_plan=False)
    _plan_dir(wt)

    brief = closeout_brief(wt, _state())

    assert f"Run this from {main.resolve()}" in brief
    assert str(wt) not in brief.split("Closeout, in order:")[0]


def test_primary_checkout_falls_back_to_the_given_root_outside_git(tmp_path: Path) -> None:
    from fr.run.closeout import primary_checkout

    assert primary_checkout(tmp_path) == tmp_path


def test_primary_checkout_resolves_a_relocated_git_dir_primary_from_its_linked_worktree(
    tmp_path: Path,
) -> None:
    """pd-r1: a primary whose `.git` was relocated with `--separate-git-dir`
    (the common-dir basename isn't literally `.git`) must still resolve to
    the PRIMARY checkout when called from a linked worktree cut off it — not
    the worktree itself, which the basename == ".git" guard used to fall
    back to. `git worktree list --porcelain`'s first entry is the main
    worktree; for a relocated git-dir it reports the git-dir path itself
    (a real git limitation, verified live against git 2.53.0), which is
    recovered here as the checkout containing it. The relocated dir is
    nested under `primary` (an absolute path, never a relative one — a
    relative `--separate-git-dir` resolves against the *process* cwd, not
    against the target directory, and would otherwise plant a git-dir
    inside this very repo)."""
    import subprocess

    from fr.run.closeout import primary_checkout

    git = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]
    primary = tmp_path / "primary"
    primary.mkdir()
    gitdir = primary / "elsewhere-gitdir"
    subprocess.run(
        [*git, "init", "-q", "-b", "main", f"--separate-git-dir={gitdir}", str(primary)],
        check=True,
    )
    subprocess.run(
        [*git, "-C", str(primary), "commit", "-q", "--allow-empty", "-m", "init"], check=True
    )
    wt = tmp_path / "wt"
    subprocess.run(
        [*git, "-C", str(primary), "worktree", "add", "-q", "-b", "feat/x", str(wt)], check=True
    )

    assert primary_checkout(wt) == primary.resolve()


def test_primary_checkout_falls_back_to_repo_root_for_a_bare_repository(tmp_path: Path) -> None:
    """pd-r1: a bare repo's `git worktree list --porcelain` first entry is
    marked `bare` (no actual checkout) — fall back to `repo_root` rather
    than naming a nonexistent working tree."""
    import subprocess

    from fr.run.closeout import primary_checkout

    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)

    assert primary_checkout(bare) == bare


def test_closeout_brief_without_a_plan_still_resolves_off_the_default_branch(
    tmp_path: Path,
) -> None:
    """gh#621 (1), the no-plan edge: with no plan the housekeeping branch is
    named off the run id (`chore/closeout-<run-id>`) rather than a plan slug,
    but the housekeeping block (§D: always printed) and `fr archive --branch
    <b>` still appear, and an out-of-scope spec finding still needs a
    workspace to be committed in — never the default branch the brief is run
    from."""
    _spec_file(tmp_path, with_test_plan=False)
    _spec_out_of_scope_finding(tmp_path)
    state = RunState(
        run="r1",
        workflow="fr-goal@1",
        branch=BRANCH,
        started="2026-09-30T00:00:00Z",
        cursor="deliver",
        steps={
            "brainstorm": StepRecord(state="done", emitted={"spec": SPEC_REL}),
            "deliver": StepRecord(state="done", emitted={"pr": PR_URL}),
        },
    )

    brief = closeout_brief(tmp_path, state)

    i_up = brief.index("fr isolation up --branch chore/closeout-r1")
    i_finding = brief.index(f"  - spec/{SPEC_SLUG}/sf1: a spec-scope finding")
    i_archive = brief.index(f"fr archive --branch {BRANCH} --issues spec/{SPEC_SLUG}/sf1")
    i_push = brief.index("git push -u origin chore/closeout-r1")
    assert i_up < i_finding < i_archive < i_push
    assert "chore: close out feat/x" in brief
