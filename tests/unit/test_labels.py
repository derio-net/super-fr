"""Tests for the canonical label registry."""

from __future__ import annotations

import re

import pytest
from fr import labels

HEX_RE = re.compile(r"^[0-9A-Fa-f]{6}$")


class TestLabelDef:
    def test_all_constants_have_six_char_hex_color(self) -> None:
        for ld in (
            labels.VK_READY,
            labels.MANUAL,
            labels.IN_PROGRESS,
            labels.PR_READY,
            labels.VK_SYNCED,
        ):
            assert HEX_RE.match(ld.color), f"{ld.name}: bad color {ld.color!r}"

    def test_all_constants_have_non_empty_description(self) -> None:
        for ld in (
            labels.VK_READY,
            labels.MANUAL,
            labels.IN_PROGRESS,
            labels.PR_READY,
            labels.VK_SYNCED,
        ):
            assert ld.description, f"{ld.name}: empty description"

    def test_lifecycle_names_are_unique(self) -> None:
        names = [
            labels.VK_READY.name,
            labels.MANUAL.name,
            labels.IN_PROGRESS.name,
            labels.PR_READY.name,
            labels.VK_SYNCED.name,
        ]
        assert len(names) == len(set(names))

    def test_lifecycle_names_match_spec(self) -> None:
        assert labels.VK_READY.name == "vk-ready"
        assert labels.MANUAL.name == "manual"
        assert labels.IN_PROGRESS.name == "in-progress"
        assert labels.PR_READY.name == "pr-ready"
        assert labels.VK_SYNCED.name == "vk-synced"

    @pytest.mark.parametrize("bad_color", ["", "abc", "abcde", "1234567", "xxxxxx", "#ABCDEF"])
    def test_rejects_non_hex_color(self, bad_color: str) -> None:
        with pytest.raises(ValueError, match="6-char hex"):
            labels.LabelDef("x", bad_color, "desc")

    def test_accepts_uppercase_and_lowercase_hex(self) -> None:
        labels.LabelDef("upper", "ABCDEF", "desc")
        labels.LabelDef("lower", "abcdef", "desc")
        labels.LabelDef("mixed", "AbCdEf", "desc")


class TestPlanLabel:
    def test_renders_name(self) -> None:
        assert labels.plan_label("foo").name == "plan:foo"

    def test_color_is_canonical(self) -> None:
        assert labels.plan_label("foo").color == labels.PLAN_LABEL_COLOR

    def test_description_includes_slug(self) -> None:
        assert "foo" in labels.plan_label("foo").description


class TestPhaseLabel:
    def test_renders_name(self) -> None:
        assert labels.phase_label(3).name == "phase:3"

    def test_color_is_canonical(self) -> None:
        assert labels.phase_label(3).color == labels.PHASE_LABEL_COLOR

    def test_description_includes_number(self) -> None:
        assert "3" in labels.phase_label(3).description


class TestNormalizeLabelSlug:
    """Frank's `YYYY-MM-DD--<layer>--<topic>` slugs produced labels with a
    leading dash (spec:) or an embedded date (plan:). Normalization strips
    the date prefix PLUS all dashes that follow it, in one place."""

    def test_strips_date_and_double_dash(self) -> None:
        assert (
            labels.normalize_label_slug("2026-05-27--auto--awx-deployment")
            == "auto--awx-deployment"
        )

    def test_strips_date_and_single_dash(self) -> None:
        assert labels.normalize_label_slug("2026-05-27-single-dash") == "single-dash"

    def test_no_date_prefix_passes_through(self) -> None:
        assert (
            labels.normalize_label_slug("agents--restart-resilience")
            == "agents--restart-resilience"
        )

    def test_date_not_at_start_passes_through(self) -> None:
        assert labels.normalize_label_slug("awx-2026-05-27-redo") == "awx-2026-05-27-redo"

    def test_date_only_slug_normalizes_to_empty(self) -> None:
        assert labels.normalize_label_slug("2026-05-27-") == ""

    def test_plan_label_strips_date_prefix(self) -> None:
        assert (
            labels.plan_label("2026-05-27--auto--awx-deployment").name
            == "plan:auto--awx-deployment"
        )

    def test_spec_label_has_no_leading_dash(self) -> None:
        assert (
            labels.spec_label("2026-05-27--auto--awx-deployment-design").name
            == "spec:auto--awx-deployment-design"
        )


class TestRegistryLookup:
    def test_lifecycle_dict_keys_are_role_names(self) -> None:
        assert set(labels.LIFECYCLE.keys()) == {
            "vk_ready",
            "vk_blocked",
            "manual",
            "in_progress",
            "pr_ready",
        }

    def test_lifecycle_values_match_module_constants(self) -> None:
        assert labels.LIFECYCLE["vk_ready"] is labels.VK_READY
        assert labels.LIFECYCLE["vk_blocked"] is labels.VK_BLOCKED
        assert labels.LIFECYCLE["manual"] is labels.MANUAL
        assert labels.LIFECYCLE["in_progress"] is labels.IN_PROGRESS
        assert labels.LIFECYCLE["pr_ready"] is labels.PR_READY


class TestBoundedLabelNames:
    """#249: GitHub caps label names at 50 chars. Slug-derived labels must
    stay within that, truncating with a stable hash so long slugs don't 422."""

    def test_long_plan_slug_label_bounded_to_50(self) -> None:
        slug = "2026-05-23--obs--hop-blog-edge-monitoring-rework-1"  # 50 -> 'plan:'+slug = 55
        lab = labels.plan_label(slug)
        assert len(lab.name) <= 50, f"label too long: {lab.name!r} ({len(lab.name)})"
        assert lab.name.startswith("plan:")
        # deterministic across calls
        assert labels.plan_label(slug).name == lab.name
        # distinct long slugs -> distinct labels (hash prevents collision)
        assert labels.plan_label(slug + "-extra").name != lab.name
        # full slug preserved in the human-readable description
        assert slug in lab.description

    def test_short_slug_labels_unchanged(self) -> None:
        assert labels.plan_label("2026-05-09-short").name == "plan:short"
        assert labels.spec_label("vk-rebuild-design").name == "spec:vk-rebuild-design"

    def test_long_spec_slug_label_bounded_to_50(self) -> None:
        lab = labels.spec_label("x" * 60)
        assert len(lab.name) <= 50 and lab.name.startswith("spec:")

    def test_labeldef_rejects_name_over_50_chars(self) -> None:
        with pytest.raises(ValueError, match="50"):
            labels.LabelDef("plan:" + "x" * 50, "B60205", "too long")

    def test_normalized_long_slug_skips_the_hash(self) -> None:
        # Raw 'plan:'+slug is 56 chars, but the NORMALIZED form fits under 50 —
        # normalization must run BEFORE bounding so no truncate+hash kicks in.
        slug = "2026-05-23--obs--hop-blog-edge-monitoring-rework-1"
        assert labels.plan_label(slug).name == "plan:obs--hop-blog-edge-monitoring-rework-1"

    def test_bounded_name_stays_within_50_for_any_prefix(self) -> None:
        # Even a pathological (over-long) prefix must not slice the value from
        # the end or overflow — the result is unconditionally clamped to 50.
        from fr.labels import _bounded_label_name

        out = _bounded_label_name("x" * 45 + ":", "some-long-value-here")
        assert len(out) <= 50
        out2 = _bounded_label_name("plan:", "y" * 200)
        assert len(out2) == 50 and out2.startswith("plan:")
