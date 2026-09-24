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


def _journal(repo: Path, entry_id: str, kind: str, title: str, body: str) -> None:
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
    assert "origin/main" in report.splitlines()[0]


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
