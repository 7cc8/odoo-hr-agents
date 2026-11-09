"""Web Service & API Middleware for Odoo HR Agents (Phase 7).

FastAPI application providing the complete API and graphical interface for
HR staff and automation bots:
1. POST /upload: Secure upload of Excel sheets (max 2MB, no execution).
2. POST /dry-run: Generate dry-run inspection report without touching Odoo.
3. GET /dry-run/{run_id}: Read existing dry-run inspection report (read-only).
4. POST /approve: Record formal human approval in approval.json (accepted rows only).
5. POST /write: Execute employee creation in Odoo (requires auth token + valid approval).
6. GET /write/{run_id}/stream: Server-Sent Events stream of live writer execution.
"""

from __future__ import annotations

import os
import sys

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import json
import time
import shutil
import asyncio
import uuid
import tempfile
import secrets
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request, Header
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import dry_run_report
import parser
import make_approval
import approval_schema
import writer
from odoo_readonly_repository import OdooReadonlyRepository
from odoo_write_gateway import OdooWriteGateway, EnvironmentGuardError
import telegram_notifier
from odoo_config_manager import get_active_odoo_config, save_active_odoo_config, test_odoo_connection, clear_active_odoo_config, normalize_odoo_url
from generate_employee_template import generate_template
from template_catalog import get_template, list_templates


app = FastAPI(
    title="Odoo HR Agents Web & Automation API",
    description="Secure HR Import & Verification Portal for Odoo ERP (Phase 7)",
    version="1.1.0",
)

# Keep browser credentials scoped to explicitly configured origins. A wildcard
# origin cannot be combined safely with credentialed requests in production.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles

IMAGES_DIR = Path(__file__).parent / "frontend" / "images"
if not IMAGES_DIR.exists():
    IMAGES_DIR = Path(__file__).parent / "images"
if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
    css_dir = FRONTEND_DIR / "css"
    if css_dir.exists():
        app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
    js_dir = FRONTEND_DIR / "js"
    if js_dir.exists():
        app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")


# ==================== COMMON API UTILITIES & ROUTERS ====================
INSECURE_PUBLISHED_WRITE_TOKENS = frozenset({"hr-write-secret-token", "replace_with_a_long_random_secret"})
import api.common
api.common.INSECURE_PUBLISHED_WRITE_TOKENS = INSECURE_PUBLISHED_WRITE_TOKENS

from api.common import (
    API_LOG_FILE,
    LOGS_DIR,
    OUTPUT_ROOT,
    SAFE_ID_RE,
    TEMPLATE_DIR,
    UPLOAD_DIR,
    WRITE_API_TOKEN,
    _safe_artifact_path,
    _safe_operation_id,
    audit_log_access,
    verify_api_auth,
    verify_write_auth,
)
from api.routers.excel import (
    ApprovalRequest,
    ConditionalExecutionApprovalRequest,
    DryRunBodyRequest,
    QuickApproveAndExecuteRequest,
    TemplateGenerateRequest,
    WriteRequest,
    _build_offline_dry_run_report,
    approve_and_execute_endpoint,
    approve_conditional_execution_endpoint,
    create_approval_endpoint,
    download_legacy_template_endpoint,
    download_template_endpoint,
    execute_writer_endpoint,
    get_dry_run_report_detail_endpoint,
    get_hr_reference_options_endpoint,
    get_run_details,
    get_template_catalog_endpoint,
    generate_template_endpoint,
    list_recent_runs,
    router as excel_router,
    run_dry_run_endpoint,
    stream_writer_results,
)

# تسجيل راوتر مسارات الإكسل المفصول مع الحفاظ الكامل على المسارات السابقة
app.include_router(excel_router)

from api.routers.chat import (
    router as chat_router,
    SerajChatApiRequest,
    ChatMessage,
    post_seraj_chat_endpoint,
    chat_endpoint,
    chat_with_langgraph,
    search_assistants_endpoint,
    get_assistant_detail_endpoint,
    search_threads_endpoint,
    list_chat_threads,
    get_thread_history,
)

# تسجيل راوتر مسارات المحادثة والمساعدين مع الحفاظ الكامل على المسارات السابقة
app.include_router(chat_router)

from api.routers.audit import (
    router as audit_router,
    ConnectionSettingsRequest,
    LLMProviderSettingsRequest,
    LLMTestRequest,
    AgentApprovalApiRequest,
    AgentCancelApiRequest,
    get_system_status,
    update_connection_settings,
    reset_connection_settings,
    get_llm_settings_endpoint,
    update_llm_settings_endpoint,
    test_llm_settings_endpoint,
    start_local_ollama_endpoint,
    get_sijil_summary_endpoint,
    get_sijil_html_report_endpoint,
    get_sijil_pdf_report_endpoint,
    get_sijil_portal_page,
    get_sijil_search_endpoint,
    get_sijil_operation_detail_endpoint,
    get_sijil_operation_pdf_endpoint,
    get_sijil_recent_operations_endpoint,
    get_agents_overview_endpoint,
    get_agents_operations_endpoint,
    get_agent_operation_endpoint,
    get_agent_operation_events_endpoint,
    get_agent_traces_endpoint,
    stream_agent_operation_events,
    post_agent_approve_endpoint,
    post_agent_cancel_endpoint,
    upload_agent_file_endpoint,
)

# تسجيل راوتر مسارات التدقيق والعمليات وسجل النظام مع الحفاظ الكامل على المسارات السابقة
app.include_router(audit_router)



# ==================== HR SERVICES & DOMAINS ROUTER ====================
from api.routers.hr_services import (
    hr_services_router,
    # 33 request/response models
    LeaveDryRunPayload,
    LeaveApplyPayload,
    AttendanceDryRunPayload,
    AttendanceActionPayload,
    AttendanceApplyPayload,
    DisciplinaryDryRunPayload,
    DisciplinaryApplyPayload,
    EOSDryRunPayload,
    EOSApplyPayload,
    GRDryRunPayload,
    GRApplyPayload,
    AppraisalDryRunPayload,
    AppraisalApplyPayload,
    LoanDryRunPayload,
    LoanApplyPayload,
    ApplicantDryRunPayload,
    ApplicantApplyPayload,
    ContractDryRunPayload,
    ContractApplyPayload,
    PayslipDryRunPayload,
    PayslipApplyPayload,
    WpsSifPayload,
    SaudizationSimPayload,
    LetterDryRunPayload,
    LetterApplyPayload,
    WarningDryRunPayload,
    WarningApplyPayload,
    ExpenseDryRunPayload,
    ExpenseApplyPayload,
    ExpiryScanQueryPayload,
    MuslehDiagnoseRowRequest,
    MuslehHealBatchRequest,
    MuslehRecoverSubmissionRequest,
    # 89 functions
    get_leave_service_instance,
    get_leave_types_endpoint,
    get_employee_leave_summary_endpoint,
    dry_run_leave_endpoint,
    apply_leave_endpoint,
    get_attendance_service_instance,
    get_attendance_summary_endpoint,
    dry_run_attendance_endpoint,
    check_in_endpoint,
    check_out_endpoint,
    apply_attendance_endpoint,
    get_disciplinary_service_instance,
    get_disciplinary_categories_endpoint,
    get_disciplinary_summary_endpoint,
    dry_run_disciplinary_endpoint,
    apply_disciplinary_endpoint,
    get_eos_service_instance,
    get_eos_reasons_endpoint,
    get_eos_summary_endpoint,
    dry_run_eos_endpoint,
    apply_eos_endpoint,
    get_gr_service_instance,
    get_common_gr_transactions_endpoint,
    get_gr_summary_endpoint,
    dry_run_gr_endpoint,
    apply_gr_endpoint,
    get_appraisal_service_instance,
    get_appraisal_ratings_guide_endpoint,
    get_appraisal_summary_endpoint,
    dry_run_appraisal_endpoint,
    apply_appraisal_endpoint,
    get_loan_service_instance,
    get_loan_rules_endpoint,
    get_loan_summary_endpoint,
    dry_run_loan_endpoint,
    apply_loan_endpoint,
    get_recruitment_service_instance,
    get_recruitment_jobs_endpoint,
    get_recruitment_stages_endpoint,
    get_recruitment_applicants_endpoint,
    get_applicant_detail_endpoint,
    dry_run_applicant_endpoint,
    apply_applicant_endpoint,
    get_contract_service_instance,
    get_contract_types_endpoint,
    get_employee_contract_endpoint,
    dry_run_contract_endpoint,
    apply_contract_endpoint,
    get_payroll_service_instance,
    get_payroll_structures_endpoint,
    get_employee_payslip_endpoint,
    dry_run_payslip_endpoint,
    apply_payslip_endpoint,
    generate_wps_sif_endpoint,
    get_analytics_service_instance,
    get_unified_dashboard_endpoint,
    get_workforce_analytics_endpoint,
    get_operations_analytics_endpoint,
    get_financial_analytics_endpoint,
    get_compliance_analytics_endpoint,
    get_recruitment_analytics_endpoint,
    simulate_saudization_endpoint,
    get_letter_types_endpoint,
    get_letter_categories_endpoint,
    get_employee_letters_endpoint,
    post_letter_dry_run_endpoint,
    post_letter_apply_endpoint,
    get_letter_html_view,
    get_letter_pdf_view,
    get_warning_levels_endpoint,
    get_warning_types_endpoint,
    get_employee_warnings_endpoint,
    post_warning_dry_run_endpoint,
    post_warning_apply_endpoint,
    get_warning_html_view,
    get_warning_pdf_view,
    get_expense_categories_endpoint,
    get_employee_expenses_endpoint,
    post_expense_dry_run_endpoint,
    post_expense_apply_endpoint,
    get_expense_html_view,
    get_expense_pdf_view,
    get_expiries_alerts_endpoint,
    post_scan_expiries_endpoint,
    get_expiries_html_report_endpoint,
    get_expiries_pdf_report_endpoint,
    post_musleh_diagnose_row_endpoint,
    post_musleh_heal_batch_endpoint,
    post_musleh_recover_submission_endpoint,
    # 11 globals
    _global_leave_service,
    _global_attendance_service,
    _global_disciplinary_service,
    _global_eos_service,
    _global_gr_service,
    _global_appraisal_service,
    _global_loan_service,
    _global_recruitment_service,
    _global_contract_service,
    _global_payroll_service,
    _global_analytics_service,
)

# تسجيل راوتر مسارات الموارد البشرية والخدمات التخصصية مع الحفاظ الكامل على المسارات السابقة
app.include_router(hr_services_router)

# ==================== STATIC & DASHBOARD ====================

@app.get("/guide", response_class=HTMLResponse)
def get_user_guide_page() -> str:
    """Returns the HR User Guide in the matching design system."""
    guide_file = Path("docs") / "user_guide.html"
    if guide_file.exists():
        return guide_file.read_text(encoding="utf-8")
    return "<h1>دليل الاستخدام غير متوفر</h1>"


DASHBOARD_FILE = Path(__file__).parent / "frontend" / "dashboard.html"
if DASHBOARD_FILE.exists():
    DASHBOARD_HTML_PAGE = DASHBOARD_FILE.read_text(encoding="utf-8")
else:
    DASHBOARD_HTML_PAGE = "<h1>بوابة أتمتة إدخال الموظفين في Odoo</h1>"



# ==================== STATIC & DASHBOARD VIEWS ====================

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def get_main_dashboard_html() -> str:
    """Returns the primary multi-agent operations cockpit (templates/dashboard.html)."""
    raw_content = DASHBOARD_FILE.read_text(encoding="utf-8") if DASHBOARD_FILE.exists() else DASHBOARD_HTML_PAGE
    return raw_content


@app.get("/chat", response_class=HTMLResponse)
def get_standalone_chat_html() -> str:
    """Returns the unified operational cockpit positioned on Seraj copilot chat."""
    return get_main_dashboard_html()


@app.get("/unified-dashboard", response_class=HTMLResponse)
def get_unified_dashboard_fallback() -> str:
    """Returns the primary multi-agent operations cockpit."""
    return get_main_dashboard_html()


@app.get("/diagram/companies", response_class=HTMLResponse)
def get_companies_diagram_html() -> str:
    """Returns the unified cockpit positioned on the editorial multi-company census diagram."""
    return get_main_dashboard_html()


@app.get("/design-preview", response_class=HTMLResponse)
def get_design_preview_html() -> str:
    """Returns the improved design preview (unslopped version)."""
    preview_file = Path(__file__).parent / "frontend" / "design_preview.html"
    if not preview_file.exists():
        preview_file = Path(__file__).parent / "templates" / "design_preview.html"
    if preview_file.exists():
        return preview_file.read_text(encoding="utf-8")
    return "<h1>ملف design_preview.html غير متوفر</h1>"


@app.get("/proposals", response_class=HTMLResponse)
def get_agents_proposals_html() -> str:
    """Returns the interactive showcase for the 8 agents redesign proposals."""
    proposals_file = Path(__file__).parent / "frontend" / "agents_redesign_proposals.html"
    if not proposals_file.exists():
        proposals_file = Path(__file__).parent / "templates" / "agents_redesign_proposals.html"
    if proposals_file.exists():
        return proposals_file.read_text(encoding="utf-8")
    return "<h1>ملف مقترحات التصميم غير متوفر</h1>"


@app.get("/odoo-hr-hq", response_class=HTMLResponse)
@app.get("/hq", response_class=HTMLResponse)
@app.get("/nadr-hq", response_class=HTMLResponse)
def get_odoo_hr_hq_html() -> str:
    """Returns the complete Odoo HR HQ with live walking agents, 13 scenarios, and Bento dashboard."""
    hq_file = Path(__file__).parent / "odoo_hr_hq" / "index.html"
    if hq_file.exists():
        return hq_file.read_text(encoding="utf-8")
    return "<h1>ملف مقر شركة سراج الذكي (odoo_hr_hq/index.html) غير متوفر</h1>"


if __name__ == "__main__":
    import uvicorn
    print("Starting Odoo HR Dashboard on http://localhost:8000 ...")
    uvicorn.run("web_service:app", host="127.0.0.1", port=8000, reload=False)