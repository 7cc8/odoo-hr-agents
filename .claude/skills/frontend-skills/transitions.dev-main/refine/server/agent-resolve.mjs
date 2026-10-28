// Shared agent-CLI resolution, used by BOTH:
//   • bin/cli.mjs  — once, at `npx transitions-refine live` (may also install).
//   • server/relay.mjs — repeatedly, at runtime, so the relay SELF-HEALS: if no
//     agent was wired at boot (CLI not on PATH yet, not logged in, a startup
//     race) the relay re-checks and auto-wires the moment one becomes available,
//     instead of being stuck in /refine-live poller mode for its whole life.
//
// Everything here is PURE: detection by host env markers + a PATH scan, with no
// install and no logging, so the relay can call it on a short TTL with no side
// effects. Installation (Cursor CLI) stays in the CLI, which owns user prompts.

import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { homedir } from "node:os";

const HOME = process.env.HOME || homedir();
const envHasPrefix = (p, env) => Object.keys(env).some((k) => k.startsWith(p));

// The agent CLIs we know how to drive headlessly. `host(env)` detects the agent
// HOSTING this run (so Refine bills the subscription the user already has);
// `bins` are probed in order; `cmd(bin)` builds the headless invocation.
export const AGENTS = [
  {
    key: "cursor",
    label: "Cursor",
    host: (env) => Boolean(env.CURSOR_AGENT),
    bins: [
      "cursor-agent",
      join(HOME, ".local/bin/cursor-agent"),
      join(HOME, ".cursor/bin/cursor-agent"),
    ],
    cmd: (bin) => `${bin} -p --force`,
    canInstall: true,
    auth: "run `cursor-agent` once to log in, or set CURSOR_API_KEY",
  },
  {
    key: "claude",
    label: "Claude Code",
    host: (env) => Boolean(env.CLAUDECODE || env.CLAUDE_CODE_ENTRYPOINT),
    bins: [
      "claude",
      join(HOME, ".claude/local/claude"),
      join(HOME, ".local/bin/claude"),
    ],
    cmd: (bin) => `${bin} -p --dangerously-skip-permissions`,
    canInstall: false,
    auth: "run `claude` once to sign in",
  },
  {
    key: "codex",
    label: "Codex",
    host: (env) => Boolean(env.CODEX_SANDBOX) || envHasPrefix("CODEX_", env),
    bins: ["codex", join(HOME, ".local/bin/codex")],
    cmd: (bin) => `${bin} exec --sandbox workspace-write --skip-git-repo-check -`,
    canInstall: false,
    auth: "run `codex` once to sign in, or set CODEX_API_KEY",
  },
];

// Host-detection precedence. Claude/Codex export very specific markers; check
// them BEFORE Cursor so a Claude Code or Codex session launched from inside a
// Cursor terminal (which still carries CURSOR_*) is not mis-wired to cursor-agent.
export const HOST_PRECEDENCE = ["claude", "codex", "cursor"];

// A bare `cursor-agent` goes interactive ("⚠ Workspace Trust Required", exit 1)
// and `codex exec` needs a trailing `-` to read the prompt from stdin. Normalise
// an externally-provided REFINE_AGENT_CMD so headless jobs don't silently fail.
export function augmentAgentCmd(cmd) {
  if (!cmd) return cmd;
  if (/(^|\s|\/)codex(\s|$)/.test(cmd) && /(^|\s)exec(\s|$)/.test(cmd)) {
    return /(^|\s)-(\s|$)/.test(cmd) ? cmd : `${cmd} -`;
  }
  if (!/(^|\s|\/)cursor-agent(\s|$)/.test(cmd)) return cmd;
  const has = (...flags) =>
    flags.some((f) => new RegExp(`(^|\\s)${f.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(\\s|$)`).test(cmd));
  const extra = [];
  if (!has("-p", "--print")) extra.push("-p");
  if (!has("--trust")) extra.push("--trust");
  if (!has("-f", "--force", "--yolo")) extra.push("--force");
  return extra.length ? `${cmd} ${extra.join(" ")}` : cmd;
}

export function isRunnable(bin) {
  try {
    return spawnSync(bin, ["--version"], { stdio: "ignore" }).status === 0;
  } catch {
    return false;
  }
}

export function findBin(agent) {
  return agent.bins.find(isRunnable) || null;
}

export function detectHostAgent(env = process.env) {
  for (const key of HOST_PRECEDENCE) {
    const a = AGENTS.find((x) => x.key === key);
    if (a && a.host(env)) return a;
  }
  return null;
}

// Pure resolution — no install, no logging. Returns one of:
//   { cmd, agent, source }                       → wire this command, or
//   { cmd:null, agent?, reason, needsInstall? }   → couldn't wire (caller decides
//                                                    whether to install / surface).
// Precedence: explicit REFINE_AGENT_CMD → forced key → host agent → PATH scan.
export function resolveAgentCmd({ env = process.env, forceKey = null } = {}) {
  if (env.REFINE_AGENT_CMD) {
    return { cmd: augmentAgentCmd(env.REFINE_AGENT_CMD), source: "env" };
  }

  let target = null;
  if (forceKey) {
    target = AGENTS.find((a) => a.key === forceKey) || null;
    if (!target) {
      return { cmd: null, reason: `unknown agent "${forceKey}" (use cursor | claude | codex)` };
    }
  }
  if (!target) target = detectHostAgent(env);

  if (target) {
    const bin = findBin(target);
    if (bin) return { cmd: target.cmd(bin), agent: target, source: forceKey ? "forced" : "host" };
    return {
      cmd: null,
      agent: target,
      needsInstall: target.canInstall,
      reason:
        `detected ${target.label} but its CLI isn't on PATH` +
        (target.canInstall ? " — re-run with --llm to install it" : ` — install the ${target.label} CLI first`),
    };
  }

  for (const a of AGENTS) {
    const bin = findBin(a);
    if (bin) return { cmd: a.cmd(bin), agent: a, source: "scan" };
  }

  return { cmd: null, reason: "no agent CLI found", needsInstall: true };
}
