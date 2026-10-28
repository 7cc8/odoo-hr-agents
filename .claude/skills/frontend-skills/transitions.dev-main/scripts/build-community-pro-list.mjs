#!/usr/bin/env node
// Builds assets/community/library-pro.json: the Pro transitions on
// library.html by name only (slug, title, description, category). Their code
// is paid content and never leaves the API. The Studio's library picker shows
// them to free accounts, locked; scripts/build-community-thumbs.mjs captures
// their thumbnails.
//
//   node scripts/build-community-pro-list.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const page = readFileSync(join(root, "library.html"), "utf8");
const decode = (s) => s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&rsquo;/g, "’");

const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

// Every card in page order. A Pro card records the card before it ("after":
// a free card's slug as in library.json, or a Pro id), so the picker mixes
// them in where the library page shows them.
const pro = [];
let prev = null;
for (const m of page.matchAll(/<article class="card" data-proto-card[^>]*>/g)) {
  const end = page.indexOf("</article>", m.index);
  const art = page.slice(m.index, end < 0 ? m.index + 8000 : end);
  const title = decode((art.match(/class="card-title[^"]*">([^<]+)</) || [])[1] || "").trim();
  const id = /data-pro="true"/.test(m[0]) && (m[0].match(/data-pro-id="([^"]+)"/) || [])[1];
  if (!id) { if (title) prev = slug(title); continue; }
  pro.push({
    after: prev,
    slug: id,
    title: decode((art.match(/class="card-title[^"]*">([^<]+)</) || [])[1] || id).trim(),
    desc: decode((art.match(/class="card-subtitle[^"]*">([^<]+)</) || [])[1] || "").trim(),
    cat: (m[0].match(/data-cat="([^"]+)"/) || [])[1] || "essential",
  });
  prev = id;
}
writeFileSync(join(root, "assets/community/library-pro.json"), JSON.stringify(pro, null, 0) + "\n");
console.log("wrote", pro.length, "Pro transitions to assets/community/library-pro.json");
