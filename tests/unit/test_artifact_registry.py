"""The artifact registry: the ONE place that enumerates artifact kinds.

Spec: docs/superpowers/specs/2026-08-30-artifact-migration-framework-design.md
§3.A — every generated artifact declares the version it was written for, a
missing stamp means version 1 (the pre-framework era), and archived artifacts
under `implemented/` are frozen and never matched.
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest
from fr.artifacts.registry import (
    ARTIFACT_KINDS,
    PRE_FRAMEWORK_VERSION,
    UnknownArtifactKindError,
    artifact_kind,
    iter_all_artifacts,
    iter_artifact_paths,
    read_version,
    write_version,
)

EXPECTED_KINDS = {"plan", "journal", "run", "matrix", "spec"}


# --- Task 1: the registry ------------------------------------------------


def test_registry_covers_every_stamped_kind() -> None:
    assert set(ARTIFACT_KINDS) == EXPECTED_KINDS


def test_each_entry_carries_version_locator_and_callables() -> None:
    for name, kind in ARTIFACT_KINDS.items():
        assert kind.name == name, "the mapping key must be the kind's own name"
        assert isinstance(kind.current_version, int) and kind.current_version >= 1
        assert isinstance(kind.locator, str) and kind.locator
        assert not Path(kind.locator).is_absolute(), "locator is relative to repo root"
        assert callable(kind.read_version)
        assert callable(kind.write_version)


def test_locators_never_reach_archived_artifacts() -> None:
    """`implemented/` records what shipped; rewriting it would falsify history."""
    for kind in ARTIFACT_KINDS.values():
        assert "implemented" not in kind.locator


def test_unknown_kind_raises() -> None:
    with pytest.raises(UnknownArtifactKindError):
        artifact_kind("brainstorm")


def test_pre_framework_version_is_one() -> None:
    assert PRE_FRAMEWORK_VERSION == 1


# --- Task 1: iteration skips the archive ---------------------------------


def _seed_repo(root: Path) -> dict[str, Path]:
    """A repo with one live artifact per kind and an archived twin of each."""
    live: dict[str, Path] = {}

    def w(rel: str, text: str) -> Path:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    live["plan"] = w("docs/superpowers/plans/2026-01-01-live/_meta.yaml", "schema_version: 2\n")
    w("docs/superpowers/implemented/plans/2026-01-01-done/_meta.yaml", "schema_version: 2\n")

    live["journal"] = w("docs/superpowers/journals/plans/2026-01-01-live.md", "# live\n")
    w("docs/superpowers/implemented/journals/plans/2026-01-01-done.md", "# done\n")

    live["run"] = w("docs/superpowers/runs/2026-01-01-live.yaml", "run: live\n")
    w("docs/superpowers/implemented/runs/2026-01-01-done.yaml", "run: done\n")

    live["matrix"] = w("docs/acceptance/matrix.yaml", "rows: []\n")

    live["spec"] = w("docs/superpowers/specs/2026-01-01-live-design.md", "# live\n")
    w("docs/superpowers/implemented/specs/2026-01-01-done-design.md", "# done\n")

    return live


def test_iter_artifact_paths_finds_live_and_skips_archived(tmp_path: Path) -> None:
    live = _seed_repo(tmp_path)
    for name in EXPECTED_KINDS:
        found = list(iter_artifact_paths(tmp_path, name))
        assert found == [live[name]], f"{name}: expected only the live artifact"


def test_iter_all_artifacts_covers_every_kind_once(tmp_path: Path) -> None:
    live = _seed_repo(tmp_path)
    found = {(kind.name, path) for kind, path in iter_all_artifacts(tmp_path)}
    assert found == {(name, path) for name, path in live.items()}


def test_iter_artifact_paths_rejects_unknown_kind(tmp_path: Path) -> None:
    with pytest.raises(UnknownArtifactKindError):
        list(iter_artifact_paths(tmp_path, "brainstorm"))


def test_iter_artifact_paths_on_an_empty_repo_is_empty(tmp_path: Path) -> None:
    for name in EXPECTED_KINDS:
        assert list(iter_artifact_paths(tmp_path, name)) == []


# --- Task 2: stamps, with ABSENT meaning version 1 -----------------------


def _diff(before: str, after: str) -> tuple[list[str], list[str]]:
    """`(removed, added)` lines between two texts, headers stripped."""
    body = list(
        difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), n=0)
    )[2:]
    removed = [ln[1:] for ln in body if ln.startswith("-")]
    added = [ln[1:] for ln in body if ln.startswith("+")]
    return removed, added


# Deliberately messy carriers: comments, unusual key order, blank lines, and a
# trailing comment. A fixture emitted by the writer itself would pass against a
# reformatting implementation and prove nothing.
UNSTAMPED: dict[str, str] = {
    "plan": (
        "# hand-edited plan meta — key order is NOT the canonical one\n"
        "\n"
        "plan: 2026-01-01-live\n"
        "target_repo: derio-net/super-fr\n"
        "fr_version: '>=3.0.0,<4.0.0'   # the ceiling 4.0.0 must widen\n"
        "\n"
        "spec: docs/superpowers/specs/2026-01-01-live-design.md\n"
        "created: '2026-01-01'\n"
        "# trailing comment\n"
    ),
    "journal": (
        "# 2026-01-01-live\n"
        "\n"
        "<!-- fr:journal kind=discovery scope=plan id=d1 created=2026-01-01T00:00:00 -->\n"
        "### d1 · discovery · a thing\n"
        "\n"
        "body\n"
    ),
    "run": (
        "# a run an operator has open right now\n"
        "cursor: implement\n"
        "\n"
        "run: 2026-01-01-live\n"
        "workflow: fr-goal@1\n"
        "branch: feat/live\n"
        "started: '2026-01-01T00:00:00'\n"
        "steps:\n"
        "  implement:\n"
        "    state: running   # mid-flight\n"
        "\n"
        "# trailing comment\n"
    ),
    "matrix": (
        "# Acceptance matrix — the registry of business-level acceptance tests.\n"
        "\n"
        "repo: super-fr\n"
        "org: derio-net\n"
        "rows:\n"
        "- id: a-row\n"
        "  capability: Thing   # inline comment\n"
        "  acceptance: It works\n"
        "  status: ci\n"
        "\n"
        "# trailing comment\n"
    ),
    "spec": (
        "# A design spec\n"
        "\n"
        "Status: design\n"
        "\n"
        "---\n"
        "\n"
        "A horizontal rule above must NOT be mistaken for front matter.\n"
    ),
}

# The same carriers, already stamped at version 3 — the reader must return the
# declared stamp, and the writer must UPDATE it in place rather than adding a
# second one.
STAMPED_3: dict[str, str] = {
    "plan": "schema_version: 3\n" + UNSTAMPED["plan"],
    "journal": "<!-- fr:journal-schema=3 -->\n" + UNSTAMPED["journal"],
    "run": UNSTAMPED["run"].replace(
        "cursor: implement\n", "schema_version: 3\ncursor: implement\n"
    ),
    "matrix": UNSTAMPED["matrix"].replace(
        "repo: super-fr\n", "schema_version: 3\nrepo: super-fr\n"
    ),
    "spec": "---\nfr_schema: 3\n---\n" + UNSTAMPED["spec"],
}


def _artifact_path(root: Path, name: str) -> Path:
    return _seed_repo(root)[name]


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_absent_stamp_reads_as_version_one(tmp_path: Path, name: str) -> None:
    """No flag day: every artifact in the wild predates the framework."""
    path = _artifact_path(tmp_path, name)
    path.write_text(UNSTAMPED[name])
    assert read_version(name, path) == 1


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_declared_stamp_is_read_back(tmp_path: Path, name: str) -> None:
    path = _artifact_path(tmp_path, name)
    path.write_text(STAMPED_3[name])
    assert read_version(name, path) == 3


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_write_version_round_trips(tmp_path: Path, name: str) -> None:
    path = _artifact_path(tmp_path, name)
    path.write_text(UNSTAMPED[name])
    write_version(name, path, 7)
    assert read_version(name, path) == 7


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_stamping_an_unstamped_file_removes_nothing(tmp_path: Path, name: str) -> None:
    """Byte-stability: the only diff is the stamp being ADDED."""
    path = _artifact_path(tmp_path, name)
    before = UNSTAMPED[name]
    path.write_text(before)
    write_version(name, path, 7)
    removed, added = _diff(before, path.read_text())
    assert removed == [], f"{name}: writing a stamp must not remove or rewrite any line"
    # Exactly one added line carries the version. A carrier with no container
    # yet (an unstamped spec has no front matter) may also add its delimiters,
    # and nothing else.
    carriers = [i for i, ln in enumerate(added) if "7" in ln]
    assert len(carriers) == 1, f"{name}: expected one stamp line, got {added!r}"
    others = [ln for i, ln in enumerate(added) if i not in carriers]
    assert all(ln.strip() == "---" for ln in others), f"{name}: stray additions {others!r}"


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_restamping_replaces_the_stamp_in_place(tmp_path: Path, name: str) -> None:
    """Byte-stability again: exactly one line out, one line in — no duplicate stamp."""
    path = _artifact_path(tmp_path, name)
    before = STAMPED_3[name]
    path.write_text(before)
    write_version(name, path, 7)
    after = path.read_text()
    removed, added = _diff(before, after)
    assert len(removed) == 1 and "3" in removed[0], f"{name}: removed {removed!r}"
    assert len(added) == 1 and "7" in added[0], f"{name}: added {added!r}"
    assert read_version(name, path) == 7


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_writing_the_same_version_twice_is_byte_identical(tmp_path: Path, name: str) -> None:
    path = _artifact_path(tmp_path, name)
    path.write_text(UNSTAMPED[name])
    write_version(name, path, 7)
    once = path.read_text()
    write_version(name, path, 7)
    assert path.read_text() == once


def test_plan_stamp_is_the_existing_schema_version_field(tmp_path: Path) -> None:
    """Plans are already stamped — the framework reads that field, it does not
    add a second one (`PlanMeta` is `extra="forbid"`)."""
    path = _artifact_path(tmp_path, "plan")
    path.write_text("schema_version: 2\nplan: x\n")
    assert read_version("plan", path) == 2
    assert ARTIFACT_KINDS["plan"].current_version == 2


def test_journal_stamp_is_not_mistaken_for_an_entry_delimiter(tmp_path: Path) -> None:
    """`<!-- fr:journal ` is the ENTRY delimiter prefix; the stamp must not
    collide with it or every existing journal becomes unparseable."""
    from fr.journal.model import parse_journal

    path = _artifact_path(tmp_path, "journal")
    path.write_text(UNSTAMPED["journal"])
    before = parse_journal(path.read_text())
    write_version("journal", path, 7)
    after = parse_journal(path.read_text())
    assert [e.id for e in after] == [e.id for e in before] == ["d1"]


def test_spec_stamp_leaves_the_implementation_plans_table_parseable(tmp_path: Path) -> None:
    from fr.spec import parse_spec

    path = _artifact_path(tmp_path, "spec")
    path.write_text(
        "# A design spec\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n|---|---|---|---|\n"
        "| p | `derio-net/super-fr` | `p` | — |\n"
    )
    write_version("spec", path, 7)
    meta = parse_spec(path)
    assert meta.title == "A design spec"
    assert [p.name for p in meta.plans] == ["p"]


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_stamp_helpers_reject_an_unknown_kind(tmp_path: Path, name: str) -> None:
    path = _artifact_path(tmp_path, name)
    with pytest.raises(UnknownArtifactKindError):
        read_version("brainstorm", path)
    with pytest.raises(UnknownArtifactKindError):
        write_version("brainstorm", path, 2)


# --- review r4-f6: re-stamping must not eat the operator's blank lines ----


def test_restamping_a_journal_preserves_the_blank_lines_after_the_stamp(tmp_path: Path) -> None:
    """Property 3 of this module: "writing a stamp disturbs nothing else".

    `_JOURNAL_STAMP_RE` ended `\\s*$` under `re.MULTILINE`, and `\\s` matches
    `\\n` — so the match ran past the stamp's own line and swallowed every
    blank line that followed it. A journal re-stamped twice would lose the
    separation the writer put there.
    """
    path = _artifact_path(tmp_path, "journal")
    path.write_text("<!-- fr:journal-schema=1 -->\n\n\n# Journal\n")

    write_version("journal", path, 2)

    assert path.read_text() == "<!-- fr:journal-schema=2 -->\n\n\n# Journal\n"


def test_restamping_a_journal_does_not_reach_past_its_own_line(tmp_path: Path) -> None:
    """Trailing spaces on the stamp line are the stamp's; the newline is not."""
    path = _artifact_path(tmp_path, "journal")
    path.write_text("<!-- fr:journal-schema=1 -->  \n\n<!-- fr:journal kind=x -->\n")

    write_version("journal", path, 4)

    assert path.read_text() == "<!-- fr:journal-schema=4 -->\n\n<!-- fr:journal kind=x -->\n"


# =========================================================================
# Stamp readers and writers, one case per carrier (review r5-e10)
# =========================================================================
#
# The writers are documented as disturbing nothing else in the file (module
# property 3). "Nothing else" has to include the bytes nobody thinks about:
# line endings, a BOM, a `---` document marker, a missing trailing newline.
# An artifact rewritten with normalised endings is a diff the operator did not
# make, in a commit they did not type, under a message that says "migrate".

_YAML_KINDS = ("plan", "run", "matrix")


def _yaml_carrier(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
    return p


@pytest.mark.parametrize("kind", _YAML_KINDS)
def test_a_crlf_yaml_carrier_keeps_its_line_endings(tmp_path: Path, kind: str) -> None:
    p = tmp_path / "a.yaml"
    p.write_bytes(b"schema_version: 1\r\nplan: p\r\n")

    artifact_kind(kind).write_version(p, 2)

    raw = p.read_bytes()
    assert raw == b"schema_version: 2\r\nplan: p\r\n"


@pytest.mark.parametrize("kind", _YAML_KINDS)
def test_a_utf8_bom_survives_a_restamp(tmp_path: Path, kind: str) -> None:
    p = tmp_path / "a.yaml"
    p.write_bytes(b"\xef\xbb\xbfschema_version: 1\nplan: p\n")

    artifact_kind(kind).write_version(p, 2)

    assert p.read_bytes().startswith(b"\xef\xbb\xbf")
    assert b"schema_version: 2" in p.read_bytes()


@pytest.mark.parametrize("kind", _YAML_KINDS)
def test_a_document_marker_keeps_the_stamp_below_it(tmp_path: Path, kind: str) -> None:
    p = tmp_path / "a.yaml"
    p.write_text("---\n# header comment\nplan: p\n")

    artifact_kind(kind).write_version(p, 2)

    lines = p.read_text().splitlines()
    assert lines[0] == "---"
    assert lines[1] == "# header comment"
    assert lines[2] == "schema_version: 2"


@pytest.mark.parametrize("kind", _YAML_KINDS)
def test_a_file_without_a_trailing_newline_is_not_given_one(tmp_path: Path, kind: str) -> None:
    p = tmp_path / "a.yaml"
    p.write_text("plan: p\nschema_version: 1")

    artifact_kind(kind).write_version(p, 2)

    assert p.read_text() == "plan: p\nschema_version: 2"


@pytest.mark.parametrize("kind", _YAML_KINDS)
@pytest.mark.parametrize("literal", ['"2"', "2.0", "'2'"])
def test_a_non_integer_stamp_is_a_failure_not_a_coercion(
    tmp_path: Path, kind: str, literal: str
) -> None:
    """A quoted or float `schema_version` is a hand edit, and guessing what it
    meant is how a migration runs against the wrong shape."""
    from fr.artifacts.registry import ArtifactStampError

    p = tmp_path / "a.yaml"
    p.write_text(f"schema_version: {literal}\nplan: p\n")

    with pytest.raises(ArtifactStampError):
        artifact_kind(kind).read_stamp(p)


@pytest.mark.parametrize("kind", _YAML_KINDS)
@pytest.mark.parametrize("bad", ["0", "-3", "yes", "null-ish"])
def test_a_zero_negative_or_non_numeric_stamp_raises_artifact_stamp_error(
    tmp_path: Path, kind: str, bad: str
) -> None:
    from fr.artifacts.registry import ArtifactStampError

    p = tmp_path / "a.yaml"
    p.write_text(f"schema_version: {bad}\nplan: p\n")

    with pytest.raises(ArtifactStampError):
        artifact_kind(kind).read_stamp(p)


@pytest.mark.parametrize("kind", _YAML_KINDS)
def test_a_stamp_that_appears_only_in_a_comment_is_absent(tmp_path: Path, kind: str) -> None:
    p = tmp_path / "a.yaml"
    p.write_text("# schema_version: 7\nplan: p\n")

    assert artifact_kind(kind).read_stamp(p) is None
    assert artifact_kind(kind).read_version(p) == PRE_FRAMEWORK_VERSION


def test_matrix_anchors_and_aliases_are_left_alone(tmp_path: Path) -> None:
    """A restamp is line surgery, not a YAML round-trip: `yaml.safe_dump`
    would expand every alias and lose every anchor."""
    p = tmp_path / "matrix.yaml"
    p.write_text("defaults: &d\n  status: ci\nrows:\n  - <<: *d\n    id: a\n")

    artifact_kind("matrix").write_version(p, 2)

    text = p.read_text()
    assert "&d" in text and "*d" in text
    assert text.startswith("schema_version: 2\n")


# --- the journal stamp lives on the first non-blank line (r5-c5) ---------


def test_a_stamp_quoted_inside_the_journal_is_not_read_as_the_stamp(tmp_path: Path) -> None:
    """This framework's OWN journal quotes the stamp format in prose. Read
    with `re.MULTILINE`, that quoted line declared the journal's version — and
    the writer then rewrote the quotation instead of the header."""
    p = tmp_path / "j.md"
    p.write_text(
        "# Journal\n\nThe stamp looks like this:\n\n```\n<!-- fr:journal-schema=7 -->\n```\n"
    )

    assert artifact_kind("journal").read_stamp(p) is None


def test_stamping_a_journal_whose_first_line_is_a_heading_prepends(tmp_path: Path) -> None:
    """Where the stamp lives is defined: the first non-blank line. A journal
    that starts with a title gets the stamp ABOVE it, which is where the
    reader looks."""
    p = tmp_path / "j.md"
    p.write_text("# Journal\n\nBody.\n")

    artifact_kind("journal").write_version(p, 1)

    assert p.read_text().splitlines()[0] == "<!-- fr:journal-schema=1 -->"
    assert artifact_kind("journal").read_stamp(p) == 1


def test_a_real_journal_stamp_on_line_one_still_round_trips(tmp_path: Path) -> None:
    p = tmp_path / "j.md"
    p.write_text("<!-- fr:journal-schema=1 -->\n# Journal\n\nBody.\n")

    assert artifact_kind("journal").read_stamp(p) == 1
    artifact_kind("journal").write_version(p, 2)
    assert p.read_text() == "<!-- fr:journal-schema=2 -->\n# Journal\n\nBody.\n"


def test_a_journal_with_leading_blank_lines_still_finds_its_stamp(tmp_path: Path) -> None:
    p = tmp_path / "j.md"
    p.write_text("\n\n<!-- fr:journal-schema=1 -->\n# Journal\n")

    assert artifact_kind("journal").read_stamp(p) == 1


# --- spec front matter ---------------------------------------------------


def test_a_spec_with_no_front_matter_reads_as_version_one(tmp_path: Path) -> None:
    p = tmp_path / "s.md"
    p.write_text("# Design\n\nProse.\n")

    assert artifact_kind("spec").read_stamp(p) is None
    assert artifact_kind("spec").read_version(p) == PRE_FRAMEWORK_VERSION


def test_a_spec_with_empty_front_matter_reads_as_version_one(tmp_path: Path) -> None:
    p = tmp_path / "s.md"
    p.write_text("---\n\n---\n# Design\n")

    assert artifact_kind("spec").read_stamp(p) is None


def test_a_spec_whose_fr_schema_is_null_reads_as_version_one(tmp_path: Path) -> None:
    """`fr_schema:` with no value is "not stamped", not "stamped as nothing"."""
    from fr.artifacts.registry import ArtifactStampError

    p = tmp_path / "s.md"
    p.write_text("---\nfr_schema:\n---\n# Design\n")

    with pytest.raises(ArtifactStampError):
        artifact_kind("spec").read_stamp(p)


def test_a_horizontal_rule_further_down_is_not_front_matter(tmp_path: Path) -> None:
    p = tmp_path / "s.md"
    p.write_text("# Design\n\n---\nfr_schema: 9\n---\n")

    assert artifact_kind("spec").read_stamp(p) is None


# --- newer than this fr --------------------------------------------------


@pytest.mark.parametrize("kind", sorted(EXPECTED_KINDS))
def test_an_artifact_from_the_future_says_upgrade_fr_not_chain_gap(
    tmp_path: Path, kind: str
) -> None:
    """A stamp above `current_version` is a NEWER fr's artifact. "The chain
    has a gap" blames the registry for what is really "your fr is old" — and
    the fix for the two is opposite (write a migration vs. upgrade)."""
    from fr.artifacts.validate import validate_repo

    seeded = _seed_one(tmp_path, kind, version=99)
    assert seeded is not None

    report = validate_repo(tmp_path)

    problems = " ".join(str(i) for i in report.issues)
    assert not report.ok
    assert "upgrade" in problems.lower(), problems
    assert "chain" not in problems.lower(), problems


def _seed_one(root: Path, kind: str, *, version: int) -> Path | None:
    """One artifact of `kind`, stamped `version`, at its locator."""
    from tests.unit.test_validate_artifacts import PLAN_SLUG, seed_good_repo

    seed_good_repo(root)
    target = {
        "plan": root / "docs" / "superpowers" / "plans" / PLAN_SLUG / "_meta.yaml",
        "journal": next((root / "docs" / "superpowers" / "journals").rglob("*.md")),
        "run": next((root / "docs" / "superpowers" / "runs").glob("*.yaml")),
        "matrix": root / "docs" / "acceptance" / "matrix.yaml",
        "spec": next((root / "docs" / "superpowers" / "specs").glob("*.md")),
    }[kind]
    artifact_kind(kind).write_version(target, version)
    return target


# --- CRLF and BOM for the NON-yaml carriers too (r5-e10) ------------------
#
# The yaml carriers had these covered; the journal and the spec did not, and
# both were broken in the same way: a writer that read the file with a
# different function than the reader used, so the two disagreed about where
# the stamp was and the writer added a second one.


def test_a_bom_crlf_journal_is_restamped_in_place(tmp_path: Path) -> None:
    """`_write_journal_stamp` read with `read_text`, so the BOM sat in front of
    the stamp and the match failed — leaving TWO stamps declaring two versions,
    with every line ending rewritten as a bonus."""
    p = tmp_path / "j.md"
    p.write_bytes(b"\xef\xbb\xbf<!-- fr:journal-schema=1 -->\r\n# T\r\nBody\r\n")

    artifact_kind("journal").write_version(p, 2)

    assert p.read_bytes() == b"\xef\xbb\xbf<!-- fr:journal-schema=2 -->\r\n# T\r\nBody\r\n"
    assert artifact_kind("journal").read_stamp(p) == 2


def test_a_crlf_journal_gaining_its_first_stamp_gets_a_crlf_stamp_line(tmp_path: Path) -> None:
    p = tmp_path / "j.md"
    p.write_bytes(b"# T\r\nBody\r\n")

    artifact_kind("journal").write_version(p, 1)

    assert p.read_bytes() == b"<!-- fr:journal-schema=1 -->\r\n# T\r\nBody\r\n"


def test_a_crlf_spec_front_matter_is_seen_at_all(tmp_path: Path) -> None:
    """`_FRONT_MATTER_RE` required `\\n`, so a CRLF spec's front matter was
    invisible: the stamp read as absent (version 1 forever) and the writer
    prepended a SECOND `---` block above the real one, once per migration."""
    p = tmp_path / "s.md"
    p.write_bytes(b"---\r\nfr_schema: 1\r\ntitle: x\r\n---\r\n# Design\r\n")

    assert artifact_kind("spec").read_stamp(p) == 1

    artifact_kind("spec").write_version(p, 2)

    assert p.read_bytes() == b"---\r\nfr_schema: 2\r\ntitle: x\r\n---\r\n# Design\r\n"
    assert p.read_bytes().count(b"---") == 2


def test_a_crlf_spec_gaining_fr_schema_keeps_crlf_throughout(tmp_path: Path) -> None:
    """The key is inserted into the EXISTING block, with the file's own line
    ending — not an LF island in a CRLF file."""
    p = tmp_path / "s.md"
    p.write_bytes(b"---\r\ntitle: x\r\n---\r\n# D\r\n")

    artifact_kind("spec").write_version(p, 2)

    assert p.read_bytes() == b"---\r\nfr_schema: 2\r\ntitle: x\r\n---\r\n# D\r\n"


def test_a_bom_spec_keeps_its_bom_and_one_front_matter_block(tmp_path: Path) -> None:
    p = tmp_path / "s.md"
    p.write_bytes(b"\xef\xbb\xbf---\nfr_schema: 1\n---\n# D\n")

    artifact_kind("spec").write_version(p, 2)

    assert p.read_bytes() == b"\xef\xbb\xbf---\nfr_schema: 2\n---\n# D\n"
