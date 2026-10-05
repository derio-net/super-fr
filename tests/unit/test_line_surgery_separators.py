"""super-fr#806 (`p2r-splitlines`): fr's YAML line surgery splits on `\\n` only.

`str.splitlines` also breaks on `\\x0c`, `\\x1c`, U+2028 and friends. YAML does
not — to YAML they are ordinary characters inside a comment — so a fragment
after one looked like a line of its own to the writer: a comment's tail could
be matched as a top-level key and rewritten or dropped.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.profiles_services import _drop_legacy_lines
from fr.artifacts.registry import artifact_kind

SEPARATORS = ("\x0c", "\x1c", " ")


def test_the_services_migration_keeps_a_comment_whose_tail_looks_like_a_legacy_key() -> None:
    for sep in SEPARATORS:
        comment = f"# was{sep}backend: gitlab\n"
        text = comment + "backend: github\nprofiles: {}\n"
        assert _drop_legacy_lines(text) == comment + "profiles: {}\n", repr(sep)


def test_the_stamp_writer_never_rewrites_a_comment_whose_tail_looks_like_the_stamp(
    tmp_path: Path,
) -> None:
    for sep in SEPARATORS:
        path = tmp_path / "fr-profiles.yaml"
        comment = f"# was{sep}schema_version: 7\n"
        path.write_text(comment + "profiles: {}\n", newline="")
        artifact_kind("profiles").write_version(path, 2)
        # `open(newline="")`, not `read_text(newline=)`: that keyword is 3.13+,
        # and the floor is 3.11. Untranslated, so a lone `\r` would show too.
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
        assert text.startswith(comment), repr(sep)
        assert "schema_version: 2\n" in text, repr(sep)
