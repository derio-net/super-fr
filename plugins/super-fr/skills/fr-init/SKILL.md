---
name: fr-init
description: >
  Initialize a repo for isolated runs: scan it, interview the operator about
  working patterns, tools, and credentials, then scaffold one or more
  devcontainer profiles via `fr init scaffold`. Use when a repo has no
  devcontainer profile, when fr-isolation or fr-brainstorming hard-stops
  asking for one, when the operator says "init this repo", "set up the
  devcontainer", or wants separate read-only/admin environments.
---

# fr-init

Captures "how you work in this repo" as committed devcontainer profiles plus
host-only secrets placeholders. Interactive BY DESIGN — the interview is
operator-owned context, so this skill is exempt from autonomy contracts:
under a fr-goal run, a missing devcontainer is a blocker; pause, run this
interview, resume isolated.

**Announce at start:** "I'm using fr-init to set up this repo's profiles."

## 1. Scan first

Before asking anything, learn what the repo already says:

- Languages and toolchains: manifests (pyproject/package.json/go.mod/...),
  lockfiles, `.tool-versions`, CI workflows (what does CI install?).
- Existing `.devcontainer/` (profiles already present? then this is an
  edit, not a green-field init).
- Credential surface: `.env*` patterns in .gitignore, CI secret names,
  cloud/k8s configs — candidates for the profile's expected secrets.
- Working patterns: Makefile/justfile/scripts (what do humans run here?).

The interview confirms and fills gaps; it never asks what the scan answers.

## 2. Interview (AskUserQuestion, batched ≤4 per round)

Cover, with scan-informed recommended options:

1. **Profiles wanted** — one `dev` default, or split (e.g. `readonly` for
   review/exploration vs `admin` with deploy credentials)? Profiles differ
   by CREDENTIALS first, tools second — same binaries, different env-files
   is the normal shape.
2. **Tools** — confirm the scan's toolchain list; surface what CI installs
   that local work also needs (kubectl, terraform, docker-in-docker...).
3. **Credentials per profile** — which env KEYS each profile expects
   (names only, never values). **Do NOT ask for a GitHub token by
   default:** push, PR creation, and every `fr`-driven gh call run on the
   authenticated HOST (fr-isolation's credential boundary) — the container
   needs no GH_TOKEN — gh is host-side. A non-default profile may still
   declare *other* in-container credentials (e.g. `KUBECONFIG_B64`, a
   deploy or registry token), but never a GitHub token.
4. **Working patterns** — test/build/run commands worth recording in the
   profile's purpose/notes so future runs know the repo's verbs.

## 3. Scaffold per profile

```bash
fr init scaffold --repo . --profile dev --purpose "day-to-day development" \
    --tool uv --tool node --default
fr init scaffold --repo . --profile admin --purpose "in-cluster deploys" \
    --secret KUBECONFIG_B64 --secret REGISTRY_TOKEN
```

Each call writes:

- `.devcontainer/<profile>/devcontainer.json` — committed by scaffold; base
  image + git/gh features + mapped tool features + vk installed in postCreate +
  `--env-file` pointing at the host secrets path.
- `.devcontainer/fr-profiles.yaml` — committed by scaffold; default profile,
  purpose, expected secret keys, notes for tools without a feature mapping.
- `~/.config/fr/secrets/<repo>/<profile>.env` — host-only; commented
  placeholders per secret key. Existing operator values are never
  overwritten; re-runs only append missing placeholders.

Unknown tools land in the profile's notes — wire them into
`postCreateCommand` by editing the devcontainer.json, and say so.

## 4. Hand back

- Tell the operator which placeholders to fill
  (`~/.config/fr/secrets/<repo>/<profile>.env`) before the first
  `fr isolation up` — an empty env-file is normal for a default profile
  (GitHub work needs only the host's `gh auth status` to be green).
- `fr init scaffold` already **committed** the `.devcontainer/` files (scoped
  commit on the current branch — `main` during bootstrap), so the profile is in
  the committed tree that `fr isolation up` checks out. No separate commit step
  — and the agent couldn't do one anyway (base-repo `git commit` is gate-denied).
  Pass `--no-commit` only if you want to stage/commit them yourself (e.g. to open
  a PR in a repo that blocks direct pushes to `main`).
- If a run was paused on this init, resume it: `fr isolation up` now works.

## Multi-profile principles

- The DEFAULT profile is the one autonomous runs use; keep it least-
  privileged enough to be safe unattended (admin credentials belong in a
  non-default profile the operator selects explicitly).
- Adding a profile later is one more `fr init scaffold` call — the layout
  is per-profile subfolders from day one, no migration.
