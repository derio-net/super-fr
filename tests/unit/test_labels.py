"""Tests for the canonical label registry."""

from __future__ import annotations

import re

from vk import labels

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


class TestRegistryLookup:
    def test_lifecycle_dict_keys_are_role_names(self) -> None:
        assert set(labels.LIFECYCLE.keys()) == {
            "vk_ready",
            "manual",
            "in_progress",
            "pr_ready",
        }

    def test_lifecycle_values_match_module_constants(self) -> None:
        assert labels.LIFECYCLE["vk_ready"] is labels.VK_READY
        assert labels.LIFECYCLE["manual"] is labels.MANUAL
        assert labels.LIFECYCLE["in_progress"] is labels.IN_PROGRESS
        assert labels.LIFECYCLE["pr_ready"] is labels.PR_READY
