"""`fr gate pass` — R14's explicit route (spec 2026-10-14-exit-gates §D).

It swaps a PR's `gate:<g>` for `gate:<g>-passed` and comments what passed it, through
the forge adapter, only with `--yes`; it refuses an unknown gate, a gate that holds no
merge (not post-merge), and a PR that does not carry `gate:<g>`; and it prints the
release dispatch, so a final follows the last pass (R20). The forge is faked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fr.artifacts import trigger
from fr.cli import app
from fr.commands import gate_cmd
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

    import yaml

    root = tmp_path / "widgets"
    root.mkdir()
    for args in (
        ["init", "-q", "-b", "main"],
        ["remote", "add", "origin", f"https://github.com/{BACKFILL_REPO}.git"],
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    matrix = root / "docs" / "acceptance" / "matrix.yaml"
    matrix.parent.mkdir(parents=True)
    org, name = BACKFILL_REPO.split("/")
    matrix.write_text(yaml.safe_dump({"schema_version": 5, "org": org, "repo": name, "rows": []}))
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


def test_yes_closes_the_prs_trackers_after_the_pass_and_prints_the_discharge(forge: Any) -> None:
    fake = forge(["gate:tester"])
    _with_tracker(fake)

    result = _pass("--gate", "tester", "--yes")

    assert result.exit_code == 0, result.output
    names = [c[0] for c in fake.calls]
    assert names.index("edit_pr_labels") < names.index("close_issue")
    (close,) = [c[1] for c in fake.calls if c[0] == "close_issue"]
    assert close["number"] == 12 and close["comment"] == "Gate tester passed on #5: walked live"
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
