# Plugin cache: running sessions break after a super-fr reinstall

## Symptom & reproduction

A live Claude Code session, after `scripts/install.sh` is re-run for a new
super-fr version, starts erroring ("complaining") about the plugin instead of
quietly continuing on the old version until restart.

Repro:
1. Start a Claude Code session with super-fr vX installed.
2. Bump the version and re-run `scripts/install.sh` (installs vX+1).
3. In the still-running session, trigger anything that touches the plugin
   (a plugin hook firing, a skill invocation) → path errors.

## Evidence

`install.sh` registers each plugin with a **version-keyed** `installPath`
(`.../cache/derio-net/super-fr/<version>`) and then **deletes every cache
version dir except the current one** (`rm -rf`, "keep only current").

The running session resolved its plugin paths at startup from the *old*
version's `installPath`. The reinstall `rm -rf`'s that exact directory out from
under the live session → hook scripts (`${CLAUDE_PLUGIN_ROOT}/...`) and skill
reads now point at a directory that no longer exists.

### Empirical probe of harness path handling (symprobe)

Before committing to a fix we measured how Claude Code stores `installPath`,
because the fix depends on it and the behavior is undocumented. A throwaway
plugin was registered with `installPath` pointing at a **symlink**
(`cache/current -> v1`); a `PreToolUse` hook logged `${CLAUDE_PLUGIN_ROOT}`,
which script file ran, and a per-version marker.

- Baseline (every fire): `CLAUDE_PLUGIN_ROOT=.../cache/current` — the harness
  exports the **literal symlink path**, not a realpath'd version dir.
- After `ln -sfn v2 current` **mid-session, with no reload and no restart**, the
  next hook fire ran `v2`'s script and read `v2`'s marker.

Conclusion: the harness keeps `installPath` literal and the OS resolves the
symlink at exec time. A stable-symlink `installPath` therefore lets a running
session pick up new plugin **hook/command** code with zero restart. (Skill
prose and the reported version remain frozen at startup — no on-disk swap
changes context already loaded; that is out of scope here.)

## Root cause

`install.sh` couples two things that should be decoupled: the **identity** the
session holds (`installPath`) and the **content** of a specific version. Because
`installPath` is version-keyed AND the installer prunes all-but-current, every
reinstall invalidates the path a live session is using. The breakage is not
inherent to updating a plugin — it is caused by deleting the in-use directory
and never giving the session a stable handle.

## Fix

In `install.sh` step 4, per plugin:

1. rsync into the version dir as before.
2. After the sync completes, atomically repoint a stable relative symlink
   `cache/<marketplace>/<plugin>/current -> <version>` (`ln -sfn`).
3. Write `installPath` = the `current` **symlink**, not the version dir.
4. Prune to **current + the most-recent previous** version dir (N-1 buffer),
   never touching the `current` symlink itself. The glob `*/` matches the
   symlink, so pruning explicitly skips symlinks.

Result: a live session's `installPath` (`.../current`) survives every reinstall;
its hooks/commands resolve to the new version on the next fire. The N-1 buffer
is defensive insurance for any environment/harness that might realpath at
startup (not observed here, but undocumented and may vary by release).

## Rejected hypotheses

- **"Just keep N-1 version dirs, no symlink."** Stops the `rm -rf` breakage but
  leaves `installPath` version-keyed, so a live session still points at the old
  dir and never sees the new version without restart. Insufficient.
- **"Hot-reload in the session instead."** `/reload-plugins` is a partial
  refresh and is *not available in every environment* (confirmed absent in the
  Mac app harness during this investigation), so it cannot be the mechanism.
- **"Realpath makes the symlink pointless."** Disproved empirically above — the
  harness keeps the literal path.
