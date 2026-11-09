<!--
=== Sync Impact Report ===
Version change: 1.0.0 → 1.1.0
Modified principles:
  - Specification-First (Non-Negotiable) → I. Specification-First Development (Non-Negotiable) [Clarified mandatory SDD workflow]
  - Local Environment Isolation → II. Strict Local Environment Isolation [Formalized boundary controls]
  - Continuous Code Health & Anti-Slop → III. Continuous Code Health & Anti-Slop (Desloppify Mandate) [Codified strict score >= 85 requirement]
  - Arabic UX/UI & Cultural Compliance → IV. Arabic UX/UI & Cultural Charter [Added WCAG 2.2 and RTL constraints]
  - Saudi Labor Law & HR Integrity → V. Saudi Labor Law & Regulatory Integrity [Reinforced statutory compliance]
  - Impact Analysis & Code Intelligence → VI. Code Intelligence & Impact Analysis (GitNexus) [Codified pre-edit blast radius checks]
Added sections:
  - Additional Constraints & Security Standards
Removed sections:
  - None
Deferred TODOs:
  - None
==========================
-->

# Odoo HR Multi-Agent System Constitution

## Core Principles

### I. Specification-First Development (Non-Negotiable)
Every non-trivial feature, architectural alteration, or functional enhancement MUST begin with a formal specification (`/speckit-specify`), followed by an architectural and implementation blueprint (`/speckit-plan`), and break down into testable atomic tasks (`/speckit-tasks`). "Vibe coding" or writing code without approved specifications is strictly prohibited. Rationale: Eliminates architectural drift, hidden assumptions, and untracked side effects.

### II. Strict Local Environment Isolation
All agent skills, tooling dependencies, and configurations MUST remain strictly isolated within this workspace (`d:\mjrm0\Documents\odoo-hr-agents-2`). Agents MUST NOT modify global system directories, user home directory configurations (`~/.gemini`, `~/.claude`, etc.), or external development environments. Rationale: Prevents environment contamination across different IDEs and maintains complete project reproducibility.

### III. Continuous Code Health & Anti-Slop (Desloppify Mandate)
The codebase MUST maintain a Desloppify Strict Score of at least **85/100**. Agents MUST execute the continuous remediation cycle (**scan → plan → next → execute/autofix → rescan**) using the local `.\.venv\Scripts\desloppify.exe`. Dead code, architectural cycles, unverified AI slop, and suppressed warnings without justification are forbidden. Rationale: Ensures long-term maintainability and prevents structural rot.

### IV. Arabic UX/UI & Cultural Charter
All user-facing interfaces, dashboards, visual components, and copywriting MUST strictly comply with `.agents/rules/ui-ux-motion-design-arabic.md`:
- Arabic microcopy MUST use natural, professional, and clear language (no robotic or literal translations).
- Layouts MUST support complete Right-to-Left (RTL) reading order, optical alignment, and concentric radii.
- Visuals MUST eliminate AI-slop indicators: no random neon/purple gradients, no emoji spam as icons, no `transition: all`.
- Non-text elements MUST meet a 3:1 contrast ratio; body copy MUST meet a 4.5:1 ratio (WCAG 2.2).
Rationale: Preserves regional professional credibility and exceptional user experience.

### V. Saudi Labor Law & Regulatory Integrity
All HR business logic—including employment contracts, probation periods, leave accruals, working hours, and End-of-Service Benefits (EOSB)—MUST strictly conform to the Saudi Labor Law codified in `saudi_labor_law.md` and enforced via `saudi_labor_law_rules.py`. Any code conflicting with statutory requirements MUST be rejected. Rationale: Non-compliance risks legal liability and financial penalties.

### VI. Code Intelligence & Impact Analysis (GitNexus)
Before modifying any existing function, class, or service, agents MUST evaluate the blast radius using GitNexus (`impact --direction upstream`). Prior to committing code changes, agents MUST run graph change detection (`detect-changes`). Finding a risk level of HIGH or CRITICAL MUST stop the workflow until resolved. Rationale: Protects inter-agent communication contracts and prevents regression in critical execution paths.

## Additional Constraints & Security Standards

- **BOLA / Authorization Guard**: Every query and endpoint MUST enforce object-level access control filtered by user/organization context for non-admin requests.
- **SSRF & Input Sanitization**: All incoming network payloads, RTSP URLs, and dynamic parameters MUST be sanitized and validated against SSRF protection policies.
- **Dependency Hygiene**: Python dependencies MUST be pinned and managed through the project `.venv`. Node scripts and agent tools MUST run locally without global side-effects.

## Development Workflow & Quality Gates

The Spec Kit delivery lifecycle consists of the following mandatory sequence:

1. **Specify Stage (`/speckit-specify`)**: Model user scenarios, define functional scope, and declare edge cases.
2. **Clarify Stage (`/speckit-clarify` - optional)**: Resolve open questions and ambiguities before technical planning.
3. **Plan Stage (`/speckit-plan`)**: Establish component architecture, schema migrations, and API contracts.
4. **Tasks Stage (`/speckit-tasks`)**: Generate dependency-ordered, verifiable task cards.
5. **Implement Stage (`/speckit-implement`)**: Code tasks sequentially with test verification and static checks.
6. **Converge & Health Stage (`/speckit-converge` & `desloppify`)**: Confirm implementation coverage against the specification and verify that the Desloppify Strict Score remains >= 85.

## Governance

- This Constitution is the highest technical authority in the workspace and supersedes informal conventions.
- All Pull Requests, agent workflows, and automated checks MUST enforce compliance with these principles.
- Amendments require a formal version bump (Semantic Versioning: MAJOR for principle removals/redefinitions, MINOR for new principles/sections, PATCH for wording clarifications) and an accompanying Sync Impact Report.
- Development guidance and agent execution rules are maintained in `.specify/` templates and `.agents/rules/`.

**Version**: 1.1.0 | **Ratified**: 2026-11-07 | **Last Amended**: 2026-11-07
