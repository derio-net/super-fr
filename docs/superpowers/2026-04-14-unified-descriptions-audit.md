# Unified Descriptions — Impact Audit

**Date:** 2026-04-14
**Phase:** 0 of archive-and-unified-descriptions plan
**Scope:** All derio-net repos — superpowers-for-vk, secure-agent-kali, frank, willikins, vibe-kanban

---

## Title consumers found

### superpowers-for-vk

| File | Line | Description |
|---|---|---|
| `src/vk/commands/dispatch_cmd.py` | 64–66 | `_build_issue_title()` — generates `{slug}-{phase_num}-{tag}` format |
| `src/vk/commands/dispatch_cmd.py` | 138 | Calls `_build_issue_title` during initial dispatch |
| `src/vk/commands/dispatch_cmd.py` | 252 | Calls `_build_issue_title` during migrate/re-dispatch |
| `src/vk/commands/progress_cmd.py` | 391 | Regex `r"-\d+-(?:agentic\|manual)$"` strips phase suffix for duplicate detection |
| `tests/unit/test_audit.py` | 96 | Test fixture uses `title="my-plan-0-agentic"` |

### secure-agent-kali

| File | Line | Description |
|---|---|---|
| `scripts/vk-issue-bridge.py` | 383 | Reads `raw["title"]` from GH API response |
| `scripts/vk-issue-bridge.py` | 415 | Constructs VK card title as `gh#{issue.number}: {issue.title}` |
| `scripts/vk-issue-bridge.py` | 591 | Dedup check: compares `gh#{i.number}: {i.title}` against existing VK cards |

### Other repos

- **frank:** No code-level title consumers. `blog/prompt_for_images.yaml:298` contains a YAML key `building-11-agentic-control-plane` — coincidental match, not a title consumer.
- **willikins:** Archived plans and session summaries reference old-format titles in prose — no code-level consumers.
- **vibe-kanban:** Archived plan at `docs/superpowers/archived-plans/2026-04-13-workspace-lifecycle-backend-jobs.md:51` contains a test fixture string — not a runtime consumer.

---

## Label consumers found

### superpowers-for-vk

| File | Line | Label(s) | Description |
|---|---|---|---|
| `src/vk/config.py` | 45, 91 | `vk-ready`, `manual` | Default label config in `DispatchConfig` |
| `src/vk/commands/common.py` | 80 | `vk-ready` | Default label in YAML scaffold |
| `src/vk/commands/init_cmd.py` | 86 | `vk-ready` | Default label in `vk init` |
| `src/vk/commands/dispatch_cmd.py` | 263 | `vk-ready` | Applied to dispatched Issues |

### secure-agent-kali

| File | Line | Label(s) | Description |
|---|---|---|---|
| `scripts/vk-issue-bridge.py` | 27 | `vk-ready` | `GH_LABEL_READY` constant (env-overridable) |
| `scripts/vk-issue-bridge.py` | 28 | `vk-synced` | `GH_LABEL_SYNCED` constant (env-overridable) |
| `scripts/vk-issue-bridge.py` | 355 | `vk-ready` | Query filter for unsynced Issues |
| `scripts/vk-issue-bridge.py` | 502–505 | `in-progress` | Lifecycle transition after workspace creation |
| `scripts/vk-issue-bridge.py` | 541 | `vk-ready` | Log message for unsynced count |

### willikins

| File | Line | Label(s) | Description |
|---|---|---|---|
| `scripts/hooks/vk-lifecycle-transition.sh` | 6, 9 | `in-progress` | Lifecycle state list and usage example |
| `scripts/plan-status.sh` | 8 | `in-progress` | CLI help text |

### frank

| File | Line | Label(s) | Description |
|---|---|---|---|
| `docs/superpowers/plan-config.yaml` | 44 | `vk-ready` | Dispatch label config for Frank plans |

### Not found

- **`pr-ready`**: No code-level consumers found in any repo. Safe to introduce in later phases without migration.

---

## Open Issues to migrate

| Repo | Issue # | Title | URL |
|---|---|---|---|
| derio-net/superpowers-for-vk | #9 | archive-and-unified-descriptions-0-agentic | [link](https://github.com/derio-net/superpowers-for-vk/issues/9) |
| derio-net/superpowers-for-vk | #10 | archive-and-unified-descriptions-1-agentic | [link](https://github.com/derio-net/superpowers-for-vk/issues/10) |
| derio-net/superpowers-for-vk | #11 | archive-and-unified-descriptions-2-agentic | [link](https://github.com/derio-net/superpowers-for-vk/issues/11) |
| derio-net/superpowers-for-vk | #13 | archive-and-unified-descriptions-4-agentic | [link](https://github.com/derio-net/superpowers-for-vk/issues/13) |

**Total: 4 open `vk-ready` Issues** (all from this plan's dispatch).

No Frank Issues (#68–#72) found with `vk-ready` label — they have either been closed or had their labels removed.

---

## Bridge singleton status

| Path | Inode | Size | Owner | Modified |
|---|---|---|---|---|
| `/home/claude/.local/bin/vk-issue-bridge.py` | 2883604 | 20,502 B | claude:claude | 2026-04-10 |
| `/opt/scripts/vk-issue-bridge.py` | 1814824537 | 21,680 B | root:root | 2026-04-12 |
| `/home/claude/repos/secure-agent-kali/scripts/vk-issue-bridge.py` | 1772694 | 23,050 B | claude:claude | 2026-04-14 |

**Not a singleton.** All three are independent copies (different inodes, different sizes). `secure-agent-kali/scripts/vk-issue-bridge.py` is the **source of truth** — newest and largest. The other two are **stale copies** that have drifted behind.

---

## Additional title parsers outside expected surfaces

**willikins:** `scripts/hooks/vk-lifecycle-transition.sh:21` uses `jq` to select a GitHub Project by `.title` — this parses a **Project** title, not an Issue title. Not a consumer of the `{slug}-{phase}-{tag}` format.

**vibe-kanban:** No runtime title parsers found. Only archived plan docs reference the old format.

**None found.**

---

## Summary

All title consumers are confined to two files: `dispatch_cmd.py` (generator) and `progress_cmd.py` (regex parser) in superpowers-for-vk, plus the bridge in secure-agent-kali (passthrough — reads title but does not parse the `{slug}-{phase}-{tag}` structure). No scope extension required.
