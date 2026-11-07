"""Commit subject templates (spec 2026-11-04-repo-feature-settings R14).

`git.commit.with_issue` / `without_issue` over `{type}`, `{scope}`, `{summary}`,
`{issue}`. fr's own commits go through ONE seam (`fr.artifacts.commit.commit_paths`,
plus the few committers that run git themselves), and with the default templates
every `chore(fr): …` subject fr writes today is byte-identical: the release
cross-check and the usage parsers read them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fr.artifacts.commit import commit_paths, migration_commit_message
from fr.git_policy.templates import (
    fr_message,
    parse_subject,
    render_subject,
    subject_matches,
    subject_ok,
)
from fr.records_commit import commit_records
from fr.settings.model import parse_settings

from tests.unit.settings_repo import git, land_on_main, make_repo

DEFAULTS = parse_settings({}, source="test")
CUSTOM = parse_settings(
    {
        "git": {
            "commit": {
                "with_issue": "[{scope}] {summary} #{issue}",
                "without_issue": "[{scope}] {summary}",
            }
        }
    },
    source="test",
)

# One subject per producer of `chore(fr): …` in packages/fr/src (see
# `test_every_chore_fr_producer_goes_through_the_seam` for the list's guard).
PRODUCER_SUBJECTS = (
    "chore(fr): migrate 2 artifacts to fr 6.1.0",
    "chore(fr): record",
    "chore(fr): verification set — d1 (docs/superpowers/specs/s.md)",
    "chore(fr): verification set — d1: row -> candidate",
    "chore(fr): run r1 — branch renamed to feat/x by batch adopt",
    "chore(fr): scaffold dev devcontainer profile",
    "chore(fr): render the agents artifact",
    "chore(fr): journal plan/p — discovery d1",
    "chore(fr): journal plan/p — finding f1",
    "chore(fr): journal plan/p — file f1",
    "chore(fr): run r1 — adopt, supersedes r0",
    "chore(fr): run r1 — resolve implement-phase phase/4 done",
    "chore(fr): acceptance — row-a status ci -> walked",
    "chore(fr): acceptance — add row-a",
    "chore(fr): acceptance init",
    "chore(fr): acceptance init --refresh-ci",
    "chore(fr): plan p — tick",
    "chore(fr): closeout s — Test Plan step(s) 1 passed",
    "chore(fr): archive merged plans (debt sweep)",
    "chore(fr): migrate artifacts",
)


def _feature(repo: Path, branch: str = "feat/x") -> Path:
    git(repo, "switch", "-q", "-c", branch)
    return repo


# --- render / match ----------------------------------------------------------


def test_render_uses_without_issue_when_there_is_no_issue() -> None:
    assert render_subject(DEFAULTS, "chore", "fr", "hello", None) == "chore(fr): hello"


def test_render_uses_with_issue_iff_an_issue_is_given() -> None:
    assert render_subject(DEFAULTS, "chore", "fr", "hello", 12) == "chore(fr): hello (#12)"
    assert render_subject(CUSTOM, "feat", "api", "x", 3) == "[api] x #3"
    assert render_subject(CUSTOM, "feat", "api", "x", None) == "[api] x"


def test_subject_matches_accepts_a_rendered_subject_and_rejects_others() -> None:
    template = DEFAULTS.git.commit.without_issue
    assert subject_matches(template, "feat(run): record the issue")
    assert not subject_matches(template, "record the issue")
    assert not subject_matches(template, "feat: no scope")
    assert subject_matches(CUSTOM.git.commit.without_issue, "[fr] hello")
    assert not subject_matches(CUSTOM.git.commit.without_issue, "chore(fr): hello")


def test_a_template_with_regex_metacharacters_matches_literally() -> None:
    assert subject_matches("{type}.*({scope}) {summary}", "a.*(b) c")
    assert not subject_matches("{type}.*({scope}) {summary}", "aXX(b) c")


def test_parse_subject_returns_the_placeholder_values() -> None:
    parsed = parse_subject(DEFAULTS.git.commit.with_issue, "chore(fr): run r1 — x (#9)")
    assert parsed == {"type": "chore", "scope": "fr", "summary": "run r1 — x", "issue": "9"}
    assert parse_subject(DEFAULTS.git.commit.with_issue, "chore(fr): no issue") is None


def test_merge_commits_are_exempt_by_parent_count() -> None:
    assert subject_ok(DEFAULTS, "Merge branch 'main' into feat/x", parents=2, issue=None)
    assert not subject_ok(DEFAULTS, "Merge branch 'main' into feat/x", parents=1, issue=None)
    assert subject_ok(DEFAULTS, "feat(x): y (#4)", parents=1, issue=4)
    assert not subject_ok(DEFAULTS, "feat(x): y", parents=1, issue=4)


# --- the seam: fr's own commits ----------------------------------------------


@pytest.mark.parametrize("subject", PRODUCER_SUBJECTS)
def test_default_templates_keep_every_fr_subject_byte_identical(
    tmp_path: Path, subject: str
) -> None:
    repo = _feature(make_repo(tmp_path))
    message = f"{subject}\n\nbody line\n"
    assert fr_message(repo, message) == message


def test_the_migration_message_is_unchanged_by_the_seam(tmp_path: Path) -> None:
    from fr.artifacts.runner import MigrationReport

    repo = _feature(make_repo(tmp_path))
    message = migration_commit_message(MigrationReport(dry_run=False), fr_version="6.1.0")
    assert fr_message(repo, message) == message


def test_commit_records_writes_todays_subject_with_defaults(tmp_path: Path) -> None:
    repo = _feature(make_repo(tmp_path))
    (repo / "a.txt").write_text("a\n")
    outcome = commit_records(repo, [Path("a.txt")], "chore(fr): journal plan/p — discovery d1")
    assert outcome.committed, outcome.reason
    assert (
        git(repo, "log", "-1", "--format=%s").strip() == "chore(fr): journal plan/p — discovery d1"
    )


def test_a_custom_template_changes_frs_subjects_through_the_one_seam(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, 'git:\n  commit:\n    without_issue: "[{scope}] {summary}"\n')
    _feature(repo)
    (repo / "a.txt").write_text("a\n")
    outcome = commit_paths(
        repo, [Path("a.txt")], "chore(fr): journal plan/p — discovery d1\n\nbody\n"
    )
    assert outcome.committed, outcome.reason
    assert (
        git(repo, "log", "-1", "--format=%B").strip()
        == "[fr] journal plan/p — discovery d1\n\nbody"
    )


def test_a_message_fr_did_not_write_is_left_alone(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, 'git:\n  commit:\n    without_issue: "[{scope}] {summary}"\n')
    _feature(repo)
    assert fr_message(repo, "chore(ops): x DevOps stage 1") == "chore(ops): x DevOps stage 1"


def test_the_runs_issue_selects_the_with_issue_template(tmp_path: Path) -> None:
    repo = _feature(make_repo(tmp_path))
    runs = repo / "docs" / "superpowers" / "runs"
    runs.mkdir(parents=True)
    (runs / "r1.yaml").write_text(
        "schema_version: 11\nrun: r1\nworkflow: fr-goal@1\nbranch: feat/x\n"
        "started: '2026-11-07T00:00:00Z'\ncursor: a\nsteps:\n  a:\n    state: pending\n"
        "issue: 42\n"
    )
    assert fr_message(repo, "chore(fr): run r1 — start") == "chore(fr): run r1 — start (#42)"


def test_another_branchs_run_issue_is_not_used(tmp_path: Path) -> None:
    repo = _feature(make_repo(tmp_path))
    runs = repo / "docs" / "superpowers" / "runs"
    runs.mkdir(parents=True)
    (runs / "r1.yaml").write_text(
        "schema_version: 11\nrun: r1\nworkflow: fr-goal@1\nbranch: feat/other\n"
        "started: '2026-11-07T00:00:00Z'\ncursor: a\nsteps:\n  a:\n    state: pending\n"
        "issue: 42\n"
    )
    assert fr_message(repo, "chore(fr): run r1 — start") == "chore(fr): run r1 — start"


def test_an_unreadable_policy_refuses_the_commit(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, "git: [not a mapping\n")
    _feature(repo)
    (repo / "a.txt").write_text("a\n")
    before = git(repo, "rev-parse", "HEAD")
    outcome = commit_paths(repo, [Path("a.txt")], "chore(fr): journal plan/p — discovery d1")
    assert not outcome.committed
    assert "settings" in outcome.reason
    assert git(repo, "rev-parse", "HEAD") == before


_NOT_A_PRODUCER = {
    "git_policy/templates.py": "the seam itself",
    "artifacts/trigger.py": "prints the subject commit_paths returned; its literal is a label",
    "git_policy/push.py": "recognises today's migration subject; writes no subject of its own",
}


def test_every_chore_fr_producer_goes_through_the_seam(repo_root: Path) -> None:
    """A module that writes a `chore(fr): …` subject either commits through
    `commit_paths`/`commit_records` (which apply the template) or calls `fr_message`
    itself. A new producer that runs git directly would bypass R14 silently."""
    src = repo_root / "packages" / "fr" / "src" / "fr"
    literal = re.compile(r"""f?["']chore\(fr\): """)
    seams = ("commit_paths", "commit_records", "fr_message", "record_target", "RecordTarget")
    offenders: list[str] = []
    for path in sorted(src.rglob("*.py")):
        text = path.read_text()
        rel = path.relative_to(src).as_posix()
        if not literal.search(text) or rel in _NOT_A_PRODUCER:
            continue
        if not any(seam in text for seam in seams):
            offenders.append(rel)
    assert offenders == [], offenders
