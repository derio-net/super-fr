"""Tests for fr.glab — subprocess wrappers for glab (GitLab) CLI operations.

Contract tests: verify the correct glab invocations are constructed, using
mocked subprocess calls — mirrors tests/unit/test_gh.py's structure and
mocking style, but every flag/error string here is glab's own (verified
directly against the installed `glab` binary's `--help` output during
research, not copy-pasted from gh's conventions — see the design doc's
capability matrix for the concrete differences, e.g. glab's `--description`
where gh uses `--body`, and glab's `#`-prefixed label color).
"""

import os
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fr import glab
from fr.glab import (
    GlabError,
    close_issue,
    create_issue,
    edit_issue_body,
    ensure_label,
    ensure_labels,
    is_already_exists,
    is_not_found,
    reopen_issue,
    swap_issue_labels,
    view_issue,
)
from fr.labels import LabelDef

from tests.unit.test_real_glabclient import (
    GLAB_STDERR_400_MISSING_REF,
    GLAB_STDERR_404_FILE,
    GLAB_STDERR_404_PROJECT,
    GLAB_STDERR_404_TREE,
    GLAB_STDERR_UNAUTHENTICATED,
    GLAB_STDOUT_400_MISSING_REF,
    GLAB_STDOUT_404_FILE,
    GLAB_STDOUT_404_PROJECT,
    GLAB_STDOUT_404_TREE,
    GLAB_STDOUT_UNAUTHENTICATED,
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
                ],
                host=None,
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
                ["issue", "view", "42", "--repo", "group/proj", "--output", "json"], host=None
            )


class TestCloseIssue:
    def test_close(self) -> None:
        with patch("fr.glab._run_glab") as mock:
            close_issue(repo="group/proj", number=42)
            mock.assert_called_once_with(
                ["issue", "close", "42", "--repo", "group/proj"], host=None
            )


class TestEditIssueBody:
    def test_uses_description_flag_not_body(self) -> None:
        """glab's flag is --description; gh's is --body — a real difference."""
        with patch("fr.glab._run_glab") as mock:
            edit_issue_body(repo="group/proj", number=42, body="New body.")
            mock.assert_called_once_with(
                ["issue", "update", "42", "--repo", "group/proj", "--description", "New body."],
                host=None,
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
                ],
                host=None,
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
            *,
            repo: str,
            name: str,
            color: str = "ededed",
            description: str = "",
            host: str | None = None,
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

    def test_default_stdout(self) -> None:
        assert glab.GlabError("boom").stdout == ""


def test_a_failed_call_keeps_the_api_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    """glab puts its own summary on STDERR and the API's JSON body on
    STDOUT; `_run_glab` used to build GlabError from stderr alone and
    discard the body — the part that actually says *what* was wrong
    (gh-486; spec §2.A)."""

    def _fake_run(argv, **kwargs):  # type: ignore[no-untyped-def]
        raise subprocess.CalledProcessError(
            1,
            argv,
            output='{"error":"ref is missing, ref is empty"}',
            stderr="glab: HTTP 400\n",
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)
    with pytest.raises(GlabError) as exc:
        glab._run_glab(["api", "projects/g%2Fp/repository/files/README.md"])
    assert exc.value.stdout == '{"error":"ref is missing, ref is empty"}'
    assert "ref is missing, ref is empty" in str(exc.value)
    assert "HTTP 400" in str(exc.value)


# Every public helper in `fr.glab`, called with a host. A TABLE rather than
# eight tests, so a helper added later WITHOUT the keyword-only `host`
# parameter fails loudly here instead of silently talking to gitlab.com
# (gh-486; spec §4.C).
_HOST_FORWARDING_CALLS = {
    "create_issue": lambda h: create_issue(repo="g/p", title="t", body="b", labels=[], host=h),
    "view_issue": lambda h: view_issue("g/p", 1, host=h),
    "close_issue": lambda h: close_issue(repo="g/p", number=1, host=h),
    "reopen_issue": lambda h: reopen_issue(repo="g/p", number=1, host=h),
    "edit_issue_body": lambda h: edit_issue_body(repo="g/p", number=1, body="b", host=h),
    "swap_issue_labels": lambda h: swap_issue_labels(
        repo="g/p", number=1, add=["a"], remove=[], host=h
    ),
    "ensure_label": lambda h: ensure_label(repo="g/p", name="n", host=h),
    "ensure_labels": lambda h: ensure_labels(
        repo="g/p", labels=[LabelDef("n", "ededed", "")], host=h
    ),
}


def test_the_table_covers_every_public_glab_helper() -> None:
    """The table is only a guard if it is complete — pin it against the
    module's own public surface so a new helper cannot slip past it."""
    public = {
        name
        for name in dir(glab)
        if not name.startswith("_")
        and callable(getattr(glab, name))
        and getattr(getattr(glab, name), "__module__", "") == "fr.glab"
    }
    # Classification/retry helpers take a GlabError or a callable, not a host.
    public -= {
        "GlabError",
        "LabelDef",
        "is_transient",
        "is_not_found",
        "is_already_exists",
        "with_retry",
    }
    assert public == set(_HOST_FORWARDING_CALLS)


@pytest.mark.parametrize("name", sorted(_HOST_FORWARDING_CALLS))
def test_every_helper_forwards_the_host(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    seen: list[str | None] = []

    def _spy(args, *, host=None):  # type: ignore[no-untyped-def]
        seen.append(host)
        return "{}"

    monkeypatch.setattr(glab, "_run_glab", _spy)
    _HOST_FORWARDING_CALLS[name]("gl.corp.com")
    assert seen == ["gl.corp.com"]


class TestRunGlabHost:
    """`GITLAB_HOST`, not `--hostname`: only the env var is honoured by
    every glab subcommand (`glab api` takes `--hostname`, `glab label
    create` does not) — verified live against a self-hosted instance,
    spec §2.D. And it goes in the CHILD's env only, so one repo's host
    cannot leak into another repo's call in the same process (gh-486)."""

    def test_run_glab_puts_the_host_in_the_child_env_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: dict[str, object] = {}

        def _fake_run(argv, **kwargs):  # type: ignore[no-untyped-def]
            seen["argv"], seen["env"] = argv, kwargs.get("env")
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)

        monkeypatch.setattr(subprocess, "run", _fake_run)
        monkeypatch.delenv("GITLAB_HOST", raising=False)
        assert glab._run_glab(["api", "user"], host="gl.corp.com") == "ok"
        env = seen["env"]
        assert isinstance(env, dict)
        assert env["GITLAB_HOST"] == "gl.corp.com"
        assert "--hostname" not in seen["argv"]  # type: ignore[operator]
        assert "GITLAB_HOST" not in os.environ  # never mutated globally

    def test_run_glab_host_env_inherits_the_rest_of_the_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A copy of os.environ plus one key — not a one-entry env, which
        would strip PATH and HOME out from under glab."""
        seen: dict[str, object] = {}

        def _fake_run(argv, **kwargs):  # type: ignore[no-untyped-def]
            seen["env"] = kwargs.get("env")
            return SimpleNamespace(stdout="", stderr="", returncode=0)

        monkeypatch.setattr(subprocess, "run", _fake_run)
        monkeypatch.setenv("FR_SENTINEL_FOR_TEST", "kept")
        glab._run_glab(["api", "user"], host="gl.corp.com")
        env = seen["env"]
        assert isinstance(env, dict)
        assert env["FR_SENTINEL_FOR_TEST"] == "kept"

    def test_run_glab_without_a_host_leaves_the_env_alone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """env is None -> the child inherits os.environ unchanged, which is
        what keeps glab's own git-directory host resolution working (§2.D)."""
        seen: dict[str, object] = {}

        def _fake_run(argv, **kwargs):  # type: ignore[no-untyped-def]
            seen["env"] = kwargs.get("env", "MISSING")
            return SimpleNamespace(stdout="", stderr="", returncode=0)

        monkeypatch.setattr(subprocess, "run", _fake_run)
        glab._run_glab(["api", "user"])
        assert seen["env"] is None


def test_the_body_alone_still_classifies_as_not_found() -> None:
    """Makes the second _NOT_FOUND_PATTERN reachable: a 404 whose stderr
    summary is absent is still a not-found via the body."""
    err = GlabError("", stderr="", stdout='{"message":"404 File Not Found"}')
    assert is_not_found(err)


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


class TestIsNotFound:
    """`is_not_found` decides whether GitLab said "absent" or said "your
    request was wrong". Reading the second as the first is what made
    gh-486 a wrong answer instead of an error."""

    @pytest.mark.parametrize(
        ("err", "out"),
        [
            (GLAB_STDERR_404_FILE, GLAB_STDOUT_404_FILE),
            (GLAB_STDERR_404_PROJECT, GLAB_STDOUT_404_PROJECT),
            (GLAB_STDERR_404_TREE, GLAB_STDOUT_404_TREE),
        ],
    )
    def test_every_captured_404_shape_is_not_found(self, err, out):
        assert is_not_found(GlabError(err.strip(), stderr=err))

    @pytest.mark.parametrize(
        ("err", "out"),
        [
            (GLAB_STDERR_400_MISSING_REF, GLAB_STDOUT_400_MISSING_REF),
            (GLAB_STDERR_UNAUTHENTICATED, GLAB_STDOUT_UNAUTHENTICATED),
        ],
    )
    def test_a_bad_request_or_auth_failure_is_not_absence(self, err, out):
        assert not is_not_found(GlabError(err.strip(), stderr=err))

    def test_a_path_containing_404_does_not_read_as_not_found(self):
        """The probed path is echoed in some glab errors, so a loose
        `"404" in text` would call a 400 on `errors/404.md` absent."""
        err = GlabError(
            "glab: HTTP 400",
            stderr='glab: HTTP 400\n{"error":"ref is missing"} errors/404.md',
        )
        assert not is_not_found(err)


class TestAlreadyExists:
    """`glab label create` has no `--force`, so re-creating a label 409s.

    Captured live 2026-09-19 — note rich WRAPPED the message mid-phrase, which
    is why `_haystack` normalizes whitespace and why a naive
    `"already exists" in stderr` test would not have matched:
    """

    LIVE_409 = (
        "          \n   ERROR  \n          \n  Post https://gitlab.local.gebit.de/api/v4/"
        "projects/IDermitzakis%2Fdevops-scripts/labels: 409 {message: Label already\n"
        "  exists}.                                        \n\n"
    )

    def test_the_live_409_reads_as_already_exists(self):
        assert is_already_exists(GlabError("409", stderr=self.LIVE_409))

    def test_it_matches_across_the_wrap(self):
        """The whole point: the phrase is split by rich's line break."""
        assert "already exists" not in self.LIVE_409  # literally absent
        assert is_already_exists(GlabError("409", stderr=self.LIVE_409))

    def test_a_stray_409_without_the_api_envelope_is_not_already_exists(self):
        """A bare 409 is not enough, and the asymmetry is why: a match makes
        `ensure_labels` skip SILENTLY, so a false positive is a label that was
        never created with no error to say so — less discoverable than the loud
        abort it replaced. A gateway or proxy 409 must not read as "already
        there" (phase 7 review, Important #1)."""
        assert not is_already_exists(
            GlabError("gateway", stderr="proxy rejected the request : 409 ")
        )
        assert not is_already_exists(GlabError("409", stderr="Error: HTTP 409"))

    def test_the_api_envelope_pairs_with_the_status(self):
        """The paired form still matches even if the phrase itself were absent."""
        assert is_already_exists(
            GlabError("409", stderr="Post .../labels: 409 {message: Label taken}")
        )

    def test_a_404_or_a_400_is_not_already_exists(self):
        assert not is_already_exists(GlabError("404", stderr=GLAB_STDERR_404_FILE))
        assert not is_already_exists(GlabError("400", stderr=GLAB_STDERR_400_MISSING_REF))

    def test_ensure_labels_skips_one_that_exists_and_keeps_going(self, monkeypatch):
        """The tolerance fr.glab.ensure_label's docstring always claimed.

        Before this, the first pre-existing label aborted the whole
        `fr apply`, so a second run could never converge (gh-486 f15).
        """
        seen = []

        def _fake(*, repo, name, color="ededed", description="", host=None):
            seen.append(name)
            if name == "phase:1":
                raise GlabError("409", stderr=TestAlreadyExists.LIVE_409)

        monkeypatch.setattr(glab, "ensure_label", _fake)
        glab.ensure_labels(
            repo="g/p",
            labels=[
                LabelDef(name="phase:1", color="ededed", description=""),
                LabelDef(name="phase:2", color="ededed", description=""),
            ],
        )
        assert seen == ["phase:1", "phase:2"]  # did not stop at the 409

    def test_ensure_labels_still_raises_a_real_failure(self, monkeypatch):
        def _fake(*, repo, name, color="ededed", description="", host=None):
            raise GlabError("400", stderr=GLAB_STDERR_400_MISSING_REF)

        monkeypatch.setattr(glab, "ensure_label", _fake)
        with pytest.raises(GlabError):
            glab.ensure_labels(
                repo="g/p", labels=[LabelDef(name="x", color="ededed", description="")]
            )
