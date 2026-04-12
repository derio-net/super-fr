from vk import __version__


def test_version_is_string():
    assert isinstance(__version__, str)


def test_version_is_semver():
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_version_value():
    from vk import __version__

    assert __version__ == "1.0.1"
