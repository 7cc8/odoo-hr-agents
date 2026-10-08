#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const root = process.cwd();
const packagePath = path.join(root, "package.json");
const changelogPath = path.join(root, "CHANGELOG.md");
const isDryRun = process.argv.includes("--dry-run");

function fail(message) {
  console.error(`Error: ${message}`);
  process.exit(1);
}

function bumpVersion(version, bumpType) {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(version);
  if (!match) fail(`Invalid semver version in package.json: ${version}`);

  let major = Number(match[1]);
  let minor = Number(match[2]);
  let patch = Number(match[3]);

  if (bumpType === "major") {
    major += 1;
    minor = 0;
    patch = 0;
  } else if (bumpType === "minor") {
    minor += 1;
    patch = 0;
  } else {
    patch += 1;
  }

  return `${major}.${minor}.${patch}`;
}

function detectBumpType(unreleasedSection) {
  const lower = unreleasedSection.toLowerCase();
  if (/\n###\s+breaking\b/.test(lower) || /\n###\s+breakings\b/.test(lower)) {
    return "major";
  }
  if (/\n###\s+added\b/.test(lower)) {
    return "minor";
  }
  if (/\n###\s+(changed|fixed)\b/.test(lower)) {
    return "patch";
  }
  return null;
}

function hasRealChanges(unreleasedSection) {
  const lines = unreleasedSection
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  return lines.some(
    (line) =>
      line.startsWith("- ") &&
      !/^-\s*todo\b/i.test(line) &&
      !/^-\s*tbd\b/i.test(line)
  );
}

if (!fs.existsSync(packagePath)) fail("package.json not found.");
if (!fs.existsSync(changelogPath)) fail("CHANGELOG.md not found.");

const pkg = JSON.parse(fs.readFileSync(packagePath, "utf8"));
const changelog = fs.readFileSync(changelogPath, "utf8");

const unreleasedHeaderRegex = /^##\s+\[?Unreleased\]?\s*$/m;
const unreleasedHeaderMatch = unreleasedHeaderRegex.exec(changelog);
if (!unreleasedHeaderMatch) {
  fail("Cannot find '## [Unreleased]' section in CHANGELOG.md.");
}

const unreleasedStart = unreleasedHeaderMatch.index + unreleasedHeaderMatch[0].length;
const afterUnreleased = changelog.slice(unreleasedStart);
const nextVersionHeaderMatch = /\n##\s+/.exec(afterUnreleased);
const unreleasedEnd =
  nextVersionHeaderMatch === null
    ? changelog.length
    : unreleasedStart + nextVersionHeaderMatch.index + 1;

const unreleasedBody = changelog.slice(unreleasedStart, unreleasedEnd).trim();
if (!unreleasedBody) {
  fail("Unreleased section is empty. Add release notes before bumping.");
}
if (!hasRealChanges(unreleasedBody)) {
  fail("Unreleased section only contains TODO/TBD placeholders.");
}

const bumpType = detectBumpType(`\n${unreleasedBody}\n`);
if (!bumpType) {
  fail("Cannot infer bump type. Add a heading: ### Breaking, ### Added, ### Changed, or ### Fixed.");
}

const currentVersion = pkg.version;
const nextVersion = bumpVersion(currentVersion, bumpType);

const newReleaseSection = `## [${nextVersion}]\n\n${unreleasedBody}\n\n`;
const newUnreleasedSection = "## [Unreleased]\n\n### Changed\n- TODO: Add upcoming changes here.\n\n";

const changelogBeforeUnreleased = changelog.slice(0, unreleasedHeaderMatch.index);
const changelogAfterUnreleased = changelog.slice(unreleasedEnd);
const nextChangelog =
  changelogBeforeUnreleased +
  newUnreleasedSection +
  newReleaseSection +
  changelogAfterUnreleased.replace(/^\n+/, "");

if (isDryRun) {
  console.log(`Current version: ${currentVersion}`);
  console.log(`Bump type: ${bumpType}`);
  console.log(`Next version: ${nextVersion}`);
  process.exit(0);
}

pkg.version = nextVersion;
fs.writeFileSync(packagePath, `${JSON.stringify(pkg, null, 2)}\n`, "utf8");
fs.writeFileSync(changelogPath, nextChangelog, "utf8");

console.log(`Bumped version ${currentVersion} -> ${nextVersion} (${bumpType}).`);
console.log("Updated package.json and CHANGELOG.md.");
