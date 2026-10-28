#!/usr/bin/env node
// Generate refine/.agents/skills/<skill> from the repo's canonical skills
// (../../skills/<skill>) so the published tarball is self-contained. Runs
// automatically via `prepack`; the generated copies are gitignored to avoid
// keeping two copies in version control.

import { cpSync, existsSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const PKG_ROOT = fileURLToPath(new URL("..", import.meta.url));
const REPO_ROOT = dirname(PKG_ROOT);

// Canonical skills shipped inside the refine tarball. transitions-dev supplies
// the recipes + motion tokens; transitions-polish is the optional add-on whose
// _refine-rules.md the relay inlines into Small refinements when installed.
const SKILLS = ["transitions-dev", "transitions-polish"];

let synced = 0;
for (const skill of SKILLS) {
  const src = join(REPO_ROOT, "skills", skill);
  const dest = join(PKG_ROOT, ".agents", "skills", skill);
  if (!existsSync(src)) {
    console.error(`! canonical skill not found at ${src}`);
    console.error("  (run this from within the transitions.dev repo)");
    process.exit(1);
  }
  rmSync(dest, { recursive: true, force: true });
  cpSync(src, dest, { recursive: true });
  console.log(`✓ synced ${skill} skill → ${dest.replace(PKG_ROOT, "refine")}`);
  synced++;
}

if (!synced) {
  console.error("! no skills synced");
  process.exit(1);
}
