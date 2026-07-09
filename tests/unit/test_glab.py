"""Tests for fr.glab — subprocess wrappers for glab (GitLab) CLI operations.

Contract tests: verify the correct glab invocations are constructed, using
mocked subprocess calls — mirrors tests/unit/test_gh.py's structure and
mocking style, but every flag/error string here is glab's own (verified
directly against the installed `glab` binary's `--help` output during
research, not copy-pasted from gh's conventions — see the design doc's
capability matrix for the concrete differences, e.g. glab's `--description`
where gh uses `--body`, and glab's `#`-prefixed label color).
"""

import subprocess
from unittest.mock import patch

import pytest
from fr import glab
from fr.glab import (
    GlabError,
    close_issue,
    create_issue,
    edit_issue_body,
    ensure_label,
    swap_issue_labels,
    view_issue,
)


class TestCreateIssue:
    def test_basic_creation(self) -> None:
        with patch(
            "fr.glab._run_glab",
            return_value="https://gitlab.com/group/proj/-/issues/42",
        ) as mock:
            url = create_issue(
                repo="group/proj",
                title="Phase 1: Setup",
                body="Implementation plan body.",
                labels=["fr:ready"],
            )
            assert url == "https://gitlab.com/group/proj/-/issues/42"
            mock.assert_called_once_with(
                [
                    "issue",
                    "create",
                    "--repo",
                    "group/proj",
                    "--title",
                    "Phase 1: Setup",
                    "--description",
                    "Implementation plan body.",
                    "--label",
                    "fr:ready",
                ]
            )

    def test_multiple_labels(self) -> None:
        with patch(
            "fr.glab._run_glab",
            return_value="https://gitlab.com/group/proj/-/issues/43",
        ) as mock:
            create_issue(repo="group/proj", title="Task", body="Body.", labels=["a", "b"])
            args = mock.call_args[0][0]
            assert args.count("--label") == 2

    def test_no_labels(self) -> None:
        with patch("fr.glab._run_glab", return_value="url") as mock:
            create_issue(repo="group/proj", title="T", body="B", labels=[])
            args = mock.call_args[0][0]
            assert "--label" not in args


class TestViewIssue:
    def test_parses_json_output(self) -> None:
        import json

        response = json.dumps({"title": "T", "description": "B", "labels": [], "state": "opened"})
        with patch("fr.glab._run_glab", return_value=response) as mock:
            result = view_issue("group/proj", 42)
            assert result["title"] == "T"
            assert result["state"] == "opened"
            mock.assert_called_once_with(
                ["issue", "view", "42", "--repo", "group/proj", "--output", "json"]
            )


class TestCloseIssue:
    def test_close(self) -> None:
        with patch("fr.glab._run_glab") as mock:
            close_issue(repo="group/proj", number=42)
            mock.assert_called_once_with(["issue", "close", "42", "--repo", "group/proj"])


class TestEditIssueBody:
    def test_uses_description_flag_not_body(self) -> None:
        """glab's flag is --description; gh's is --body — a real difference."""
        with patch("fr.glab._run_glab") as mock:
            edit_issue_body(repo="group/proj", number=42, body="New body.")
            mock.assert_called_once_with(
                ["issue", "update", "42", "--repo", "group/proj", "--description", "New body."]
            )


class TestSwapIssueLabels:
    def test_emits_label_and_unlabel_flags(self) -> None:
        with patch("fr.glab._run_glab") as mock:
            swap_issue_labels(
                repo="group/proj",
                number=42,
                add=["pr-ready"],
                remove=["in-progress", "fr:ready"],
            )
            mock.assert_called_once_with(
                [
                    "issue",
                    "update",
                    "42",
                    "--repo",
                    "group/proj",
                    "--label",
                    "pr-ready",
                    "--unlabel",
                    "in-progress",
                    "--unlabel",
                    "fr:ready",
                ]
            )

    def test_empty_add_and_remove_is_noop(self) -> None:
        with patch("fr.glab._run_glab") as mock:
            swap_issue_labels(repo="group/proj", number=42, add=[], remove=[])
            mock.assert_not_called()


class TestEnsureLabel:
    """glab's label color takes a leading `#` (default `#428BCA`), unlike
    gh's bare 6-hex — the adapter prepends it here; LabelDef itself (which
    stores the bare 6-hex form) is untouched."""

    def test_prepends_hash_to_color(self) -> None:
        with patch("fr.glab._run_glab") as mock:
            ensure_label(repo="group/proj", name="fr:ready", color="0E8AE6")
            args = mock.call_args[0][0]
            assert args[:3] == ["label", "create", "--name"]
            color_idx = args.index("--color") + 1
            assert args[color_idx] == "#0E8AE6"

    def test_includes_description_when_given(self) -> None:
        with patch("fr.glab._run_glab") as mock:
            ensure_label(repo="group/proj", name="fr:ready", color="0E8AE6", description="Ready")
            args = mock.call_args[0][0]
            assert "--description" in args
            assert "Ready" in args

    def test_propagates_glab_error(self) -> None:
        with patch("fr.glab._run_glab", side_effect=GlabError("permission denied")):
            with pytest.raises(GlabError, match="permission denied"):
                ensure_label(repo="group/proj", name="fr:ready", color="0E8AE6")


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

        monkeypatch.setattr(glab, "ensure_label", fake_ensure)
        defs = [LabelDef("fr:ready", "0E8AE6", "queued")]
        glab.ensure_labels(repo="g/p", labels=defs)
        assert captured == [
            {"repo": "g/p", "name": "fr:ready", "color": "0E8AE6", "description": "queued"}
        ]


class TestRunGlabError:
    def test_subprocess_error_raises_glab_error(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "glab", stderr="fail"),
        ):
            with pytest.raises(GlabError):
                create_issue(repo="group/proj", title="T", body="B", labels=[])

    def test_run_glab_populates_fields_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(*a, **kw):  # type: ignore[no-untyped-def]
            raise subprocess.CalledProcessError(
                returncode=1, cmd=["glab"], output="", stderr="HTTP 403 Forbidden\n"
            )

        monkeypatch.setattr(glab.subprocess, "run", fake_run)
        with pytest.raises(glab.GlabError) as exc_info:
            glab._run_glab(["api", "user"])
        assert exc_info.value.stderr == "HTTP 403 Forbidden\n"
        assert exc_info.value.returncode == 1


class TestGlabErrorFields:
    def test_default_stderr_and_returncode(self) -> None:
        err = glab.GlabError("boom")
        assert err.stderr == ""
        assert err.returncode == 0
        assert str(err) == "boom"


class TestIsTransient:
    """glab-specific fixture strings — network/HTTP vocabulary a Go CLI
    wrapping HTTP calls plausibly emits, verified conceptually against
    glab's own `--help`/error conventions during research; exact wording
    is reconfirmed against a live glab in Phase 9's manual verification."""

    @pytest.mark.parametrize(
        "stderr",
        [
            "HTTP 500: Internal Server Error",
            "HTTP 502 Bad Gateway",
            "HTTP 503 Service Unavailable",
            "dial tcp: lookup gitlab.com: no such host",
            "connection reset by peer",
            "context deadline exceeded (Client.Timeout exceeded)",
        ],
    )
    def test_returns_true_for_transient(self, stderr: str) -> None:
        err = glab.GlabError("x", stderr=stderr, returncode=1)
        assert glab.is_transient(err)

    @pytest.mark.parametrize(
        "stderr",
        [
            "HTTP 401 Unauthorized",
            "HTTP 403 Forbidden",
            "HTTP 404 Not Found",
            "422 Unprocessable Entity: label already exists",
            "",
        ],
    )
    def test_returns_false_for_permanent(self, stderr: str) -> None:
        err = glab.GlabError("x", stderr=stderr, returncode=1)
        assert not glab.is_transient(err)


class TestWithRetry:
    def test_retries_transient_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(glab.time, "sleep", lambda s: None)
        attempts = {"n": 0}

        def op() -> str:
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise glab.GlabError("x", stderr="HTTP 503", returncode=1)
            return "ok"

        assert glab.with_retry(op) == "ok"
        assert attempts["n"] == 2

    def test_no_retry_on_permanent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(glab.time, "sleep", lambda s: None)
        attempts = {"n": 0}

        def op() -> str:
            attempts["n"] += 1
            raise glab.GlabError("x", stderr="HTTP 403", returncode=1)

        with pytest.raises(glab.GlabError):
            glab.with_retry(op)
        assert attempts["n"] == 1
