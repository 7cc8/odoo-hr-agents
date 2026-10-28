// Builds a self-contained, self-mounting timeline module from the working demo.
//
// Instead of maintaining a second copy of the timeline UI, we transform the
// already-tested code inside demo.html into a single ES module that can be
// dropped onto ANY page via:
//
//     <script type="module" src="http://localhost:7331/inject.js"></script>
//
// The module imports React from absolute esm.sh URLs (so the host page does
// not need an import map), injects the timeline CSS, then mounts the panel
// into its own container while scanning document.body for CSS transitions.

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const DEMO_PATH = fileURLToPath(new URL("../demo.html", import.meta.url));
const PKG_PATH = fileURLToPath(new URL("../package.json", import.meta.url));

// Absolute module URLs so the injected script works without an import map.
const REACT_URL = "https://esm.sh/react@19";
const REACT_DOM_URL = "https://esm.sh/react-dom@19";
const REACT_DOM_CLIENT_URL = "https://esm.sh/react-dom@19/client";
// `deps=` (not `external=`) so esm.sh resolves border-beam's own react/react-dom
// to the same esm.sh/react@19 the panel uses — one React instance, no import map
// required on the host page.
const BORDER_BEAM_URL = "https://esm.sh/border-beam@1.2.0?deps=react@19,react-dom@19";

const CUT_MARKER = "// ── demo boxes ──";

function extractBetween(src, openRe, closeTag) {
  const open = src.match(openRe);
  if (!open) return null;
  const start = open.index + open[0].length;
  const end = src.indexOf(closeTag, start);
  if (end === -1) return null;
  return src.slice(start, end);
}

// Remove every /* @inject-skip-start */ … /* @inject-skip-end */ region.
function stripSkipRegions(css) {
  return css.replace(/\/\*\s*@inject-skip-start[\s\S]*?@inject-skip-end\s*\*\//g, "").trim();
}

function buildJs(scriptSrc, version) {
  let js = scriptSrc;
  // Drop everything from the demo-only boxes onward (App + createRoot render).
  const cut = js.indexOf(CUT_MARKER);
  if (cut !== -1) js = js.slice(0, cut);

  // Rewrite the demo's bare-specifier imports to absolute URLs.
  js = js
    .replace(/import\s+React\s+from\s+["']react["'];?/, `import React from "${REACT_URL}";`)
    .replace(/import\s+\{\s*createRoot\s*\}\s+from\s+["']react-dom\/client["'];?/, `import { createRoot } from "${REACT_DOM_CLIENT_URL}";`)
    .replace(/import\s+\{\s*createPortal\s*\}\s+from\s+["']react-dom["'];?/, `import { createPortal } from "${REACT_DOM_URL}";`)
    .replace(/import\s+\{\s*BorderBeam\s*\}\s+from\s+["']border-beam["'];?/, `import { BorderBeam } from "${BORDER_BEAM_URL}";`);

  // Point the relay client at whatever origin served this module, so the panel
  // works on any port the CLI chose (the script is served BY the relay).
  js = js.replace(
    /(import\s+\{\s*createPortal\s*\}\s+from\s+"[^"]+";)/,
    `$1\n    try { if (typeof window !== "undefined") { if (!window.REFINE_RELAY_URL) window.REFINE_RELAY_URL = new URL(import.meta.url).origin; window.__TX_REFINE_VERSION = ${JSON.stringify(version || "")}; } } catch (e) {}`
  );

  return js.trim();
}

function buildEpilogue(css) {
  // JSON.stringify handles all escaping for the embedded stylesheet.
  const cssLiteral = JSON.stringify(css);
  return `
// ── injected timeline mount ──
(function mountInjectedTimeline(){
  if (typeof document === "undefined") return;
  if (document.getElementById("tl-inject-root")) return; // idempotent

  if (!document.getElementById("tl-inject-style")) {
    const st = document.createElement("style");
    st.id = "tl-inject-style";
    // Scoped reset so panel layout is correct without touching the host page.
    st.textContent = "[data-timeline-panel],[data-timeline-panel] *,.tl-refine-panel,.tl-refine-panel *{box-sizing:border-box;}\\n" + ${cssLiteral};
    document.head.appendChild(st);
  }

  const mount = document.createElement("div");
  mount.id = "tl-inject-root";
  document.body.appendChild(mount);

  function InjectedRoot(){
    const registry = useMemo(() => new TransitionRegistry(), []);
    const [activeId, setActiveId] = useState(null);
    useEffect(() => {
      const scanner = new DomScanner(document.body, registry);
      scanner.start();
      return () => { scanner.stop(); };
    }, [registry]);
    const ctx = useMemo(() => ({ registry, activeId, setActiveId }), [registry, activeId]);
    return h(TimelineCtx.Provider, { value: ctx }, h(TimelinePanel));
  }

  createRoot(mount).render(h(InjectedRoot));
})();
`;
}

let _cache = null;
export async function buildInjectModule({ noCache = false } = {}) {
  if (_cache && !noCache) return _cache;
  const html = await readFile(DEMO_PATH, "utf8");

  const styleSrc = extractBetween(html, /<style>/, "</style>");
  const scriptSrc = extractBetween(html, /<script\s+type="module">/, "</script>");
  if (!styleSrc || !scriptSrc) {
    throw new Error("inject: could not locate <style> or module <script> in demo.html");
  }

  let version = "";
  try { version = JSON.parse(await readFile(PKG_PATH, "utf8")).version || ""; } catch (e) {}

  const css = stripSkipRegions(styleSrc);
  const js = buildJs(scriptSrc, version);
  _cache = `${js}\n${buildEpilogue(css)}`;
  return _cache;
}
