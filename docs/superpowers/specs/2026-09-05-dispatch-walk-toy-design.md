# Dispatch-walk toy plan — design

**Status:** live walk fixture
**Date:** 2026-09-05

## Problem

The acceptance row `vk-dispatch-unchanged-after-cutover` (spec
2026-08-14 §4.D/6/8, Test Plan step 3) can only be closed by watching the
real VK bridge dispatch a plan after the 4.0.0 WorkItem cutover: one card per
ready phase on the first tick, zero new cards on the second. Every plan the
bridge tracks was already either dispatched before the cutover or landed
without dispatch, so nothing live projects a ready phase.

## Design

A deliberately trivial one-phase plan whose only deliverable is a line
appended to this spec's walk log. It exists to be dispatched, observed, and
archived; it changes no code.

## Walk log

- 2026-09-05: fixture created; awaiting dispatch.

## Implementation Plans

| Plan | Repo | File | Depends on |
| ---- | ---- | ---- | ---------- |
| 2026-09-05-dispatch-walk-toy | `derio-net/super-fr` | `2026-09-05-dispatch-walk-toy` | — |
