# Journal: 2026-10-06-state-sync-race

<!-- fr:journal kind=repro scope=debug id=23b1534454a6 created=2026-10-06T16:35:42+00:00 -->
### 23b1534454a6 · repro · state_sync checks for a symlink, then copy2 opens the paths again

packages/fr/src/fr/triage/state_sync.py _sync: the source is classified (durable_entries, lstat) and the destination checked (_symlinked_dest, lstat per component), then shutil.copy2(source, target) re-resolves both paths by name. A swap in between (target -> symlink, a destination directory -> symlink, or the source -> symlink) is written through or copied as a link: copy2's follow_symlinks=False only governs the SOURCE, and copies a source symlink AS a symlink into the destination. Repro: monkeypatch the check to swap the path right after it returns.

<!-- fr:journal kind=hypothesis scope=debug id=975eabbb195b created=2026-10-06T16:35:47+00:00 -->
### 975eabbb195b · hypothesis · single cause: path-based re-resolution between check and open (gh#1003)

Every variant is the same defect: the check and the write resolve the name independently. Fix: open every component with O_NOFOLLOW from a held directory descriptor (dir_fd walk, O_DIRECTORY|O_NOFOLLOW), open the file itself O_NOFOLLOW, fstat it regular, and copy fd-to-fd, restoring mode and times on the descriptor.

<!-- fr:journal kind=root-cause scope=debug id=895a7c5680d0 created=2026-10-06T16:48:26+00:00 -->
### 895a7c5680d0 · root-cause · check and copy resolved the paths independently

state_sync._sync lstat-checked source and destination by name, then shutil.copy2 opened both by name again. copy2(follow_symlinks=False) governs only the source and, for a source that became a symlink, recreates the link in the destination, so a swap after the check either wrote through a destination symlink or planted a symlink in the export.

<!-- fr:journal kind=finding scope=debug id=3e962b0c8e68 created=2026-10-06T16:48:30+00:00 state=fixed -->
### 3e962b0c8e68 · finding [fixed] · copy from O_NOFOLLOW descriptors

state_sync._copy walks each component from its parent descriptor (dir_fd, O_DIRECTORY|O_NOFOLLOW), opens the file O_NOFOLLOW (source also O_NONBLOCK, fstat must be regular), copies fd to fd and restores mode and times with fchmod/utime on the descriptor. A symlink met at open time maps to SYMLINK / SYMLINK_DEST. Pinned by tests/unit/test_triage_state_sync.py: three race tests (destination file, destination directory, source) that swap the path right after the check, plus mode/mtime preservation. Green on Linux and macOS.

<!-- fr:journal kind=review scope=debug id=597c6759a996 created=2026-10-06T16:51:48+00:00 -->
### 597c6759a996 · review · independent adversarial review: no defects

An independent reviewer read state_sync.py and the gh#1003 tests: no defects at >=80% confidence. Checked the file-where-a-directory-goes error path, Linux/macOS errno differences (_open lstats after any failure, so ENOTDIR vs ELOOP does not matter), metadata parity with copy2 (xattrs/flags no longer copied: harmless), fd leaks, and that the swap tests exercise the real window. Gaps raised: no source-directory swap test (added: test_a_source_directory_swapped_for_a_symlink_is_not_followed); no fifo-swap test and no import-direction race test (minor, shared _copy, not added). Noted, out of scope by design: the trusted roots (state dir, contained() output) are still opened by name, as the module docstring states.
