# S1: configuration homes — plan

Spec: `docs/superpowers/specs/2026-11-19-event-driven-a-la-carte-design.md` (#1653, epic #1652).

Seven agentic phases, in dependency order:

1. **The configuration space** (skeleton): `fr/config/space.py`, its three reads, every `.fr` reader moved onto it, and the `ast` tripwire. Under `repo` nothing a user sees changes, so it lands first and everything later builds on it.
2. **The configuration branch and the edit gate** (hard: a guard change on three harnesses): the switch moves to `fr-config` / `<branch>-config`, the legacy settings file is written in step for older fr, and the hook library, OpenCode plugin and Hermes hook learn the new switch, the new write targets and `.fr/isolation-allow`. Its PR needs an independent adversarial review before merge.
3. **Protection for executable configuration**: one forge read (`rules/branches/<b>`) and one guard every executor calls under quiet and stealth.
4. **The migration** (hard: the artifact framework every caller relies on): relocating, location-stamped kinds, the cross-space ordering, the profiles 2 → 3 hop, the transition notice and the owed end; then this repo dogfoods it.
5. **Shipped defaults**: one tree, one sync, one tripwire, one resolver order.
6. **Triage state** (hard: concurrency with a live driver and state that must not be lost): the cache repository, the five move rules, the default state repo and the override.
7. **Scenario, pages and mirrors**: the candidate walk scenario every row cites, the pages section H lists, the skills, rules and their generated mirrors.

Tests: every executor runs this repo's declared fast tier last (`tests: ci`, `.fr/ci.yaml`).
