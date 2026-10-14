import re

from fr import __version__


def test_version_is_string():
    assert isinstance(__version__, str)


def test_version_is_semver():
    # A final `X.Y.Z`, or the PEP 440 spelling of a release candidate (`X.Y.ZrcN`):
    # the release stages an RC tree and runs this suite on it (spec 2026-10-14-exit-gates R25).
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:rc[1-9]\d*)?", __version__), __version__


def test_version_value():
    """__version__ should match the installed package metadata."""
    from importlib.metadata import version

    from fr import __version__

    assert __version__ == version("fr")
