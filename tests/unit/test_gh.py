"""Tests for vk.gh — subprocess wrappers for gh CLI operations.

These are contract tests: they verify the correct gh invocations
are constructed, using mocked subprocess calls.
"""

import subprocess
from unittest.mock import patch

import pytest

from vk import gh
from vk.gh import (
    GhError,
    add_to_project,
    auth_status,
    close_issue,
    create_issue,
    edit_issue_body,
    ensure_label,
    set_field,
)


class TestCreateIssue:
    def test_basic_creation(self) -> None:
        with patch("vk.gh._run_gh", return_value="https://github.com/org/repo/issues/42") as mock:
            url = create_issue(
                repo="org/repo",
                title="Phase 1: Setup",
                body="Implementation plan body.",
                labels=["vk-ready"],
            )
            assert url == "https://github.com/org/repo/issues/42"
            mock.assert_called_once_with(
                [
                    "issue",
                    "create",
                    "--repo",
                    "org/repo",
                    "--title",
                    "Phase 1: Setup",
                    "--body",
                    "Implementation plan body.",
                    "--label",
                    "vk-ready",
                ]
            )

    def test_multiple_labels(self) -> None:
        with patch("vk.gh._run_gh", return_value="https://github.com/org/repo/issues/43") as mock:
            create_issue(
                repo="org/repo",
                title="Task",
                body="Body.",
                labels=["vk-ready", "manual"],
            )
            args = mock.call_args[0][0]
            assert args.count("--label") == 2

    def test_no_labels(self) -> None:
        with patch("vk.gh._run_gh", return_value="url") as mock:
            create_issue(repo="org/repo", title="T", body="B", labels=[])
            args = mock.call_args[0][0]
            assert "--label" not in args


class TestCloseIssue:
    def test_close(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            close_issue(repo="org/repo", number=42)
            mock.assert_called_once_with(
                [
                    "issue",
                    "close",
                    "--repo",
                    "org/repo",
                    "42",
                ]
            )


class TestEditIssueBody:
    def test_edit_body_calls_gh(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            edit_issue_body(repo="org/repo", number=42, body="New body content.")
            mock.assert_called_once_with(
                ["issue", "edit", "42", "--repo", "org/repo", "--body", "New body content."]
            )

    def test_edit_body_propagates_gh_error(self) -> None:
        with patch("vk.gh._run_gh", side_effect=GhError("rate limited")):
            with pytest.raises(GhError, match="rate limited"):
                edit_issue_body(repo="org/repo", number=42, body="body")


class TestAddToProject:
    def test_add(self) -> None:
        with patch("vk.gh._run_gh", return_value="item-id-123") as mock:
            item_id = add_to_project(
                url="https://github.com/org/repo/issues/42",
                project_owner="org",
                project_number=5,
            )
            assert item_id == "item-id-123"
            mock.assert_called_once_with(
                [
                    "project",
                    "item-add",
                    "5",
                    "--owner",
                    "org",
                    "--url",
                    "https://github.com/org/repo/issues/42",
                    "--format",
                    "json",
                ]
            )


class TestSetField:
    def test_set_text_field(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            set_field(
                project_owner="org",
                project_number=5,
                item_id="item-123",
                field_name="Status",
                field_value="In Progress",
            )
            mock.assert_called_once_with(
                [
                    "project",
                    "item-edit",
                    "--owner",
                    "org",
                    "--project-id",
                    "5",
                    "--id",
                    "item-123",
                    "--field-name",
                    "Status",
                    "--field-value",
                    "In Progress",
                ]
            )


class TestAuthStatus:
    def test_authenticated(self) -> None:
        with patch("vk.gh._run_gh", return_value="github.com\n  Logged in") as mock:
            result = auth_status()
            assert result is True
            mock.assert_called_once_with(["auth", "status"])

    def test_not_authenticated(self) -> None:
        with patch(
            "vk.gh._run_gh",
            side_effect=GhError("not logged in"),
        ):
            result = auth_status()
            assert result is False


class TestRunGhError:
    def test_subprocess_error_raises_gh_error(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "gh", stderr="fail"),
        ):
            with pytest.raises(GhError):
                create_issue(repo="org/repo", title="T", body="B", labels=[])


class TestEnsureLabel:
    """`ensure_label` creates a label via `gh label create --force`, which
    is idempotent: creates if missing, updates color/description if present.
    Without this, `vk dispatch` fails hard on any repo that doesn't already
    have `vk-ready`, `manual`, `plan:<slug>`, `phase:<n>` — which was the
    silent-partial-dispatch failure mode on content-factory and kid-laptops.
    """

    def test_calls_gh_label_create_with_force(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            ensure_label(repo="org/repo", name="vk-ready")
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert args[:3] == ["label", "create", "vk-ready"]
            assert "--force" in args
            assert "--repo" in args
            assert "org/repo" in args
            assert "--color" in args  # a default color is always supplied

    def test_includes_description_when_given(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            ensure_label(
                repo="org/repo",
                name="vk-ready",
                description="Ready for VK pickup",
            )
            args = mock.call_args[0][0]
            assert "--description" in args
            assert "Ready for VK pickup" in args

    def test_omits_description_by_default(self) -> None:
        with patch("vk.gh._run_gh") as mock:
            ensure_label(repo="org/repo", name="vk-ready")
            args = mock.call_args[0][0]
            assert "--description" not in args

    def test_propagates_gh_error(self) -> None:
        with patch("vk.gh._run_gh", side_effect=GhError("permission denied")):
            with pytest.raises(GhError, match="permission denied"):
                ensure_label(repo="org/repo", name="vk-ready")


class TestEnsureLabels:
    def test_calls_ensure_label_per_def_with_color_and_desc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vk.labels import LabelDef

        captured: list[dict[str, str]] = []

        def fake_ensure(
            *, repo: str, name: str, color: str = "ededed", description: str = ""
        ) -> None:
            captured.append(
                {"repo": repo, "name": name, "color": color, "description": description}
            )

        monkeypatch.setattr(gh, "ensure_label", fake_ensure)
        defs = [
            LabelDef("vk-ready", "0E8AE6", "queued"),
            LabelDef("phase:1", "FBCA04", "phase 1"),
        ]
        gh.ensure_labels(repo="o/r", labels=defs)
        assert captured == [
            {"repo": "o/r", "name": "vk-ready", "color": "0E8AE6", "description": "queued"},
            {"repo": "o/r", "name": "phase:1", "color": "FBCA04", "description": "phase 1"},
        ]

    def test_empty_list_is_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called = {"n": 0}

        def fake_ensure(**kw: object) -> None:
            called["n"] += 1

        monkeypatch.setattr(gh, "ensure_label", fake_ensure)
        gh.ensure_labels(repo="o/r", labels=[])
        assert called["n"] == 0

    def test_first_failure_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from vk.labels import LabelDef

        seen: list[str] = []

        def fake_ensure(
            *, repo: str, name: str, color: str = "ededed", description: str = ""
        ) -> None:
            seen.append(name)
            if name == "phase:1":
                raise gh.GhError("nope", stderr="", returncode=1)

        monkeypatch.setattr(gh, "ensure_label", fake_ensure)
        defs = [
            LabelDef("vk-ready", "0E8AE6", ""),
            LabelDef("phase:1", "FBCA04", ""),
            LabelDef("phase:2", "FBCA04", ""),
        ]
        with pytest.raises(gh.GhError):
            gh.ensure_labels(repo="o/r", labels=defs)
        assert seen == ["vk-ready", "phase:1"]  # third never reached


class TestGhErrorFields:
    def test_default_stderr_and_returncode(self) -> None:
        err = gh.GhError("boom")
        assert err.stderr == ""
        assert err.returncode == 0
        assert str(err) == "boom"

    def test_explicit_stderr_and_returncode(self) -> None:
        err = gh.GhError("boom", stderr="HTTP 503\n", returncode=1)
        assert err.stderr == "HTTP 503\n"
        assert err.returncode == 1
        assert str(err) == "boom"

    def test_run_gh_populates_fields_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(*a, **kw):  # type: ignore[no-untyped-def]
            raise subprocess.CalledProcessError(
                returncode=1, cmd=["gh"], output="", stderr="HTTP 403\n"
            )

        monkeypatch.setattr(gh.subprocess, "run", fake_run)
        with pytest.raises(gh.GhError) as exc_info:
            gh._run_gh(["api", "user"])
        assert exc_info.value.stderr == "HTTP 403\n"
        assert exc_info.value.returncode == 1

    def test_run_gh_falls_back_to_returncode_message_when_stderr_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # When the subprocess fails with empty stderr (e.g. crash, signal),
        # _run_gh synthesises a message from the returncode and leaves
        # GhError.stderr as "" rather than None.
        def fake_run(*a, **kw):  # type: ignore[no-untyped-def]
            raise subprocess.CalledProcessError(returncode=2, cmd=["gh"], output="", stderr=None)

        monkeypatch.setattr(gh.subprocess, "run", fake_run)
        with pytest.raises(gh.GhError) as exc_info:
            gh._run_gh(["api", "user"])
        assert str(exc_info.value) == "gh exited with code 2"
        assert exc_info.value.stderr == ""
        assert exc_info.value.returncode == 2


class TestSwapIssueLabels:
    def test_emits_add_and_remove_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[list[str]] = []

        def fake_run(args: list[str]) -> str:
            captured.append(args)
            return ""

        monkeypatch.setattr(gh, "_run_gh", fake_run)
        gh.swap_issue_labels(
            repo="o/r",
            number=42,
            add=["pr-ready"],
            remove=["in-progress", "vk-ready"],
        )
        assert captured == [
            [
                "issue",
                "edit",
                "42",
                "--repo",
                "o/r",
                "--add-label",
                "pr-ready",
                "--remove-label",
                "in-progress",
                "--remove-label",
                "vk-ready",
            ]
        ]

    def test_empty_add_and_remove_is_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[list[str]] = []
        monkeypatch.setattr(
            gh,
            "_run_gh",
            lambda args: captured.append(args) or "",
        )
        gh.swap_issue_labels(repo="o/r", number=42, add=[], remove=[])
        assert captured == []

    def test_propagates_gh_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(args: list[str]) -> str:
            raise gh.GhError("HTTP 404", stderr="HTTP 404\n", returncode=1)

        monkeypatch.setattr(gh, "_run_gh", fake_run)
        with pytest.raises(gh.GhError):
            gh.swap_issue_labels(repo="o/r", number=42, add=["x"], remove=[])


class TestListLabels:
    def test_returns_parsed_label_objects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import json

        captured: list[list] = []

        def fake(args: list) -> str:
            captured.append(args)
            return json.dumps(
                [
                    {"name": "vk-ready", "color": "0E8AE6", "description": "queued"},
                    {"name": "bug", "color": "d73a4a", "description": "Something's wrong"},
                ]
            )

        monkeypatch.setattr(gh, "_run_gh", fake)
        labels = gh.list_labels(repo="o/r")
        assert labels[0]["name"] == "vk-ready"
        assert labels[0]["color"] == "0E8AE6"
        assert labels[1]["name"] == "bug"
        assert captured[0] == [
            "label",
            "list",
            "--repo",
            "o/r",
            "--json",
            "name,color,description",
            "--limit",
            "200",
        ]


class TestListRepos:
    def test_returns_non_archived_repos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import json

        captured: list[list] = []

        def fake(args: list) -> str:
            captured.append(args)
            return json.dumps(
                [
                    {"name": "frank", "isArchived": False},
                    {"name": "old-repo", "isArchived": True},
                    {"name": "willikins", "isArchived": False},
                ]
            )

        monkeypatch.setattr(gh, "_run_gh", fake)
        repos = gh.list_repos(owner="derio-net")
        assert [r["name"] for r in repos] == ["frank", "willikins"]
        assert captured[0] == [
            "repo",
            "list",
            "derio-net",
            "--json",
            "name,isArchived",
            "--limit",
            "200",
        ]

    def test_includes_repo_missing_is_archived_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Repos missing `isArchived` should be included (treated as non-archived)."""
        import json

        monkeypatch.setattr(gh, "_run_gh", lambda args: json.dumps([{"name": "mystery"}]))
        repos = gh.list_repos(owner="derio-net")
        assert [r["name"] for r in repos] == ["mystery"]


class TestDeleteLabel:
    def test_emits_delete_yes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[list] = []
        monkeypatch.setattr(gh, "_run_gh", lambda args: captured.append(args) or "")
        gh.delete_label(repo="o/r", name="bug")
        assert captured == [
            [
                "label",
                "delete",
                "bug",
                "--repo",
                "o/r",
                "--yes",
            ]
        ]


class TestIsTransient:
    @pytest.mark.parametrize(
        "stderr",
        [
            "HTTP 500: server error",
            "HTTP 502 Bad Gateway",
            "HTTP 503: temporarily unavailable",
            "could not resolve host: api.github.com",
            "connection reset by peer",
            "connection refused",
            "i/o timeout",
        ],
    )
    def test_returns_true_for_transient(self, stderr: str) -> None:
        err = gh.GhError("x", stderr=stderr, returncode=1)
        assert gh.is_transient(err)

    @pytest.mark.parametrize(
        "stderr",
        [
            "HTTP 401: Bad credentials",
            "HTTP 403: forbidden",
            "HTTP 404: not found",
            "validation failed",
            "label already exists",
            "",
        ],
    )
    def test_returns_false_for_permanent(self, stderr: str) -> None:
        err = gh.GhError("x", stderr=stderr, returncode=1)
        assert not gh.is_transient(err)


class TestWithRetry:
    def test_succeeds_first_try(self) -> None:
        calls = {"n": 0}

        def op() -> str:
            calls["n"] += 1
            return "ok"

        assert gh.with_retry(op) == "ok"
        assert calls["n"] == 1

    def test_retries_transient_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        slept: list[float] = []
        monkeypatch.setattr(gh.time, "sleep", lambda s: slept.append(s))
        attempts = {"n": 0}

        def op() -> str:
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise gh.GhError("x", stderr="HTTP 503", returncode=1)
            return "ok"

        assert gh.with_retry(op) == "ok"
        assert attempts["n"] == 3
        assert slept == [1.0, 2.0]  # backoff before attempts 2 and 3

    def test_gives_up_after_max_attempts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gh.time, "sleep", lambda s: None)

        def op() -> str:
            raise gh.GhError("x", stderr="HTTP 503", returncode=1)

        with pytest.raises(gh.GhError):
            gh.with_retry(op)

    def test_no_retry_on_permanent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        slept: list[float] = []
        monkeypatch.setattr(gh.time, "sleep", lambda s: slept.append(s))
        attempts = {"n": 0}

        def op() -> str:
            attempts["n"] += 1
            raise gh.GhError("x", stderr="HTTP 403", returncode=1)

        with pytest.raises(gh.GhError):
            gh.with_retry(op)
        assert attempts["n"] == 1
        assert slept == []

    def test_rejects_max_attempts_below_one(self) -> None:
        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            gh.with_retry(lambda: "x", max_attempts=0)

    def test_rejects_backoff_shorter_than_required(self) -> None:
        # max_attempts=4 needs at least 3 backoff entries; only 2 supplied.
        with pytest.raises(ValueError, match="backoff_seconds has 2"):
            gh.with_retry(lambda: "x", max_attempts=4, backoff_seconds=(1.0, 2.0))

    def test_accepts_backoff_exactly_max_minus_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # max_attempts=3 with 2-entry backoff is the minimum-sized config.
        monkeypatch.setattr(gh.time, "sleep", lambda s: None)
        assert gh.with_retry(lambda: "ok", max_attempts=3, backoff_seconds=(1.0, 2.0)) == "ok"


class TestCountIssuesWithLabel:
    def test_returns_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import json

        captured: list[list[str]] = []

        def fake(args: list[str]) -> str:
            captured.append(args)
            return json.dumps([{"id": 1}, {"id": 2}, {"id": 3}])

        monkeypatch.setattr(gh, "_run_gh", fake)
        n = gh.count_issues_with_label(repo="o/r", name="bug")
        assert n == 3
        assert captured[0] == [
            "issue",
            "list",
            "--repo",
            "o/r",
            "--label",
            "bug",
            "--state",
            "all",
            "--json",
            "id",
            "--limit",
            "1000",
        ]

    def test_empty_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gh, "_run_gh", lambda args: "[]")
        assert gh.count_issues_with_label(repo="o/r", name="bug") == 0
