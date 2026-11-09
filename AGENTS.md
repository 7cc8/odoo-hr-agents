<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **odoo-hr-agents** (8787 symbols, 17499 relationships, 485 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact before editing.** Use `impact({target: "symbolName", direction: "upstream"})` or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .`; report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- MUST warn on HIGH/CRITICAL `risk` pre-edit; never use `riskSharedAxes` to waive a HIGH/CRITICAL `risk` warning. Compare File/symbol: MCP File omits axes; Graph-RAG expands File.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- **MUST use `query({search_query: "concept"})` for concepts/flows, `context({name: "symbolName"})` for a named symbol, or `impact` for blast radius, on read-only callers, dependencies, imports, or execution flow.** Graph first; text search only for empty/`UNKNOWN`/literals.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/odoo-hr-agents/context` | Codebase overview, check index freshness |
| `gitnexus://repo/odoo-hr-agents/clusters` | All functional areas |
| `gitnexus://repo/odoo-hr-agents/processes` | All execution flows |
| `gitnexus://repo/odoo-hr-agents/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

## Specification-Driven Development & Code Health (Spec Kit & Desloppify)

This workspace integrates **Spec Kit** (`github/spec-kit`) and **Desloppify** (`peteromallet/desloppify`) locally:

- **Spec Kit**: Use `/speckit-specify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`, `/speckit-converge` for any feature development. Consult [.specify/memory/constitution.md](file:///d:/mjrm0/Documents/odoo-hr-agents-2/.specify/memory/constitution.md).
- **Desloppify**: Use `.\.venv\Scripts\desloppify.exe status`, `next`, `plan` for health scanning, debt remediation, and anti-slop code refinement. Target strict score >= 85.
- Rules reference: [.agents/rules/spec-driven-desloppify.md](file:///d:/mjrm0/Documents/odoo-hr-agents-2/.agents/rules/spec-driven-desloppify.md).

## AI Skills & Knowledge Ingestion (Skill Seekers)

This workspace integrates **Skill Seekers** (yusufkaraaslan/Skill_Seekers):

- **CLI**: .\.venv\Scripts\skill-seekers.exe (detect, create, scan, enhance, package, install-agent, doctor, ui)
- **MCP Server**: FastMCP server with 35+ tools (python -m skill_seekers.mcp.server_fastmcp)
- **Skill definition**: [.agents/skills/skill-seekers/SKILL.md](file:///d:/mjrm0/Documents/odoo-hr-agents-2/.agents/skills/skill-seekers/SKILL.md)
- **Source repository & configs**: [Skill_Seekers/](file:///d:/mjrm0/Documents/odoo-hr-agents-2/Skill_Seekers)

