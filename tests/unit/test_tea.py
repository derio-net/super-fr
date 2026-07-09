"""Tests for fr.tea — subprocess wrappers for tea (Gitea) CLI operations.

Contract tests: verify the correct tea invocations are constructed, using
mocked subprocess calls — mirrors tests/unit/test_gh.py's structure and
mocking style. Flag names verified directly against the installed `tea`
binary's `--help` output; label-color format verified against Gitea's live
swagger spec (gitea.com/swagger.v1.json) rather than assumed by analogy to
gh — see docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md for the correction.
"""

import subprocess
from unittest.mock import patch

import pytest
from fr import tea
from fr.tea import (
    TeaError,
    close_issue,
    create_issue,
    ensure_label,
    swap_issue_labels,
    view_issue,
)


class TestCreateIssue:
    def test_basic_creation(self) -> None:
        with patch(
            "fr.tea._run_tea",
            return_value="https://gitea.example.com/owner/repo/issues/42",
        ) as mock:
            url = create_issue(
                repo="owner/repo",
                title="Phase 1: Setup",
                body="Implementation plan body.",
                labels=["fr:ready"],
            )
            assert url == "https://gitea.example.com/owner/repo/issues/42"
            mock.assert_called_once_with(
                [
                    "issues",
                    "create",
                    "--repo",
                    "owner/repo",
                    "--title",
                    "Phase 1: Setup",
                    "--description",
                    "Implementation plan body.",
                    "--labels",
                    "fr:ready",
                ]
            )

    def test_multiple_labels_comma_joined(self) -> None:
        """tea takes ONE comma-joined --labels flag, not one flag per label
        (unlike gh/glab, which repeat the flag) — a real CLI-ergonomics
        difference verified against `tea issues create --help`."""
        with patch("fr.tea._run_tea", return_value="url") as mock:
            create_issue(repo="owner/repo", title="T", body="B", labels=["a", "b"])
            args = mock.call_args[0][0]
            assert args.count("--labels") == 1
            idx = args.index("--labels")
            assert args[idx + 1] == "a,b"

    def test_no_labels_omits_flag(self) -> None:
        with patch("fr.tea._run_tea", return_value="url") as mock:
            create_issue(repo="owner/repo", title="T", body="B", labels=[])
            args = mock.call_args[0][0]
            assert "--labels" not in args


class TestViewIssue:
    def test_parses_json_output_no_view_subcommand(self) -> None:
        """tea has no `view` subcommand — `tea issues <n> -o json` alone
        shows the issue in detail (per `tea issues --help`'s own
        description: 'If issue index is provided, will show it in
        detail')."""
        import json

        response = json.dumps({"title": "T", "body": "B", "labels": [], "state": "open"})
        with patch("fr.tea._run_tea", return_value=response) as mock:
            result = view_issue("owner/repo", 42)
            assert result["title"] == "T"
            assert result["state"] == "open"
            mock.assert_called_once_with(
                ["issues", "42", "--repo", "owner/repo", "--output", "json"]
            )


class TestCloseIssue:
    def test_close(self) -> None:
        with patch("fr.tea._run_tea") as mock:
            close_issue(repo="owner/repo", number=42)
            mock.assert_called_once_with(["issues", "close", "42", "--repo", "owner/repo"])


class TestSwapIssueLabels:
    def test_emits_comma_joined_add_and_remove_labels(self) -> None:
        with patch("fr.tea._run_tea") as mock:
            swap_issue_labels(
                repo="owner/repo",
                number=42,
                add=["pr-ready"],
                remove=["in-progress", "fr:ready"],
            )
            mock.assert_called_once_with(
                [
                    "issues",
                    "edit",
                    "42",
                    "--repo",
                    "owner/repo",
                    "--add-labels",
                    "pr-ready",
                    "--remove-labels",
                    "in-progress,fr:ready",
                ]
            )

    def test_empty_add_and_remove_is_noop(self) -> None:
        with patch("fr.tea._run_tea") as mock:
            swap_issue_labels(repo="owner/repo", number=42, add=[], remove=[])
            mock.assert_not_called()

    def test_add_only_omits_remove_flag(self) -> None:
        with patch("fr.tea._run_tea") as mock:
            swap_issue_labels(repo="owner/repo", number=42, add=["x"], remove=[])
            args = mock.call_args[0][0]
            assert "--remove-labels" not in args
            assert "--add-labels" in args


class TestEnsureLabel:
    """Gitea's label color also needs a leading `#` on write — verified
    directly against Gitea's live swagger spec (CreateLabelOption.color
    example '#00aabb'), NOT bare hex as originally assumed by analogy to
    gh. LabelDef itself (bare 6-hex) is unchanged; the adapter prepends
    `#` here, same pattern as fr.glab."""

    def test_prepends_hash_to_color(self) -> None:
        with patch("fr.tea._run_tea") as mock:
            ensure_label(repo="owner/repo", name="fr:ready", color="0E8AE6")
            args = mock.call_args[0][0]
            assert args[:2] == ["labels", "create"]
            color_idx = args.index("--color") + 1
            assert args[color_idx] == "#0E8AE6"

    def test_includes_description_when_given(self) -> None:
        with patch("fr.tea._run_tea") as mock:
            ensure_label(repo="owner/repo", name="fr:ready", color="0E8AE6", description="Ready")
            args = mock.call_args[0][0]
            assert "--description" in args
            assert "Ready" in args

    def test_propagates_tea_error(self) -> None:
        with patch("fr.tea._run_tea", side_effect=TeaError("permission denied")):
            with pytest.raises(TeaError, match="permission denied"):
                ensure_label(repo="owner/repo", name="fr:ready", color="0E8AE6")


class TestEnsureLabels:
    def test_calls_ensure_label_per_def(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fr.labels import LabelDef

        captured: list[dict[str, str]] = []

        def fake_ensure(
            *, repo: str, name: str, color: str = "ededed", description: str = ""
        ) -> None:
            captured.append(
                {"repo": repo, "name": name, "color": color, "description": description}
            )

        monkeypatch.setattr(tea, "ensure_label", fake_ensure)
        defs = [LabelDef("fr:ready", "0E8AE6", "queued")]
        tea.ensure_labels(repo="o/r", labels=defs)
        assert captured == [
            {"repo": "o/r", "name": "fr:ready", "color": "0E8AE6", "description": "queued"}
        ]


class TestRunTeaError:
    def test_subprocess_error_raises_tea_error(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "tea", stderr="fail"),
        ):
            with pytest.raises(TeaError):
                create_issue(repo="owner/repo", title="T", body="B", labels=[])

    def test_run_tea_populates_fields_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(*a, **kw):  # type: ignore[no-untyped-def]
            raise subprocess.CalledProcessError(
                returncode=1, cmd=["tea"], output="", stderr="404 Not Found\n"
            )

        monkeypatch.setattr(tea.subprocess, "run", fake_run)
        with pytest.raises(tea.TeaError) as exc_info:
            tea._run_tea(["issues", "999", "--repo", "o/r", "--output", "json"])
        assert exc_info.value.stderr == "404 Not Found\n"
        assert exc_info.value.returncode == 1


class TestTeaErrorFields:
    def test_default_stderr_and_returncode(self) -> None:
        err = tea.TeaError("boom")
        assert err.stderr == ""
        assert err.returncode == 0
        assert str(err) == "boom"


class TestIsTransient:
    """tea-specific fixture strings, verified conceptually against tea's
    own error conventions; exact wording reconfirmed against a live tea
    in Phase 9's manual verification."""

    @pytest.mark.parametrize(
        "stderr",
        [
            "500 Internal Server Error",
            "502 Bad Gateway",
            "503 Service Unavailable",
            "no such host",
            "connection reset by peer",
            "context deadline exceeded",
        ],
    )
    def test_returns_true_for_transient(self, stderr: str) -> None:
        err = tea.TeaError("x", stderr=stderr, returncode=1)
        assert tea.is_transient(err)

    @pytest.mark.parametrize(
        "stderr",
        [
            "401 Unauthorized",
            "403 Forbidden",
            "404 Not Found",
            "422 Unprocessable Entity",
            "",
        ],
    )
    def test_returns_false_for_permanent(self, stderr: str) -> None:
        err = tea.TeaError("x", stderr=stderr, returncode=1)
        assert not tea.is_transient(err)


class TestWithRetry:
    def test_retries_transient_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tea.time, "sleep", lambda s: None)
        attempts = {"n": 0}

        def op() -> str:
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise tea.TeaError("x", stderr="503 Service Unavailable", returncode=1)
            return "ok"

        assert tea.with_retry(op) == "ok"
        assert attempts["n"] == 2

    def test_no_retry_on_permanent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tea.time, "sleep", lambda s: None)
        attempts = {"n": 0}

        def op() -> str:
            attempts["n"] += 1
            raise tea.TeaError("x", stderr="403 Forbidden", returncode=1)

        with pytest.raises(tea.TeaError):
            tea.with_retry(op)
        assert attempts["n"] == 1
