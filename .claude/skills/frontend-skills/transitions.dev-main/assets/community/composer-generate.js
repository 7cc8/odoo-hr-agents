// The homepage prompt box arrives with the
// transitions-ui-generation skill's skeleton: drawn as a dotted wireframe,
// then revealed with a cross-blur fade (no scan line). Once per load. The
// drawing runs its full 1.6s; the box starts fading in over it at 0.93s,
// about a quarter second before the drawing ends. Any click or key cancels it
// at once, so the box is never in the way of typing.
// The page hides the box before its first paint (html.cm-gen-pending, set in
// <head> unless the visitor prefers reduced motion), so it never shows and
// then vanishes for the drawing.
import { generate } from "../ui-generation/ui-generation.js?v=5";

const root = document.documentElement;
const box = document.getElementById("cm-beam");
if (box && root.classList.contains("cm-gen-pending")) {
  (async () => {
    // Text lines are measured from the fonts; wait for them, briefly.
    if (document.fonts && document.fonts.ready) await Promise.race([document.fonts.ready, new Promise((r) => setTimeout(r, 600))]);
    box.__tGenOpacity = ""; // restored to this at the reveal
    const run = generate(box, { mode: "skeleton", duration: 1600, reveal: "fade", fadeDuration: 475, revealAt: 930 });
    root.classList.remove("cm-gen-pending"); // the runtime holds it hidden now
    const off = () => ["pointerdown", "keydown", "focusin"].forEach((t) => document.removeEventListener(t, stop, true));
    const stop = () => { run.cancel(); off(); };
    ["pointerdown", "keydown", "focusin"].forEach((t) => document.addEventListener(t, stop, true));
    run.finished.then(off);
  })();
} else root.classList.remove("cm-gen-pending");
