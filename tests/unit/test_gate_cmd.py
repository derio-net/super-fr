"""`fr gate pass` — R14's explicit route (spec 2026-10-14-exit-gates §D).

It swaps a PR's `gate:<g>` for `gate:<g>-passed` and comments what passed it, through
the forge adapter, only with `--yes`; it refuses an unknown gate, a gate that holds no
merge (not post-merge), and a PR that does not carry `gate:<g>`; and it prints the
release dispatch, so a final follows the last pass (R20). The forge is faked.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.artifacts import trigger
from fr.cli import app
from fr.commands import gate_cmd
from fr.verification.labels import gate_pass_comment
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

REPO = "derio-net/super-fr"


def _fake(labels: list[str], state: str = "MERGED") -> FakeGhClient:
    fake = FakeGhClient()
    fake.prs[(REPO, 5)] = {
        "state": state, "draft": False, "head_ref": "feat/x", "base_ref": "main",
        "mergeable": "UNKNOWN", "title": "t", "body": "b", "labels": list(labels),
    }  # fmt: skip
    return fake


@pytest.fixture
def forge(monkeypatch: pytest.MonkeyPatch) -> Any:
    holder: dict[str, Any] = {"urls": []}

    def client(url: str) -> FakeGhClient:
        holder["urls"].append(url)
        return holder["fake"]

    def install(labels: list[str], state: str = "MERGED") -> FakeGhClient:
        holder["fake"] = _fake(labels, state)
        holder["fake"].urls = holder["urls"]
        monkeypatch.setattr(gate_cmd, "client_for_url", client)
        monkeypatch.setattr("fr._hosts.origin_slug", lambda root: None)
        return holder["fake"]

    return install


@pytest.fixture
def keep_forge(forge: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """`forge`, with this checkout's origin naming the PR's repo: a checkout `--keep` accepts."""

    def install(labels: list[str]) -> FakeGhClient:
        fake = forge(labels)
        monkeypatch.setattr("fr.archive_followups.owed_identity", lambda *a, **k: (REPO, ""))
        return fake

    return install


def _pass(*args: str) -> Any:
    return CliRunner().invoke(
        app, ["gate", "pass", "--repo", REPO, "--pr", "5", "--notes", "walked live", *args]
    )


def _writes(fake: FakeGhClient) -> list[str]:
    return [c[0] for c in fake.calls if c[0] in ("edit_pr_labels", "comment_pr", "ensure_labels")]


def test_without_yes_it_prints_the_swap_and_the_comment_and_writes_nothing(forge: Any) -> None:
    fake = forge(["gate:tester", "verification:live"])

    result = _pass("--gate", "tester")

    assert result.exit_code == 0, result.output
    assert "gate:tester -> gate:tester-passed" in result.output
    assert "walked live" in result.output
    assert "re-run with --yes" in result.output
    assert _writes(fake) == []


def test_with_yes_it_swaps_the_label_and_comments(forge: Any) -> None:
    fake = forge(["gate:tester"])

    result = _pass("--gate", "tester", "--yes")

    assert result.exit_code == 0, result.output
    (edit,) = [c[1] for c in fake.calls if c[0] == "edit_pr_labels"]
    assert (edit["add"], edit["remove"]) == (
        frozenset({"gate:tester-passed"}),
        frozenset({"gate:tester"}),
    )
    (comment,) = [c[1] for c in fake.calls if c[0] == "comment_pr"]
    assert comment["pr"] == 5 and "tester" in comment["body"] and "walked live" in comment["body"]
    assert f"gh workflow run release.yml --repo {REPO}" in result.output


@pytest.mark.parametrize(
    ("gate", "labels", "why"),
    [
        ("qa", ["gate:tester"], "unknown gate"),
        ("owner", ["gate:owner"], "not a post-merge gate"),
        ("devops", ["gate:tester"], "does not carry gate:devops"),
    ],
)
def test_it_refuses_what_is_not_a_held_post_merge_gate(
    forge: Any, gate: str, labels: list[str], why: str
) -> None:
    fake = forge(labels)

    result = _pass("--gate", gate, "--yes")

    assert result.exit_code == 2, result.output
    assert why in result.output
    assert _writes(fake) == []


def test_gate_is_a_read_only_command() -> None:
    assert "gate" in trigger.READ_ONLY_COMMANDS


# ------------------------------------------------------------ review p4-r4..r9


def test_p4_r5_it_refuses_a_pr_that_is_not_merged(forge: Any) -> None:
    fake = forge(["gate:tester"], state="OPEN")

    result = _pass("--gate", "tester", "--yes")

    assert result.exit_code == 2, result.output
    assert "is OPEN, not merged" in result.output
    assert _writes(fake) == []


def test_p4_r9_no_release_command_while_another_gate_still_holds(forge: Any) -> None:
    forge(["gate:tester", "gate:devops"])

    result = _pass("--gate", "tester", "--yes")

    assert result.exit_code == 0, result.output
    assert "gh workflow run" not in result.output
    assert "gate:devops still holds" in result.output


def test_p4_r6_the_host_is_the_named_one_or_the_checkouts_origin(
    forge: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = forge(["gate:tester"])
    assert _pass("--gate", "tester", "--host", "ghe.example.com").exit_code == 0
    assert fake.urls[-1] == f"https://ghe.example.com/{REPO}"

    monkeypatch.setattr("fr._hosts.origin_slug", lambda root: REPO)
    monkeypatch.setattr("fr._hosts.origin_hostname", lambda root: "git.example.org")
    assert _pass("--gate", "tester").exit_code == 0
    assert fake.urls[-1] == f"https://git.example.org/{REPO}"


def test_p4_r4_pass_gate_comments_first_and_never_twice() -> None:
    from fr.verification.labels import gate_pass_comment, pass_gate

    fake = _fake(["gate:tester"])
    pass_gate(fake, REPO, 5, "tester", why="walked")
    order = [c[0] for c in fake.calls if c[0] in ("comment_pr", "edit_pr_labels")]
    assert order == ["comment_pr", "edit_pr_labels"]

    again = _fake(["gate:tester"])
    again.issue_comments[(REPO, 5)] = [{"body": gate_pass_comment("tester", "walked")}]
    pass_gate(again, REPO, 5, "tester", why="walked")
    assert [c[0] for c in again.calls if c[0] == "comment_pr"] == []
    assert [c[0] for c in again.calls if c[0] == "edit_pr_labels"] == ["edit_pr_labels"]

    failing = _fake(["gate:tester"])
    failing.fail_on_mutation = 0  # the comment
    with pytest.raises(Exception, match="configured failure"):
        pass_gate(failing, REPO, 5, "tester", why="walked")
    assert [c[0] for c in failing.calls if c[0] == "edit_pr_labels"] == []


# --- `fr gate backfill` (spec 2026-11-01-gate-backfill) -----------------------------------

BACKFILL_REPO = "example-org/widgets"
FORGE_READS = frozenset({
    "list_issues", "pr_view", "list_prs_by_head", "prs_for_commit", "list_linked_prs",
    "viewer_login", "authenticated_login", "view_issue", "file_exists", "list_dir", "read_file",
    "open_pr_in_repo", "open_pr_for_head", "list_open_issues_with_body", "list_issue_comments",
    "base_rules", "required_check_names", "commit_checks", "label_exists", "pr_required_checks",
    "closing_ref", "repo_merge_methods", "repo_visibility",
})  # fmt: skip


def _only_reads(fake: FakeGhClient) -> list[str]:
    """Every recorded forge call that is not a known READ (an allowlist: a new write verb the
    dry run grew would show up here, a denylist would miss it)."""
    return [c[0] for c in fake.calls if c[0] not in FORGE_READS]


def _backfill_repo(tmp_path: Path) -> Path:
    import subprocess

    root = tmp_path / "widgets"
    root.mkdir()
    for args in (
        ["init", "-q", "-b", "main"],
        ["remote", "add", "origin", f"https://github.com/{BACKFILL_REPO}.git"],
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    from tests.unit.acceptance_helpers import write_fragments

    write_fragments(root, [], repo=BACKFILL_REPO, feature="legacy")
    return root


@pytest.fixture
def backfill_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    root = _backfill_repo(tmp_path)
    fake = FakeGhClient()
    monkeypatch.setattr(gate_cmd, "client_for_url", lambda url: fake)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(root)
    return root, fake


def test_backfill_is_a_gate_verb_and_dry_run_writes_nothing(backfill_env: Any) -> None:
    _root, fake = backfill_env

    helped = CliRunner().invoke(app, ["gate", "backfill", "--help"])
    assert helped.exit_code == 0, helped.output
    for flag in ("--yes", "--plan", "--from"):
        assert flag in helped.output

    result = CliRunner().invoke(app, ["gate", "backfill"])

    assert result.exit_code == 0, result.output
    assert _only_reads(fake) == []


def test_the_dry_run_writes_the_plan_file_keeps_edited_decisions_and_never_the_forge(
    backfill_env: Any, tmp_path: Path
) -> None:
    import yaml

    from tests.unit.gatebackfill_fixtures import commit_at, row, write_matrix

    root, fake = backfill_env
    write_matrix(root, [row("r1", "walk-owed")])
    commit_at(root, "seed", "2026-10-30T00:00:00+00:00")
    plan = tmp_path / "home" / ".cache/fr/gate-backfill/example-org--widgets/plan.yaml"

    first = CliRunner().invoke(app, ["gate", "backfill"])

    assert first.exit_code == 0, first.output
    assert "row:r1" in first.output and "gate=tester" in first.output
    data = yaml.safe_load(plan.read_text())
    assert data["repo"] == BACKFILL_REPO
    [entry] = data["entries"]
    assert (entry["key"], entry["decision"]) == ("row:r1", "owed")

    entry["decision"] = "park"
    plan.write_text(yaml.safe_dump(data))
    again = CliRunner().invoke(app, ["gate", "backfill"])

    assert again.exit_code == 0, again.output
    assert yaml.safe_load(plan.read_text())["entries"][0]["decision"] == "park"
    assert "Parked (1)" in again.output
    assert _only_reads(fake) == []


@pytest.mark.parametrize("gate", ["tester", "devops"])
def test_gh1322_the_dry_run_says_a_passed_gate_is_tracked_only_and_never_re_gated(
    backfill_env: Any, tmp_path: Path, gate: str
) -> None:
    import yaml

    root, fake = backfill_env
    fake.add_pr(BACKFILL_REPO, 41, state="MERGED", labels=[f"gate:{gate}-passed"])
    fake.add_pr(BACKFILL_REPO, 42, state="MERGED", labels=[])
    manifest = tmp_path / "m.yaml"
    manifest.write_text(yaml.safe_dump({"schema": 1, "items": [
        {"key": "row:done-gate", "kind": "walk", "title": "a", "pr": 41, "gate": gate},
        {"key": "row:held-gate", "kind": "walk", "title": "b", "pr": 42, "gate": gate},
    ]}))  # fmt: skip
    plan = tmp_path / "home" / ".cache/fr/gate-backfill/example-org--widgets/plan.yaml"

    result = CliRunner().invoke(app, ["gate", "backfill", "--from", str(manifest)])

    assert result.exit_code == 0, result.output
    [done] = [ln for ln in result.output.splitlines() if "row:done-gate" in ln]
    [held] = [ln for ln in result.output.splitlines() if "row:held-gate" in ln]
    assert f"gate:{gate} already passed on PR #41: tracked only, never re-gated" in done
    assert "-> owed" in done and "already passed" not in held
    entries = {e["key"]: e for e in yaml.safe_load(plan.read_text())["entries"]}
    assert entries["row:done-gate"]["gate_passed"] is True
    assert entries["row:held-gate"]["gate_passed"] is False
    assert _only_reads(fake) == []
    assert [c for c in fake.calls if c[0] == "pr_view"] == [
        ("pr_view", {"repo": BACKFILL_REPO, "number": 41}),
        ("pr_view", {"repo": BACKFILL_REPO, "number": 42}),
    ]  # the delivery read is reused: no second read per PR


@pytest.mark.parametrize(("other", "gate"), [("devops", "tester"), ("tester", "devops")])
def test_gh1322_the_dry_run_does_not_call_another_gates_pass_this_ones(
    backfill_env: Any, tmp_path: Path, other: str, gate: str
) -> None:
    import yaml

    root, fake = backfill_env
    fake.add_pr(BACKFILL_REPO, 41, state="MERGED", labels=[f"gate:{other}-passed"])
    manifest = tmp_path / "m.yaml"
    manifest.write_text(yaml.safe_dump({"schema": 1, "items": [
        {"key": "row:cross-gate", "kind": "walk", "title": "a", "pr": 41, "gate": gate},
    ]}))  # fmt: skip
    plan = tmp_path / "home" / ".cache/fr/gate-backfill/example-org--widgets/plan.yaml"

    result = CliRunner().invoke(app, ["gate", "backfill", "--from", str(manifest)])

    assert result.exit_code == 0, result.output
    [line] = [ln for ln in result.output.splitlines() if "row:cross-gate" in ln]
    assert "-> owed" in line and "already passed" not in line
    [e] = yaml.safe_load(plan.read_text())["entries"]
    assert e["gate_passed"] is False


def test_backfill_refuses_a_repo_that_disagrees_with_origin_and_yes_before_apply(
    backfill_env: Any,
) -> None:
    bad = CliRunner().invoke(app, ["gate", "backfill", "--repo", "example-org/other"])
    assert bad.exit_code == 2 and "disagrees" in bad.output
    yes = CliRunner().invoke(app, ["gate", "backfill", "--yes"])
    assert yes.exit_code == 2 and "no plan file" in yes.output


def test_p1_r8_an_unwritable_plan_path_is_an_exit_2_refusal_not_a_traceback(
    backfill_env: Any, tmp_path: Path
) -> None:
    blocker = tmp_path / "a-file"
    blocker.write_text("x")

    result = CliRunner().invoke(app, ["gate", "backfill", "--plan", str(blocker / "plan.yaml")])

    assert result.exit_code == 2, result.output
    assert "fr gate backfill:" in result.output
    assert "Traceback" not in result.output and not isinstance(result.exception, OSError)


def _applied_env(backfill_env: Any, tmp_path: Path) -> tuple[Any, FakeGhClient, Path]:
    """A repo whose manifest names an audit gap delivered by merged PR 12; dry-run once."""
    from tests.unit.gatebackfill_fixtures import commit_at, row, write_matrix

    root, fake = backfill_env
    write_matrix(root, [row("r1", "manual")])
    commit_at(root, "seed", "2026-10-30T00:00:00+00:00")
    manifest = tmp_path / "m.yaml"
    manifest.write_text(
        "schema: 1\nitems:\n"
        "  - {key: 'plan:2026-04-02-fleet#p3', kind: audit-gap, title: fleet,"
        " pr: 12, gate: devops}\n"
    )
    fake.add_pr(BACKFILL_REPO, 12, state="MERGED", head_ref="feat/r1")
    first = CliRunner().invoke(app, ["gate", "backfill", "--from", str(manifest)])
    assert first.exit_code == 0, first.output
    assert _only_reads(fake) == []
    return root, fake, manifest


def test_yes_applies_the_plan_once_and_a_second_run_writes_nothing(
    backfill_env: Any, tmp_path: Path
) -> None:
    _root, fake, manifest = _applied_env(backfill_env, tmp_path)
    args = ["gate", "backfill", "--from", str(manifest), "--yes"]

    result = CliRunner().invoke(app, args)

    assert result.exit_code == 0, result.output
    assert fake.pr_labels[(BACKFILL_REPO, 12)] == {"gate:devops"}
    assert fake.issues[(BACKFILL_REPO, 1)].labels == {"fr:owed"}
    before = fake.attempted_mutations
    again = CliRunner().invoke(app, args)
    assert again.exit_code == 0, again.output
    assert fake.attempted_mutations == before


def test_yes_under_tracking_none_labels_the_pr_only(backfill_env: Any, tmp_path: Path) -> None:
    root, fake, manifest = _applied_env(backfill_env, tmp_path)
    (root / ".devcontainer").mkdir()
    (root / ".devcontainer" / "fr-profiles.yaml").write_text(
        "schema_version: 2\ntracking: {type: none}\n"
    )

    result = CliRunner().invoke(app, ["gate", "backfill", "--from", str(manifest), "--yes"])

    assert result.exit_code == 0, result.output
    assert fake.pr_labels[(BACKFILL_REPO, 12)] == {"gate:devops"} and not fake.issues


def test_yes_under_forge_labels_off_refuses_before_any_write(
    backfill_env: Any, tmp_path: Path
) -> None:
    """spec 2026-11-04-repo-feature-settings R9: a backfill's one write is the PR's gate
    label, so under `forge.labels: off` it writes nothing and names the setting."""
    import subprocess

    root, fake, manifest = _applied_env(backfill_env, tmp_path)
    (root / ".fr").mkdir()
    (root / ".fr" / "settings.yaml").write_text("forge:\n  labels: 'off'\n")
    for args in (
        ["add", "-A"],
        ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "quiet"],
        ["update-ref", "refs/remotes/origin/main", "HEAD"],  # as a push leaves it
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    before = fake.attempted_mutations
    result = CliRunner().invoke(app, ["gate", "backfill", "--from", str(manifest), "--yes"])

    assert result.exit_code == 2, result.output
    assert "forge.labels: off" in result.output and "nothing was written" in result.output
    assert fake.attempted_mutations == before and not fake.issues


def test_yes_refuses_an_unreadable_services_declaration_before_any_write(
    backfill_env: Any, tmp_path: Path
) -> None:
    root, fake, manifest = _applied_env(backfill_env, tmp_path)
    (root / ".devcontainer").mkdir()
    (root / ".devcontainer" / "fr-profiles.yaml").write_text(": : not yaml [\n")

    result = CliRunner().invoke(app, ["gate", "backfill", "--from", str(manifest), "--yes"])

    assert result.exit_code == 2 and "services declaration" in result.output
    assert fake.attempted_mutations == 0


def test_a_bare_owed_on_an_open_issue_key_is_refused_at_the_dry_run(
    backfill_env: Any, tmp_path: Path
) -> None:
    """p2-r2: an open `issue:` candidate files no tracker, so `owed` is only valid as `adopt`."""
    import yaml

    _root, fake = backfill_env
    plan = tmp_path / "home" / ".cache/fr/gate-backfill/example-org--widgets/plan.yaml"
    fake.add_issue(BACKFILL_REPO, 8, labels={"fr:owed"}, body="please do it")
    fake.issue_authors[(BACKFILL_REPO, 8)] = "some-stranger"

    assert CliRunner().invoke(app, ["gate", "backfill"]).exit_code == 0
    data = yaml.safe_load(plan.read_text())
    data["entries"][0]["decision"] = "owed"
    plan.write_text(yaml.safe_dump(data))

    result = CliRunner().invoke(app, ["gate", "backfill"])

    assert f"issue:{BACKFILL_REPO}#8" in result.output
    assert result.exit_code == 2, result.output
    assert "adopt it" in result.output and "give the manifest entry an issue:" in result.output


# --- P3.T2: a pass closes the PR's backfill trackers (spec gate-backfill §H, R12) ------------


def _with_tracker(fake: FakeGhClient, n: int = 12, *, pr: int = 5, gate: str = "tester") -> None:
    from fr.gatebackfill import trackers

    fake.comment_author = "fr-bot"
    fake.add_issue(
        REPO, n, labels={"fr:owed"}, body=trackers.tracker_body("row:r-live", "t", gate, pr)
    )


def test_yes_closes_the_prs_trackers_after_the_pass_and_prints_the_discharge(
    keep_forge: Any,
) -> None:
    fake = keep_forge(["gate:tester"])
    _with_tracker(fake)

    result = _pass("--gate", "tester", "--yes")

    assert result.exit_code == 0, result.output
    names = [c[0] for c in fake.calls]
    assert names.index("edit_pr_labels") < names.index("close_issue")
    (close,) = [c[1] for c in fake.calls if c[0] == "close_issue"]
    assert close["number"] == 12
    assert close["comment"].startswith("Gate tester passed on #5: walked live; `row:r-live` is")
    assert "closed tracker #12" in result.output


def test_the_dry_run_lists_the_trackers_it_would_close(forge: Any) -> None:
    fake = forge(["gate:tester"])
    _with_tracker(fake)

    result = _pass("--gate", "tester")

    assert "would close tracker #12" in result.output
    assert not [c for c in fake.calls if c[0] == "close_issue"]


def test_a_passed_gate_retries_only_the_close(forge: Any) -> None:
    fake = forge(["gate:tester-passed"])
    _with_tracker(fake)
    fake.comment_pr(REPO, 5, gate_pass_comment("tester", "walked live"))
    fake.calls.clear()

    dry = _pass("--gate", "tester")
    assert dry.exit_code == 0, dry.output
    assert "gate tester already passed on #5; closing its trackers" in dry.output
    assert "would close tracker #12" in dry.output
    assert not [c for c in fake.calls if c[0] == "close_issue"]

    result = _pass("--gate", "tester", "--yes")

    assert result.exit_code == 0, result.output
    assert _writes(fake) == []  # no comment, no label swap
    assert [c[1]["number"] for c in fake.calls if c[0] == "close_issue"] == [12]


def test_a_pr_with_neither_label_still_refuses(forge: Any) -> None:
    forge(["verification:live"])
    result = _pass("--gate", "tester", "--yes")
    assert result.exit_code == 2
    assert "does not carry gate:tester" in result.output


def test_a_tracker_failure_never_reverses_the_pass(forge: Any) -> None:
    from tests.unit.fakes import FakeGhError

    fake = forge(["gate:tester"])
    _with_tracker(fake)

    def boom(*a: Any, **k: Any) -> Any:
        raise FakeGhError("rate limited")

    fake.list_issues = boom  # type: ignore[method-assign]
    result = _pass("--gate", "tester", "--yes")

    assert result.exit_code == 0, result.output
    assert "passed: PR #5 now carries gate:tester-passed" in result.output
    assert "rate limited" in result.output


def test_the_retry_hint_is_a_valid_invocation(forge: Any) -> None:
    """p3-r1: the printed `re-run ...` line carries --notes/--repo and parses as a real call."""
    import shlex

    fake = forge(["gate:tester"])
    _with_tracker(fake)

    def boom(*a: Any, **k: Any) -> Any:
        from tests.unit.fakes import FakeGhError

        raise FakeGhError("rate limited")

    fake.list_issues = boom  # type: ignore[method-assign]
    first = _pass("--gate", "tester", "--yes")
    (hint,) = [ln for ln in first.output.splitlines() if "to retry the close" in ln]
    cmd = hint.split("`")[1]
    argv = shlex.split(cmd)
    assert argv[:2] == ["fr", "gate"] and "--notes" in argv and "--repo" in argv
    del fake.list_issues  # the forge recovers
    again = CliRunner().invoke(app, argv[1:])
    assert "Missing option" not in again.output and again.exit_code != 2, again.output


def test_a_hand_labelled_passed_gate_is_not_retried(forge: Any) -> None:
    """p3-r3: `gate:<g>-passed` with no fr:gate-pass comment by us was not set by fr."""
    fake = forge(["gate:tester-passed"])
    _with_tracker(fake)

    result = _pass("--gate", "tester", "--yes")

    assert result.exit_code == 2, result.output
    assert "was not set by fr gate pass" in result.output
    assert "no fr:gate-pass comment by fr-bot" in result.output
    assert not [c for c in fake.calls if c[0] == "close_issue"]


def test_a_foreign_authors_gate_pass_comment_does_not_count(forge: Any) -> None:
    fake = forge(["gate:tester-passed"])
    _with_tracker(fake)
    fake.comment_author = "someone-else"
    fake.comment_pr(REPO, 5, gate_pass_comment("tester", "x"))
    fake.comment_author = "fr-bot"

    assert _pass("--gate", "tester", "--yes").exit_code == 2


def test_a_forge_without_pr_comment_reads_refuses_the_retry(forge: Any) -> None:
    from fr.ghclient import UnsupportedForgeOperation

    fake = forge(["gate:tester-passed"])

    def nope(*a: Any, **k: Any) -> Any:
        raise UnsupportedForgeOperation("glab", "list_issue_comments")

    fake.list_issue_comments = nope  # type: ignore[method-assign]
    result = _pass("--gate", "tester", "--yes")
    assert result.exit_code == 2 and "cannot read the comments" in result.output


# --- R9 (amended): the PR gate ledger, read from the PR's repo (p3-r1, p3-r2, p3-r5) -------

SETTINGS = ".fr/settings.yaml"


def test_p3_r2_with_no_checkout_of_the_repo_the_policy_is_read_through_the_forge(
    forge: Any,
) -> None:
    fake = forge(["gate:tester"])
    result = _pass("--gate", "tester", "--yes")
    assert result.exit_code == 0, result.output
    assert ("read_file", {"repo": REPO, "path": SETTINGS}) in fake.calls
    assert _writes(fake) == ["comment_pr", "ensure_labels", "edit_pr_labels"]


def test_p3_r5_labels_off_on_the_remote_repo_refuses_before_any_write(forge: Any) -> None:
    fake = forge(["gate:tester"])
    fake.remote_tree[(REPO, SETTINGS)] = "forge:\n  labels: 'off'\n"
    result = _pass("--gate", "tester", "--yes")
    assert result.exit_code == 2, result.output
    assert "forge.labels: off" in result.output
    assert fake.attempted_mutations == 0


def test_p3_r2_an_unreadable_remote_policy_refuses_before_any_write(forge: Any) -> None:
    from tests.unit.fakes import FakeGhError

    fake = forge(["gate:tester"])

    def broken(repo: str, path: str) -> str:
        raise FakeGhError("HTTP 502: bad gateway")

    fake.read_file = broken  # type: ignore[method-assign]
    result = _pass("--gate", "tester", "--yes")
    assert result.exit_code == 2, result.output
    assert SETTINGS in result.output and "nothing was written" in result.output
    assert fake.attempted_mutations == 0


def test_p3_r5_comments_off_swaps_the_label_with_no_comment_and_closes_no_tracker(
    forge: Any,
) -> None:
    fake = forge(["gate:tester"])
    _with_tracker(fake)
    fake.remote_tree[(REPO, SETTINGS)] = "forge:\n  comments: 'off'\n"
    result = _pass("--gate", "tester", "--yes")
    assert result.exit_code == 0, result.output
    assert _writes(fake) == ["ensure_labels", "edit_pr_labels"]  # pass_gate(comment=False)
    assert "comment: none (forge.comments: off)" in result.output
    assert "trackers not closed" in result.output
    assert not [c for c in fake.calls if c[0] == "close_issue"]


def test_p3_r5_comments_off_retries_with_no_fr_gate_pass_comment_check(forge: Any) -> None:
    """Under comments off no pass leaves a comment, so a retry does not ask for one
    (`_require_fr_pass` is skipped) and closes no tracker (a close carries a comment)."""
    fake = forge(["gate:tester-passed"])
    _with_tracker(fake)
    fake.remote_tree[(REPO, SETTINGS)] = "forge:\n  comments: 'off'\n"
    result = _pass("--gate", "tester", "--yes")
    assert result.exit_code == 0, result.output
    assert "gate tester already passed on #5" in result.output
    assert not [c for c in fake.calls if c[0] in ("list_issue_comments", "close_issue")]


def test_p3_r1_tracking_none_in_the_checkout_still_writes_the_ledger(
    forge: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """From the repo's own checkout under `tracking: none`: the pass swaps the label and
    comments (the ledger), and closes no tracker (there is none)."""
    from tests.unit.settings_repo import make_repo

    fake = forge(["gate:tester"])
    _with_tracker(fake)
    root = make_repo(tmp_path)
    (root / ".devcontainer").mkdir()
    (root / ".devcontainer" / "fr-profiles.yaml").write_text(
        "schema_version: 2\ntracking: {type: none}\n"
    )
    monkeypatch.chdir(root)
    monkeypatch.setattr("fr._hosts.origin_slug", lambda _root: REPO)
    result = _pass("--gate", "tester", "--yes")
    assert result.exit_code == 0, result.output
    assert _writes(fake) == ["comment_pr", "ensure_labels", "edit_pr_labels"]
    assert not [c for c in fake.calls if c[0] == "read_file"]  # the checkout answered
    assert "trackers not closed: tracking: none" in result.output


# --- gh#1369: an ambiguous delivering PR is resolved by a manifest `pr:` override -------------

AMBIG_PLAN = "2026-10-20-ops"
AMBIG_KEY = f"plan:{AMBIG_PLAN}#p1"


def _ambiguous_env(backfill_env: Any) -> tuple[Path, FakeGhClient]:
    """An open manual phase whose plan two run cursors emitted, on two branches whose PRs
    (21, 22) both merged: the `run` step finds two delivering PRs, an ambiguity."""
    from tests.unit.gatebackfill_fixtures import commit_at, git
    from tests.unit.test_merge_evidence import _write_plan

    root, fake = backfill_env
    _write_plan(root, AMBIG_PLAN, [("manual", False)])
    for rel, branch in (("runs", "feat/ops"), ("implemented/runs", "feat/ops-2")):
        p = root / "docs/superpowers" / rel / "run-ops.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"run: run-ops\nworkflow: fr-goal@1\nbranch: {branch}\n"
            "started: '2026-01-01T09:00:00Z'\ncursor: deliver\nsteps:\n"
            "  plan:\n    state: done\n"
            f"    emitted: {{plan: docs/superpowers/plans/{AMBIG_PLAN}}}\n"
        )
    # Seeded a day ago, not on a fixed date: past `fr debt`'s default stale_days (14) the
    # plan reads as stale and the entry defaults to `review`, which is not what gh#1369 pins.
    seeded = (datetime.now(UTC) - timedelta(days=1)).isoformat(timespec="seconds")
    commit_at(root, "seed", seeded)
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")  # published, without a push
    git(root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    fake.add_pr(BACKFILL_REPO, 21, state="MERGED", head_ref="feat/ops")
    fake.add_pr(BACKFILL_REPO, 22, state="MERGED", head_ref="feat/ops-2")
    return root, fake


def test_gh1369_a_manifest_pr_resolves_an_ambiguous_key_fr_debt_holds(
    backfill_env: Any, tmp_path: Path
) -> None:
    import yaml

    _root, fake = _ambiguous_env(backfill_env)
    plan = tmp_path / "home" / ".cache/fr/gate-backfill/example-org--widgets/plan.yaml"
    assert CliRunner().invoke(app, ["gate", "backfill"]).exit_code == 0
    (before,) = yaml.safe_load(plan.read_text())["entries"]
    assert before["key"] == AMBIG_KEY and before["ambiguous"] == [21, 22]
    assert before["decision"] == "review" and "--from" in before["why"]

    manifest = tmp_path / "m.yaml"
    manifest.write_text(f"schema: 1\nitems:\n  - {{key: '{AMBIG_KEY}', pr: 22}}\n")
    dry = CliRunner().invoke(app, ["gate", "backfill", "--from", str(manifest)])
    assert dry.exit_code == 0, dry.output
    (after,) = yaml.safe_load(plan.read_text())["entries"]
    assert after["pr"] == {"number": 22, "basis": "manifest", "planning": False}
    assert after["decision"] == "owed" and after["gate"] == "devops" and after["ambiguous"] == []

    result = CliRunner().invoke(app, ["gate", "backfill", "--from", str(manifest), "--yes"])

    assert result.exit_code == 0, result.output
    assert fake.pr_labels.get((BACKFILL_REPO, 22)) == {"gate:devops"}
    assert (BACKFILL_REPO, 21) not in fake.pr_labels
    assert [i.labels for i in fake.issues.values()] == [{"fr:owed"}]


def test_gh1369_an_ambiguous_entry_applied_without_its_manifest_says_how_to_resolve_it(
    backfill_env: Any, tmp_path: Path
) -> None:
    """Hand-editing the plan file's `pr:` is not the route (R15 re-resolves it): the skip says
    which one is."""
    import yaml

    _root, fake = _ambiguous_env(backfill_env)
    plan = tmp_path / "home" / ".cache/fr/gate-backfill/example-org--widgets/plan.yaml"
    assert CliRunner().invoke(app, ["gate", "backfill"]).exit_code == 0
    data = yaml.safe_load(plan.read_text())
    data["entries"][0].update(pr={"number": 22, "basis": "manifest"}, decision="owed")
    plan.write_text(yaml.safe_dump(data))

    result = CliRunner().invoke(app, ["gate", "backfill", "--yes"])

    assert result.exit_code == 0, result.output
    assert "ambiguous (#21, #22)" in result.output and "--from" in result.output
    assert fake.attempted_mutations == 0


# --- fr gate pass --keep (spec 2026-11-08-sweep-fixes R10, R11) --------------------------------

KEEP = "row:r-live"


def _keep_writes(fake: FakeGhClient) -> list[str]:
    writes = {
        "edit_pr_labels", "comment_pr", "ensure_labels", "comment_issue", "edit_issue_body",
        "close_issue",
    }  # fmt: skip
    return [c[0] for c in fake.calls if c[0] in writes]


def test_keep_converts_the_tracker_after_the_pass(keep_forge: Any) -> None:
    from fr.gatebackfill import trackers

    fake = keep_forge(["gate:tester"])
    _with_tracker(fake)

    result = _pass("--gate", "tester", "--keep", KEEP, "--yes")

    assert result.exit_code == 0, result.output
    assert fake.pr_labels[(REPO, 5)] >= {"gate:tester-passed"}
    assert not [c for c in fake.calls if c[0] == "close_issue"]
    assert trackers.fr_passed_marker(fake.issues[(REPO, 12)].body) == ("tester", 5)
    assert "kept #12 open" in result.output


def test_keep_dry_run_writes_nothing(keep_forge: Any) -> None:
    fake = keep_forge(["gate:tester"])
    _with_tracker(fake)
    result = _pass("--gate", "tester", "--keep", KEEP)
    assert result.exit_code == 0, result.output
    assert "would keep #12" in result.output and _keep_writes(fake) == []


def test_keep_of_a_key_no_tracker_holds_is_refused_before_the_pass_writes(keep_forge: Any) -> None:
    fake = keep_forge(["gate:tester"])
    _with_tracker(fake)
    result = _pass("--gate", "tester", "--keep", "row:typo", "--yes")
    assert result.exit_code == 2 and "row:typo" in result.output
    assert _keep_writes(fake) == []
    assert fake.prs[(REPO, 5)]["labels"] == ["gate:tester"]


def test_keep_of_a_key_of_another_pr_or_gate_is_refused(keep_forge: Any) -> None:
    fake = keep_forge(["gate:tester"])
    _with_tracker(fake, pr=6)
    _with_tracker(fake, 13, gate="devops")
    result = _pass("--gate", "tester", "--keep", KEEP, "--yes")
    assert result.exit_code == 2 and _keep_writes(fake) == []


def test_keep_is_refused_on_the_retry_route_too(keep_forge: Any) -> None:
    fake = _gate_passed_by_fr(keep_forge)
    _with_tracker(fake)
    before = fake.attempted_mutations
    result = _pass("--gate", "tester", "--keep", "row:typo", "--yes")
    assert result.exit_code == 2 and "row:typo" in result.output
    assert fake.attempted_mutations == before


def _gate_passed_by_fr(install: Any) -> FakeGhClient:
    fake = install(["gate:tester-passed"])
    fake.comment_author = "fr-bot"
    fake.comment_pr(REPO, 5, gate_pass_comment("tester", "walked"))
    return fake


def test_keep_retry_over_an_already_tracked_only_tracker_passes_and_writes_nothing(
    keep_forge: Any,
) -> None:
    fake = _gate_passed_by_fr(keep_forge)
    _with_tracker(fake)
    first = _pass("--gate", "tester", "--keep", KEEP, "--yes")
    assert first.exit_code == 0, first.output
    before = fake.attempted_mutations

    again = _pass("--gate", "tester", "--keep", KEEP, "--yes")

    assert again.exit_code == 0, again.output
    assert fake.attempted_mutations == before


def test_keep_retry_over_an_adopted_issue_already_tracked_only_passes_and_writes_nothing(
    keep_forge: Any, tmp_path: Path
) -> None:
    from fr.gatebackfill import trackers

    fake = _gate_passed_by_fr(keep_forge)
    fake.add_issue(REPO, 9, labels={"fr:owed"}, body="a human's issue")
    fake.issue_authors[(REPO, 9)] = "someone-else"
    fake.comment_issue(
        REPO, 9, trackers.adopt_passed_comment(KEEP, "tester", 5, repo_root=tmp_path)
    )
    before = fake.attempted_mutations
    result = _pass("--gate", "tester", "--keep", KEEP, "--yes")
    assert result.exit_code == 0, result.output
    assert fake.attempted_mutations == before and "gh issue close" not in result.output


def test_the_retry_line_carries_every_keep(keep_forge: Any) -> None:
    import shlex

    fake = keep_forge(["gate:tester"])
    _with_tracker(fake)
    _with_tracker(fake, 13, pr=5)
    fake.issues[(REPO, 13)].body = fake.issues[(REPO, 13)].body.replace("row:r-live", "plan:p#p1")
    from tests.unit.fakes import FakeGhError

    real_edit = fake.edit_issue_body

    def boom(repo: str, number: int, body: str) -> None:
        raise FakeGhError("rate limited")

    fake.edit_issue_body = boom  # type: ignore[method-assign]
    result = _pass("--gate", "tester", "--keep", KEEP, "--keep", "plan:p#p1", "--yes")
    (hint,) = [ln for ln in result.output.splitlines() if "to retry the close" in ln]
    argv = shlex.split(hint.split("`")[1])
    kept = [argv[i + 1] for i, a in enumerate(argv) if a == "--keep"]
    assert kept == [KEEP, "plan:p#p1"]
    # the retry line runs, and finishes the job
    fake.edit_issue_body = real_edit  # type: ignore[method-assign]
    again = CliRunner().invoke(app, argv[1:])
    assert again.exit_code == 0, again.output
    assert not [c for c in fake.calls if c[0] == "close_issue"]


def test_keep_with_no_checkout_is_refused(keep_forge: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = keep_forge(["gate:tester"])
    _with_tracker(fake)
    monkeypatch.setattr(gate_cmd, "_repo_root", lambda: None)
    result = _pass("--gate", "tester", "--keep", KEEP, "--yes")
    assert result.exit_code == 2 and "needs a checkout" in result.output
    assert _keep_writes(fake) == []


def test_p4_r4_a_checkout_of_another_repo_is_no_checkout(
    forge: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R10, R12: its evidence and discharge commands describe some other repo."""
    fake = forge(["gate:tester"])
    _with_tracker(fake)
    monkeypatch.setattr(
        "fr.archive_followups.owed_identity", lambda *a, **k: ("other-org/other", "")
    )

    refused = _pass("--gate", "tester", "--keep", KEEP, "--yes")
    assert refused.exit_code == 2 and f"checkout of {REPO}" in refused.output
    assert _keep_writes(fake) == []

    result = _pass("--gate", "tester", "--yes")
    assert result.exit_code == 0, result.output
    (close,) = [c[1] for c in fake.calls if c[0] == "close_issue"]
    assert close["comment"] == "Gate tester passed on #5: walked live"
    assert "set-status" not in result.output


def test_p4_r4_the_retry_route_reads_no_other_repos_evidence(
    forge: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _gate_passed_by_fr(forge)
    _with_tracker(fake)
    monkeypatch.setattr(
        "fr.archive_followups.owed_identity", lambda *a, **k: ("other-org/other", "")
    )
    result = _pass("--gate", "tester", "--yes")
    assert result.exit_code == 0, result.output
    (close,) = [c[1] for c in fake.calls if c[0] == "close_issue"]
    assert close["comment"] == "Gate tester passed on #5: walked live"
    refused = _pass("--gate", "tester", "--keep", KEEP, "--yes")
    assert refused.exit_code == 2


def test_p4_r4_the_origin_is_compared_without_case(
    forge: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = forge(["gate:tester"])
    _with_tracker(fake)
    monkeypatch.setattr("fr.archive_followups.owed_identity", lambda *a, **k: (REPO.upper(), ""))
    result = _pass("--gate", "tester", "--keep", KEEP)
    assert result.exit_code == 0, result.output


def test_p4_r11_a_keep_pass_lists_the_trackers_once(keep_forge: Any) -> None:
    fake = keep_forge(["gate:tester"])
    _with_tracker(fake)
    result = _pass("--gate", "tester", "--keep", KEEP, "--yes")
    assert result.exit_code == 0, result.output
    assert len([c for c in fake.calls if c[0] == "list_issues"]) == 1


def test_p4_r4_a_repo_fr_cannot_name_is_no_checkout(
    forge: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = forge(["gate:tester"])
    _with_tracker(fake)
    monkeypatch.setattr("fr.archive_followups.owed_identity", lambda *a, **k: (None, "no origin"))
    assert _pass("--gate", "tester", "--keep", KEEP).exit_code == 2
