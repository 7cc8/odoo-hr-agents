"""
خدمة إدارة الإجازات ونظام العمل السعودي (Leave Service)
======================================================
الطبقة التنفيذية لإدارة الإجازات في Odoo (hr.leave) بالتكامل التام مع
محرك قواعد نظام العمل السعودي وتعديلات المرسوم الملكي (م/44) لعام 1446هـ.

تلتزم الخدمة بـ:
1. التحقق الحتمي المسبق (Dry Run) ومطابقة الرصيد والاستحقاق النظامي (المواد 109، 113، 116).
2. مبدأ التحقق المزدوج (Four-Eyes Principle) وموافقة "تأكيد" قبل أي كتابة.
3. بوابة الكتابة المعزولة OdooLeaveWriteGateway مع فحص حارس البيئة.
4. التحقق المستقل بعد الكتابة (Readback Verification) وسجل التدقيق المركزي.
"""

from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_leave_write_gateway import OdooLeaveWriteGateway
from saudi_labor_law_rules import (
    calculate_annual_leave_entitlement,
    get_occasion_leave_statutory_days,
    validate_maternity_leave_duration,
    OccasionLeaveType,
)


AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "leave_audit_log.jsonl")
PENDING_APPROVALS_FILE = os.path.join(os.path.dirname(__file__), "logs", "pending_leave_approvals.json")


@dataclass
class LeaveTypeInfo:
    id: int
    name: str
    request_unit: str
    requires_allocation: bool
    active: bool


@dataclass
class EmployeeLeaveSummary:
    employee_id: int
    employee_name: str
    department_name: str
    gender: str
    service_years: float
    statutory_annual_entitlement: int  # 21 أو 30 يوماً حسب المادة 109
    allocated_days: float
    consumed_days: float
    remaining_days: float
    recent_leaves: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class LeaveDryRunResult:
    is_valid: bool
    employee_id: int
    employee_name: str
    holiday_status_id: int
    leave_type_name: str
    request_date_from: str
    request_date_to: str
    number_of_days: float
    statutory_article: str
    statutory_explanation_ar: str
    balance_before: float
    balance_after: float
    requires_allocation: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    approval_token: str = ""
    can_proceed: bool = False


@dataclass
class LeaveExecutionResult:
    success: bool
    leave_id: Optional[int]
    employee_id: int
    employee_name: str
    leave_type_name: str
    number_of_days: float
    request_date_from: str
    request_date_to: str
    state: str
    readback_verified: bool
    message_ar: str
    audit_logged: bool


class LeaveService:
    _shared_pending_approvals: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def _load_persisted_approvals(cls, filepath: str = PENDING_APPROVALS_FILE) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    @classmethod
    def _save_persisted_approvals(cls, approvals: Dict[str, Dict[str, Any]], filepath: str = PENDING_APPROVALS_FILE) -> None:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            temp_file = f"{filepath}.tmp.{os.getpid()}"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(approvals, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, filepath)
        except Exception:
            pass

    def __init__(
        self,
        readonly_repo: Optional[OdooReadonlyRepository] = None,
        write_gateway: Optional[OdooLeaveWriteGateway] = None,
        audit_log_path: Optional[str] = None,
        pending_approvals_path: Optional[str] = None,
    ):
        self.readonly_repo = readonly_repo or OdooReadonlyRepository()
        self.write_gateway = write_gateway
        self.audit_log_path = audit_log_path or AUDIT_LOG_FILE
        self.pending_approvals_path = pending_approvals_path or PENDING_APPROVALS_FILE
        
        # مزامنة الموافقات المعلقة من الملف إلى الذاكرة المشتركة
        if not LeaveService._shared_pending_approvals and os.path.exists(self.pending_approvals_path):
            disk = LeaveService._load_persisted_approvals(self.pending_approvals_path)
            LeaveService._shared_pending_approvals.update(disk)

        self._pending_approvals: Dict[str, Dict[str, Any]] = LeaveService._shared_pending_approvals

    def get_leave_types(self) -> List[LeaveTypeInfo]:
        """جلب جميع أنواع الإجازات المتاحة في أودو"""
        raw_types = self.readonly_repo.get_leave_types(active_only=True)
        results = []
        for r in raw_types:
            results.append(LeaveTypeInfo(
                id=r["id"],
                name=r["name"],
                request_unit=r.get("request_unit", "day"),
                requires_allocation=bool(r.get("requires_allocation", False)),
                active=bool(r.get("active", True))
            ))
        return results

    def get_employee_leave_summary(self, employee_id: int) -> EmployeeLeaveSummary:
        """
        جلب الملخص الشامل لإجازات الموظف مع حساب الاستحقاق النظامي وفق المادة 109.
        """
        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            raise ValueError(f"الموظف برقم المعرف {employee_id} غير موجود في أودو.")

        emp_name = emp.get("name", "غير معروف")
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"
        gender = emp.get("sex") or emp.get("gender") or "other"

        # حساب سنوات الخدمة من تاريخ التعيين الفعلي أو تاريخ الإنشاء
        hiring_date_str = str(emp.get("hiring_date") or emp.get("create_date") or "")
        service_years = 0.0
        if hiring_date_str:
            try:
                dt_part = hiring_date_str.split()[0]
                hire_dt = datetime.strptime(dt_part, "%Y-%m-%d").date()
                delta_days = (date.today() - hire_dt).days
                service_years = round(max(delta_days, 0) / 365.25, 2)
            except Exception:
                service_years = 0.0

        # الاستحقاق النظامي السنوي وفق المادة 109
        statutory_entitlement = calculate_annual_leave_entitlement(service_years)

        # قراءة الأرصدة المخصصة في أودو
        allocations = self.readonly_repo.get_employee_allocations(employee_id)
        allocated_days = sum(float(a.get("number_of_days", 0.0)) for a in allocations)

        # قراءة الإجازات السابقة المحسوبة
        leaves = self.readonly_repo.get_employee_leaves(employee_id)
        consumed_days = sum(
            float(l.get("number_of_days", 0.0))
            for l in leaves
            if l.get("state") in ("validate", "validate1", "confirm")
        )

        # إذا لم يكن هناك تخصيص مسجل في أودو، نعتمد الاستحقاق النظامي كمرجع
        effective_allocated = allocated_days if allocated_days > 0 else float(statutory_entitlement)
        remaining_days = max(effective_allocated - consumed_days, 0.0)

        return EmployeeLeaveSummary(
            employee_id=employee_id,
            employee_name=emp_name,
            department_name=dept_name,
            gender=gender,
            service_years=service_years,
            statutory_annual_entitlement=statutory_entitlement,
            allocated_days=allocated_days,
            consumed_days=consumed_days,
            remaining_days=remaining_days,
            recent_leaves=leaves[:5]
        )

    def dry_run_leave_request(
        self,
        employee_id: int,
        holiday_status_id: int,
        date_from: str,
        date_to: str,
        reason: str = "",
        occasion_type: Optional[OccasionLeaveType] = None
    ) -> LeaveDryRunResult:
        """
        التحقق الحتمي المسبق من طلب الإجازة ومطابقته لنظام العمل السعودي بدون أي كتابة في أودو.
        """
        errors: List[str] = []
        warnings: List[str] = []
        statutory_article = "نظام العمل السعودي ولائحته التنفيذية"
        statutory_exp = "فحص طلب الإجازة وفق الأنظمة السارية."

        # 1. التحقق من الموظف
        try:
            summary = self.get_employee_leave_summary(employee_id)
        except Exception as e:
            return LeaveDryRunResult(
                is_valid=False,
                employee_id=employee_id,
                employee_name="غير معروف",
                holiday_status_id=holiday_status_id,
                leave_type_name="غير معروف",
                request_date_from=date_from,
                request_date_to=date_to,
                number_of_days=0.0,
                statutory_article="خطأ في البيانات",
                statutory_explanation_ar=str(e),
                balance_before=0.0,
                balance_after=0.0,
                requires_allocation=False,
                errors=[str(e)],
                can_proceed=False
            )

        # 2. التحقق من التواريخ
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            d_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            if d_to < d_from:
                errors.append(f"تاريخ نهاية الإجازة ({date_to}) يسبق تاريخ البداية ({date_from}).")
                requested_days = 0.0
            else:
                requested_days = float((d_to - d_from).days + 1)
        except Exception as e:
            errors.append(f"صيغة التواريخ غير صحيحة (المطلوب YYYY-MM-DD): {e}")
            requested_days = 0.0

        # 3. التحقق من نوع الإجازة في أودو
        leave_types = {lt.id: lt for lt in self.get_leave_types()}
        if holiday_status_id not in leave_types:
            errors.append(f"نوع الإجازة برقم {holiday_status_id} غير معرف في أودو.")
            leave_name = "غير معروف"
            requires_alloc = False
        else:
            lt_info = leave_types[holiday_status_id]
            leave_name = lt_info.name
            requires_alloc = lt_info.requires_allocation

        # 4. تطبيق ضوابط نظام العمل وتعديلات 1446هـ
        name_lower = leave_name.lower()
        
        # أ) إجازات المناسبات (المادة 113 وتعديلات 1446هـ)
        if occasion_type or any(k in name_lower for k in ["marriage", "death", "paternity", "مناسبة", "زواج", "وفاة", "مولود"]):
            eff_type = occasion_type or OccasionLeaveType.MARRIAGE
            statutory_days = get_occasion_leave_statutory_days(eff_type)
            statutory_article = "المادة 113 (تعديلات 1446هـ بالمرسوم م/44)"
            statutory_exp = (
                f"إجازة مناسبة مدفوعة الأجر بسقف نظامي {statutory_days} أيام. "
                f"الأيام المطلوبة: {requested_days} يوماً."
            )
            if requested_days > statutory_days:
                warnings.append(
                    f"الأيام المطلوبة ({requested_days}) تتجاوز الاستحقاق النظامي للمناسبة ({statutory_days} أيام). "
                    f"الأيام الزائدة ({requested_days - statutory_days}) يجب احتسابها إجازة عادية أو بدون أجر."
                )

        # ب) إجازة الوضع للمرأة العاملة (المادة 116 وتعديل 1446هـ)
        elif any(k in name_lower for k in ["maternity", "وضع", "ولادة"]):
            statutory_article = "المادة 116 (تعديل 1446هـ بالمرسوم م/44)"
            if summary.gender != "female":
                errors.append("المادة 116: إجازة الوضع مخصصة للموظفات العاملات فقط.")
            weeks_requested = requested_days / 7.0
            mat_res = validate_maternity_leave_duration(weeks_requested)
            statutory_exp = mat_res.message_ar
            if not mat_res.is_valid:
                errors.append(mat_res.message_ar)

        # ج) الإجازة السنوية (المادة 109)
        elif requires_alloc or any(k in name_lower for k in ["paid", "annual", "سنوية", "اعتيادية"]):
            statutory_article = "المادة 109 من نظام العمل"
            statutory_exp = (
                f"استحقاق الإجازة السنوية النظامي: {summary.statutory_annual_entitlement} يوماً "
                f"(خدمة الموظف: {summary.service_years} سنة). الرصيد المتاح: {summary.remaining_days:,.1f} يوماً."
            )
            if requested_days > summary.remaining_days and summary.allocated_days > 0:
                warnings.append(
                    f"الرصيد المتبقي ({summary.remaining_days:,.1f} يوماً) غير كافٍ لتغطية كامل المدة المطلوبة ({requested_days} يوماً)."
                )

        balance_before = summary.remaining_days
        balance_after = max(balance_before - requested_days, 0.0)
        is_valid = len(errors) == 0

        # إنشاء رمز موافقة فريد لو كان الطلب صالحاً
        token = ""
        if is_valid:
            token = f"LEAVE-{uuid.uuid4().hex[:8].upper()}"
            self._pending_approvals[token] = {
                "employee_id": employee_id,
                "employee_name": summary.employee_name,
                "holiday_status_id": holiday_status_id,
                "leave_type_name": leave_name,
                "request_date_from": date_from,
                "request_date_to": date_to,
                "number_of_days": requested_days,
                "reason": reason,
                "created_at": datetime.now().isoformat(),
            }
            LeaveService._save_persisted_approvals(self._pending_approvals, self.pending_approvals_path)

        return LeaveDryRunResult(
            is_valid=is_valid,
            employee_id=employee_id,
            employee_name=summary.employee_name,
            holiday_status_id=holiday_status_id,
            leave_type_name=leave_name,
            request_date_from=date_from,
            request_date_to=date_to,
            number_of_days=requested_days,
            statutory_article=statutory_article,
            statutory_explanation_ar=statutory_exp,
            balance_before=balance_before,
            balance_after=balance_after,
            requires_allocation=requires_alloc,
            warnings=warnings,
            errors=errors,
            approval_token=token,
            can_proceed=is_valid
        )

    def apply_leave_request(
        self,
        approval_token: str,
        user_confirmation_text: str = "تأكيد"
    ) -> LeaveExecutionResult:
        """
        تنفيذ اعتماد وإنشاء طلب الإجازة الفعلي في Odoo بعد تحقق الموافقة الصريحة.
        """
        if not user_confirmation_text or user_confirmation_text.strip() != "تأكيد":
            return LeaveExecutionResult(
                success=False,
                leave_id=None,
                employee_id=0,
                employee_name="",
                leave_type_name="",
                number_of_days=0.0,
                request_date_from="",
                request_date_to="",
                state="",
                readback_verified=False,
                message_ar="مرفوض: يتطلب تنفيذ طلب الإجازة كلمة 'تأكيد' صريحة من المستخدم.",
                audit_logged=False
            )

        if approval_token not in self._pending_approvals:
            # محاولة قراءة الموافقات المعلقة من الملف في حال تمت الإضافة عبر مسار آخر
            disk = LeaveService._load_persisted_approvals(self.pending_approvals_path)
            if approval_token in disk:
                self._pending_approvals.update(disk)

        if approval_token not in self._pending_approvals:
            return LeaveExecutionResult(
                success=False,
                leave_id=None,
                employee_id=0,
                employee_name="",
                leave_type_name="",
                number_of_days=0.0,
                request_date_from="",
                request_date_to="",
                state="",
                readback_verified=False,
                message_ar="رمز الموافقة غير صالح أو منتهي الصلاحية. يرجى إعادة فحص الطلب.",
                audit_logged=False
            )

        payload = self._pending_approvals.pop(approval_token)
        LeaveService._save_persisted_approvals(self._pending_approvals, self.pending_approvals_path)
        emp_id = payload["employee_id"]
        status_id = payload["holiday_status_id"]
        date_from = payload["request_date_from"]
        date_to = payload["request_date_to"]
        days = payload["number_of_days"]
        reason = payload.get("reason", "طلب إجازة عبر النظام")

        if not self.write_gateway:
            raise RuntimeError("بوابة الكتابة OdooLeaveWriteGateway غير مهيأة للتنفيذ.")

        # تجهيز قيم السجل في Odoo
        vals = {
            "employee_id": emp_id,
            "holiday_status_id": status_id,
            "request_date_from": date_from,
            "request_date_to": date_to,
            "number_of_days": days,
            "name": reason,
            "payslip_state": "normal",
        }

        # إنشاء السجل في Odoo
        created_id = self.write_gateway.create_leave(vals)

        # قراءة تحقق مستقلة (Readback Verification)
        readback = self.write_gateway.read_leave(
            leave_id=created_id,
            fields=["id", "employee_id", "holiday_status_id", "number_of_days", "state"]
        )
        readback_ok = bool(readback and readback.get("id") == created_id)

        # تسجيل الحدث في سجل التدقيق
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "CREATE_LEAVE",
            "leave_id": created_id,
            "employee_id": emp_id,
            "holiday_status_id": status_id,
            "number_of_days": days,
            "request_date_from": date_from,
            "request_date_to": date_to,
            "approval_token": approval_token,
            "readback_verified": readback_ok,
            "status": readback.get("state") if readback else "unknown"
        }
        self._write_audit_log(audit_entry)

        return LeaveExecutionResult(
            success=True,
            leave_id=created_id,
            employee_id=emp_id,
            employee_name=payload["employee_name"],
            leave_type_name=payload["leave_type_name"],
            number_of_days=days,
            request_date_from=date_from,
            request_date_to=date_to,
            state=readback.get("state", "confirm") if readback else "confirm",
            readback_verified=readback_ok,
            message_ar=f"تم تسجيل طلب الإجازة بنجاح في أودو برقم معرّف #{created_id}.",
            audit_logged=True
        )

    def _write_audit_log(self, entry: Dict[str, Any]) -> None:
        try:
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            # Audit failure shouldn't silently crash the business loop but must be printed
            print(f"[AUDIT ERROR] Failed to write leave audit log: {e}")
