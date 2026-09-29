"""`fr plan proportionality` (2026-09-24 fr-goal-scope-proportion-cost spec §C).

Every fixture is a real git repo in tmp_path with a local bare repository as
`origin`, so the merge-base, the default-ref lookup and the diff are git's own
answers rather than a stub's. Nothing here touches the checkout under test.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.journal.model import JournalEntry, append_journal_entry, journal_path
from fr.parser import parse as parse_plan
from fr.plan_ops import PhaseSpec, create
from fr.proportionality import build_report, run_report
from typer.testing import CliRunner

runner = CliRunner()
SLUG = "2026-09-24-toy"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _repo(
    tmp_path: Path,
    *,
    files: tuple[str, ...] = ("src/**",),
    estimate: int | None = None,
    with_origin: bool = True,
) -> Path:
    """A repo whose `main` is pushed to a bare `origin`, then a feature branch
    carrying a plan. `files`/`estimate` land on phase 1."""
    repo = tmp_path / "work"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _write(repo, "src/app.py", "import helper\n")
    _write(repo, "src/helper.py", "X = 1\n")
    _write(repo, "README.md", "readme\n")
    _commit_all(repo, "base")
    if with_origin:
        bare = tmp_path / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        _git(repo, "remote", "add", "origin", str(bare))
        _git(repo, "push", "-q", "origin", "main")
    _git(repo, "checkout", "-q", "-b", "feat/x")
    (repo / "docs" / "superpowers" / "plans").mkdir(parents=True)
    create(
        repo_root=repo,
        slug=SLUG,
        spec=None,
        target_repo="derio-net/test",
        fr_version=">=3.0.0,<5.0.0",
        phases=[
            PhaseSpec(
                number=1,
                title="Build",
                tag="agentic",
                skeleton=True,
                files=files,
                estimate_lines=estimate,
            )
        ],
        prose="# x\n",
    )
    _commit_all(repo, "plan")
    return repo


def _plan(repo: Path):
    return parse_plan(repo / "docs" / "superpowers" / "plans" / SLUG)


def _journal(
    repo: Path, entry_id: str, kind: str, title: str, body: str, *, commit: bool = True
) -> None:
    """Append a plan-journal entry and (by default) commit it — the report
    reads the journal at HEAD, never the working tree (review p3-f4)."""
    extra = {"state": "open"} if kind == "finding" else {}
    append_journal_entry(
        journal_path(repo, "plan", SLUG),
        SLUG,
        JournalEntry(
            kind=kind,  # type: ignore[arg-type]
            scope="plan",
            id=entry_id,
            created="2026-09-24T10:00:00",
            phase=1,
            title=title,
            body=body,
            **extra,  # type: ignore[arg-type]
        ),
    )
    if commit:
        _commit_all(repo, f"journal {entry_id}")


def _section(report: str, heading: str) -> str:
    """The body of one `## <heading>` section."""
    tail = report.split(f"## {heading}", 1)[1]
    return tail.split("\n## ", 1)[0]


# ── header and base ──────────────────────────────────────────────────────────


def test_the_first_line_records_the_merge_base_sha(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    base_sha = _git(repo, "rev-parse", "main")
    _write(repo, "src/more.py", "import helper\n")
    _commit_all(repo, "work")

    report = build_report(repo, _plan(repo), None)

    assert base_sha in report.splitlines()[0]
    # Only the SHA: the base's NAME differs across clones (`origin`,
    # `upstream`) and would change the bytes deliver hashes (review p3-f4).
    assert "origin" not in report.splitlines()[0]


def test_the_diff_is_from_the_merge_base_not_the_moving_base(tmp_path: Path) -> None:
    """A commit landing on main after the branch forked is not this branch's
    touch; diffing against the base tip would report it."""
    repo = _repo(tmp_path)
    fork = _git(repo, "rev-parse", "main")
    _git(repo, "checkout", "-q", "main")
    _write(repo, "unrelated/landed.py", "Y = 2\n")
    _commit_all(repo, "landed on main")
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "checkout", "-q", "feat/x")

    report = build_report(repo, _plan(repo), None)

    assert fork in report.splitlines()[0]
    assert "unrelated/landed.py" not in report


def test_no_determinable_base_is_a_single_line_naming_base(tmp_path: Path) -> None:
    repo = _repo(tmp_path, with_origin=False)

    report = build_report(repo, _plan(repo), None)

    assert len(report.strip().splitlines()) == 1
    assert "--base" in report


def test_an_unresolvable_explicit_base_is_a_single_line_naming_base(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    report = build_report(repo, _plan(repo), "origin/nope")

    assert len(report.strip().splitlines()) == 1
    assert "--base" in report


def test_an_explicit_base_is_honoured(tmp_path: Path) -> None:
    repo = _repo(tmp_path, with_origin=False)
    base_sha = _git(repo, "rev-parse", "main")

    result = run_report(repo, _plan(repo), "main")

    assert result.merge_base == base_sha
    assert base_sha in result.text.splitlines()[0]


# ── section 1: unreferenced new files ────────────────────────────────────────


def test_an_added_file_referenced_nowhere_is_listed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo, "src/scratch_fixture.json", "{}\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Unreferenced new files")

    assert "src/scratch_fixture.json" in section


def test_an_added_file_referenced_by_path_is_not_listed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo, "src/data/table.csv", "a,b\n")
    _write(repo, "src/loader.py", "open('src/data/table.csv')\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Unreferenced new files")

    assert "src/data/table.csv" not in section


def test_an_added_file_referenced_by_stem_is_not_listed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo, "src/widget.py", "W = 1\n")
    _write(repo, "src/app.py", "import helper\nimport widget\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Unreferenced new files")

    assert "src/widget.py" not in section


def test_a_stem_under_four_characters_does_not_count_as_a_reference(tmp_path: Path) -> None:
    """A three-letter stem matches half the repo by accident."""
    repo = _repo(tmp_path)
    _write(repo, "src/abc.py", "Z = 1\n")
    _write(repo, "src/app.py", "import helper\n# abc\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Unreferenced new files")

    assert "src/abc.py" in section


def test_fr_artifacts_are_exempt_from_the_unreferenced_check(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo, "docs/superpowers/journals/plans/other.md", "# j\n")
    _write(repo, "docs/acceptance/report_linked.md", "# r\n")
    _commit_all(repo, "work")

    report = build_report(repo, _plan(repo), None)

    assert "docs/superpowers" not in _section(report, "Unreferenced new files")
    assert "docs/acceptance" not in _section(report, "Unreferenced new files")


# ── section 2: out-of-plan touches ───────────────────────────────────────────


def test_a_touch_outside_every_phase_glob_is_flagged(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo, "src/helper.py", "X = 2\n")
    _write(repo, "README.md", "readme, edited\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Out-of-plan touches")

    assert "README.md" in section
    assert "src/helper.py" not in section  # `src/**` covers it


def test_a_glob_star_spans_directories(tmp_path: Path) -> None:
    repo = _repo(tmp_path, files=("src/*",))
    _write(repo, "src/deep/nested/mod.py", "import helper\n")
    _write(repo, "src/app.py", "import helper\nimport mod\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Out-of-plan touches")

    assert "src/deep/nested/mod.py" not in section


def test_a_touch_named_in_a_journal_finding_is_justified_by_it(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo, "README.md", "readme, edited\n")
    _write(repo, "setup.cfg", "[x]\n")
    _commit_all(repo, "work")
    _journal(repo, "p1-f3", "finding", "README drift", "README.md named a removed flag")

    section = _section(build_report(repo, _plan(repo), None), "Out-of-plan touches")

    readme = next(line for line in section.splitlines() if "README.md" in line)
    assert "justified by p1-f3" in readme
    setup = next(line for line in section.splitlines() if "setup.cfg" in line)
    assert "justified" not in setup


def test_a_touch_named_in_a_deviation_decision_is_justified_by_it(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo, "README.md", "readme, edited\n")
    _commit_all(repo, "work")
    _journal(repo, "v-p1-x", "decision", "DEVIATION: also touched README.md", "why")

    section = _section(build_report(repo, _plan(repo), None), "Out-of-plan touches")

    assert "justified by v-p1-x" in section


def test_a_plain_decision_naming_the_path_does_not_justify_it(tmp_path: Path) -> None:
    """Only a finding or a recorded deviation says "this touch was not the
    plan's, and here is why" — an ordinary decision is not that claim."""
    repo = _repo(tmp_path)
    _write(repo, "README.md", "readme, edited\n")
    _commit_all(repo, "work")
    _journal(repo, "d-1", "decision", "chose a layout", "README.md stays short")

    section = _section(build_report(repo, _plan(repo), None), "Out-of-plan touches")

    assert "justified" not in section


def test_with_no_phase_declaring_files_the_section_says_so(tmp_path: Path) -> None:
    repo = _repo(tmp_path, files=())
    _write(repo, "README.md", "readme, edited\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Out-of-plan touches")

    assert "no phase declares `files`" in section
    assert "README.md" not in section


def test_fr_artifacts_are_never_out_of_plan(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo, "docs/superpowers/runs/r.yaml", "x: 1\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Out-of-plan touches")

    assert "docs/superpowers" not in section


# ── section 3: size ──────────────────────────────────────────────────────────


def _lines(n: int) -> str:
    return "".join(f"import helper  # {i}\n" for i in range(n))


def test_size_above_twice_the_estimate_is_flagged(tmp_path: Path) -> None:
    repo = _repo(tmp_path, estimate=10)
    _write(repo, "src/big.py", _lines(25))
    _write(repo, "src/app.py", "import helper\nimport big\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Size")

    assert "26" in section  # 25 added + 1 added in app.py
    assert "above 2×" in section
    assert "PR body" in section


def test_size_within_twice_the_estimate_is_not_flagged(tmp_path: Path) -> None:
    repo = _repo(tmp_path, estimate=20)
    _write(repo, "src/big.py", _lines(25))
    _write(repo, "src/app.py", "import helper\nimport big\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Size")

    assert "above 2×" not in section
    assert "1.3" in section  # 26 / 20


def test_size_without_an_estimate_prints_no_ratio(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo, "src/big.py", _lines(5))
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Size")

    assert "5" in section
    assert "×" not in section
    assert "no phase declares `estimate_lines`" in section


def test_size_counts_deletions(tmp_path: Path) -> None:
    repo = _repo(tmp_path, estimate=100)
    (repo / "src" / "helper.py").unlink()
    _write(repo, "src/app.py", "")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Size")

    assert "2 lines" in section


def test_the_validator_wrapper_is_an_fr_artifact(tmp_path: Path) -> None:
    """`fr plan create` writes scripts/validate-plans.sh on a repo's first plan
    (gh#610 §3.B); it is fr's bookkeeping, not work the estimate covered."""
    (tmp_path / "plain").mkdir()
    (tmp_path / "wrapper").mkdir()
    plain = _repo(tmp_path / "plain", estimate=100)
    _write(plain, "src/app.py", "x = 1\n")
    _commit_all(plain, "work")

    with_wrapper = _repo(tmp_path / "wrapper", estimate=100)
    _write(with_wrapper, "src/app.py", "x = 1\n")
    _write(with_wrapper, "scripts/validate-plans.sh", "#!/usr/bin/env bash\nexit 0\n")
    _commit_all(with_wrapper, "work")

    report = build_report(with_wrapper, _plan(with_wrapper), None)

    assert "validate-plans.sh" not in report
    assert _section(report, "Size") == _section(build_report(plain, _plan(plain), None), "Size")


# ── determinism and the CLI ──────────────────────────────────────────────────


def test_the_report_is_deterministic(tmp_path: Path) -> None:
    """deliver stores its SHA-256, so two runs at one HEAD must agree."""
    repo = _repo(tmp_path)
    _write(repo, "src/scratch.json", "{}\n")
    _commit_all(repo, "work")

    first = build_report(repo, _plan(repo), None)
    second = build_report(repo, _plan(repo), None)

    assert hashlib.sha256(first.encode()).hexdigest() == hashlib.sha256(second.encode()).hexdigest()


@pytest.mark.parametrize("with_origin", [True, False])
def test_the_cli_always_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, with_origin: bool
) -> None:
    repo = _repo(tmp_path, with_origin=with_origin, estimate=1)
    _write(repo, "src/scratch.json", "{}\n" * 10)
    _write(repo, "README.md", "edited\n")
    _commit_all(repo, "work")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["plan", "proportionality", f"docs/superpowers/plans/{SLUG}"])

    assert result.exit_code == 0, result.output
    assert result.output.strip()


def test_the_cli_passes_base_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, with_origin=False)
    monkeypatch.chdir(repo)

    result = runner.invoke(
        app, ["plan", "proportionality", f"docs/superpowers/plans/{SLUG}", "--base", "main"]
    )

    assert result.exit_code == 0, result.output
    assert _git(repo, "rev-parse", "main") in result.output


# ── review p3-f1: runner-discovered test modules ─────────────────────────────


@pytest.mark.parametrize(
    "module", ["tests/unit/test_widget.py", "tests/widget_test.py", "tests/conftest.py"]
)
def test_a_new_test_module_is_not_listed_while_a_sibling_fixture_is(
    tmp_path: Path, module: str
) -> None:
    """A test runner loads these by NAME, so "nothing references them" is
    their normal state — listing them drowned gh#597's signal on this very
    branch. The scratch fixture beside them is still what the section is for."""
    repo = _repo(tmp_path)
    _write(repo, module, "def test_x():\n    pass\n")
    _write(repo, "tests/fixtures/scratch_payload.json", "{}\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Unreferenced new files")

    assert module not in section
    assert "tests/fixtures/scratch_payload.json" in section


def test_a_new_helper_module_under_tests_is_still_listed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo, "tests/unit/orphan_helpers.py", "def h():\n    pass\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Unreferenced new files")

    assert "tests/unit/orphan_helpers.py" in section


# ── review p3-f2: whole-word references, and directory loads ─────────────────


def test_a_stem_inside_a_longer_word_is_not_a_reference(tmp_path: Path) -> None:
    """`data` inside `metadata` or `dataset` is not a reference to data.py."""
    repo = _repo(tmp_path)
    _write(repo, "src/data.py", "D = 1\n")
    _write(repo, "src/app.py", "import helper\nmetadata = dataset = 1\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Unreferenced new files")

    assert "src/data.py" in section


def test_a_file_in_a_new_directory_loaded_by_its_path_is_not_listed(tmp_path: Path) -> None:
    """Fixtures are often loaded by globbing their directory: a reference to
    the directory the branch created is a reference to what is in it."""
    repo = _repo(tmp_path)
    _write(repo, "tests/fixtures/cursors_v9/2026-01-01-a.yaml", "a: 1\n")
    _write(repo, "src/app.py", "import helper\nglob('tests/fixtures/cursors_v9/*.yaml')\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Unreferenced new files")

    assert "cursors_v9" not in section


def test_a_reference_to_a_pre_existing_parent_directory_does_not_count(tmp_path: Path) -> None:
    """`src` is named all over any repo; if naming an OLD directory counted,
    every new file under it would pass — the false negative this section
    exists to avoid. Only directories the branch created count."""
    repo = _repo(tmp_path)
    _write(repo, "src/lonely_scratch.json", "{}\n")
    _write(repo, "README.md", "code lives in src/ and src\n")
    _commit_all(repo, "work")

    section = _section(build_report(repo, _plan(repo), None), "Unreferenced new files")

    assert "src/lonely_scratch.json" in section


# ── review p3-f4: a pure function of HEAD ───────────────────────────────────


def test_an_uncommitted_journal_edit_does_not_change_the_report(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo, "README.md", "readme, edited\n")
    _commit_all(repo, "work")
    before = build_report(repo, _plan(repo), None)

    _journal(repo, "p1-f9", "finding", "README drift", "README.md", commit=False)

    assert build_report(repo, _plan(repo), None) == before


def test_an_uncommitted_plan_edit_does_not_change_the_report(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo, "README.md", "readme, edited\n")
    _commit_all(repo, "work")
    before = build_report(repo, _plan(repo), None)
    phase = repo / "docs" / "superpowers" / "plans" / SLUG / "01.yaml"
    phase.write_text(phase.read_text().replace("- src/**", "- '**'"))

    assert build_report(repo, _plan(repo), None) == before


def test_a_plan_not_committed_at_head_is_one_line(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "rm", "-q", "-r", "--cached", "docs/superpowers/plans")
    _git(repo, "commit", "-q", "-m", "untrack the plan")  # files stay on disk

    result = run_report(repo, _plan(repo), None)

    assert result.merge_base is None
    assert len(result.text.strip().splitlines()) == 1
    assert "HEAD" in result.text


# ── review p3-f5: git grep failure is not "unreferenced" ─────────────────────


def test_a_failing_git_grep_is_reported_not_read_as_no_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess as sp

    import fr.proportionality as prop

    repo = _repo(tmp_path)
    _write(repo, "src/new_thing.json", "{}\n")
    _commit_all(repo, "work")
    real = prop.git_answer

    def broken(root: Path, *args: str, **kw):
        if args and args[0] == "grep":
            return sp.CompletedProcess(["git", *args], 128, "", "fatal: boom")
        return real(root, *args, **kw)

    monkeypatch.setattr(prop, "git_answer", broken)

    result = run_report(repo, _plan(repo), None)

    assert result.merge_base is None
    assert "src/new_thing.json" not in result.text
    assert "git could not answer" in result.text


# ── review p3-f6: renames, deletions, binaries ───────────────────────────────


def test_a_rename_is_a_delete_plus_an_add(tmp_path: Path) -> None:
    repo = _repo(tmp_path, estimate=100)
    _git(repo, "mv", "src/helper.py", "src/renamed_helper.py")
    _commit_all(repo, "rename")

    report = build_report(repo, _plan(repo), None)

    assert "src/renamed_helper.py" in _section(report, "Unreferenced new files")
    assert "2 lines changed (+1 -1" in _section(report, "Size")


def test_a_deleted_file_outside_the_plan_is_an_out_of_plan_touch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "README.md").unlink()
    _commit_all(repo, "delete")

    report = build_report(repo, _plan(repo), None)

    assert "README.md" in _section(report, "Out-of-plan touches")
    assert "README.md" not in _section(report, "Unreferenced new files")


def test_a_binary_file_counts_zero_lines(tmp_path: Path) -> None:
    repo = _repo(tmp_path, estimate=100)
    (repo / "src" / "blob.bin").write_bytes(b"\x00\x01\x02" * 50)
    _commit_all(repo, "binary")

    section = _section(build_report(repo, _plan(repo), None), "Size")

    assert "0 lines changed (+0 -0" in section


# ── ## Phases: agentic phases against the spec's asks (2026-09-28 phase-sizing §D)

SIZED = "2026-09-28-sized"
SIZED_SPEC = "docs/superpowers/specs/2026-09-28-sized-design.md"
SIZED_REQUIREMENTS = """\
## Requirements

R1. First ask.
R2. Second ask.
R3. Third ask.
R4. Fourth ask.
"""

LEGACY_SIZED_REQUIREMENTS = """\
## Requirements

| id | requirement | source |
|---|---|---|
| R1 | First ask. | decision d1 |
| R2 | Second ask. | decision d2 |
| R3 | Third ask. | decision d3 |
| R4 | Fourth ask. | decision d4 |
"""
"""A spec written before 5.0.0: its table counts the same asks."""


def _sized_matrix(*, repo_key: bool = True) -> str:
    head = "org: derio-net\n" + ("repo: own\n" if repo_key else "") + "rows:\n"
    rows = ""
    for rid, reqs in (("row-r1", ["R1"]), ("row-r2", ["R2", "R3"]), ("row-r1b", ["R1"])):
        origins = "".join(f"    - own:{SIZED_SPEC}#{r}\n" for r in reqs)
        rows += (
            f"  - id: {rid}\n    capability: C\n    acceptance: A\n    origin:\n{origins}"
            "    levels: {}\n    status: not-implemented\n    notes: ''\n"
        )
    return head + rows


def _sized_repo(
    tmp_path: Path,
    phases: list[tuple[tuple[str, ...], str]],
    *,
    requirements: str | None = SIZED_REQUIREMENTS,
    matrix: str | None = None,
) -> Path:
    """A committed repo with a spec, a matrix and a plan whose phases are
    `(rows, tag)` pairs. `matrix=None` writes the default; `""` writes none."""
    repo = tmp_path / "work"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _write(repo, "README.md", "readme\n")
    _commit_all(repo, "base")
    _git(repo, "checkout", "-q", "-b", "feat/x")
    body = "# Sized\n\n" + (requirements + "\n" if requirements else "")
    body += "## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|--|--|--|--|\n"
    _write(repo, SIZED_SPEC, body)
    if matrix != "":
        _write(repo, "docs/acceptance/matrix.yaml", matrix or _sized_matrix())
    (repo / "docs" / "superpowers" / "plans").mkdir(parents=True, exist_ok=True)
    create(
        repo_root=repo,
        slug=SIZED,
        spec=SIZED_SPEC,
        target_repo="derio-net/own",
        fr_version=">=4.20.0,<5.0.0",
        phases=[
            PhaseSpec(number=i, title=f"P{i}", tag=tag, acceptance=rows)  # type: ignore[arg-type]
            for i, (rows, tag) in enumerate(phases, start=1)
        ],
        prose="# x\n",
    )
    _commit_all(repo, "plan")
    return repo


def _split(repo: Path, n: int, title: str, *, commit: bool = True) -> None:
    append_journal_entry(
        journal_path(repo, "spec", SIZED),
        SIZED,
        JournalEntry(
            kind="decision",
            scope="spec",
            id=f"phase-split-{SIZED}-p{n}",
            created="2026-09-28T10:00:00",
            title=title,
        ),
    )
    if commit:
        _commit_all(repo, f"split p{n}")


def _phases_report(repo: Path) -> str:
    plan = parse_plan(repo / "docs" / "superpowers" / "plans" / SIZED)
    return _section(build_report(repo, plan, "main"), "Phases")


def test_the_phases_section_follows_size(tmp_path: Path) -> None:
    repo = _sized_repo(tmp_path, [(("row-r1",), "agentic")])
    plan = parse_plan(repo / "docs" / "superpowers" / "plans" / SIZED)
    report = build_report(repo, plan, "main")
    assert report.index("## Size") < report.index("## Phases")


def test_the_745_shape_names_the_phase_with_no_ask(tmp_path: Path) -> None:
    repo = _sized_repo(
        tmp_path,
        [((), "agentic"), (("row-r1",), "agentic"), (("row-r2",), "agentic"), ((), "manual")],
    )
    body = _phases_report(repo)
    assert "3 agentic phases serve 3 of 4 requirements (R1, R2, R3)." in body
    assert "- phase 1 — no ask of its own; no split reason" in body
    assert "phase 2" not in body
    assert "phase 4" not in body  # a manual phase is not counted


def test_the_folded_shape_has_no_phase_without_an_ask(tmp_path: Path) -> None:
    repo = _sized_repo(tmp_path, [(("row-r1",), "agentic"), (("row-r2",), "agentic")])
    _split(repo, 2, "ask: the second ask")
    body = _phases_report(repo)
    assert "2 agentic phases serve 3 of 4 requirements (R1, R2, R3)." in body
    # #815: with every phase serving its own ask there is nothing to list, and
    # a bare `none.` under the count line reads as "no requirements served".
    assert "none." not in body
    assert body.strip().endswith("(R1, R2, R3).")


def test_a_phase_with_no_own_ask_shows_its_split_reason(tmp_path: Path) -> None:
    repo = _sized_repo(tmp_path, [(("row-r1",), "agentic"), (("row-r1b",), "agentic")])
    _split(repo, 2, "tier: needs the hard tier")
    body = _phases_report(repo)
    assert "2 agentic phases serve 1 of 4 requirements (R1)." in body
    assert "- phase 2 — no ask of its own; split reason: tier: needs the hard tier" in body
    assert "phase 1 —" not in body  # the waived phase leaves R1 to phase 1


def test_one_agentic_phase_reads_in_the_singular(tmp_path: Path) -> None:
    repo = _sized_repo(tmp_path, [(("row-r1", "row-r2"), "agentic")])
    assert "1 agentic phase serves 3 of 4 requirements (R1, R2, R3)." in _phases_report(repo)


def test_an_uncommitted_split_decision_does_not_change_the_report(tmp_path: Path) -> None:
    repo = _sized_repo(tmp_path, [(("row-r1",), "agentic"), (("row-r1b",), "agentic")])
    before = _phases_report(repo)
    _split(repo, 2, "tier: uncommitted", commit=False)
    assert _phases_report(repo) == before


def test_an_uncommitted_matrix_edit_does_not_change_the_report(tmp_path: Path) -> None:
    repo = _sized_repo(tmp_path, [(("row-r1",), "agentic")])
    before = _phases_report(repo)
    _write(repo, "docs/acceptance/matrix.yaml", _sized_matrix().replace("#R1", "#R4"))
    assert _phases_report(repo) == before


def test_an_archived_spec_journal_at_head_is_read(tmp_path: Path) -> None:
    from fr.journal.model import archived_journal_path

    repo = _sized_repo(tmp_path, [(("row-r1",), "agentic"), (("row-r1b",), "agentic")])
    append_journal_entry(
        archived_journal_path(repo, "spec", SIZED),
        SIZED,
        JournalEntry(
            kind="decision",
            scope="spec",
            id=f"phase-split-{SIZED}-p2",
            created="2026-09-28T10:00:00",
            title="review-size: archived",
        ),
    )
    _commit_all(repo, "archived journal")
    assert "split reason: review-size: archived" in _phases_report(repo)


def test_no_requirements_list_says_asks_cannot_be_counted(tmp_path: Path) -> None:
    repo = _sized_repo(tmp_path, [(("row-r1",), "agentic")], requirements=None)
    assert "spec has no Requirements list; asks cannot be counted." in _phases_report(repo)


def test_a_legacy_requirements_table_counts_the_same_asks(tmp_path: Path) -> None:
    phases = [(("row-r1",), "agentic"), (("row-r2",), "agentic")]
    (tmp_path / "legacy").mkdir()
    (tmp_path / "plain").mkdir()
    legacy = _sized_repo(tmp_path / "legacy", phases, requirements=LEGACY_SIZED_REQUIREMENTS)
    plain = _sized_repo(tmp_path / "plain", phases)
    assert _phases_report(legacy) == _phases_report(plain)


def test_no_matrix_says_asks_cannot_be_derived(tmp_path: Path) -> None:
    repo = _sized_repo(tmp_path, [((), "agentic")], matrix="")
    assert "no acceptance matrix; asks cannot be derived." in _phases_report(repo)


def test_a_matrix_naming_no_repo_says_asks_cannot_be_derived(tmp_path: Path) -> None:
    repo = _sized_repo(tmp_path, [(("row-r1",), "agentic")], matrix=_sized_matrix(repo_key=False))
    assert "matrix names no repo; asks cannot be derived." in _phases_report(repo)


def test_a_plan_with_no_spec_says_asks_cannot_be_counted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    report = build_report(repo, _plan(repo), None)
    assert "spec has no Requirements list; asks cannot be counted." in _section(report, "Phases")


def test_r2_an_uncommitted_meta_spec_edit_does_not_change_the_report(tmp_path: Path) -> None:
    repo = _sized_repo(tmp_path, [(("row-r1",), "agentic")])
    before = _phases_report(repo)
    meta = repo / "docs" / "superpowers" / "plans" / SIZED / "_meta.yaml"
    meta.write_text(meta.read_text().replace("2026-09-28-sized-design.md", "other-design.md"))
    _write(repo, "docs/superpowers/specs/other-design.md", "# other\n")
    assert _phases_report(repo) == before


def test_r2_an_uncommitted_archive_move_of_the_spec_does_not_change_the_report(
    tmp_path: Path,
) -> None:
    repo = _sized_repo(tmp_path, [(("row-r1",), "agentic")])
    before = _phases_report(repo)
    assert "1 agentic phase serves" in before
    archived = SIZED_SPEC.replace("docs/superpowers/specs/", "docs/superpowers/implemented/specs/")
    (repo / archived).parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", SIZED_SPEC, archived)
    assert _phases_report(repo) == before


def test_r2_a_spec_archived_at_head_is_found_under_its_archive_root(tmp_path: Path) -> None:
    repo = _sized_repo(tmp_path, [(("row-r1",), "agentic")])
    archived = SIZED_SPEC.replace("docs/superpowers/specs/", "docs/superpowers/implemented/specs/")
    (repo / archived).parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", SIZED_SPEC, archived)
    _commit_all(repo, "archive spec")
    assert "1 agentic phase serves 1 of 4 requirements (R1)." in _phases_report(repo)
