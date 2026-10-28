// Builder page, "Real patterns, not guesses": a Community component (Event
// Card With Attendees) generates in the card, over and over, with the
// transitions-ui-generation skill's runtime (assets/ui-generation). The
// drawing is quieter than the skill's default (builder.html, .t-gen.is-quiet)
// and stays inside the card. It only runs while the card is on screen, and
// not at all with reduced motion: the component simply sits there. The
// component is the real one, so it can be used, and the loop waits while it is.
import { generate } from "../ui-generation/ui-generation.js?v=5";

const card = document.querySelector("[data-ub-generate]");
const stage = card && card.querySelector(".ub-gen");

// The component in its own shadow root, so its styles and class names never
// meet the page's. Its :root tokens and dark rules move to the host, and its
// script gets a document scoped to that root (as in the skill's demo).
function mount(c) {
  const host = document.createElement("div");
  host.className = "ub-gen-host";
  const theme = () => { host.dataset.theme = document.documentElement.dataset.theme === "dark" ? "dark" : "light"; };
  theme();
  host.__themeWatch = new MutationObserver(theme);
  host.__themeWatch.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  const root = host.attachShadow({ mode: "open" });
  const css = c.css
    .replace(/html\[data-theme="dark"\]\s*\{/g, ':host([data-theme="dark"]) {')
    .replace(/html\[data-theme="dark"\]\s+/g, ':host([data-theme="dark"]) ')
    .replace(/:root\b/g, ":host");
  root.innerHTML = `<style>${css}</style>${c.html}`;
  // on the page before its script runs (it reads its tokens and sizes); a
  // later mount replaces the used card
  const old = stage.querySelector(".ub-gen-host");
  if (old) { if (old.__themeWatch) old.__themeWatch.disconnect(); old.replaceWith(host); } else stage.append(host);
  const scoped = new Proxy(document, {
    get(target, prop) {
      if (prop === "querySelector" || prop === "querySelectorAll") return (...a) => root[prop](...a);
      if (prop === "getElementById") return (id) => root.querySelector("#" + CSS.escape(id));
      if (prop === "documentElement" || prop === "body") return host;
      const v = Reflect.get(target, prop);
      return typeof v === "function" ? v.bind(target) : v;
    },
  });
  try { new Function("document", c.js)(scoped); } catch (e) { console.warn("ub-generate", e); }
  return [...root.children].find((n) => n.tagName !== "STYLE");
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let onScreen = false, wake = null;
const awake = () => new Promise((r) => { if (onScreen && !document.hidden) r(); else wake = r; });
const nudge = () => { if (wake && onScreen && !document.hidden) { const w = wake; wake = null; w(); } };

// The drawing sits on the page over the component; keep it inside the card.
function quiet(el) {
  const layer = el.__tGenLayer;
  if (!layer || layer.classList.contains("is-quiet")) return;
  layer.classList.add("is-quiet");
  const c = card.getBoundingClientRect(), l = layer.getBoundingClientRect();
  // Negative insets reach past the layer's own box (its drawing overflows it)
  // out to the card's edges, and the card's rounded corners.
  layer.style.clipPath = `inset(${c.top - l.top}px ${l.right - c.right}px ${l.bottom - c.bottom}px ${c.left - l.left}px round 24px)`;
}

// The card is live: while someone hovers or uses it (and for a while after a
// tap or a key), no new build starts under them. A card that was used (an
// attendee list left open) is put back to its first state before the next
// build, so every build draws the same card.
let busyUntil = 0, hovered = false, used = false;
const idle = async () => { while (hovered || Date.now() < busyUntil) await wait(400); };

function watch(el) {
  const host = el.getRootNode().host;
  host.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse") hovered = true; });
  host.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") { hovered = false; busyUntil = Date.now() + 1500; } });
  ["pointerdown", "keydown", "focusin"].forEach((t) => host.addEventListener(t, () => { used = true; busyUntil = Date.now() + 6000; }));
}

let el = null;
async function loop(c) {
  for (;;) {
    await awake();
    await idle();
    await awake();
    if (used) {
      el = mount(c);
      watch(el);
      used = false;
    }
    const run = generate(el, { mode: "skeleton", duration: 2800 });
    // the overlay is built a frame or two later (el.__tGenLayer still holds
    // the last run's, already removed); style it as soon as it is on the page
    for (let i = 0; i < 30 && !(el.__tGenLayer && el.__tGenLayer.isConnected); i++) await new Promise((r) => requestAnimationFrame(r));
    if (el.__tGenLayer && el.__tGenLayer.isConnected) quiet(el);
    await run.finished;
    await wait(2600); // the real component rests before the next build
  }
}

async function start() {
  if (!stage) return;
  const c = await fetch("assets/community/ub-event-card.json?v=1").then((r) => r.json()).catch(() => null);
  if (!c) return;
  el = mount(c);
  if (!el || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  watch(el);
  new IntersectionObserver((entries) => {
    onScreen = entries.some((e) => e.isIntersecting);
    if (!onScreen) { if (el.__tGen) el.__tGen.cancel(); } else nudge();
  }, { threshold: 0.35 }).observe(card);
  document.addEventListener("visibilitychange", () => { if (document.hidden && el.__tGen) el.__tGen.cancel(); else nudge(); });
  await document.fonts.ready;
  await Promise.all([...el.querySelectorAll("img")].map((i) => (i.complete ? null : new Promise((r) => { i.onload = i.onerror = r; }))));
  loop(c);
}
start();
