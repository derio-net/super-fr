from fr.forge_body import not_json_reason


def test_html_is_named_with_the_remedy():
    r = not_json_reason("<html></html>")
    assert r and "SSO or forward-auth login page" in r and "internal URL" in r


def test_leading_whitespace_still_matches():
    assert not_json_reason("\n  <!DOCTYPE html>")


def test_stderr_naming_html_matches():
    assert not_json_reason("x", "content-type: text/html") is not None


def test_other_output_is_none():
    assert not_json_reason("garbage") is None
    assert not_json_reason("{") is None


# ── read_failure: the one line adopt and push print for an unreadable PR ──────
# (spec 2026-11-28-batch-silent-failures R5, R6)


def test_read_failure_names_the_pr_and_the_reason() -> None:
    from fr.forge_body import read_failure

    line = read_failure("https://example.com/o/r/pull/7", RuntimeError("boom"))
    assert line == "warning: could not read the state of PR https://example.com/o/r/pull/7: boom"


def test_read_failure_redacts_and_replaces_control_and_bidi_characters() -> None:
    from fr.forge_body import read_failure

    token = "ghp_" + "a" * 24
    exc = RuntimeError(f"https://user:tok@host/x {token} /Users/jane/work \x1b[31mred‮ end")
    line = read_failure("https://example.com/o/r/pull/7", exc)
    for leaked in ("user:tok", token, "/Users/jane", "\x1b", "‮"):
        assert leaked not in line
    assert "red" in line


def test_read_failure_keeps_one_line_of_at_most_300_characters() -> None:
    from fr.forge_body import read_failure

    line = read_failure("https://example.com/o/r/pull/7", RuntimeError("first\nsecond line"))
    assert line.endswith(": first") and "second" not in line
    long = read_failure("https://example.com/o/r/pull/7", RuntimeError("x" * 1000))
    assert len(long.split(": ", 2)[2]) == 300


def test_read_failure_keeps_a_login_page_error_intact() -> None:
    from fr.forge_body import not_json_reason, read_failure

    reason = not_json_reason("<html>login</html>")
    assert reason is not None
    line = read_failure("https://example.com/o/r/pull/7", RuntimeError(reason))
    assert reason in line


def test_forge_body_does_not_import_the_debt_package() -> None:
    import subprocess
    import sys

    code = "import sys, fr.forge_body; sys.exit(1 if 'fr.debt' in sys.modules else 0)"
    assert subprocess.run([sys.executable, "-I", "-c", code]).returncode == 0


def test_read_failure_sanitises_the_url_too() -> None:
    from fr.forge_body import read_failure

    line = read_failure("https://user:tok@host/o/r/pull/7\x1b[31m", RuntimeError("boom"))
    assert "user:tok" not in line and "\x1b" not in line
    assert line.endswith(": boom")
