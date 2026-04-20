# Fence-In-Preamble Plan

**Spec:** `docs/superpowers/specs/example.md`
**Status:** Not Started

**Goal:** Exercise a preamble that contains a ``\n---`` inside a fenced code block.

**Example config:** a snippet of the config the plan is about.

```yaml
---
key: value
nested:
  - one
  - two
---
```

> **Operator note:** this should survive the round-trip even though the yaml
> block above embeds ``---`` delimiters.

---

### Task 1: Demo [agentic]

- [ ] **Step 1: Do the thing.**
  ```bash
  echo hi
  ```
