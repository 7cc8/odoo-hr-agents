// The transitions.dev motion-token vocabulary, plus a deterministic refine pass
// that maps a transition's current values onto the nearest token and proposes
// the differences. This mirrors the `transitions refine` behaviour in
// ~/.agents/skills/transitions-dev/SKILL.md so the reference agent can answer
// without an LLM. A real agent driven by the skill can do better — it infers
// *usage* (modal close vs dropdown open) from the surrounding code rather than
// snapping to the nearest number.

// Durations — from the skill's "## Motion tokens" table.
export const DURATION_TOKENS = [
  { ms: 40, name: "Stagger", usage: "per-item stagger offset" },
  { ms: 80, name: "Micro", usage: "tooltip delay, shake segment, large stagger" },
  { ms: 150, name: "Quick", usage: "modal close, dropdown close, text swap, tooltip appear" },
  { ms: 250, name: "Fast", usage: "icon swap, dropdown open, modal open, tabs sliding, page slide" },
  { ms: 350, name: "Medium", usage: "panel close, toast close" },
  { ms: 400, name: "Slow", usage: "panel open, skeleton content reveal, input clear" },
  { ms: 500, name: "Very slow", usage: "emphasis, badge appear, text reveal, success check" },
];

// The transitions.dev default ease-out — "Smooth ease out" in the skill.
export const SMOOTH_OUT = "cubic-bezier(0.22, 1, 0.36, 1)";

// Scales — from the skill's "## Motion tokens" Scales table. These are the
// non-resting ("pre") scale a surface animates FROM (it always settles to 1).
export const SCALE_TOKENS = [
  { v: 0.96, name: "Large", usage: "modal open / close" },
  { v: 0.97, name: "Medium", usage: "dropdown open" },
  { v: 0.98, name: "Small", usage: "tooltip open" },
  { v: 0.99, name: "Tiny", usage: "dropdown close" },
];

// Blur (px) — from the skill's "## Motion tokens" Blur table. The non-resting
// blur a surface animates FROM (it always settles to 0).
export const BLUR_TOKENS = [
  { px: 2, name: "Small", usage: "panel reveal, icon swap, text swap, skeleton reveal, number pop-in" },
  { px: 3, name: "Medium", usage: "page slide, text reveal" },
  { px: 8, name: "Large", usage: "success check open" },
];

// Distances (px) — from the skill's "## Motion tokens" Distances table. The
// non-resting translate a surface animates FROM (it always settles to 0). The
// transitions-polish add-on skill documents these; without it, the base skill
// only names them in prose. Mirrors the scale/blur usage-first matching.
export const DISTANCE_TOKENS = [
  { px: 4, name: "Micro", usage: "text swap" },
  { px: 6, name: "Small", usage: "error shake (small segment)" },
  { px: 8, name: "Base", usage: "badge diagonal reveal, page slide, error shake (large segment)" },
  { px: 12, name: "Medium", usage: "text reveal" },
  { px: 30, name: "Large", usage: "check badge appear" },
];

// Easing values that ARE motion tokens — leave these alone.
const TOKEN_EASINGS = new Set(
  [
    SMOOTH_OUT,
    "ease-in-out",
    "ease-out",
    "linear",
    "cubic-bezier(0.34, 1.36, 0.64, 1)", // bouncy overshoot (badge pop)
    "cubic-bezier(0.34, 3.85, 0.64, 1)", // strong bouncy overshoot (avatar return)
  ].map(normEase)
);

function normEase(s) {
  return String(s || "").replace(/\s+/g, "").toLowerCase();
}

function nearestDuration(ms) {
  let best = DURATION_TOKENS[0];
  let bestDelta = Infinity;
  for (const t of DURATION_TOKENS) {
    const d = Math.abs(t.ms - ms);
    if (d < bestDelta) {
      bestDelta = d;
      best = t;
    }
  }
  return { token: best, delta: bestDelta };
}

function nearestScale(v) {
  let best = SCALE_TOKENS[0];
  let bestDelta = Infinity;
  for (const t of SCALE_TOKENS) {
    const d = Math.abs(t.v - v);
    if (d < bestDelta) { bestDelta = d; best = t; }
  }
  return { token: best, delta: bestDelta };
}

function nearestBlur(px) {
  let best = BLUR_TOKENS[0];
  let bestDelta = Infinity;
  for (const t of BLUR_TOKENS) {
    const d = Math.abs(t.px - px);
    if (d < bestDelta) { bestDelta = d; best = t; }
  }
  return { token: best, delta: bestDelta };
}

function nearestDistance(px) {
  let best = DISTANCE_TOKENS[0];
  let bestDelta = Infinity;
  for (const t of DISTANCE_TOKENS) {
    const d = Math.abs(t.px - px);
    if (d < bestDelta) { bestDelta = d; best = t; }
  }
  return { token: best, delta: bestDelta };
}

const norm = (s) => String(s || "").toLowerCase();

// Usage-aware token pick — the skill says "match on USAGE, not the nearest
// number". Even deterministic should honour this when the label/selector/phase
// reveal the component, so a dropdown's 0.8 pre-scale snaps to 0.97 (dropdown
// open), not to 0.96 (the nearest number). Returns null when usage is unclear,
// and the caller falls back to nearest-by-magnitude.
function pickScaleByUsage(hint) {
  const h = norm(hint);
  if (!h) return null;
  const isClose = /clos/.test(h);
  if (/\bmodal\b|\bdialog\b|\blightbox\b/.test(h)) return SCALE_TOKENS.find((t) => t.v === 0.96);
  if (/\btooltip\b|\btip\b|\bpopover\b/.test(h)) return SCALE_TOKENS.find((t) => t.v === 0.98);
  if (/\bdropdown\b|drop-down|\bmenu\b|\bselect\b|\bcombobox\b|\bcaret\b/.test(h))
    return SCALE_TOKENS.find((t) => t.v === (isClose ? 0.99 : 0.97));
  return null;
}

function pickBlurByUsage(hint) {
  const h = norm(hint);
  if (!h) return null;
  if (/success|check/.test(h)) return BLUR_TOKENS.find((t) => t.px === 8);
  if (/\bpage\b|\bslide\b/.test(h)) return BLUR_TOKENS.find((t) => t.px === 3);
  if (/text/.test(h) && /reveal/.test(h)) return BLUR_TOKENS.find((t) => t.px === 3);
  if (/panel|icon|swap|skeleton|number|digit|reveal/.test(h)) return BLUR_TOKENS.find((t) => t.px === 2);
  return null;
}

function pickDistanceByUsage(hint) {
  const h = norm(hint);
  if (!h) return null;
  // Order matters: more specific usages first so a "text reveal" beats "text swap".
  if (/success|check|badge.*appear|appear.*badge/.test(h)) return DISTANCE_TOKENS.find((t) => t.px === 30);
  if (/text/.test(h) && /reveal/.test(h)) return DISTANCE_TOKENS.find((t) => t.px === 12);
  if (/\bpage\b|\bslide\b|\bbadge\b|\bnotification\b/.test(h)) return DISTANCE_TOKENS.find((t) => t.px === 8);
  if (/shake|error|invalid/.test(h)) return DISTANCE_TOKENS.find((t) => t.px === 6);
  if (/text/.test(h) && /swap/.test(h)) return DISTANCE_TOKENS.find((t) => t.px === 4);
  return null;
}

// A generic/non-token easing the skill would nudge toward the default ease-out.
function shouldRefineEasing(easing) {
  const n = normEase(easing);
  if (!n) return false;
  if (TOKEN_EASINGS.has(n)) return false;
  // "ease", "ease-in", or any hand-rolled cubic-bezier that isn't a token.
  return n === "ease" || n === "ease-in" || n.startsWith("cubic-bezier") || n.startsWith("linear(");
}

/**
 * Produce token-alignment suggestions for a list of property timings.
 * @param {{property:string,durationMs:number,delayMs:number,easing:string,scale?:number,blur?:number,translate?:number,varName?:string,translateVarName?:string,hint?:string}[]} timings
 * @param {{label?:string,selector?:string,phase?:string}} [ctx] usage hints for scale/blur token selection
 * @returns {object[]} suggestions
 */
export function refineTimings(timings, ctx) {
  const suggestions = [];
  if (!Array.isArray(timings)) return suggestions;
  const c = ctx || {};
  const blurByMember = new Map(); // memberKey -> {member,hint,sawBlur,varName}

  for (const t of timings) {
    const prop = t.property || "all";
    // Usage hint for scale/blur: combine the transition's label/selector/phase
    // with this lane's own property/member so component words (dropdown, modal,
    // page slide…) are visible to the usage matcher.
    const hint = [c.label, c.selector, c.phase, t.hint, t.property, t.member].filter(Boolean).join(" ");
    const memberKey = t.member || "__all__";
    if (!blurByMember.has(memberKey)) {
      blurByMember.set(memberKey, { member: t.member || null, hint, sawBlur: false, varName: null });
    }
    const bm = blurByMember.get(memberKey);
    bm.hint = [bm.hint, hint].filter(Boolean).join(" ");
    if (t.varName && (!bm.varName || prop === "filter")) bm.varName = t.varName;

    // Duration → nearest token (skip if already on-grid or within 10ms).
    if (Number.isFinite(t.durationMs)) {
      const { token, delta } = nearestDuration(t.durationMs);
      if (delta > 10) {
        suggestions.push({
          id: `${prop}-duration`,
          kind: "duration",
          property: prop,
          member: t.member || null,
          title: `Duration → ${token.name}`,
          from: `${t.durationMs}ms`,
          to: `${token.ms}ms`,
          patch: { property: prop, durationMs: token.ms, ...(t.member ? { member: t.member } : {}) },
          reason: `${token.name} (${token.ms}ms) is the closest motion token — used for ${token.usage}. ${t.durationMs}ms is off-grid.`,
        });
      }
    }

    // Easing → the transitions.dev default ease-out.
    if (shouldRefineEasing(t.easing)) {
      suggestions.push({
        id: `${prop}-easing`,
        kind: "easing",
        property: prop,
        member: t.member || null,
        title: `Easing → Smooth ease out`,
        from: t.easing,
        to: SMOOTH_OUT,
        patch: { property: prop, easing: SMOOTH_OUT, ...(t.member ? { member: t.member } : {}) },
        reason: `"${t.easing}" is a generic curve. The transitions.dev standard ease-out reads more intentional on opens, closes, slides, and resizes.`,
      });
    }

    // Scale → a transitions.dev scale token (usage-first, nearest fallback). The
    // captured value is the non-resting "pre" scale (settles to 1); skip 1/none.
    if (Number.isFinite(t.scale) && Math.abs(t.scale - 1) > 1e-4) {
      const usage = pickScaleByUsage(hint);
      const { token: near, delta } = nearestScale(t.scale);
      const token = usage || near;
      // Suggest when usage names a token, or the current value is off-grid.
      if (token && (usage || delta > 5e-3) && Math.abs(token.v - t.scale) > 1e-4) {
        suggestions.push({
          id: `${prop}-scale`,
          kind: "scale",
          property: prop,
          member: t.member || null,
          title: `Scale → ${token.name}`,
          from: String(t.scale),
          to: String(token.v),
          patch: { property: prop, scale: token.v, ...(t.varName ? { varName: t.varName } : {}), ...(t.member ? { member: t.member } : {}) },
          reason: `${token.name} (${token.v}) is the transitions.dev scale token for ${token.usage}. ${t.scale} is ${usage ? "off the usage token" : "off-grid"}.`,
        });
      }
    }

    // Blur → a transitions.dev blur token (usage-first, nearest fallback). The
    // captured value is the non-resting "pre" blur (settles to 0); skip 0/none.
    if (Number.isFinite(t.blur) && t.blur > 1e-4) {
      bm.sawBlur = true;
      const usage = pickBlurByUsage(hint);
      const { token: near, delta } = nearestBlur(t.blur);
      const token = usage || near;
      if (token && (usage || delta > 0.5) && Math.abs(token.px - t.blur) > 1e-4) {
        suggestions.push({
          id: `${prop}-blur`,
          kind: "blur",
          property: prop,
          member: t.member || null,
          title: `Blur → ${token.name}`,
          from: `${t.blur}px`,
          to: `${token.px}px`,
          patch: { property: prop, blur: token.px, ...(t.varName ? { varName: t.varName } : {}), ...(t.member ? { member: t.member } : {}) },
          reason: `${token.name} (${token.px}px) is the transitions.dev blur token for ${token.usage}. ${t.blur}px is ${usage ? "off the usage token" : "off-grid"}.`,
        });
      }
    }

    // Translate distance → a transitions.dev distance token (usage-first,
    // nearest fallback). The captured value is the non-resting "pre" translate
    // (settles to 0); skip 0/none. This is the transitions-polish dimension the
    // engine previously didn't check.
    if (Number.isFinite(t.translate) && Math.abs(t.translate) > 1e-4) {
      const dist = Math.abs(t.translate);
      const usage = pickDistanceByUsage(hint);
      const { token: near, delta } = nearestDistance(dist);
      const token = usage || near;
      if (token && (usage || delta > 1) && Math.abs(token.px - dist) > 1e-4) {
        suggestions.push({
          id: `${prop}-distance`,
          kind: "distance",
          property: prop,
          member: t.member || null,
          title: `Distance → ${token.name}`,
          from: `${dist}px`,
          to: `${token.px}px`,
          patch: { property: prop, translate: token.px, ...(t.translateVarName ? { translateVarName: t.translateVarName } : {}), ...(t.member ? { member: t.member } : {}) },
          reason: `${token.name} (${token.px}px) is the transitions.dev distance token for ${token.usage}. ${dist}px is ${usage ? "off the usage token" : "off-grid"}.`,
        });
      }
    }
  }

  // Missing-blur detection: when usage clearly maps to a blur token but no blur
  // lane is present, suggest adding one so the motion isn't opacity-only.
  for (const [memberKey, info] of blurByMember) {
    if (info.sawBlur) continue;
    const token = pickBlurByUsage(info.hint);
    if (!token) continue;
    const member = info.member;
    suggestions.push({
      id: `${memberKey}-blur-add`,
      kind: "blur",
      property: "filter",
      member,
      title: `Blur → ${token.name}`,
      from: "0px",
      to: `${token.px}px`,
      patch: {
        property: "filter",
        blur: token.px,
        ...(info.varName ? { varName: info.varName } : {}),
        ...(member ? { member } : {}),
      },
      reason: `${token.name} (${token.px}px) is the transitions.dev blur token for ${token.usage}. This transition currently has no blur.`,
    });
  }

  return suggestions;
}
