# Bugfix Requirements Document

## Introduction

The Odoo HR Agents system is experiencing multiple integration and workflow issues that prevent users from accessing critical functionality through the web dashboard and API. The system currently has:
- **Template generation** limited to CLI only (not accessible via web/API)
- **Dashboard UI** missing conditional execution workflow for dry-run results
- **Result display** not showing rejection details clearly to end users
- **Seraj Meta-Agent** not providing user choice flow for approve/reject decisions
- **Auto-execution** not working when all rows are accepted

These issues prevent the system from delivering a complete user experience where:
1. Users can generate company-specific templates from the dashboard
2. Dry-run results with rejected rows trigger a user approval workflow
3. Clean dry-runs (no rejected rows) auto-execute immediately
4. Agent execution traces are visible in real-time

**Impact**: HR staff must use CLI tools manually, cannot make informed decisions on rejected data, and experience unnecessary delays on clean imports.

---

## Bug Analysis

### Current Behavior (Defect)

#### 1. Template Generation Issues

1.1 WHEN a user accesses the unified dashboard THEN the system does NOT provide any UI button or form to generate company-specific employee templates

1.2 WHEN a user attempts to generate a template via API THEN the system returns 404 because no `/api/template/generate` endpoint exists

1.3 WHEN template generation is needed THEN the system requires manual CLI execution of `generate_employee_template.py --output-dir DIR`

1.4 WHEN `generate_employee_template.py` is executed THEN it generates generic templates without company-specific customization (no company_id filtering for departments/jobs)

#### 2. Dry-Run Result Display Issues

2.1 WHEN a dry-run completes with rejected rows THEN the system returns a generic response without detailed rejection reasons, field locations, or suggested fixes

2.2 WHEN Seraj Meta-Agent processes dry-run results THEN it does NOT format rejection details in a user-friendly structure with row numbers, display names, and exact field locations

2.3 WHEN rejected rows exist THEN the dashboard displays only counts (accepted vs rejected) without an expandable table showing individual rejection details

2.4 WHEN a user views dry-run results THEN template detection logic from `template_detector.py` is NOT used to validate or enhance error messages

#### 3. Conditional Execution Workflow Issues

3.1 WHEN a dry-run completes with rejected rows > 0 THEN the system does NOT present a user choice interface (execute accepted only / try auto-fix / cancel)

3.2 WHEN a dry-run completes with rejected rows = 0 THEN the system does NOT auto-execute immediately but instead waits for manual approval

3.3 WHEN user approval is needed THEN no `/api/approve-conditional` endpoint exists to handle user decisions

3.4 WHEN Seraj Meta-Agent orchestrates execution THEN no `conditional_execution_node` exists in LangGraph to branch based on rejected row count

#### 4. Agent Tracing Issues

4.1 WHEN agents execute in LangGraph THEN the unified dashboard does NOT display a real-time timeline of agent execution

4.2 WHEN Seraj Meta-Agent makes orchestration decisions THEN the reasoning and selected agents are NOT exposed in dashboard UI

4.3 WHEN an agent completes or fails THEN no visual success/failure indicators appear in the dashboard timeline

4.4 WHEN users need to debug agent behavior THEN no `/api/agent-traces/{operation_id}` endpoint exists to retrieve execution history

#### 5. State Management Issues

5.1 WHEN dry-run results include rejected rows THEN `SerajState` does NOT include `rejected_rows_details` field to store detailed rejection information

5.2 WHEN user makes an execution decision THEN `SerajState` does NOT include `user_execution_choice` field to track approve/fix/cancel

5.3 WHEN auto-execution should occur THEN `SerajState` does NOT include `auto_execute` boolean flag to trigger immediate execution

---

### Expected Behavior (Correct)

#### 1. Template Generation Fixes

2.1 WHEN a user accesses the unified dashboard THEN the system SHALL display a "Generate Template" section with company selector, template type dropdown, and generate button

2.2 WHEN a user clicks "Generate Template" THEN the system SHALL call `POST /api/template/generate` with `{company_id, template_type, include_example_row, language}` and return a download link

2.3 WHEN template generation is requested via API THEN the system SHALL create company-specific templates by filtering departments/jobs/custom fields by company_id from Odoo

2.4 WHEN template generation completes THEN the system SHALL return JSON with `{status, template_path, download_url, sheet_count, generated_at}` and enable download via `/api/template/download/{template_id}`

#### 2. Dry-Run Result Display Fixes

2.5 WHEN a dry-run completes with rejected rows THEN the system SHALL return detailed rejection data including `{row_number, name, reason_ar, field, value, suggestion, can_auto_fix}` for each rejected row

2.6 WHEN Seraj Meta-Agent formats results THEN it SHALL include a `_format_rejection_details()` method that structures rejection data with Arabic reasons and field locations

2.7 WHEN dashboard displays dry-run results THEN it SHALL show an expandable "Rejected Rows" table with columns: Row #, Name, Reason (Arabic), Field, Value, Suggested Fix

2.8 WHEN dry-run validation occurs THEN the system SHALL integrate `template_detector.py` to detect template format and provide better validation error messages

#### 3. Conditional Execution Workflow Fixes

2.9 WHEN a dry-run completes with rejected_rows > 0 THEN the system SHALL display action buttons: "Execute Accepted Only (X rows)", "Try Auto-Fix (Musleh)", "Cancel - Fix Manually"

2.10 WHEN a dry-run completes with rejected_rows = 0 THEN the system SHALL auto-execute immediately without user prompt and display "✅ All rows (X) accepted - Executing now..."

2.11 WHEN user clicks an action button THEN the system SHALL call `POST /api/approve-conditional` with `{operation_id, choice: "execute"|"fix"|"cancel"}` and proceed accordingly

2.12 WHEN LangGraph processes execution THEN it SHALL include a `conditional_execution_node` in `agentic_nodes.py` that branches to auto-execute, wait for approval, or trigger Musleh based on rejection count

#### 4. Agent Tracing Fixes

2.13 WHEN agents execute THEN the system SHALL emit events to `agent_events_service` with `{timestamp, agent, action, decision, reasoning, status}` for each step

2.14 WHEN dashboard loads THEN it SHALL display an "Agent Timeline" section showing agent execution with icons, status indicators (✅/❌), and reasoning tooltips

2.15 WHEN Seraj Meta-Agent orchestrates THEN dashboard SHALL show "Selected agents: Fahas, Mudaqqiq, Katib" with reasoning like "Query type: employee import → needs validation + write"

2.16 WHEN user requests traces THEN `GET /api/agent-traces/{operation_id}` SHALL return chronological list of agent events from `agent_events_service`

#### 5. State Management Fixes

2.17 WHEN dry-run completes THEN `SerajState` SHALL include `rejected_rows_details: Optional[List[Dict[str, Any]]]` populated with detailed rejection data

2.18 WHEN user makes approval decision THEN `SerajState` SHALL include `user_execution_choice: Optional[str]` set to "execute", "fix", or "cancel"

2.19 WHEN rejected_rows = 0 THEN `SerajState` SHALL include `auto_execute: Optional[bool]` set to True to trigger immediate execution

---

### Unchanged Behavior (Regression Prevention)

#### 3. Existing API Contracts

3.1 WHEN existing endpoints like `/upload`, `/dry-run`, `/approve`, `/write` are called THEN the system SHALL CONTINUE TO return responses in the same JSON format with no breaking changes

3.2 WHEN Telegram bot integration calls API endpoints THEN the system SHALL CONTINUE TO work with current authentication and response handling

3.3 WHEN CLI tools like `generate_employee_template.py` are executed THEN they SHALL CONTINUE TO work with `--output-dir` argument for backward compatibility

#### 4. Agent Execution Logic

3.4 WHEN Seraj Meta-Agent orchestrates without conditional execution THEN existing agent selection logic SHALL CONTINUE TO work (Fahas for query, Mudaqqiq for validation, Katib for write)

3.5 WHEN Musleh agent heals data THEN existing `musleh_agentic_heal` node SHALL CONTINUE TO process rejected rows using perceive-plan-execute-reflect cycle

3.6 WHEN LangGraph state transitions occur THEN existing state fields like `operation_id`, `company_id`, `user_query`, `parsed_data` SHALL CONTINUE TO be preserved

#### 5. Authentication & Security

3.7 WHEN write operations are requested THEN the system SHALL CONTINUE TO require `WRITE_API_TOKEN` via X-API-Key header

3.8 WHEN audit logging occurs THEN `audit_log_access()` SHALL CONTINUE TO log every API request to `logs/web_access.log`

3.9 WHEN Odoo connections are made THEN `odoo_config_manager` SHALL CONTINUE TO validate connections before allowing write operations

#### 6. File Upload & Parsing

3.10 WHEN Excel files are uploaded THEN `parser.py` SHALL CONTINUE TO parse employee data with the same column mapping and validation rules

3.11 WHEN dry-run reports are generated THEN `dry_run_report.py` SHALL CONTINUE TO produce JSON reports with accepted/rejected row categorization

3.12 WHEN approval schema validation occurs THEN `approval_schema.py` SHALL CONTINUE TO enforce the same rules for approval.json format

#### 7. Dashboard Analytics

3.13 WHEN `/api/analytics/dashboard` is called THEN the system SHALL CONTINUE TO return existing metrics (total operations, success rate, agent performance)

3.14 WHEN unified dashboard loads THEN existing sections like "System Overview", "Recent Operations", "Analytics Charts" SHALL CONTINUE TO display correctly

#### 8. Test Coverage

3.15 WHEN existing test suites run THEN all tests in `tests/` SHALL CONTINUE TO pass with > 80% code coverage for modified modules

3.16 WHEN new features are added THEN existing test files like `test_generate_employee_template.py` SHALL CONTINUE TO validate CLI functionality
