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
