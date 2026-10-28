// Provisional, in-process grouping straight from the CSSOM harvest
// (entry.cssRules + entry.timings). It mirrors what buildScanPrompt asks the
// agent to do MECHANICALLY for the common case — cluster by component root,
// split open/close phases, copy the current-state timings, read the
// opposite-phase timings from a state-variant rule — so the panel can show
// grouped components in <1s instead of waiting out a cold agent turn.
//
// This is deliberately PROVISIONAL: the relay still runs the real agent scan
// (wired CLI) or leaves the job for a `/refine live` agent, and that result
// OVERWRITES this one when it lands. So any imperfection here is transient and
// the FINAL naming/grouping stays agent-quality. We return `null` (defer fully
// to the agent, today's exact behaviour) whenever the harvest is missing or no
// confident group emerges — never a worse-than-today result.

// Component vocabulary — names a cluster from its class tokens. Order = most
// specific first. Only used for the provisional label; the agent renames later.
// Matched against a name "haystack" with -/_ normalized to spaces, so it hits
// both class tokens (dd-dropdown) and human labels ("Dropdown panel").
const VOCAB = [
  [/\b(?:dropdown|combobox|listbox|autocomplete)\b/i, "Dropdown"],
  [/\bmenu\b/i, "Menu"],
  [/\b(?:modal|dialog|lightbox)\b/i, "Modal"],
  [/\b(?:popover|popup)\b/i, "Popover"],
  [/\btooltip\b/i, "Tooltip"],
  [/\b(?:accordion|collapse|collapsible|disclosure)\b/i, "Accordion"],
  [/\b(?:drawer|offcanvas|sheet)\b/i, "Drawer"],
  [/\bsidebar\b/i, "Sidebar"],
  [/\b(?:toast|snackbar|notification)\b/i, "Toast"],
  [/\btabs?\b/i, "Tabs"],
  [/\bpanel\b/i, "Panel"],
];

// State-token class names. A class on an ancestor (or the element) that matches
// one of these marks the toggled state that drives a phase.
const OPEN_CLASS = /^(?:is-)?(?:open|opened|active|show|shown|visible|expanded|entered|in)$/i;
const CLOSE_CLASS = /^(?:is-)?(?:clos(?:e|ed|ing)|hidden|hide|leaving|exiting|out|collapsed)$/i;

function isStateClass(c) {
  return OPEN_CLASS.test(c) || CLOSE_CLASS.test(c);
}
function classPhase(c) {
  return CLOSE_CLASS.test(c) ? "close" : "open";
}

// ── tiny CSS helpers ─────────────────────────────────────────────────────────

// Split respecting parens/brackets so cubic-bezier(0.22, 1, 0.36, 1) and
// [data-state="open"] stay intact.
function splitTop(str, sep) {
  const out = [];
  let depth = 0;
  let cur = "";
  for (const ch of String(str)) {
    if (ch === "(" || ch === "[") depth++;
    else if (ch === ")" || ch === "]") depth = Math.max(0, depth - 1);
    if (ch === sep && depth === 0) {
      out.push(cur);
      cur = "";
    } else cur += ch;
  }
  out.push(cur);
  return out.map((s) => s.trim()).filter(Boolean);
}

function timeToMs(t) {
  const m = String(t).trim().match(/^(-?[\d.]+)\s*(ms|s)$/i);
  if (!m) return null;
  const n = parseFloat(m[1]);
  if (!Number.isFinite(n)) return null;
  return m[2].toLowerCase() === "s" ? Math.round(n * 1000) : Math.round(n);
}

function parseRule(str) {
  const i = String(str).indexOf("{");
  if (i < 0) return null;
  const head = str.slice(0, i).trim();
  let body = str.slice(i + 1);
  const j = body.lastIndexOf("}");
  if (j >= 0) body = body.slice(0, j);
  return { selectors: splitTop(head, ","), body };
}

function declMap(body) {
  const m = new Map();
  for (const d of splitTop(body, ";")) {
    const c = d.indexOf(":");
    if (c < 0) continue;
    m.set(d.slice(0, c).trim().toLowerCase(), d.slice(c + 1).trim());
  }
  return m;
}

const EASING_KW = /^(?:ease|ease-in|ease-out|ease-in-out|linear|step-start|step-end)$/i;
const EASING_FN = /^(?:cubic-bezier|steps|linear)\s*\(/i;

// transition shorthand → [{property,durationMs,delayMs,easing}]
function parseShorthand(value) {
  const out = [];
  for (const seg of splitTop(value, ",")) {
    const toks = splitTop(seg, " ");
    let prop = null;
    let easing = null;
    const times = [];
    for (const tk of toks) {
      const ms = timeToMs(tk);
      if (ms != null) {
        times.push(ms);
        continue;
      }
      if (EASING_KW.test(tk) || EASING_FN.test(tk)) {
        easing = tk;
        continue;
      }
      if (!prop && /^[a-z][\w-]*$/i.test(tk)) prop = tk;
    }
    if (prop && prop.toLowerCase() !== "none") {
      out.push({
        property: prop,
        durationMs: times[0] ?? 0,
        delayMs: times[1] ?? 0,
        easing: easing || "ease",
      });
    }
  }
  return out;
}

function timingsFromBody(body) {
  const d = declMap(body);
  if (d.has("transition")) return parseShorthand(d.get("transition"));
  const props = d.get("transition-property");
  if (!props) return [];
  const plist = splitTop(props, ",");
  const durs = splitTop(d.get("transition-duration") || "", ",").map(timeToMs);
  const eas = splitTop(d.get("transition-timing-function") || "", ",");
  const dels = splitTop(d.get("transition-delay") || "", ",").map(timeToMs);
  const at = (arr, i, fb) => (arr.length ? arr[i % arr.length] : fb);
  return plist
    .filter((p) => p && p.toLowerCase() !== "none")
    .map((p, i) => ({
      property: p,
      durationMs: at(durs, i, 0) ?? 0,
      delayMs: at(dels, i, 0) ?? 0,
      easing: at(eas, i, "ease") || "ease",
    }));
}

// ── selector analysis ────────────────────────────────────────────────────────

// Classes in the LAST compound of a selector (the element the rule targets).
function leafClasses(selector) {
  const compounds = String(selector).split(/\s*[>+~]\s*|\s+/).filter(Boolean);
  const last = compounds[compounds.length - 1] || "";
  return (last.match(/\.[-\w]+/g) || []).map((s) => s.slice(1));
}

// Does this selector (one compound chain) target the member identified by its
// own leaf classes? True when its last compound carries one of those classes.
function targetsMember(selector, leaf) {
  if (!leaf.length) return false;
  const compounds = String(selector).split(/\s*[>+~]\s*|\s+/).filter(Boolean);
  const last = compounds[compounds.length - 1] || "";
  return leaf.some((c) => new RegExp("\\." + escapeRe(c) + "(?![\\w-])").test(last));
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// From a state-variant selector that targets `leaf`, pull out the toggled state
// token and the stateTarget selector (the element the token sits on, with the
// token stripped). Returns {stateTarget, token, phase} or null.
function deriveState(selector, leaf) {
  const compounds = String(selector).split(/\s+/).filter(Boolean); // descendant only — keep it simple
  if (!compounds.length) return null;
  const memberIdx = compounds.length - 1;
  // walk compounds, find the FIRST that carries a state class or state attr.
  for (let i = 0; i < compounds.length; i++) {
    const comp = compounds[i];
    const classes = (comp.match(/\.[-\w]+/g) || []).map((s) => s.slice(1));
    const stateCls = classes.find(isStateClass);
    // attribute state: [data-open], [data-state="open"], [aria-expanded="true"], [open]
    const attr = comp.match(/\[[^\]]+\]/g) || [];
    const stateAttr = attr.find((a) => /data-open|data-state|aria-expanded|aria-hidden|\bopen\b|visible|expanded/i.test(a));

    if (stateCls) {
      const target = stripToken(comp, "." + stateCls) + ancestorPrefix(compounds, i);
      return { stateTarget: normalizeSel(target), token: "." + stateCls, phase: classPhase(stateCls) };
    }
    if (stateAttr) {
      const target = stripToken(comp, stateAttr) + ancestorPrefix(compounds, i);
      const phase = /clos|hidden|false|collapsed/i.test(stateAttr) ? "close" : "open";
      return { stateTarget: normalizeSel(target), token: stateAttr, phase };
    }
    if (i === memberIdx) break;
  }
  return null;
}

// Build the ancestor prefix selector for the compound at index i (everything
// before it), so stateTarget keeps its context (".wrap .dd" not just ".dd").
function ancestorPrefix() {
  return ""; // single-compound stateTarget is enough for live-preview scoping
}
function stripToken(compound, token) {
  return compound.split(token).join("");
}
function normalizeSel(sel) {
  const s = String(sel).trim();
  return s || "*";
}

function humanize(token) {
  return String(token)
    .replace(/^[.#]/, "")
    .replace(/[-_]+/g, " ")
    .replace(/\b(is|tl|tx|wd|ui|js|css)\b/gi, "")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase()) || "Component";
}

function nameFromTokens(tokens) {
  const hay = tokens.join(" ").replace(/[-_]+/g, " ");
  for (const [re, name] of VOCAB) if (re.test(hay)) return name;
  return null;
}

function slug(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "group";
}

// ── per-entry analysis ───────────────────────────────────────────────────────

function analyzeEntry(entry) {
  if (!entry || !Array.isArray(entry.cssRules) || !entry.cssRules.length) return null;
  const memberSel = entry.selector || "";
  const leaf = leafClasses(memberSel);
  if (!leaf.length) return null;

  const rules = entry.cssRules.map(parseRule).filter(Boolean);
  let state = null; // {stateTarget, token, phase} — the open toggle
  let baseTimings = null; // transition on the base (no-state) member rule
  let openTimings = null; // transition on an OPEN-state variant rule
  let closeTimings = null; // transition on a CLOSE-state variant rule

  for (const rule of rules) {
    for (const sel of rule.selectors) {
      if (!targetsMember(sel, leaf)) continue;
      const st = deriveState(sel, leaf);
      const t = timingsFromBody(rule.body);
      if (st) {
        if (st.phase === "open" && !state) state = st; // prefer an open token for stateTarget
        if (st.phase === "open" && t.length) openTimings = t;
        if (st.phase === "close" && t.length) closeTimings = t;
        if (!state) state = st; // fall back to a close token if that's all there is
      } else if (t.length && !baseTimings) {
        baseTimings = t;
      }
    }
  }
  if (!state) return null; // no toggle → can't phase it; defer to agent

  // Authoritative live timings for the element's CURRENT DOM state.
  const current = Array.isArray(entry.timings) && entry.timings.length
    ? entry.timings.map((t) => ({ property: t.property, durationMs: t.durationMs, delayMs: t.delayMs, easing: t.easing }))
    : null;

  // Standard pattern: the base rule's transition drives the OPEN (enter); a
  // `.is-closing`-style variant carries the CLOSE. Fall back sensibly when a
  // phase has no dedicated rule (one transition both ways).
  const open = openTimings || baseTimings || current;
  const close = closeTimings || baseTimings || current;
  if (!open || !close) return null;

  const memberId = slug(leaf[leaf.length - 1] || entry.label || "member");
  const member = {
    id: memberId,
    label: entry.label || humanize(leaf[leaf.length - 1]),
    selector: memberSel,
  };
  // Name hints: the element's own classes, its stateTarget, AND the human label
  // the scanner already produced (e.g. "Dropdown panel" → matches /dropdown/).
  const labelWords = String(entry.label || "").split(/\s+/).filter(Boolean);
  return {
    stateTarget: state.stateTarget,
    token: state.token,
    member,
    openTimings: open,
    closeTimings: close,
    nameTokens: [...leaf, state.stateTarget, ...labelWords],
  };
}

// ── public API ───────────────────────────────────────────────────────────────

export function groupDeterministic(raw) {
  if (process.env.REFINE_FAST_GROUP === "0") return null;
  if (!Array.isArray(raw) || !raw.length) return null;

  // Cluster entries by stateTarget. Every entry must analyze; if ANY entry has
  // cssRules but no resolvable toggle, that one alone shouldn't sink the rest —
  // but we DO require all-or-nothing on the harvest itself to avoid a confusing
  // partial provisional. Entries that don't analyze are simply left ungrouped.
  const clusters = new Map();
  let analyzed = 0;
  for (const entry of raw) {
    const info = analyzeEntry(entry);
    if (!info) continue;
    analyzed++;
    const key = info.stateTarget;
    if (!clusters.has(key)) clusters.set(key, { stateTarget: key, members: [], tokens: [] });
    const c = clusters.get(key);
    c.members.push(info);
    c.tokens.push(...info.nameTokens);
  }
  if (!clusters.size || !analyzed) return null;

  const groups = [];
  for (const c of clusters.values()) {
    const openTok = c.members[0].token; // the open toggle on the stateTarget
    const name = nameFromTokens(c.tokens) || humanize(c.stateTarget);
    const gid = slug(name + "-" + c.stateTarget);

    // OPEN phase: base → open (use each member's open timings).
    // CLOSE phase: open → base (use each member's close timings).
    const openMembers = c.members.map((m) => ({
      id: m.member.id,
      label: m.member.label,
      selector: m.member.selector,
      propertyTimings: m.openTimings,
    }));
    const closeMembers = c.members.map((m) => ({
      id: m.member.id,
      label: m.member.label,
      selector: m.member.selector,
      propertyTimings: m.closeTimings,
    }));

    const phases = [
      {
        id: gid + ":open",
        phase: "open",
        label: "Open",
        stateTarget: c.stateTarget,
        fromState: null,
        toState: openTok,
        members: openMembers,
      },
      {
        id: gid + ":close",
        phase: "close",
        label: "Close",
        stateTarget: c.stateTarget,
        fromState: openTok,
        toState: null,
        members: closeMembers,
      },
    ];
    groups.push({ id: gid, label: name, component: null, phases, provisional: true });
  }
  if (!groups.length) return null;

  return {
    groups,
    summary: `Grouped ${groups.length} component${groups.length === 1 ? "" : "s"} (provisional — refining…).`,
  };
}

export default groupDeterministic;
