# Journal: 2026-07-24-isolation-host-modes

<!-- fr:journal kind=decision scope=spec id=t1-detection created=2026-07-24T11:42:33 -->
### t1-detection · decision · T1 detection: preparer writes the .fr-isolation marker (mode external)

Operator decision (batched Q&A, 2026-07-24). The external prep process writes the marker as its explicit containment claim; fr isolation up validates and adopts. Rejected: env-var attestation alone, probe-based detection (any container would 'count').

<!-- fr:journal kind=decision scope=spec id=t2-secrets created=2026-07-24T11:42:36 -->
### t2-secrets · decision · T2 secrets: host env IS the env — no fr provisioning

Operator decision. Worktree-only mode inherits the host process environment (pods carry ESO-injected creds). Rejected: sourcing ~/.config/fr/secrets env-files (secret files on shared hosts), profile-declared env hooks (new surface without a consumer).

<!-- fr:journal kind=decision scope=spec id=t2-activation created=2026-07-24T11:42:40 -->
### t2-activation · decision · T2 activation: host-level declaration, env var only

Operator decision. FR_ISOLATION_TARGET=worktree set in the pod manifest/image declares the host worktree-only; no CLI flag, no config file, no auto-detect — a Mac session can never silently degrade. Unknown values fail closed.

<!-- fr:journal kind=decision scope=spec id=scope-one-spec created=2026-07-24T11:42:43 -->
### scope-one-spec · decision · Scope: one spec covers both host types

Operator decision. Single mode-taxonomy spec (devcontainer | host-worktree | external) so marker/hook semantics are designed once; phases may still ship independently.

<!-- fr:journal kind=decision scope=spec id=t1-hook-evidence created=2026-07-24T11:42:46 -->
### t1-hook-evidence · decision · T1 hook validity: toplevel match + container evidence

Operator decision. mode-external markers validate only with recorded-toplevel match AND container evidence (/.dockerenv, /run/.containerenv, or KUBERNETES_SERVICE_HOST). A marker forged on a bare host never unlocks edits.

<!-- fr:journal kind=decision scope=spec id=t1-branch created=2026-07-24T11:42:50 -->
### t1-branch · decision · T1 branch: up ensures the requested branch in place

Operator decision. External-mode up runs git switch -c <branch> from the preparer's HEAD when needed (preparer picks the base, fr names the feature branch); marker/state updated. Rejected: adopt-as-is (silent branch divergence), strict-match-or-fail (needless coupling).

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-07-24T11:43:54 -->
### spec-review-1 · review · Spec reviewed against Q&A answers and codebase reality

All cited surfaces verified to exist: isolation/local.py _write_isolation_marker mode field, types.py Target protocol (line 233), isolation_cmd.py _target() single selection site (line 43), hooks/lib/fr-isolation-decision.sh _fr_marker_valid, hermes hook entrypoint, fr-opencode-plugin marker.ts mode check (lines 95-96, fail-closed — port claim accurate). All 7 Q&A answers encoded in Design/Non-goals. Gap found and fixed: no post-merge Test Plan section — added, with each step pinned to one of the 4 acceptance rows.
