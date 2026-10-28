# transitions-refine

A live, agent-driven **Refine** panel for CSS and [Motion](https://motion.dev) transitions. One command injects a docked timeline + Refine panel onto your running app — no `npm install`, no source edits of your own — and every "Refine" click asks a coding agent to review the selected transition against the [transitions.dev](https://transitions.dev) motion tokens and suggest token-aligned values (or a whole-transition replacement from the library).

The feedback shows up **in a panel that slides in from the right** — not in your chat — and you pick which suggestions to apply. Applied suggestions are **live overrides** (instant preview, reversible) — the same path as dragging the timeline bars. When you're happy, **Accept** writes those values back into your source via the agent.

There's **no play button or scrubber** — the running component *is* the preview. Any edit (a dragged bar, an inspector tweak, or an applied suggestion) is written straight onto the live element as an inline `transition`, so you see it the next time you trigger the transition (open the dropdown, hover the card, …). Reset reverts the element to its source.

Real components rarely live in one CSS rule. A dropdown has an **Open** and a **Close** phase, each animating several elements (panel, backdrop, staggered items) with different timings — and the close phase usually isn't even in the DOM while the panel is open. So when the panel opens it also asks the agent to **read your source and group** the page's transitions into components → phases → member elements. You then pick a whole phase (e.g. *Dropdown · Open*) and see every sub-transition as a labeled lane on one shared timeline. If no agent is live, the panel falls back to the flat DOM scan with no regression.

Inspired by the [impeccable.style](https://impeccable.style/live-mode/) "live" pattern: the browser drops a job in a tiny local relay, and the relay answers it with **one agent run per click**. No standing loop, nothing to start per click — you just keep the relay running.

```
[Refine click] → POST /jobs → relay ──one run──► answer
[right panel]  ← GET /jobs/:id ← relay ◄── suggestions
```

## Use it

```bash
# inject the panel + start the relay (deterministic suggestions work immediately)
npx transitions-refine live

# remove the injected <script> tag again
npx transitions-refine stop
```

`live` sets everything up with no install and no edits of your own:

1. injects one `<script type="module" src=".../inject.js">` into your page (it looks for `index.html`, `public/index.html`, … or pass `--page <path>`),
2. drops the `refine-live` + `transitions-dev` skills into `.agents/skills/` (so the agent makes token-aware picks),
3. **auto-wires an LLM backend** — it detects the agent hosting this run and points the relay at *its* CLI, so Refine uses the subscription you already have (Cursor → `cursor-agent`, Claude Code → `claude`, Codex → `codex`),
4. starts the local relay (which serves the panel at `/inject.js`).

Open your app — the panel is now on the page. Press Ctrl-C to stop the relay and remove the injected tag.

## LLM quality (recommended)

The default answerer snaps each value to the nearest motion token. For *usage-aware* picks (a 300 ms modal close → `Quick` 150 ms, a dropdown open → `Fast` 250 ms), back the panel with an LLM.

Plain `npx transitions-refine live` already does this when an agent CLI is available: it prefers the **host agent** so it bills your existing plan, persistently (no `/refine live` loop to keep alive). The CLI must be authenticated once — Cursor: run `cursor-agent` to log in (or set `CURSOR_API_KEY`); Claude Code: run `claude` to sign in; Codex: run `codex` to sign in (or set `CODEX_API_KEY`).

```bash
# auto: use whichever agent hosts this run (cursor-agent / claude / codex)
npx transitions-refine live

# force a specific agent regardless of host
npx transitions-refine live --agent claude   # cursor | claude | codex

# no agent on the machine? install the Cursor CLI as a fallback
npx transitions-refine live --llm
```

Resolution order: `REFINE_AGENT_CMD` (explicit) → `--agent <name>` → detected host agent → any installed agent → (with `--llm`) install cursor-agent. If none is available the panel falls back to the in-IDE loop — run `/refine live` in your editor to answer jobs yourself (works in Cursor, Claude Code, or Codex; stays live only while that session keeps polling).

You can also point the relay at any one-shot agent CLI via `REFINE_AGENT_CMD` (the relay feeds it the prompt on stdin and reads a JSON result from stdout):

```bash
REFINE_AGENT_CMD='cursor-agent -p --trust --force' npm run relay   # or: codex exec -  |  claude -p
```

For `cursor-agent` the relay auto-appends any missing `-p`/`--trust`/`--force`, so headless jobs never stall on the workspace-trust prompt (a bare `cursor-agent` goes interactive and exits 1). `-p` = headless/print mode (prompt on stdin), `--trust` = trust the workspace without prompting (only valid with `--print`), `--force` = auto-allow tool calls so apply/scan jobs don't hang on approval.

The CLI must have the `transitions-dev` skill available (the prompt tells it to read the skill).

## Grouped scan — Open / Close phases

When the panel opens it posts a **scan job** to the relay; the agent reads your source and returns the page's animated components, each split into phases (`open`, `close`, …) with their **member elements** and the *real* per-state timings — including the close transition the DOM can't show you. The picker then groups by component, you select a phase, and the timeline renders one lane per member-property (each lane labeled with its member) on a single time axis so stagger and delays line up. Editing any lane applies **live** as an inline `transition` on that member element, so triggering the component yourself (open/close it) previews the whole phase with your values; **Accept** writes back to the correct state rule (`.is-open` vs `.is-closing`) per member.

Grouping needs the agent (`/refine live`, `--llm`, or `REFINE_AGENT_CMD`); with no agent the panel just shows the flat DOM scan as before.

## Refine modes

- **Small refinements** — keeps the transition, suggests motion-token tweaks (duration/easing), and may add a whole-transition replacement when one clearly fits better.
- **Replace transition** — only whole-transition replacements from the transitions.dev library (no token tweaks). This path needs the agent; the deterministic answerer will tell you to switch to the LLM.

## Accept — write changes to your code

The **Accept** button (next to Refine) is enabled whenever the selected transition has unsaved changes — whether you edited the bars/easing by hand or applied a Refine suggestion. Pressing it sends an **apply job** to the relay: the agent finds where that transition is declared in your source (plain CSS, CSS Modules, styled-components/emotion, Tailwind, or inline styles), edits only the changed timings, and reports back. The button shows a spinner while saving and flips to **Done** on success.

Like Replace, Accept needs the agent — run `/refine live` (or `--llm` / `REFINE_AGENT_CMD`). The deterministic answerer can't edit files.

## Pieces

| Piece | File | Role |
|-------|------|------|
| CLI | `bin/cli.mjs` | inject the panel, drop skills, optionally install the Cursor CLI, start the relay |
| Relay (answers jobs) | `server/relay.mjs` | job queue + CORS + one-run-per-job dispatch; serves `/inject.js` |
| Injected UI | `server/inject.mjs` + `demo.html` | builds the browser module (timeline + Refine panel) with absolute esm.sh imports |
| Motion tokens | `server/motion-tokens.mjs` | token table + the nearest-token deterministic fallback |
| External poller (optional) | `server/refine-agent.mjs` | standing no-LLM poller for `REFINE_AUTO=0` mode |
| Skill (live agent) | `.agents/skills/refine-live/` | turns `/refine live` into the relay's answerer |

## Knobs

| Env / global | Default | Purpose |
|--------------|---------|---------|
| `REFINE_RELAY_PORT` | `7331` | relay port |
| `REFINE_AGENT_CMD` | — | one-shot LLM CLI the relay spawns per job |
| `REFINE_AGENT_TIMEOUT_MS` | `120000` | per-run timeout |
| `REFINE_SCAN_MODEL` | `composer-2.5-fast` | cursor-agent model for the initial group scan (`""` = agent default) |
| `REFINE_SCAN_EFFORT` | `low` | Codex reasoning effort for the scan — `minimal\|low\|medium\|high` (`""` = configured effort) |
| `REFINE_AUTO=0` | — | disable auto-answer and wait for an external poller |
| `window.REFINE_RELAY_URL` | injected origin | browser override for the relay URL |

Endpoints: `POST /jobs` (refine, `kind: "apply"`, or `kind: "scan"`), `GET /jobs/:id` (browser). In `REFINE_AUTO=0` mode an external poller also uses `GET /jobs/next` and `POST /jobs/:id/{status,result,error}` (the result body accepts `suggestions`, `groups`, or `applied`).

Refine suggestions stay as live overrides until you press **Accept**, which is the explicit step that writes them into your source.

## Terms & License

> Full terms: https://transitions.dev/terms.html

- **Beta software.** Refine is an early Beta. Features, commands, the panel, and
  its behavior may change, regress, or be removed at any time without notice. No
  guarantee of availability, stability, or fitness for any purpose.
- **Your agent credits.** Refine triggers *your own* AI coding agent (Cursor,
  Claude Code, Codex, …). Every Refine click and any `npx transitions-refine
  live` / `/refine live` session consumes *your* provider's tokens/credits —
  including while a live session sits idle and keeps polling. You are solely
  responsible for that spend; this project is not liable for and will not
  reimburse any credits, fees, or overages. Run `npx transitions-refine stop`
  (or say `stop refine`) when you're done.
- **The agent changes your code.** Accepting a suggestion writes changes into
  your source files. Suggestions are AI-generated and may be wrong. Use version
  control, review every change before committing, and keep backups. Use at your
  own risk.
- **No warranty.** The software is provided **"AS IS"**, without warranty of any
  kind. To the maximum extent permitted by law, the authors are not liable for
  any damages — direct, indirect, incidental, or consequential, including lost
  work or lost credits — arising from its use.

### MIT License

MIT — Copyright (c) 2026 Jakub Antalik / Transitions.dev. See
https://transitions.dev/terms.html for the full license text.
