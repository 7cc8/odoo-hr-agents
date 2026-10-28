// Optional external poller — only for REFINE_AUTO=0 mode.
//
// By default the relay answers each job itself with one run (see
// server/relay.mjs), so you don't need this. It exists for the advanced setup
// where you start the relay with REFINE_AUTO=0 and want a separate standing
// process to claim jobs via GET /jobs/next. This implementation is the
// deterministic, no-LLM one (snaps to the nearest motion token).
//
// Run: REFINE_AUTO=0 npm run relay   (in one terminal)
//      npm run refine-poller          (in another)
// Don't run it while the relay is in the default auto mode — jobs are already
// answered, so it would never receive any.

import { refineTimings } from "./motion-tokens.mjs";

const RELAY = process.env.REFINE_RELAY_URL || "http://localhost:7331";
const IDLE_MS = 800; // poll cadence when there's no work
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function post(path, body) {
  await fetch(`${RELAY}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function handle(job) {
  const { id, request } = job;
  const label = request?.label || request?.selector || "transition";
  console.log(`\n▸ job ${id.slice(0, 8)} — ${label}`);

  await post(`/jobs/${id}/status`, { message: `Scanning "${label}"…` });
  await sleep(500);
  await post(`/jobs/${id}/status`, { message: "Matching values to the motion tokens…" });
  await sleep(600);

  const suggestions = refineTimings(request?.timings || []);

  await post(`/jobs/${id}/status`, {
    message: suggestions.length
      ? `Found ${suggestions.length} refinement${suggestions.length === 1 ? "" : "s"}.`
      : "Already aligned to the motion tokens.",
  });
  await post(`/jobs/${id}/result`, {
    suggestions,
    summary: suggestions.length
      ? `${suggestions.length} value${suggestions.length === 1 ? "" : "s"} differ from the transitions.dev tokens.`
      : "Nothing to refine — values already match the tokens.",
  });
  console.log(`  ✓ posted ${suggestions.length} suggestion(s)`);
}

async function loop() {
  console.log(`refine agent polling ${RELAY}/jobs/next …`);
  // eslint-disable-next-line no-constant-condition
  while (true) {
    let res;
    try {
      res = await fetch(`${RELAY}/jobs/next`);
    } catch {
      console.log("  (relay not reachable — retrying)");
      await sleep(1500);
      continue;
    }
    if (res.status === 204) {
      await sleep(IDLE_MS);
      continue;
    }
    if (!res.ok) {
      await sleep(IDLE_MS);
      continue;
    }
    const job = await res.json();
    try {
      await handle(job);
    } catch (e) {
      console.error("  ✗ job failed:", e.message);
      try {
        await post(`/jobs/${job.id}/error`, { message: String(e.message || e) });
      } catch {}
    }
  }
}

loop();
