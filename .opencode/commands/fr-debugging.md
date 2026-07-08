---
description: Debug a bug, test failure, or unexpected behavior INSIDE an isolated
  workspace and deliver a reviewed fix-PR. Wraps superpowers:systematic-debugging
  — enters fr-isolation first (reusing an active workspace, else a fresh fix branch),
  runs the four phases via the exec-bridge, autonomous to a PR with hard stops only
  at the genuine human checkpoints. Use in a vk/fr-enabled repo (fr plans or devcontainer
  profiles present) whenever debugging starts — "this is broken", "the test fails",
  "find the root cause", "why is X happening" — or when fr-goal hits a bug mid-implementation.
---
Use the `fr-debugging` skill to handle this request.

$ARGUMENTS
