"""
عقد معالجة Excel في الرسم (P4)
=================================
تنفيذ مسار استيراد الموظفين من Excel بضمانات writer.py عبر LangGraph.

السلسلة: رفع الملف ← parse_xlsx ← Validator ← heal_batch (بدون auto_repair)
          ← تقرير dry-run ← interrupt للاعتماد ← كتابة ← تحقق راجع ← سجل
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_events_service import AgentEventsService
from approval_schema import Approval
from musleh_service import MuslehService
from parser import parse_xlsx, ParserError
from graph.state import SerajState
from validator import Validator, ValidationResult


# ثوابت الموافقة
APPROVAL_TTL_MINUTES = 5
FOUR_EYES_THRESHOLD = 10


def parse_excel_file(state: SerajState) -> Dict[str, Any]:
    """
    عقدة تحليل ملف Excel.
    - تحلل الملف باستخدام parser.py
    - تُخزن النتيجة في الحالة
    - تُصدر حدث
    """
    file_path = state.get("excel_file_path")
    if not file_path:
        return {
            "excel_error": "no_file_path",
            "excel_error_message": "لم يتم توفير مسار الملف"
        }
    
    operation_id = state.get("operation_id")
    events_service = AgentEventsService()
    
    try:
        # تحليل الملف
        parsed_data = parse_xlsx(file_path)
        
        # إصدار حدث النجاح
        if operation_id:
            events_service.emit_event(
                operation_id=operation_id,
                event_type="excel_parsed",
                agent_name="parser",
                details={
                    "run_id": parsed_data["run_id"],
                    "row_count": parsed_data["row_count"],
                    "warnings": parsed_data.get("warnings", [])
                }
            )
        
        return {
            "excel_parsed_data": parsed_data,
            "excel_run_id": parsed_data["run_id"],
            "excel_row_count": parsed_data["row_count"]
        }
    
    except ParserError as e:
        error_code = str(e)
        
        # إصدار حدث الفشل
        if operation_id:
            events_service.emit_event(
                operation_id=operation_id,
                event_type="excel_parse_failed",
                agent_name="parser",
                details={"error_code": error_code}
            )
        
        return {
            "excel_error": error_code,
            "excel_error_message": f"فشل تحليل الملف: {error_code}"
        }


def validate_excel_rows(state: SerajState) -> Dict[str, Any]:
    """
    عقدة التحقق من صحة الصفوف.
    - تستخدم Validator للتحقق من كل صف
    - تُصدر حدث مع الإحصائيات
    """
    parsed_data = state.get("excel_parsed_data")
    if not parsed_data:
        return {"excel_error": "no_parsed_data"}
    
    operation_id = state.get("operation_id")
    events_service = AgentEventsService()
    
    validator = Validator()
    rows = parsed_data.get("rows", [])
    
    # التحقق من كل صف
    validation_results = []
    for row in rows:
        result = validator.validate_row(row)
        validation_results.append(result)
    
    # حساب الإحصائيات
    passed = sum(1 for r in validation_results if r.status == "passed")
    needs_review = sum(1 for r in validation_results if r.status == "needs_review")
    rejected = sum(1 for r in validation_results if r.status == "rejected")
    
    # إصدار حدث
    if operation_id:
        events_service.emit_event(
            operation_id=operation_id,
            event_type="excel_validated",
            agent_name="validator",
            details={
                "total": len(validation_results),
                "passed": passed,
                "needs_review": needs_review,
                "rejected": rejected
            }
        )
    
    return {
        "excel_validation_results": validation_results,
        "excel_validation_stats": {
            "total": len(validation_results),
            "passed": passed,
            "needs_review": needs_review,
            "rejected": rejected
        }
    }


def heal_excel_batch(state: SerajState) -> Dict[str, Any]:
    """
    عقدة إصلاح الصفوف (بدون auto_repair).
    - تستخدم MuslehService لمعالجة الصفوف التي needs_review
    - لا تطبق الإصلاحات تلقائياً (حسب P4)
    """
    validation_results = state.get("excel_validation_results", [])
    parsed_data = state.get("excel_parsed_data")
    
    if not validation_results or not parsed_data:
        return {"excel_error": "no_validation_results"}
    
    operation_id = state.get("operation_id")
    events_service = AgentEventsService()
    
    musleh = MuslehService()
    rows = parsed_data.get("rows", [])
    
    # معالجة الصفوف التي تحتاج مراجعة
    healed_results = []
    for i, result in enumerate(validation_results):
        if result.status == "needs_review":
            # مصلح يقترح إصلاحات لكن لا يطبقها تلقائياً
            row = rows[i]
            healing_decision = musleh.diagnose_and_decide(row, result)
            healed_results.append({
                "row_number": row["excel_row_number"],
                "original_status": result.status,
                "healing_decision": healing_decision,
                "requires_approval": True
            })
        else:
            healed_results.append({
                "row_number": rows[i]["excel_row_number"],
                "original_status": result.status,
                "healing_decision": None,
                "requires_approval": False
            })
    
    # إصدار حدث
    if operation_id:
        events_service.emit_event(
            operation_id=operation_id,
            event_type="excel_healed",
            agent_name="musleh",
            details={
                "total_healed": sum(1 for r in healed_results if r["healing_decision"] is not None)
            }
        )
    
    return {
        "excel_healed_results": healed_results
    }


def generate_dry_run_report(state: SerajState) -> Dict[str, Any]:
    """
    عقدة توليد تقرير dry-run.
    - تُنشئ تقرير تفصيلي بما سيُكتب
    - تحدد ما إذا كانت الموافقة المزدوجة مطلوبة
    """
    validation_results = state.get("excel_validation_results", [])
    healed_results = state.get("excel_healed_results", [])
    parsed_data = state.get("excel_parsed_data")
    
    if not all([validation_results, healed_results, parsed_data]):
        return {"excel_error": "incomplete_data"}
    
    rows = parsed_data.get("rows", [])
    row_count = len(rows)
    
    # تحديد الصفوف القابلة للكتابة
    writable_rows = []
    for i, result in enumerate(validation_results):
        if result.status == "passed":
            writable_rows.append(rows[i])
    
    # الموافقة المزدوجة للدفعات الكبيرة
    requires_four_eyes = row_count > FOUR_EYES_THRESHOLD
    
    report = {
        "total_rows": row_count,
        "writable_rows": len(writable_rows),
        "rejected_rows": sum(1 for r in validation_results if r.status == "rejected"),
        "needs_review_rows": sum(1 for r in validation_results if r.status == "needs_review"),
        "requires_four_eyes": requires_four_eyes,
        "summary_ar": f"سيتم كتابة {len(writable_rows)} من أصل {row_count} صف"
    }
    
    operation_id = state.get("operation_id")
    if operation_id:
        events_service = AgentEventsService()
        events_service.emit_event(
            operation_id=operation_id,
            event_type="dry_run_report_generated",
            agent_name="excel_workflow",
            details=report
        )
    
    return {
        "excel_dry_run_report": report,
        "excel_requires_four_eyes": requires_four_eyes
    }


def create_excel_approval(state: SerajState) -> Dict[str, Any]:
    """
    عقدة إنشاء اعتماد Excel.
    - تُنشئ كائن Approval مع TTL
    - تربطه بمحتوى الخطة (run_id, source_hash, row_hash)
    """
    parsed_data = state.get("excel_parsed_data")
    dry_run_report = state.get("excel_dry_run_report")
    
    if not all([parsed_data, dry_run_report]):
        return {"excel_error": "cannot_create_approval"}
    
    run_id = parsed_data["run_id"]
    source_hash = parsed_data["source_hash"]
    
    # حساب تاريخ الصلاحية
    expiry_time = datetime.utcnow() + timedelta(minutes=APPROVAL_TTL_MINUTES)
    
    # إنشاء الاعتماد
    approval = Approval(
        run_id=run_id,
        source_hash=source_hash,
        row_hashes=[row["row_hash"] for row in parsed_data["rows"]],
        approved_by=state.get("user_id", "unknown"),
        approved_at=datetime.utcnow().isoformat(),
        expires_at=expiry_time.isoformat(),
        is_consumed=False
    )
    
    # حفظ الاعتماد
    approval_path = Path(f"approvals/excel_{run_id}.json")
    approval_path.parent.mkdir(exist_ok=True)
    approval_path.write_text(json.dumps(approval.__dict__, ensure_ascii=False, indent=2))
    
    operation_id = state.get("operation_id")
    if operation_id:
        events_service = AgentEventsService()
        events_service.emit_event(
            operation_id=operation_id,
            event_type="excel_approval_created",
            agent_name="excel_workflow",
            details={
                "run_id": run_id,
                "expires_at": expiry_time.isoformat(),
                "row_count": len(approval.row_hashes)
            }
        )
    
    return {
        "excel_approval": approval.__dict__,
        "excel_approval_path": str(approval_path),
        "needs_human_approval": True
    }


def route_after_excel_parse(state: SerajState) -> str:
    """توجيه بعد تحليل الملف."""
    if state.get("excel_error"):
        return "finalize"
    return "validate_excel_rows"


def route_after_validation(state: SerajState) -> str:
    """توجيه بعد التحقق."""
    stats = state.get("excel_validation_stats", {})
    if stats.get("total", 0) == 0:
        return "finalize"
    return "heal_excel_batch"


def route_after_healing(state: SerajState) -> str:
    """توجيه بعد الإصلاح."""
    return "generate_dry_run_report"


def route_after_dry_run(state: SerajState) -> str:
    """توجيه بعد تقرير dry-run."""
    report = state.get("excel_dry_run_report", {})
    if report.get("writable_rows", 0) == 0:
        return "finalize"
    return "create_excel_approval"


def route_after_excel_approval(state: SerajState) -> str:
    """توجيه بعد إنشاء الاعتماد - يتطلب موافقة بشرية."""
    return "human_approval"
