"""Tests for vk.plan.format — format enum and detection from markdown."""

import pytest

from vk.plan.format import PlanFormat, detect

# --- Enum properties ---


def test_phased_can_dispatch() -> None:
    assert PlanFormat.PHASED.can_dispatch is True


def test_flat_cannot_dispatch() -> None:
    assert PlanFormat.FLAT.can_dispatch is False


# --- Detection from markdown ---

PHASED_MARKDOWN = """\
# My Plan

**Spec:** `some/spec.md`
**Status:** Not Started

---

## Phase 1: Setup [agentic]

### Task 1: Create files

- [ ] **Step 1: Do something**
"""

FLAT_MARKDOWN = """\
# My Plan

**Spec:** `some/spec.md`
**Status:** Not Started

---

### Task 1: Create files [agentic]

- [ ] **Step 1: Do something**
"""

NO_PLAN_MARKDOWN = """\
# Just a document

Some text without any task headers.
"""


def test_detect_phased() -> None:
    assert detect(PHASED_MARKDOWN) is PlanFormat.PHASED


def test_detect_flat() -> None:
    assert detect(FLAT_MARKDOWN) is PlanFormat.FLAT


def test_detect_not_a_plan() -> None:
    with pytest.raises(ValueError, match="not a vk plan"):
        detect(NO_PLAN_MARKDOWN)


def test_detect_phased_with_multiple_phases() -> None:
    md = "## Phase 1: Setup [agentic]\n\n### Task 1: First\n\n## Phase 2: Build [agentic]\n"
    assert detect(md) is PlanFormat.PHASED


def test_detect_phase_header_variations() -> None:
    """Phase header with different tags and numbers."""
    md = "## Phase 3: Deploy [manual]\n\n### Task 1: Upload\n"
    assert detect(md) is PlanFormat.PHASED


def test_detect_flat_task_only() -> None:
    """Flat format with only task headers, no phase headers."""
    md = "### Task 1: First [agentic]\n\n### Task 2: Second [manual]\n"
    assert detect(md) is PlanFormat.FLAT
