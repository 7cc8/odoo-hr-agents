#!/usr/bin/env node
// Captures a static thumbnail of every remixable library transition for the
// Studio's library picker: the card stage as it looks on the home page, in
// light and dark. Writes assets/community/thumbs/<slug>.jpg and
// <slug>-dark.jpg at 2x (592 x 520) for sharp retina screens. The demo's own
// controls (Animate, Toggle, Play) are hidden: the picker shows the component.
// The Pro transitions get thumbnails too (assets/community/library-pro.json).
//
// Needs the site served locally and playwright-core with a Chrome install:
//   python3 -m http.server 8123          (in the repo root, another terminal)
//   npm i --no-save playwright-core
//   node scripts/build-community-thumbs.mjs
// SITE=<origin> and CHROME=<path to a Chrome binary> override the defaults.

import { mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const SITE = process.env.SITE || "http://localhost:8123";
const CHROME = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const out = join(root, "assets/community/thumbs");
mkdirSync(out, { recursive: true });

// The free transitions by their copy key, the Pro ones (locked in the
// picker for free accounts) by their Pro id. ONLY=pro captures just those.
const free = JSON.parse(readFileSync(join(root, "assets/community/library.json"), "utf8"))
  .map((t) => ({ slug: t.slug, sel: `.card:has([data-copy-key="${t.key}"]) .card-stage` }));
const pro = JSON.parse(readFileSync(join(root, "assets/community/library-pro.json"), "utf8"))
  .map((t) => ({ slug: t.slug, sel: `.card[data-pro-id="${t.slug}"] .card-stage`, pro: true }));
// ms after pressing the demo's own button, for demos that only show
// something while they play.
const PLAY = { "confetti-burst": 420, "organic-shimmer": 900 };
const only = process.env.ONLY ? process.env.ONLY.split(",") : null; // "pro", or slugs
const items = !only ? free.concat(pro) : only[0] === "pro" ? pro : free.concat(pro).filter((t) => only.includes(t.slug));
const browser = await chromium.launch({ executablePath: CHROME, headless: true });

for (const theme of ["light", "dark"]) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 }, deviceScaleFactor: 2, colorScheme: theme });
  await ctx.addInitScript((t) => { try { localStorage.setItem("tdev:theme", t); } catch (e) {} }, theme);
  const page = await ctx.newPage();
  await page.goto(SITE + "/library.html", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  // The Pro badge is left out: the picker puts the real one on the thumbnail.
  await page.addStyleTag({ content: ".card-stage:not(.thumb-keep) .btn-animate { visibility: hidden !important; } .card-pro-badge { display: none !important; }" });
  await page.mouse.move(2, 2);
  let n = 0;
  for (const t of items) {
    const stage = page.locator(t.sel).first();
    if (!(await stage.count())) { console.warn("no card for", t.slug); continue; }
    await stage.scrollIntoViewIfNeeded();
    await page.mouse.move(2, 2);
    // A Pro demo's button can be the component itself (Confetti burst), and
    // some draw a beat later (Organic shimmer): show its buttons, wait longer.
    await page.evaluate(([sel, on]) => { const el = document.querySelector(sel); if (el) el.classList.toggle("thumb-keep", on); }, [t.sel, !!t.pro]);
    await page.waitForTimeout(t.pro ? 2000 : 500);
    // Demos that rest as a bare button or an empty box are caught mid-play.
    const play = PLAY[t.slug];
    if (play) { await stage.locator(".btn-animate").first().click(); await page.mouse.move(2, 2); await page.waitForTimeout(play); }
    await stage.screenshot({ path: join(out, t.slug + (theme === "dark" ? "-dark" : "") + ".jpg"), type: "jpeg", quality: 90 });
    n++;
  }
  console.log(theme, n, "thumbnails");
  await ctx.close();
}
await browser.close();
