"""
خدمة إدارة الحضور والعمل الإضافي ونظام العمل السعودي (Attendance & Overtime Service)
===================================================================================
الطبقة التنفيذية لإدارة الحضور والانصراف في Odoo (hr.attendance) بالتكامل التام مع
محرك قواعد نظام العمل السعودي وتعديلات المواد 98 و 101 و 107.

تلتزم الخدمة بـ:
1. تطبيق ساعات العمل المعيارية (8 ساعات يومياً / 48 أسبوعياً، و 6 ساعات في رمضان للمسلمين م/98).
2. حساب أجر العمل الإضافي حتمياً وفق المادة 107 (أجر الساعة الفعلي + 50% من الأساسي = 1.5x).
3. فحص فترات الراحة الإلزامية وفق المادة 101 (حظر العمل المتصل لأكثر من 5 ساعات دون راحة).
4. مبدأ التحقق المزدوج Four-Eyes والتحقق المستقل بعد الكتابة (Readback Verification).
"""

from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, List, Optional

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_attendance_write_gateway import OdooAttendanceWriteGateway
from saudi_labor_law_rules import (
    calculate_overtime_pay,
    OvertimeCalculationResult,
    STANDARD_DAILY_WORKING_HOURS,
    RAMADAN_MUSLIM_DAILY_HOURS,
)


ATTENDANCE_AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "attendance_audit_log.jsonl")


@dataclass
class DailyAttendanceDetail:
    id: int
    date: str
    check_in: str
    check_out: Optional[str]
    worked_hours: float
    standard_hours: float
    overtime_hours: float
    is_open: bool


@dataclass
class AttendanceSummaryResult:
    employee_id: int
    employee_name: str
    department_name: str
    period_start: str
    period_end: str
    is_ramadan: bool
    is_muslim: bool
    total_days_worked: int
    total_worked_hours: float
    total_standard_hours: float
    total_overtime_hours: float
    basic_hourly_rate: float
    gross_hourly_rate: float
    overtime_compensation_sar: float
    statutory_article: str
    statutory_explanation_ar: str
    attendances: List[DailyAttendanceDetail] = field(default_factory=list)


@dataclass
class AttendanceDryRunResult:
    is_valid: bool
    employee_id: int
    employee_name: str
    date: str
    check_in: str
    check_out: str
    worked_hours: float
    standard_hours: float
    overtime_hours: float
    overtime_pay_sar: float
    statutory_article: str
    statutory_explanation_ar: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    approval_token: str = ""
    can_proceed: bool = False


@dataclass
class AttendanceExecutionResult:
    success: bool
    attendance_id: Optional[int]
    employee_id: int
    employee_name: str
    action_type: str  # CHECK_IN, CHECK_OUT, CREATE_RECORD
    timestamp_recorded: str
    worked_hours: float
    overtime_hours: float
    readback_verified: bool
    message_ar: str
    audit_logged: bool


class AttendanceService:
    _shared_pending_approvals: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        readonly_repo: Optional[OdooReadonlyRepository] = None,
        write_gateway: Optional[OdooAttendanceWriteGateway] = None,
        audit_log_path: Optional[str] = None
    ):
        self.readonly_repo = readonly_repo or OdooReadonlyRepository()
        self.write_gateway = write_gateway
        self.audit_log_path = audit_log_path or ATTENDANCE_AUDIT_LOG_FILE
        self._pending_approvals: Dict[str, Dict[str, Any]] = AttendanceService._shared_pending_approvals

    def get_attendance_summary(
        self,
        employee_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        is_ramadan: bool = False,
        is_muslim: bool = True,
        basic_wage: float = 6000.0,
        gross_wage: float = 9000.0,
        limit: int = 50
    ) -> AttendanceSummaryResult:
        """
        جلب وتلخيص سجلات حضور الموظف وحساب ساعات وأجر العمل الإضافي وفق المادتين 98 و 107.
        """
        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            raise ValueError(f"الموظف برقم المعرف #{employee_id} غير موجود في أودو.")

        emp_name = emp.get("name", "غير معروف")
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"

        records = self.readonly_repo.get_employee_attendances(
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit
        )

        daily_std = RAMADAN_MUSLIM_DAILY_HOURS if (is_ramadan and is_muslim) else STANDARD_DAILY_WORKING_HOURS

        total_worked = 0.0
        total_std = 0.0
        total_ot = 0.0
        daily_details: List[DailyAttendanceDetail] = []

        for r in records:
            w_hours = round(float(r.get("worked_hours") or 0.0), 2)
            c_in = str(r.get("check_in") or "")
            c_out = str(r.get("check_out") or "") if r.get("check_out") else None
            is_open = c_out is None

            # إذا كان السجل مفتوحاً ولا يوجد check_out بعد
            if is_open and c_in:
                try:
                    cin_dt = datetime.strptime(c_in.split(".")[0], "%Y-%m-%d %H:%M:%S")
                    now_utc = datetime.utcnow()
                    w_hours = round(max((now_utc - cin_dt).total_seconds() / 3600.0, 0.0), 2)
                except Exception:
                    w_hours = 0.0

            # حساب الساعات الإضافية
            std_for_day = min(w_hours, daily_std)
            ot_for_day = round(max(w_hours - daily_std, 0.0), 2)

            total_worked += w_hours
            total_std += std_for_day
            total_ot += ot_for_day

            daily_details.append(DailyAttendanceDetail(
                id=r["id"],
                date=str(r.get("date") or c_in.split()[0] if c_in else ""),
                check_in=c_in,
                check_out=c_out,
                worked_hours=w_hours,
                standard_hours=std_for_day,
                overtime_hours=ot_for_day,
                is_open=is_open
            ))

        total_worked = round(total_worked, 2)
        total_std = round(total_std, 2)
        total_ot = round(total_ot, 2)

        # حساب الأجر المالي للأوفرتايم وفق المادة 107
        ot_calc = calculate_overtime_pay(
            basic_wage=basic_wage,
            gross_wage=gross_wage,
            overtime_hours=total_ot,
            monthly_standard_hours=240.0
        )

        statutory_art = "المواد 98 و 107 من نظام العمل السعودي"
        explanation = (
            f"ساعات العمل المعيارية: {daily_std} ساعات/يوم "
            f"({'تطبيق ساعات رمضان 6 ساعات م/98' if (is_ramadan and is_muslim) else 'المعيار القياسي 8 ساعات م/98'}). "
            f"إجمالي الساعات الفعلية: {total_worked:,.1f} ساعة، منها {total_ot:,.1f} ساعة إضافية. "
            f"مستحق الأوفرتايم: {ot_calc.total_overtime_pay:,.2f} ر.س بموجب علاوة الـ 50% (المادة 107)."
        )

        return AttendanceSummaryResult(
            employee_id=employee_id,
            employee_name=emp_name,
            department_name=dept_name,
            period_start=date_from or (daily_details[-1].date if daily_details else ""),
            period_end=date_to or (daily_details[0].date if daily_details else ""),
            is_ramadan=is_ramadan,
            is_muslim=is_muslim,
            total_days_worked=len(daily_details),
            total_worked_hours=total_worked,
            total_standard_hours=total_std,
            total_overtime_hours=total_ot,
            basic_hourly_rate=ot_calc.basic_hourly_rate,
            gross_hourly_rate=ot_calc.gross_hourly_rate,
            overtime_compensation_sar=ot_calc.total_overtime_pay,
            statutory_article=statutory_art,
            statutory_explanation_ar=explanation,
            attendances=daily_details
        )

    def dry_run_attendance_entry(
        self,
        employee_id: int,
        date_str: str,
        check_in_str: str,
        check_out_str: str,
        is_ramadan: bool = False,
        is_muslim: bool = True,
        basic_wage: float = 6000.0,
        gross_wage: float = 9000.0
    ) -> AttendanceDryRunResult:
        """
        فحص تجريبي مسبق لحركة حضور وانصراف وحساب استحقاق الأوفرتايم قبل الكتابة في Odoo.
        """
        errors: List[str] = []
        warnings: List[str] = []

        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            return AttendanceDryRunResult(
                is_valid=False,
                employee_id=employee_id,
                employee_name="غير معروف",
                date=date_str,
                check_in=check_in_str,
                check_out=check_out_str,
                worked_hours=0.0,
                standard_hours=0.0,
                overtime_hours=0.0,
                overtime_pay_sar=0.0,
                statutory_article="خطأ بيانات",
                statutory_explanation_ar="الموظف غير موجود في Odoo.",
                errors=["الموظف غير موجود"],
                can_proceed=False
            )

        emp_name = emp.get("name", "غير معروف")

        # التحقق من صحة التواريخ والتوقيت
        try:
            # support formats: 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD HH:MM'
            cin_dt = datetime.strptime(check_in_str.split(".")[0], "%Y-%m-%d %H:%M:%S" if len(check_in_str) > 16 else "%Y-%m-%d %H:%M")
            cout_dt = datetime.strptime(check_out_str.split(".")[0], "%Y-%m-%d %H:%M:%S" if len(check_out_str) > 16 else "%Y-%m-%d %H:%M")

            if cout_dt <= cin_dt:
                errors.append(f"وقت الانصراف ({check_out_str}) يجب أن يكون بعد وقت الحضور ({check_in_str}).")
                worked_hours = 0.0
            else:
                worked_hours = round((cout_dt - cin_dt).total_seconds() / 3600.0, 2)
        except Exception as exc:
            errors.append(f"صيغة التوقيت غير صحيحة (المطلوب YYYY-MM-DD HH:MM:SS): {exc}")
            worked_hours = 0.0

        daily_std = RAMADAN_MUSLIM_DAILY_HOURS if (is_ramadan and is_muslim) else STANDARD_DAILY_WORKING_HOURS
        std_hours = min(worked_hours, daily_std)
        ot_hours = round(max(worked_hours - daily_std, 0.0), 2)

        # المادة 101: فحص فترات الراحة
        if worked_hours > 5.0:
            warnings.append(
                "المادة 101 من نظام العمل: لا يجوز تشغيل العامل أكثر من 5 ساعات متصلة دون فترة راحة لا تقل عن نصف ساعة."
            )

        # المادة 107: حساب أجر الأوفرتايم
        ot_res = calculate_overtime_pay(
            basic_wage=basic_wage,
            gross_wage=gross_wage,
            overtime_hours=ot_hours,
            monthly_standard_hours=240.0
        )

        statutory_art = "المادتان 98 و 107 من نظام العمل السعودي"
        explanation = (
            f"ساعات الدوام اليومي {worked_hours} ساعة "
            f"(معيار اليوم: {daily_std} ساعات). "
            f"الساعات الإضافية: {ot_hours} ساعة بقيمة مستحقة {ot_res.total_overtime_pay:,.2f} ر.س."
        )

        is_valid = len(errors) == 0
        token = ""
        if is_valid:
            token = f"ATTEND-{uuid.uuid4().hex[:8].upper()}"
            self._pending_approvals[token] = {
                "employee_id": employee_id,
                "employee_name": emp_name,
                "date": date_str,
                "check_in": check_in_str,
                "check_out": check_out_str,
                "worked_hours": worked_hours,
                "overtime_hours": ot_hours,
                "overtime_pay": ot_res.total_overtime_pay,
            }

        return AttendanceDryRunResult(
            is_valid=is_valid,
            employee_id=employee_id,
            employee_name=emp_name,
            date=date_str,
            check_in=check_in_str,
            check_out=check_out_str,
            worked_hours=worked_hours,
            standard_hours=std_hours,
            overtime_hours=ot_hours,
            overtime_pay_sar=ot_res.total_overtime_pay,
            statutory_article=statutory_art,
            statutory_explanation_ar=explanation,
            warnings=warnings,
            errors=errors,
            approval_token=token,
            can_proceed=is_valid
        )

    def record_check_in(
        self,
        employee_id: int,
        confirmation_text: str = "تأكيد"
    ) -> AttendanceExecutionResult:
        """
        تسجيل حركة حضور فورية (Check-In) لموظف مع منع التكرار إذا كان مسجلاً حضوراً بالفعل.
        """
        if confirmation_text != "تأكيد":
            return AttendanceExecutionResult(
                success=False,
                attendance_id=None,
                employee_id=employee_id,
                employee_name="",
                action_type="CHECK_IN",
                timestamp_recorded="",
                worked_hours=0.0,
                overtime_hours=0.0,
                readback_verified=False,
                message_ar="مرفوض: يتطلب تسجيل الحضور كلمة 'تأكيد' صريحة من المستخدم.",
                audit_logged=False
            )

        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            raise ValueError(f"الموظف #{employee_id} غير موجود في Odoo.")
        emp_name = emp.get("name", "غير معروف")

        # التحقق من عدم وجود تسجيل حضور مفتوح
        active_att = self.readonly_repo.get_employee_current_attendance(employee_id)
        if active_att:
            cin_time = active_att.get("check_in", "")
            return AttendanceExecutionResult(
                success=False,
                attendance_id=active_att["id"],
                employee_id=employee_id,
                employee_name=emp_name,
                action_type="CHECK_IN",
                timestamp_recorded=cin_time,
                worked_hours=0.0,
                overtime_hours=0.0,
                readback_verified=False,
                message_ar=f"الموظف مسجل حضور بالفعل ومفتوح منذ {cin_time}. يجب تسجيل الانصراف أولاً.",
                audit_logged=False
            )

        if not self.write_gateway:
            raise RuntimeError("بوابة كتابة الحضور OdooAttendanceWriteGateway غير مهيأة.")

        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        created_id = self.write_gateway.check_in(employee_id=employee_id, check_in_dt=now_dt)

        # Readback verification
        readback = self.write_gateway.read_attendance(
            attendance_id=created_id,
            fields=["id", "employee_id", "check_in", "check_out"]
        )
        readback_ok = bool(readback and readback.get("id") == created_id)

        # Audit log
        self._write_audit_log({
            "timestamp": now_str,
            "action": "CHECK_IN",
            "attendance_id": created_id,
            "employee_id": employee_id,
            "readback_verified": readback_ok,
        })

        return AttendanceExecutionResult(
            success=True,
            attendance_id=created_id,
            employee_id=employee_id,
            employee_name=emp_name,
            action_type="CHECK_IN",
            timestamp_recorded=now_str,
            worked_hours=0.0,
            overtime_hours=0.0,
            readback_verified=readback_ok,
            message_ar=f"تم تسجيل حضور الموظف {emp_name} بنجاح في Odoo (سجل #{created_id}).",
            audit_logged=True
        )

    def record_check_out(
        self,
        employee_id: int,
        confirmation_text: str = "تأكيد"
    ) -> AttendanceExecutionResult:
        """
        تسجيل حركة انصراف فورية (Check-Out) لسجل الحضور المفتوح حالياً للموظف.
        """
        if confirmation_text != "تأكيد":
            return AttendanceExecutionResult(
                success=False,
                attendance_id=None,
                employee_id=employee_id,
                employee_name="",
                action_type="CHECK_OUT",
                timestamp_recorded="",
                worked_hours=0.0,
                overtime_hours=0.0,
                readback_verified=False,
                message_ar="مرفوض: يتطلب تسجيل الانصراف كلمة 'تأكيد' صريحة من المستخدم.",
                audit_logged=False
            )

        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            raise ValueError(f"الموظف #{employee_id} غير موجود في Odoo.")
        emp_name = emp.get("name", "غير معروف")

        # البحث عن السجل المفتوح
        active_att = self.readonly_repo.get_employee_current_attendance(employee_id)
        if not active_att:
            return AttendanceExecutionResult(
                success=False,
                attendance_id=None,
                employee_id=employee_id,
                employee_name=emp_name,
                action_type="CHECK_OUT",
                timestamp_recorded="",
                worked_hours=0.0,
                overtime_hours=0.0,
                readback_verified=False,
                message_ar=f"لا يوجد تسجيل حضور مفتوح للموظف {emp_name} لتسجيل الانصراف منه.",
                audit_logged=False
            )

        if not self.write_gateway:
            raise RuntimeError("بوابة كتابة الحضور OdooAttendanceWriteGateway غير مهيأة.")

        att_id = active_att["id"]
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        self.write_gateway.check_out(attendance_id=att_id, check_out_dt=now_dt)

        # Readback verification
        readback = self.write_gateway.read_attendance(
            attendance_id=att_id,
            fields=["id", "employee_id", "check_in", "check_out", "worked_hours"]
        )
        readback_ok = bool(readback and readback.get("check_out"))
        w_hours = float(readback.get("worked_hours") or 0.0) if readback else 0.0
        ot_hours = max(w_hours - STANDARD_DAILY_WORKING_HOURS, 0.0)

        # Audit log
        self._write_audit_log({
            "timestamp": now_str,
            "action": "CHECK_OUT",
            "attendance_id": att_id,
            "employee_id": employee_id,
            "worked_hours": w_hours,
            "readback_verified": readback_ok,
        })

        return AttendanceExecutionResult(
            success=True,
            attendance_id=att_id,
            employee_id=employee_id,
            employee_name=emp_name,
            action_type="CHECK_OUT",
            timestamp_recorded=now_str,
            worked_hours=round(w_hours, 2),
            overtime_hours=round(ot_hours, 2),
            readback_verified=readback_ok,
            message_ar=f"تم تسجيل انصراف الموظف {emp_name} بنجاح (ساعات العمل: {w_hours:,.2f} ساعة).",
            audit_logged=True
        )

    def apply_attendance_entry(
        self,
        approval_token: str,
        confirmation_text: str = "تأكيد"
    ) -> AttendanceExecutionResult:
        """
        اعتماد وتسجيل حركة حضور تاريخية كاملة بعد الفحص التجريبي المسبق وتأكيد المستخدم.
        """
        if confirmation_text != "تأكيد":
            return AttendanceExecutionResult(
                success=False,
                attendance_id=None,
                employee_id=0,
                employee_name="",
                action_type="CREATE_RECORD",
                timestamp_recorded="",
                worked_hours=0.0,
                overtime_hours=0.0,
                readback_verified=False,
                message_ar="مرفوض: يتطلب اعتماد السجل كلمة 'تأكيد' صريحة.",
                audit_logged=False
            )

        if approval_token not in self._pending_approvals:
            return AttendanceExecutionResult(
                success=False,
                attendance_id=None,
                employee_id=0,
                employee_name="",
                action_type="CREATE_RECORD",
                timestamp_recorded="",
                worked_hours=0.0,
                overtime_hours=0.0,
                readback_verified=False,
                message_ar="رمز الموافقة غير صالح أو منتهي.",
                audit_logged=False
            )

        payload = self._pending_approvals.pop(approval_token)
        emp_id = payload["employee_id"]

        if not self.write_gateway:
            raise RuntimeError("بوابة كتابة الحضور OdooAttendanceWriteGateway غير مهيأة.")

        vals = {
            "employee_id": emp_id,
            "date": payload["date"],
            "check_in": payload["check_in"],
            "check_out": payload["check_out"],
        }

        created_id = self.write_gateway.create_attendance_record(vals)

        # Readback verification
        readback = self.write_gateway.read_attendance(
            attendance_id=created_id,
            fields=["id", "employee_id", "check_in", "check_out", "worked_hours"]
        )
        readback_ok = bool(readback and readback.get("id") == created_id)

        # Audit log
        self._write_audit_log({
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "CREATE_RECORD",
            "attendance_id": created_id,
            "employee_id": emp_id,
            "token": approval_token,
            "readback_verified": readback_ok,
        })

        return AttendanceExecutionResult(
            success=True,
            attendance_id=created_id,
            employee_id=emp_id,
            employee_name=payload["employee_name"],
            action_type="CREATE_RECORD",
            timestamp_recorded=payload["date"],
            worked_hours=payload["worked_hours"],
            overtime_hours=payload["overtime_hours"],
            readback_verified=readback_ok,
            message_ar=f"تم تسجيل حركة الدوام بنجاح في Odoo (سجل #{created_id}).",
            audit_logged=True
        )

    def _write_audit_log(self, entry: Dict[str, Any]) -> None:
        try:
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[AUDIT ERROR] Failed to write attendance audit log: {e}")
