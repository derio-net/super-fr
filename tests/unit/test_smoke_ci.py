"""A trivial test: CI runs, and the `fr` CLI imports (spec 2026-11-19-local-suite-cost)."""


def test_the_fr_cli_app_is_importable() -> None:
    from fr.cli import app

    assert app is not None
