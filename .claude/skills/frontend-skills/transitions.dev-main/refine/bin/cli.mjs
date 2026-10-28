#!/usr/bin/env node
// Refine — transitions.dev live tool.
//
//   npx transitions-refine live              # inject panel + relay; auto-wire your agent CLI
//   npx transitions-refine live --agent claude   # force an agent: cursor | claude | codex
//   npx transitions-refine live --llm        # install the Cursor CLI if no agent is found
//   npx transitions-refine stop              # remove the injected <script> tag
//
// `live` sets up the timeline + Refine with no npm install and no source edits
// of your own:
//   1. injects one <script type="module" src=".../inject.js"> into your page
//   2. drops the `refine-live` + `transitions-dev` skills (for token-aware picks)
//   3. wires an LLM backend so the relay answers jobs itself, persistently (no
//      /refine live loop). It prefers the agent HOSTING this run — Cursor →
//      cursor-agent, Claude Code → claude, Codex → codex — so Refine uses the
//      subscription you already have. Override with --agent <name> or by
//      exporting REFINE_AGENT_CMD. With no agent available it falls back to the
//      /refine live in-IDE loop (and --llm can install the Cursor CLI).
//   4. starts the local refine relay (serves the panel at /inject.js).

import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync, mkdirSync, cpSync, realpathSync, openSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";
import { get as httpGet, request as httpRequest } from "node:http";
import { AGENTS, findBin, resolveAgentCmd } from "../server/agent-resolve.mjs";

const PKG_ROOT = fileURLToPath(new URL("..", import.meta.url));
const CWD = process.cwd();
const HOME = process.env.HOME || homedir();
const PKG_VERSION = (() => {
  try {
    return JSON.parse(readFileSync(join(PKG_ROOT, "package.json"), "utf8")).version || "0";
  } catch {
    return "0";
  }
})();

const MARK_START = "<!-- timeline-inject:start -->";
const MARK_END = "<!-- timeline-inject:end -->";
const PAGE_CANDIDATES = [
  "index.html",
  "public/index.html",
  "src/index.html",
  "app/index.html",
  "dist/index.html",
];

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--page" || a === "-p") args.page = argv[++i];
    else if (a === "--port") args.port = argv[++i];
    else if (a === "--agent") args.agent = argv[++i];
    else if (a.startsWith("--")) args[a.slice(2)] = true;
    else args._.push(a);
  }
  return args;
}

function findPage(explicit) {
  if (explicit) return resolve(CWD, explicit);
  for (const c of PAGE_CANDIDATES) {
    const p = join(CWD, c);
    if (existsSync(p)) return p;
  }
  return null;
}

function injectTag(pagePath, port) {
  const tag = `${MARK_START}\n<script type="module" src="http://localhost:${port}/inject.js"></script>\n${MARK_END}`;
  let html = readFileSync(pagePath, "utf8");
  if (html.includes(MARK_START)) {
    html = stripTag(html); // refresh (e.g. port changed)
  }
  if (html.includes("</body>")) {
    html = html.replace(/<\/body>/i, `${tag}\n</body>`);
  } else {
    html += `\n${tag}\n`;
  }
  writeFileSync(pagePath, html);
}

function stripTag(html) {
  const re = new RegExp(`\\n?${escapeRe(MARK_START)}[\\s\\S]*?${escapeRe(MARK_END)}\\n?`, "g");
  return html.replace(re, "");
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Copy a whole skill directory from the package into the user's project so the
// in-IDE agent (/refine live) and any spawned cursor-agent can read it.
//
// Crucially this REFRESHES a stale copy on upgrade. An older installed skill can
// shadow newer job handling — e.g. a pre-scan `refine-live` skill that doesn't
// know how to answer kind:"scan" jobs, so scan jobs time out and the panel hangs
// on "Agent is scanning…". We stamp the package version into the skill dir and
// re-copy whenever it's missing or mismatched (so we don't clobber every run).
function dropSkill(name) {
  const src = join(PKG_ROOT, ".agents/skills", name);
  const destDir = join(CWD, ".agents/skills", name);
  if (!existsSync(src)) return false;
  if (resolve(src) === resolve(destDir)) return "exists"; // running inside the package's own repo — nothing to copy
  const marker = join(destDir, ".refine-version");
  const existed = existsSync(destDir);
  if (existed) {
    let installed = null;
    try { installed = readFileSync(marker, "utf8").trim(); } catch {}
    if (installed === PKG_VERSION) return "exists";
  }
  mkdirSync(dirname(destDir), { recursive: true });
  cpSync(src, destDir, { recursive: true, force: true });
  try { writeFileSync(marker, PKG_VERSION + "\n"); } catch {}
  return existed ? "updated" : true;
}

// ── agent CLIs (for the persistent LLM path) ─────────────────────────────────
// The relay answers LLM jobs by spawning REFINE_AGENT_CMD per job (stdin =
// prompt, stdout = JSON). To bill against the account the user ALREADY pays for,
// we detect which agent is hosting this run and wire ITS CLI: a Claude Code user
// gets `claude`, a Codex user gets `codex`, a Cursor user gets `cursor-agent`.
// The agent table + (pure) detection live in server/agent-resolve.mjs, shared
// with the relay so it can re-check and self-heal at runtime; the CLI only adds
// the one thing the relay must not do — install the Cursor CLI.

// Install the Cursor CLI (the only agent we can fetch non-interactively).
function installCursorCli() {
  log("• installing the Cursor CLI (cursor-agent) — one-time…");
  const r =
    process.platform === "win32"
      ? spawnSync(
          "powershell",
          ["-NoProfile", "-Command", "irm 'https://cursor.com/install?win32=true' | iex"],
          { stdio: "inherit" }
        )
      : spawnSync("sh", ["-c", "curl https://cursor.com/install -fsS | bash"], {
          stdio: "inherit",
        });
  if (r.status !== 0) log("! the installer exited non-zero — see its output above.");
  return findBin(AGENTS[0]);
}

// Decide which agent CLI the relay should spawn. Pure resolution is shared with
// the relay (resolveAgentCmd); the CLI layers on the one side-effecting step the
// relay must never do — installing the Cursor CLI when --llm is passed and
// nothing else is available. Returns:
//   { cmd, agent, source }          → wire this command (persistent LLM), or
//   { cmd:null, agent?, reason }    → couldn't wire; caller prints guidance.
function resolveAgent({ wantLlm, forceKey }) {
  const r = resolveAgentCmd({ forceKey });
  if (r.cmd || !wantLlm || !r.needsInstall) return r;
  // wantLlm + the only fetchable CLI (cursor-agent) is missing → install it.
  const bin = installCursorCli();
  if (bin) return { cmd: AGENTS[0].cmd(bin), agent: AGENTS[0], source: "install" };
  return r;
}

function log(msg) {
  process.stdout.write(`${msg}\n`);
}

function rel(p) {
  return p && p.startsWith(CWD + "/") ? p.slice(CWD.length + 1) : p;
}

// ── background daemon (for one-shot agent shells) ────────────────────────────
// Claude Code / Codex / Cursor run a `live` command in a NON-interactive shell
// that expects the command to EXIT. A foreground relay never exits, so the agent
// shell buffers (no output) and eventually kills the process group — which runs
// cleanup and strips the injected tag, so "nothing works". In those shells we
// instead fork the relay as a detached daemon (its own session via detached:true,
// so a process-group kill on the agent shell can't reach it), record a PID file,
// print status, and exit 0. `stop` reads the PID file to tear it down.
function daemonFile() {
  return join(CWD, ".refine-relay.json");
}

// One GET /health probe. Resolves true if the relay answers at all.
function httpOk(port, path = "/health", timeoutMs = 800) {
  return new Promise((resolveOk) => {
    let done = false;
    const finish = (v) => { if (!done) { done = true; resolveOk(v); } };
    const req = httpGet({ host: "127.0.0.1", port: Number(port), path, timeout: timeoutMs }, (res) => {
      res.resume(); // drain so the socket can close
      finish(res.statusCode >= 200 && res.statusCode < 500);
    });
    req.on("timeout", () => { req.destroy(); finish(false); });
    req.on("error", () => finish(false));
  });
}

async function waitForHealth(port, totalMs = 6000) {
  const deadline = Date.now() + totalMs;
  while (Date.now() < deadline) {
    if (await httpOk(port)) return true;
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

// GET /health → parsed JSON, or null if unreachable / unparsable.
function getHealth(port, timeoutMs = 800) {
  return new Promise((resolveJson) => {
    let done = false, body = "";
    const finish = (v) => { if (!done) { done = true; resolveJson(v); } };
    const req = httpGet({ host: "127.0.0.1", port: Number(port), path: "/health", timeout: timeoutMs }, (res) => {
      if (res.statusCode < 200 || res.statusCode >= 500) { res.resume(); return finish(null); }
      res.setEncoding("utf8");
      res.on("data", (d) => (body += d));
      res.on("end", () => { try { finish(JSON.parse(body)); } catch { finish(null); } });
    });
    req.on("timeout", () => { req.destroy(); finish(null); });
    req.on("error", () => finish(null));
  });
}

// Best-effort POST (no body). Resolves true on a 2xx.
function postRelay(port, path, timeoutMs = 1500) {
  return new Promise((resolveOk) => {
    let done = false;
    const finish = (v) => { if (!done) { done = true; resolveOk(v); } };
    const req = httpRequest({ host: "127.0.0.1", port: Number(port), path, method: "POST", timeout: timeoutMs }, (res) => {
      res.resume();
      finish(res.statusCode >= 200 && res.statusCode < 300);
    });
    req.on("timeout", () => { req.destroy(); finish(false); });
    req.on("error", () => finish(false));
    req.end();
  });
}

// Wait until nothing answers on the port (a replaced relay has fully exited).
async function waitForPortFree(port, totalMs = 4000) {
  const deadline = Date.now() + totalMs;
  while (Date.now() < deadline) {
    if (!(await httpOk(port))) return true;
    await new Promise((r) => setTimeout(r, 150));
  }
  return false;
}

// Kill a previously-detached relay for this project (best effort).
function stopDaemon({ silent = false } = {}) {
  let rec = null;
  try { rec = JSON.parse(readFileSync(daemonFile(), "utf8")); } catch {}
  if (!rec || !rec.pid) return false;
  let killed = false;
  try { process.kill(rec.pid, "SIGTERM"); killed = true; } catch {}
  try { rmSync(daemonFile()); } catch {}
  if (killed && !silent) log(`✓ stopped background relay (pid ${rec.pid})`);
  return killed;
}

// Fork the relay as a detached background process and return once it's healthy
// (or we give up waiting). The CLI then exits, so the agent's shell command
// completes and surfaces this output while the relay keeps running.
async function startDetached({ port, page, env, resolved }) {
  stopDaemon({ silent: true }); // replace any prior daemon (port clash / dupes)

  const logPath = join(CWD, ".refine-relay.log");
  let out = "ignore";
  try { out = openSync(logPath, "a"); } catch {}
  const child = spawn(process.execPath, [join(PKG_ROOT, "server/relay.mjs")], {
    detached: true,
    stdio: ["ignore", out, out],
    env,
  });
  child.unref();

  const llmWired = Boolean(env.REFINE_AGENT_CMD);
  const record = {
    pid: child.pid,
    port: Number(port),
    page: page || null,
    log: logPath,
    version: PKG_VERSION,
    agentCmd: env.REFINE_AGENT_CMD || null,
    startedAt: new Date().toISOString(),
  };
  try { writeFileSync(daemonFile(), JSON.stringify(record, null, 2) + "\n"); } catch {}

  const healthy = await waitForHealth(port, 6000);
  log("");
  if (healthy) {
    log(`✓ relay running in background (pid ${child.pid}) — http://localhost:${port}`);
  } else {
    log(`! relay started (pid ${child.pid}) but wasn't healthy within 6s — check ${rel(logPath)}`);
  }
  if (llmWired) {
    log("✓ agent wired — Refine answers jobs itself (no /refine live loop needed).");
  } else {
    log(`• agent NOT wired${resolved && resolved.reason ? ` — ${resolved.reason}` : ""}.`);
    log("  LLM jobs fall back to a /refine live poller. To wire a persistent agent,");
    log("  re-run with --agent <cursor|claude|codex> (that CLI must be on PATH).");
  }
  log("");
  log("Next:");
  log("  1. Open your app and hard-refresh — the timeline panel is on the page.");
  log("  2. Click Refine.");
  log(`  Stop it (and remove the injected tag):  npx transitions-refine stop`);
  log(`  Logs:  ${rel(logPath)}`);
}

async function cmdLive(args) {
  const port = String(args.port || process.env.REFINE_RELAY_PORT || 7331);
  const page = findPage(args.page);

  // 0) reconcile any relay already on this port. A stale, OLDER-version relay is
  //    the classic "I updated but nothing changed" trap — npx serves a cached
  //    build, or an old daemon lingers. Replace it so `live` always converges to
  //    THIS version (and picks up fixes like agent self-heal).
  const existing = await getHealth(port);
  if (existing && existing.version && existing.version !== PKG_VERSION) {
    log(`• replacing a stale relay on :${port} (v${existing.version} → v${PKG_VERSION})`);
    await postRelay(port, "/shutdown");
    stopDaemon({ silent: true });
    if (!(await waitForPortFree(port))) {
      log(`! the old relay on :${port} didn't exit — you may need to kill it manually.`);
    }
  }

  // 1) inject the script tag
  if (page) {
    injectTag(page, port);
    log(`✓ injected timeline into ${page.replace(CWD + "/", "")}`);
  } else {
    log("! no HTML entry found (looked for index.html, public/index.html, …).");
    log("  Add this one line to your page <body> yourself:");
    log(`    <script type="module" src="http://localhost:${port}/inject.js"></script>`);
    log("  …or re-run with --page <path-to-your-html>.");
  }

  // 2) drop the skills the Refine flow relies on (the in-IDE agent and any
  //    spawned cursor-agent both read transitions-dev for token-aware picks).
  for (const name of ["refine-live", "transitions-dev"]) {
    const r = dropSkill(name);
    if (r === true) log(`✓ added .agents/skills/${name}`);
    else if (r === "updated") log(`✓ updated .agents/skills/${name} (now v${PKG_VERSION})`);
    else if (r === "exists") log(`✓ ${name} skill already present (v${PKG_VERSION})`);
  }

  // 2.5) wire an agent CLI so the relay can answer LLM jobs itself — the
  //      persistent path (no `/refine live` loop to keep alive). We prefer the
  //      agent hosting this run so Refine bills the subscription the user already
  //      has. REFINE_AGENT_CMD (if set) always wins; --agent forces a choice.
  const wantLlm = Boolean(args.llm);
  const forceKey = typeof args.agent === "string" ? args.agent : null;
  const env = { ...process.env, REFINE_RELAY_PORT: port };
  // Pass a forced --agent through so the relay's runtime self-heal honors it too.
  if (forceKey) env.REFINE_AGENT = forceKey;
  const resolved = resolveAgent({ wantLlm, forceKey });
  if (resolved.cmd) {
    env.REFINE_AGENT_CMD = resolved.cmd;
    if (resolved.source === "env") {
      log(`✓ using REFINE_AGENT_CMD from environment: ${resolved.cmd}`);
    } else {
      const via =
        resolved.source === "host" ? `detected ${resolved.agent.label}`
        : resolved.source === "forced" ? `forced ${resolved.agent.label}`
        : resolved.source === "scan" ? `found ${resolved.agent.label}`
        : `installed ${resolved.agent.label}`;
      log(`✓ LLM path wired (${via}): relay will spawn  ${resolved.cmd}`);
    }
  } else if (resolved.reason) {
    log(`• LLM not wired — ${resolved.reason}.`);
  }

  // 2.75) In a one-shot agent shell (Claude Code / Codex / Cursor tool calls),
  //       stdout isn't a TTY and the command is expected to exit. Run the relay
  //       as a detached daemon and return, so the agent gets output + a persistent
  //       relay. A real interactive terminal (TTY) keeps the foreground Ctrl-C UX.
  //       Override either way with --detach / --foreground.
  const inAgentShell = !process.stdout.isTTY;
  const detach = Boolean(args.detach) || (inAgentShell && !args.foreground);
  if (detach) {
    await startDetached({ port, page, env, resolved });
    return;
  }

  // 3) start the relay (foreground; Ctrl-C stops it + reverts the injection)
  const relay = spawn(process.execPath, [join(PKG_ROOT, "server/relay.mjs")], {
    stdio: "inherit",
    env,
  });

  const llmWired = Boolean(env.REFINE_AGENT_CMD);
  const authHint = resolved.agent && resolved.agent.auth;
  log("");
  log("Next:");
  log("  1. Open your app — the timeline panel is now on the page.");
  log("  2. Click Refine. Deterministic suggestions work immediately.");
  if (llmWired) {
    log("  3. LLM suggestions are ON — the relay runs the agent CLI per click,");
    log("     so you never have to run /refine live.");
    if (authHint) log(`     One-time: make sure the CLI is authenticated — ${authHint}.`);
  } else {
    log("  3. No agent CLI wired, so LLM features need a live answerer. Either:");
    log("     • run /refine live in your editor (Cursor / Claude Code / Codex), or");
    log("     • re-run with --llm to install the Cursor CLI, or");
    log("     • export REFINE_AGENT_CMD='<your agent CLI>' and re-run.");
  }
  log("");
  log("Press Ctrl-C to stop the relay and remove the injected tag.");

  const cleanup = () => {
    try {
      if (page && existsSync(page)) {
        const html = stripTag(readFileSync(page, "utf8"));
        writeFileSync(page, html);
        log(`\n✓ removed injected tag from ${page.replace(CWD + "/", "")}`);
      }
    } catch {}
    if (!relay.killed) relay.kill("SIGINT");
    process.exit(0);
  };
  process.on("SIGINT", cleanup);
  process.on("SIGTERM", cleanup);
  relay.on("exit", (code) => process.exit(code ?? 0));
}

function cmdStop(args) {
  // 1) kill a background daemon if one is recorded for this project. Prefer the
  //    page the daemon injected (so we clean the right file even without --page).
  let rec = null;
  try { rec = JSON.parse(readFileSync(daemonFile(), "utf8")); } catch {}
  const killed = stopDaemon();

  // 2) strip the injected tag.
  const page = findPage(args.page) || (rec && rec.page) || null;
  if (!page || !existsSync(page)) {
    if (!killed) log("! no HTML entry found to clean. Pass --page <path> if needed.");
    return;
  }
  const html = readFileSync(page, "utf8");
  if (!html.includes(MARK_START)) {
    if (!killed) log(`nothing to remove in ${rel(page)}`);
    return;
  }
  writeFileSync(page, stripTag(html));
  log(`✓ removed injected tag from ${rel(page)}`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const cmd = args._[0] || "live";
  if (cmd === "live") return cmdLive(args);
  if (cmd === "stop") return cmdStop(args);
  log("Refine — transitions.dev live tool");
  log("  npx transitions-refine live                 # inject panel + relay; auto-wire your agent CLI");
  log("  npx transitions-refine live --agent claude  # force an agent: cursor | claude | codex");
  log("  npx transitions-refine live --llm           # install the Cursor CLI if no agent is found");
  log("  npx transitions-refine stop                 # stop the relay + remove the injected tag");
  log("");
  log("Options: --page <html>  --port <n>  --agent <cursor|claude|codex>  --llm");
  log("         --detach        run the relay in the background and exit (default in agent shells)");
  log("         --foreground    keep the relay in the foreground (Ctrl-C to stop)");
  log("");
  log("In a coding agent (Claude Code / Codex / Cursor) `live` auto-detaches: it starts");
  log("a background relay, wires that agent's CLI, and exits — so just running the command");
  log("works. It prefers the agent hosting this run so Refine uses the subscription you");
  log("already have. Or set REFINE_AGENT_CMD to wire any CLI.");
  process.exit(cmd ? 1 : 0);
}

// Run only when invoked as the CLI entry (npx / node bin/cli.mjs), so tests can
// import the resolver helpers without triggering a live run.
// Run only when invoked as the CLI entry (npx / global install / node bin/cli.mjs).
// We must resolve symlinks: npx and global installs invoke this via a `.bin/refine`
// symlink, so process.argv[1] is the symlink path while import.meta.url is the real
// file. Comparing raw paths fails through the symlink and silently skips main().
function isCliEntry() {
  if (!process.argv[1]) return false;
  const self = fileURLToPath(import.meta.url);
  const resolve = (p) => {
    try { return realpathSync(p); } catch { return p; }
  };
  return resolve(process.argv[1]) === resolve(self);
}
if (isCliEntry()) {
  main().catch((e) => {
    log(`! refine failed: ${e && e.message ? e.message : e}`);
    process.exit(1);
  });
}

export { resolveAgent };
export { AGENTS, HOST_PRECEDENCE, detectHostAgent, findBin } from "../server/agent-resolve.mjs";
