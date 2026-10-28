// Live Refine agent loop — polls GET /jobs/next and answers LLM jobs per refine-live skill.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { SMOOTH_OUT } from "./motion-tokens.mjs";

const RELAY = process.env.REFINE_RELAY_URL || "http://localhost:7331";
const WORKSPACE = process.env.REFINE_WORKSPACE || join(dirname(fileURLToPath(import.meta.url)), "..");
const LOG = join(WORKSPACE, ".refine-live.log");

let jobsHandled = 0;
let errors = 0;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  try {
    writeFileSync(LOG, line, { flag: "a" });
  } catch {}
  console.log(msg);
}

async function relayFetch(path, opts = {}) {
  const res = await fetch(`${RELAY}${path}`, opts);
  return res;
}

async function post(path, body) {
  await relayFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ── usage inference ──────────────────────────────────────────────────────────

function inferUsage(label = "", selector = "") {
  const s = `${label} ${selector}`.toLowerCase();
  if (/modal|dialog/.test(s)) return "modal";
  if (/dropdown|menu|popover/.test(s)) return "dropdown";
  if (/tooltip/.test(s)) return "tooltip";
  if (/badge|notification/.test(s)) return "badge";
  if (/accordion|collapse/.test(s)) return "accordion";
  if (/panel|drawer|sidebar/.test(s)) return "panel";
  if (/toast/.test(s)) return "toast";
  if (/tab/.test(s)) return "tabs";
  if (/shake|error|invalid/.test(s)) return "shake";
  if (/skeleton|shimmer/.test(s)) return "skeleton";
  if (/icon/.test(s)) return "icon";
  if (/resize|width|height|size/.test(s)) return "resize";
  if (/color|background|theme/.test(s)) return "color";
  if (/opacity|fade/.test(s)) return "fade";
  if (/transform|slide|translate/.test(s)) return "slide";
  return "generic";
}

function targetDurationMs(usage, property) {
  const p = (property || "").toLowerCase();
  switch (usage) {
    case "modal":
    case "dropdown":
      return 250; // open fast; close handled separately in scan
    case "tooltip":
      return p === "opacity" ? 150 : 150;
    case "badge":
      return 500;
    case "panel":
      return 400;
    case "toast":
      return 350;
    case "tabs":
      return 250;
    case "shake":
      return 80;
    case "skeleton":
      return 400;
    case "icon":
      return 250;
    case "resize":
      return 250;
    case "accordion":
      return 400;
    default:
      return 250;
  }
}

function shouldNudgeEasing(easing) {
  const n = String(easing || "").replace(/\s+/g, "").toLowerCase();
  if (!n) return false;
  const tokens = new Set([
    SMOOTH_OUT.replace(/\s+/g, "").toLowerCase(),
    "ease-in-out",
    "ease-out",
    "linear",
    "cubic-bezier(0.34,1.36,0.64,1)",
    "cubic-bezier(0.34,3.85,0.64,1)",
  ]);
  if (tokens.has(n)) return false;
  return n === "ease" || n === "ease-in" || n.startsWith("cubic-bezier") || n.startsWith("linear(");
}

function handleSmallRefine(request) {
  const usage = inferUsage(request.label, request.selector);
  const timings = request.timings || [];
  const suggestions = [];

  for (const t of timings) {
    const prop = t.property || "all";
    const target = targetDurationMs(usage, prop);
    if (Number.isFinite(t.durationMs) && Math.abs(t.durationMs - target) > 10) {
      suggestions.push({
        id: `${prop}-duration`,
        kind: "duration",
        property: prop,
        title: `Duration → ${target}ms`,
        from: `${t.durationMs}ms`,
        to: `${target}ms`,
        patch: { property: prop, durationMs: target },
        reason: `${usage} motion reads best at ${target}ms for ${prop}.`,
      });
    }
    if (shouldNudgeEasing(t.easing)) {
      suggestions.push({
        id: `${prop}-easing`,
        kind: "easing",
        property: prop,
        title: "Easing → Smooth ease out",
        from: t.easing,
        to: SMOOTH_OUT,
        patch: { property: prop, easing: SMOOTH_OUT },
        reason: "Generic curve → transitions.dev smooth ease-out.",
      });
    }
  }

  return {
    suggestions,
    summary: suggestions.length
      ? `Nudged ${suggestions.length} value(s) toward motion tokens.`
      : "Already aligned to motion tokens.",
  };
}

// ── replace recipes ──────────────────────────────────────────────────────────

const RECIPES = [
  { id: "card-resize", file: "01-card-resize.md", title: "Card resize", match: /resize|width|height|size/ },
  { id: "menu-dropdown", file: "05-menu-dropdown.md", title: "Menu dropdown", match: /dropdown|menu|popover/ },
  { id: "modal", file: "06-modal.md", title: "Modal open/close", match: /modal|dialog/ },
  { id: "panel-reveal", file: "07-panel-reveal.md", title: "Panel reveal", match: /panel|drawer|sidebar/ },
  { id: "tooltip", file: "17-tooltip.md", title: "Tooltip", match: /tooltip/ },
  { id: "notification-badge", file: "03-notification-badge.md", title: "Notification badge", match: /badge|notification/ },
  { id: "accordion", file: "21-accordion.md", title: "Accordion", match: /accordion|collapse/ },
  { id: "icon-swap", file: "09-icon-swap.md", title: "Icon swap", match: /icon/ },
  { id: "tabs-sliding", file: "16-tabs-sliding.md", title: "Tabs sliding", match: /tab/ },
];

function pickRecipe(request) {
  const s = `${request.label || ""} ${request.selector || ""}`.toLowerCase();
  for (const r of RECIPES) {
    if (r.match.test(s)) return r;
  }
  return null;
}

function handleReplaceRefine(request) {
  const recipe = pickRecipe(request);
  if (!recipe) {
    return { suggestions: [], summary: "No matching transitions.dev recipe for this usage." };
  }

  const prop = request.timings?.[0]?.property || "all";
  const phases = Array.isArray(request.phases) ? request.phases.filter((p) => p?.phase) : [];
  const hasOpenClose = phases.some((p) => p.phase === "open") && phases.some((p) => p.phase === "close");

  const basePatch = {
    property: prop,
    durationMs: 250,
    easing: SMOOTH_OUT,
  };

  const suggestion = {
    id: `replace-${recipe.id}`,
    kind: "replace",
    property: prop,
    title: `Replace with ${recipe.title}`,
    from: "hand-rolled transition",
    to: `transitions.dev · ${recipe.title}`,
    patch: basePatch,
    reference: `transitions-dev/${recipe.file}`,
    reason: `Usage matches ${recipe.title}. Paste ${recipe.file} for full structure.`,
  };

  if (hasOpenClose) {
    suggestion.patches = [
      { ...basePatch, durationMs: 250, phase: "open" },
      { ...basePatch, durationMs: 150, phase: "close", easing: SMOOTH_OUT },
    ];
  }

  return {
    suggestions: [suggestion],
    summary: `Suggested ${recipe.title} recipe.`,
  };
}

// ── scan: parse cssRules ─────────────────────────────────────────────────────

function parseTransitionDecl(text) {
  const out = [];
  const re = /([\w-]+)\s+(\d+(?:\.\d+)?)(ms|s)(?:\s+([\w().,-]+))?(?:\s+(\d+(?:\.\d+)?)(ms|s))?/gi;
  let m;
  while ((m = re.exec(text)) !== null) {
    let ms = parseFloat(m[2]);
    if (m[3] === "s") ms *= 1000;
    let delay = 0;
    if (m[5]) {
      delay = parseFloat(m[5]);
      if (m[6] === "s") delay *= 1000;
    }
    out.push({
      property: m[1],
      durationMs: Math.round(ms),
      delayMs: Math.round(delay),
      easing: m[4] || "ease",
    });
  }
  return out;
}

function slug(s) {
  return String(s || "item")
    .replace(/[^a-z0-9]+/gi, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase() || "item";
}

function detectPhase(selector) {
  const s = String(selector || "").toLowerCase();
  if (/closing|close|hide|exit|leave/.test(s)) return "close";
  if (/open|show|enter|visible|is-active/.test(s)) return "open";
  return null;
}

function handleScan(request) {
  const raw = request.raw || [];
  const groupMap = new Map();

  for (const entry of raw) {
    const sel = entry.selector || entry.label || "unknown";
    const baseKey = sel.split(/[\s>+~]/).pop()?.replace(/^[.#]/, "") || slug(entry.label);
    const groupId = slug(baseKey.split("-")[0] || baseKey);
    const groupLabel = groupId.charAt(0).toUpperCase() + groupId.slice(1);

    if (!groupMap.has(groupId)) {
      groupMap.set(groupId, {
        id: groupId,
        label: groupLabel,
        component: request.url || null,
        phases: new Map(),
      });
    }
    const group = groupMap.get(groupId);
    const rules = entry.cssRules || [];
    const currentTimings = entry.timings || [];

    if (rules.length) {
      for (const rule of rules) {
        const phaseHint = detectPhase(rule) || "open";
        const phaseId = `${groupId}:${phaseHint}`;
        if (!group.phases.has(phaseId)) {
          group.phases.set(phaseId, {
            id: phaseId,
            phase: phaseHint,
            label: phaseHint === "close" ? "Close" : "Open",
            members: [],
          });
        }
        const timings = parseTransitionDecl(rule);
        const memberTimings = timings.length ? timings : currentTimings;
        group.phases.get(phaseId).members.push({
          id: slug(entry.label || sel),
          label: entry.label || sel,
          selector: sel,
          toState: phaseHint === "close" ? ".is-closing" : ".is-open",
          propertyTimings: memberTimings.map((t) => ({ ...t })),
        });
      }
    } else {
      const phaseId = `${groupId}:open`;
      if (!group.phases.has(phaseId)) {
        group.phases.set(phaseId, {
          id: phaseId,
          phase: "open",
          label: "Open",
          members: [],
        });
      }
      group.phases.get(phaseId).members.push({
        id: slug(entry.label || sel),
        label: entry.label || sel,
        selector: sel,
        propertyTimings: currentTimings.map((t) => ({ ...t })),
      });
    }
  }

  const groups = [...groupMap.values()].map((g) => ({
    id: g.id,
    label: g.label,
    component: g.component,
    phases: [...g.phases.values()],
  }));

  return {
    groups,
    summary: groups.length ? `Grouped into ${groups.length} component(s).` : "Could not group transitions.",
  };
}

// ── apply: edit source ───────────────────────────────────────────────────────

function findFile(componentHint) {
  if (!componentHint) return null;
  const candidates = [
    join(WORKSPACE, componentHint),
    join(WORKSPACE, "..", componentHint),
    join(process.cwd(), componentHint),
  ];
  for (const p of candidates) {
    if (existsSync(p)) return p;
  }
  return null;
}

function replaceTimingInText(text, change) {
  const { property, from, to } = change;
  const prop = property || "all";
  const fromDur = from?.durationMs;
  const toDur = to?.durationMs;
  const toEase = to?.easing;

  let out = text;
  if (Number.isFinite(fromDur) && Number.isFinite(toDur)) {
    const patterns = [
      new RegExp(`(${prop}\\s+)${fromDur}(ms)`, "g"),
      new RegExp(`(${prop}\\s+)${fromDur / 1000}(s)`, "g"),
      new RegExp(`(transition(?:-duration)?\\s*:\\s*)${fromDur}(ms)`, "g"),
    ];
    for (const re of patterns) {
      out = out.replace(re, `$1${toDur}$2`);
    }
  }
  if (toEase && from?.easing && from.easing !== toEase) {
    out = out.replace(new RegExp(escapeRe(from.easing), "g"), toEase);
  }
  return out;
}

function escapeRe(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function handleApply(request) {
  const file = findFile(request.component);
  if (!file) {
    return {
      applied: false,
      summary: `Could not find source for ${request.component || request.selector}.`,
    };
  }

  let text = readFileSync(file, "utf8");
  const changes = request.changes || [];
  let changed = false;

  for (const c of changes) {
    const next = replaceTimingInText(text, c);
    if (next !== text) {
      text = next;
      changed = true;
    }
  }

  if (changed) {
    writeFileSync(file, text);
    return {
      applied: true,
      summary: `Updated timings in ${request.label || request.selector}.`,
      files: [`${file}`],
    };
  }

  return {
    applied: false,
    summary: `Found ${file} but could not match declarations to update.`,
  };
}

// ── dispatch ─────────────────────────────────────────────────────────────────

async function handleJob(job) {
  const { id, request } = job;
  const kind = request?.kind;
  const label = request?.label || request?.selector || kind || "job";
  log(`▸ job ${id.slice(0, 8)} — ${label} (${kind || request?.refineType || "refine"})`);

  await post(`/jobs/${id}/status`, { message: "Processing…" });

  let result;
  if (kind === "scan") {
    result = handleScan(request);
  } else if (kind === "apply") {
    result = handleApply(request);
  } else if (request?.refineType === "replace") {
    result = handleReplaceRefine(request);
  } else {
    result = handleSmallRefine(request);
  }

  await post(`/jobs/${id}/result`, result);
  jobsHandled++;
  log(`  ✓ done (${jobsHandled} total)`);
}

async function pollOnce() {
  const res = await relayFetch("/jobs/next");
  if (res.status === 204) return false;
  if (!res.ok) throw new Error(`poll HTTP ${res.status}`);
  const job = await res.json();
  // Stop signal from the panel's STOP button (relay POST /poller/stop → the
  // relay answers the next /jobs/next with {stop:true}). Honor it and exit.
  // Without this the {stop:true} body is treated as a malformed job, throws,
  // and the loop re-polls ~2s later — so the relay reports pollerActive again
  // and the panel flips "Live" back on shortly after Stop.
  if (job && job.stop) {
    log(`stop signal received — exiting (jobs=${jobsHandled} errors=${errors})`);
    process.exit(0);
  }
  await handleJob(job);
  return true;
}

async function loop() {
  log(`live refine loop → ${RELAY} (workspace: ${WORKSPACE})`);
  // Announce ourselves so the relay clears any prior Stop latch — otherwise a
  // relay that's still "stopped" from a previous panel Stop would answer our
  // first poll with {stop:true} and we'd exit immediately.
  try { await post("/poller/start", {}); } catch {}
  // eslint-disable-next-line no-constant-condition
  while (true) {
    try {
      const hadJob = await pollOnce();
      if (!hadJob) await sleep(100);
    } catch (e) {
      errors++;
      log(`  ✗ ${e.message} — retry in 2s`);
      await sleep(2000);
      try {
        const h = await relayFetch("/health");
        if (!h.ok) log("  relay health check failed");
      } catch {
        log("  relay unreachable");
      }
    }
  }
}

process.on("SIGINT", () => {
  log(`stopped — jobs=${jobsHandled} errors=${errors}`);
  process.exit(0);
});

loop();
