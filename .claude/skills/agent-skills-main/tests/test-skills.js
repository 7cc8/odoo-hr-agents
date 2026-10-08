#!/usr/bin/env node
/**
 * Structural validation for the agent-skills repo.
 *
 * Checks:
 *   1. Every skills/* and agents/* folder has a SKILL.md with
 *      valid `name` and `description` in its YAML frontmatter.
 *   2. Every component path listed in .claude-plugin/plugin.json exists.
 *   3. package.json version has a matching section in CHANGELOG.md
 *      (skipped if the version is still 0.x or under [Unreleased]).
 *
 * Exit code 0 on success, 1 on any failure.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const RED = "\x1b[31m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const RESET = "\x1b[0m";

const errors = [];
const warnings = [];

function fail(msg) {
  errors.push(msg);
  console.log(`${RED}✗${RESET} ${msg}`);
}

function warn(msg) {
  warnings.push(msg);
  console.log(`${YELLOW}!${RESET} ${msg}`);
}

function ok(msg) {
  console.log(`${GREEN}✓${RESET} ${msg}`);
}

function readFrontmatter(filePath) {
  const text = fs.readFileSync(filePath, "utf8");
  if (!text.startsWith("---")) return null;
  const end = text.indexOf("\n---", 3);
  if (end === -1) return null;
  const body = text.slice(3, end).replace(/^\r?\n/, "");
  const fields = {};
  for (const line of body.split(/\r?\n/)) {
    const m = /^([A-Za-z0-9_-]+)\s*:\s*(.*)$/.exec(line);
    if (m) fields[m[1]] = m[2].trim();
  }
  return fields;
}

function validateSkillDir(dir, label) {
  const entries = fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isDirectory());

  if (entries.length === 0) {
    warn(`${label}/ is empty`);
    return;
  }

  for (const entry of entries) {
    const skillPath = path.join(dir, entry.name, "SKILL.md");
    const rel = path.relative(ROOT, skillPath);
    if (!fs.existsSync(skillPath)) {
      fail(`missing ${rel}`);
      continue;
    }
    const fm = readFrontmatter(skillPath);
    if (!fm) {
      fail(`${rel}: no YAML frontmatter`);
      continue;
    }
    if (!fm.name) fail(`${rel}: frontmatter missing 'name'`);
    if (!fm.description) fail(`${rel}: frontmatter missing 'description'`);
    if (fm.name && fm.description) ok(rel);
  }
}

function validatePluginManifest() {
  const manifestPath = path.join(ROOT, ".claude-plugin", "plugin.json");
  if (!fs.existsSync(manifestPath)) {
    warn(".claude-plugin/plugin.json not found — skipping manifest check");
    return;
  }
  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  } catch (err) {
    fail(`plugin.json: invalid JSON (${err.message})`);
    return;
  }

  const components = manifest.components || {};
  for (const [kind, list] of Object.entries(components)) {
    if (!Array.isArray(list)) continue;
    for (const relPath of list) {
      const abs = path.join(ROOT, relPath);
      if (!fs.existsSync(abs)) {
        fail(`plugin.json: ${kind} path does not exist: ${relPath}`);
      } else {
        ok(`plugin.json/${kind}: ${relPath}`);
      }
    }
  }
}

function validateChangelog() {
  const pkgPath = path.join(ROOT, "package.json");
  const changelogPath = path.join(ROOT, "CHANGELOG.md");
  if (!fs.existsSync(pkgPath) || !fs.existsSync(changelogPath)) return;

  const version = JSON.parse(fs.readFileSync(pkgPath, "utf8")).version;
  if (!version) return;

  const changelog = fs.readFileSync(changelogPath, "utf8");
  const re = new RegExp(
    `^##\\s+\\[?v?${version.replace(/\./g, "\\.")}\\]?\\s*$`,
    "m"
  );
  if (re.test(changelog)) {
    ok(`CHANGELOG.md has section for v${version}`);
  } else {
    fail(
      `CHANGELOG.md: missing section for v${version} (expected '## [${version}]')`
    );
  }
}

function main() {
  console.log("Validating skills/");
  validateSkillDir(path.join(ROOT, "skills"), "skills");

  console.log("\nValidating agents/");
  validateSkillDir(path.join(ROOT, "agents"), "agents");

  console.log("\nValidating plugin manifest");
  validatePluginManifest();

  console.log("\nValidating CHANGELOG");
  validateChangelog();

  console.log("");
  if (errors.length > 0) {
    console.log(`${RED}${errors.length} error(s)${RESET}`);
    process.exit(1);
  }
  if (warnings.length > 0) {
    console.log(`${YELLOW}${warnings.length} warning(s)${RESET}`);
  }
  console.log(`${GREEN}All checks passed.${RESET}`);
}

main();
