"""Unit tests for fr.plan_config — strip dead keys from plan-config.yaml.

Dead keys (read by no code): `plan.save_to` and the entire top-level
`dispatch:` block. Live keys (read by scripts/validate-plans.sh):
`plan.filename`, `header.required`, `header.status_values`. The stripper is
text-based: it preserves live keys, comments, and formatting, and is idempotent.
"""

from __future__ import annotations

from pathlib import Path

import yaml

LIVE = """\
plan:
  filename: "YYYY-MM-DD-{name}.md"

header:
  required:
    - Spec
    - Status
  status_values:
    - Not Started
"""

DEAD_MIDDLE = """\
plan:
  filename: "YYYY-MM-DD-{name}.md"
  save_to: docs/superpowers/plans/

dispatch:
  target: github-issues
  owner: derio-net
  labels:
    agentic: fr:ready

header:
  required:
    - Spec
    - Status
"""

DEAD_EOF = """\
plan:
  filename: "YYYY-MM-DD-{name}.md"
  save_to: docs/superpowers/plans/

header:
  required:
    - Spec

dispatch:
  target: github-issues
  owner: derio-net
"""


def test_strip_removes_save_to_and_dispatch_middle() -> None:
    from fr.plan_config import strip_dead_keys

    out, removals = strip_dead_keys(DEAD_MIDDLE)
    assert "save_to" not in out
    # No ACTIVE dispatch mapping remains.
    data = yaml.safe_load(out)
    assert "dispatch" not in data
    assert "save_to" not in data["plan"]
    # Live keys survive.
    assert data["plan"]["filename"] == "YYYY-MM-DD-{name}.md"
    assert data["header"]["required"] == ["Spec", "Status"]
    assert set(removals) == {"plan.save_to", "dispatch"}


def test_strip_removes_dispatch_at_eof() -> None:
    from fr.plan_config import strip_dead_keys

    out, removals = strip_dead_keys(DEAD_EOF)
    data = yaml.safe_load(out)
    assert "dispatch" not in data
    assert "save_to" not in data["plan"]
    assert data["header"]["required"] == ["Spec"]
    assert set(removals) == {"plan.save_to", "dispatch"}
    # No trailing blank-line pileup.
    assert not out.endswith("\n\n")


def test_strip_preserves_comments_and_live_keys() -> None:
    from fr.plan_config import strip_dead_keys

    text = "# top comment\n" + DEAD_MIDDLE
    out, _ = strip_dead_keys(text)
    assert "# top comment" in out
    assert 'filename: "YYYY-MM-DD-{name}.md"' in out


def test_strip_leaves_commented_dead_keys_alone() -> None:
    from fr.plan_config import strip_dead_keys

    text = LIVE + "\n# dispatch:\n#   owner: x\n# save_to: nope\n"
    out, removals = strip_dead_keys(text)
    assert "# dispatch:" in out
    assert "# save_to: nope" in out
    assert removals == []


def test_strip_is_noop_on_clean_text() -> None:
    from fr.plan_config import strip_dead_keys

    out, removals = strip_dead_keys(LIVE)
    assert out == LIVE  # byte-identical when nothing to strip
    assert removals == []


def test_strip_is_idempotent() -> None:
    from fr.plan_config import strip_dead_keys

    once, _ = strip_dead_keys(DEAD_MIDDLE)
    twice, removals = strip_dead_keys(once)
    assert twice == once
    assert removals == []


def test_strip_only_removes_save_to_inside_plan_block() -> None:
    from fr.plan_config import strip_dead_keys

    # A `save_to:` nested under some OTHER top-level key is not the dead
    # `plan.save_to` and must be preserved (spec contract).
    text = (
        'plan:\n  filename: "YYYY-MM-DD-{name}.md"\n\n'
        "header:\n  save_to: keep-me\n  required:\n    - Status\n"
    )
    out, removals = strip_dead_keys(text)
    assert "save_to: keep-me" in out
    assert removals == []


# --- strip_dead_keys_file ----------------------------------------------------


def test_strip_file_writes_and_reports(tmp_path: Path) -> None:
    from fr.plan_config import strip_dead_keys_file

    cfg = tmp_path / "docs" / "superpowers" / "plan-config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(DEAD_MIDDLE)
    removals = strip_dead_keys_file(cfg)
    assert set(removals) == {"plan.save_to", "dispatch"}
    data = yaml.safe_load(cfg.read_text())
    assert "dispatch" not in data and "save_to" not in data["plan"]


def test_strip_file_absent_returns_empty(tmp_path: Path) -> None:
    from fr.plan_config import strip_dead_keys_file

    assert strip_dead_keys_file(tmp_path / "nope.yaml") == []


def test_strip_file_clean_does_not_rewrite(tmp_path: Path) -> None:
    from fr.plan_config import strip_dead_keys_file

    cfg = tmp_path / "plan-config.yaml"
    cfg.write_text(LIVE)
    before = cfg.read_text()
    removals = strip_dead_keys_file(cfg)
    assert removals == []
    assert cfg.read_text() == before
