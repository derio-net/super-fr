// One way to run a subprocess from this plugin: bounded, and never throwing.
//
// Every handler here is a guest in the session it serves — a hung `fr`, a
// missing binary or a killed child must cost that handler its answer, never
// the session its turn. So each call carries a timeout (SIGKILL on expiry), and
// each failure is a VALUE: `code` is the exit status of a process that ran and
// exited, and `null` for one that never ran, was killed, or timed out.
import { execFile, spawnSync } from "node:child_process";

export type RunAnswer = { code: number | null; stdout: string };

export type RunOptions = { cwd?: string; timeoutMs: number };

/** Run `cmd args` asynchronously. Never rejects. */
export function run(cmd: string, args: string[], options: RunOptions): Promise<RunAnswer> {
  return new Promise((resolve) => {
    try {
      execFile(
        cmd,
        args,
        { cwd: options.cwd, timeout: options.timeoutMs, killSignal: "SIGKILL", windowsHide: true },
        (error, stdout) => {
          // `error.code` is the exit status for a process that ran and exited
          // non-zero, a STRING ("ENOENT") when it never ran, and absent when it
          // was killed. Only a number is an exit status.
          const raw = error ? (error as { code?: unknown }).code : 0;
          resolve({ code: typeof raw === "number" ? raw : null, stdout: String(stdout ?? "") });
        }
      );
    } catch {
      resolve({ code: null, stdout: "" });
    }
  });
}

/** Run `cmd args` synchronously — for the gate, which must decide before the
 * call it judges. Same contract: bounded, never throws. */
export function runSync(cmd: string, args: string[], options: RunOptions): RunAnswer {
  try {
    const out = spawnSync(cmd, args, {
      cwd: options.cwd,
      timeout: options.timeoutMs,
      killSignal: "SIGKILL",
      windowsHide: true,
      stdio: ["ignore", "pipe", "ignore"],
      encoding: "utf-8",
    });
    if (out.error || out.signal) return { code: null, stdout: "" };
    return { code: out.status, stdout: String(out.stdout ?? "") };
  } catch {
    return { code: null, stdout: "" };
  }
}
