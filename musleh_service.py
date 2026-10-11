"""
خدمة وكيل الإصلاح الذاتي والتعافي: «مصلح» (Musleh Self-Healing & Diagnostic Agent)
================================================================================
يقوم «مصلح» بالتحقيق في الصفوف المعطوبة (needs_review و rejected حصراً)،
وإدارة سلسلة المشاورة التشخيصية مع:
- «فاحص» (Fahas): استعلام مراجع Odoo الحية والمؤرشفة.
- «موفق» (Muwaffaq): المطابقة الضبابية (Fuzzy Matching) واقتراح البدائل.
- «مدقق» (Mudaqqiq): التحقق من الامتثال لنظام العمل السعودي.
- «لايا» (Laya): القرار السريع وتصنيف المجال وحواجز الأمان (Four-Eyes & Deletion Guard).

ثم يصدر مصلح واحداً من 4 قرارات تنفيذية محددة:
1. APPLY_AUTO_PATCH: الإصلاح والتمرير الفوري إذا كانت الثقة >= 90% وخيار الإصلاح التلقائي مفعّل.
2. QUARANTINE_AND_PROCEED: عزل الصف المعطوب لتفادي تعطيل الدفعة.
3. PROPOSE_MISSING_ENTITY: اقتراح تأسيس القسم أو المسمى المفقود في Odoo مسبقاً.
4. ESCALATE_TO_HUMAN: الإحالة للمسؤول البشري عبر «سراج» (Seraj) مع خيارات تفاعلية محددة.

صممت المنظومة مع حظر كامل للمساس بالهويات الشخصية والإقامات تلقائياً (خط أحمر).
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher, get_close_matches
from typing import Any, Dict, List, Optional, Tuple

from failure_codes import (
    ARCHIVED_REFERENCE_MATCH,
    DUPLICATE_EXISTING_EMPLOYEE,
    DUPLICATE_IN_FILE,
    INVALID_WORK_EMAIL,
    REFERENCE_AMBIGUOUS,
    REFERENCE_NOT_FOUND,
    UNVERIFIED_NO_EMAIL,
    VALIDATION_ERROR,
)
from normalization import (
    clean_value_text,
    is_valid_email_format,
    normalize_date_text,
    reference_match_key,
)
from laya_service import LayaService
from saudi_labor_law_rules import (
    PROBATION_EXTENDED_DAYS_MAX,
    PROBATION_STANDARD_DAYS_MAX,
)
from sijil_audit_service import SijilAuditService


# =============================================================================
# 1. ثوابت قرارات مصلح التنفيذية (Executive Decision Constants)
# =============================================================================

DECISION_APPLY_AUTO_PATCH = "APPLY_AUTO_PATCH"
DECISION_QUARANTINE_AND_PROCEED = "QUARANTINE_AND_PROCEED"
DECISION_PROPOSE_MISSING_ENTITY = "PROPOSE_MISSING_ENTITY"
DECISION_ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"

CONFIDENCE_THRESHOLD_AUTO_REPAIR = 0.90  # عتبة الثقة الإلزامية للإصلاح التلقائي (90%)


@dataclass
class ActionableOption:
    """خيار تفاعلي جاهز للمسؤول البشري للاعتماد بنقرة زر."""
    option_id: str
    title_ar: str
    action_type: str
    patch_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "title_ar": self.title_ar,
            "action_type": self.action_type,
            "patch_payload": self.patch_payload,
        }


@dataclass
class SerajEscalationPacket:
    """حزمة الإحالة الرسمية المرفوعة من مصلح إلى سراج للمسؤول البشري."""
    excel_row_number: int
    employee_name: str
    failure_code: str
    verdict_ar: str
    consultation_summary: Dict[str, Any]
    actionable_options: List[ActionableOption]
    escalated_to: str = "seraj_orchestrator"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "excel_row_number": self.excel_row_number,
            "employee_name": self.employee_name,
            "failure_code": self.failure_code,
            "verdict_ar": self.verdict_ar,
            "consultation_summary": self.consultation_summary,
            "actionable_options": [opt.to_dict() for opt in self.actionable_options],
            "escalated_to": self.escalated_to,
        }


@dataclass
class MuslehDecisionResult:
    """القرار التنفيذي النهائي الصادر من وكيل مصلح."""
    excel_row_number: int
    original_status: str
    final_status: str
    decision: str
    decision_ar: str
    verdict_ar: str
    confidence: float
    patched_fields: Dict[str, Any]
    patched_row: Optional[Dict[str, Any]]
    consultation_log: Dict[str, Any]
    escalation_packet: Optional[SerajEscalationPacket] = None
    is_auto_repaired: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "excel_row_number": self.excel_row_number,
            "original_status": self.original_status,
            "final_status": self.final_status,
            "decision": self.decision,
            "decision_ar": self.decision_ar,
            "verdict_ar": self.verdict_ar,
            "confidence": self.confidence,
            "patched_fields": self.patched_fields,
            "patched_row": self.patched_row,
            "consultation_log": self.consultation_log,
            "escalation_packet": self.escalation_packet.to_dict() if self.escalation_packet else None,
            "is_auto_repaired": self.is_auto_repaired,
        }


class MuslehService:
    """
    الواجهة التنفيذية لوكيل الإصلاح الذاتي وحل المشكلات: «مصلح» (Musleh Engine).
    """

    def __init__(
        self,
        repository=None,
        laya_service: Optional[LayaService] = None,
        audit_service: Optional[SijilAuditService] = None,
    ):
        self.repository = repository
        self.laya = laya_service or LayaService()
        self.audit = audit_service or SijilAuditService()

    # =========================================================================
    # 1. الدخول الصارم وفحص الصف (Strict Entry Point)
    # =========================================================================

    def diagnose_and_heal_row(
        self,
        row: Dict[str, Any],
        validation_result: Dict[str, Any],
        live_snapshot: Optional[Dict[str, Any]] = None,
        auto_repair: bool = False,
    ) -> Optional[MuslehDecisionResult]:
        """
        فحص الصف المعطوب واتخاذ القرار العلاجي المناسب.
        صمام الأمان: يتجاوز الصف فوراً إذا كان 'accepted'.
        """
        original_status = validation_result.get("final_status")

        # 1. قيد الدخول الصارم: مصلح لا يتدخل إلا في needs_review و rejected
        if original_status not in ("needs_review", "rejected"):
            return None

        excel_row_number = row.get("excel_row_number", validation_result.get("excel_row_number", 0))
        fields = row.get("fields", {})
        failure_code = validation_result.get("failure_code", "")
        reasons = validation_result.get("reasons", [])

        # استخراج المراجع الحية إن توفرت
        if live_snapshot is None and self.repository is not None:
            try:
                live_snapshot = self.repository.get_live_reference_snapshot()
            except Exception:
                live_snapshot = {"companies": [], "departments": [], "jobs": []}
        elif live_snapshot is None:
            live_snapshot = {"companies": [], "departments": [], "jobs": []}

        # 2. إدارة سلسلة المشاورة التشخيصية الرباعية
        consultation = self._run_consultation(row, validation_result, live_snapshot)

        # 3. اتخاذ القرار التنفيذي بناءً على نتائج المشاورة
        decision_result = self._make_executive_decision(
            row=row,
            validation_result=validation_result,
            consultation=consultation,
            auto_repair=auto_repair,
        )

        # 4. توثيق القرار في دفتر التدقيق (سجل) إذا تم الإصلاح
        if decision_result.is_auto_repaired:
            try:
                self.audit.record_event(
                    action="musleh_auto_repair",
                    actor="musleh_self_healing_agent",
                    details={
                        "excel_row_number": excel_row_number,
                        "decision": decision_result.decision,
                        "patched_fields": decision_result.patched_fields,
                        "confidence": decision_result.confidence,
                    },
                    status="success",
                )
            except Exception:
                pass

        return decision_result

    # =========================================================================
    # 2. حلقة المشاورة التشخيصية (Consultation Workflow)
    # =========================================================================

    def _run_consultation(
        self,
        row: Dict[str, Any],
        validation_result: Dict[str, Any],
        live_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        استشارة الوكلاء الأربعة: فاحص، موفق، مدقق، ولايا.
        """
        fields = row.get("fields", {})
        company_val = fields.get("company", {}).get("value", "")
        department_val = fields.get("department", {}).get("value", "")
        job_val = fields.get("job", {}).get("value", "")
        name_val = fields.get("name", {}).get("value", "")
        hiring_date_val = fields.get("hiring_date", {}).get("value", "")
        email_val = fields.get("work_email", {}).get("value", "")
        mobile_val = fields.get("mobile_phone", {}).get("value", "")

        companies = live_snapshot.get("companies", [])
        departments = live_snapshot.get("departments", [])
        jobs = live_snapshot.get("jobs", [])

        # ---------------------------------------------------------
        # أ. استشارة «فاحص» (Fahas): فحص السجلات المباشرة والمؤرشفة
        # ---------------------------------------------------------
        fahas_report = {
            "company_exists": False,
            "company_archived": False,
            "department_exists": False,
            "department_archived": False,
            "job_exists": False,
            "job_archived": False,
            "matched_company_id": None,
        }

        # فحص الشركة
        for c in companies:
            if reference_match_key(c.get("name") or "") == reference_match_key(company_val):
                fahas_report["company_exists"] = True
                fahas_report["company_archived"] = (c.get("active") is False)
                fahas_report["matched_company_id"] = c.get("id")
                break

        comp_id = fahas_report["matched_company_id"]

        # فحص القسم
        if department_val:
            for d in departments:
                d_comp = d.get("company_id")
                d_cid = d_comp[0] if isinstance(d_comp, (list, tuple)) else d_comp
                if comp_id and d_cid and d_cid != comp_id:
                    continue
                if reference_match_key(d.get("complete_name") or "") == reference_match_key(department_val):
                    fahas_report["department_exists"] = True
                    fahas_report["department_archived"] = (d.get("active") is False)
                    break

        # فحص المسمى
        if job_val:
            for j in jobs:
                j_comp = j.get("company_id")
                j_cid = j_comp[0] if isinstance(j_comp, (list, tuple)) else j_comp
                if comp_id and j_cid and j_cid != comp_id:
                    continue
                if reference_match_key(j.get("name") or "") == reference_match_key(job_val):
                    fahas_report["job_exists"] = True
                    fahas_report["job_archived"] = (j.get("active") is False)
                    break

        # ---------------------------------------------------------
        # ب. استشارة «موفق» (Muwaffaq): المطابقة الضبابية
        # ---------------------------------------------------------
        muwaffaq_report = {
            "suggested_department": None,
            "department_confidence": 0.0,
            "suggested_job": None,
            "job_confidence": 0.0,
        }

        if department_val and not fahas_report["department_exists"]:
            valid_dept_names = [
                d.get("complete_name") or ""
                for d in departments
                if (not comp_id or (isinstance(d.get("company_id"), (list, tuple)) and d.get("company_id")[0] == comp_id))
            ]
            sug, conf = self._find_fuzzy_match(department_val, valid_dept_names)
            muwaffaq_report["suggested_department"] = sug
            muwaffaq_report["department_confidence"] = conf

        if job_val and not fahas_report["job_exists"]:
            valid_job_names = [
                j.get("name") or ""
                for j in jobs
                if (not comp_id or (isinstance(j.get("company_id"), (list, tuple)) and j.get("company_id")[0] == comp_id))
            ]
            sug, conf = self._find_fuzzy_match(job_val, valid_job_names)
            muwaffaq_report["suggested_job"] = sug
            muwaffaq_report["job_confidence"] = conf

        # ---------------------------------------------------------
        # ج. استشارة «مدقق» (Mudaqqiq): الامتثال لنظام العمل
        # ---------------------------------------------------------
        mudaqqiq_report = {
            "is_statutorily_compliant": True,
            "labor_law_notes": [],
        }

        # فحص صيغة تاريخ التعيين
        date_fix = self.heal_date_format(hiring_date_val)
        if hiring_date_val and not date_fix:
            mudaqqiq_report["is_statutorily_compliant"] = False
            mudaqqiq_report["labor_law_notes"].append("تاريخ التعيين غير صحيح أو خارج النطاق المنطقي لنظام العمل.")

        # ---------------------------------------------------------
        # د. استشارة «لايا» (Laya): القرار السريع وحواجز الأمان
        # ---------------------------------------------------------
        laya_query = f"إدخال موظف جديد {name_val} شركة {company_val} قسم {department_val}"
        laya_res = self.laya.triage_request(laya_query)
        laya_report = {
            "domain": laya_res.domain,
            "action_type": laya_res.action_type,
            "requires_four_eyes": laya_res.requires_four_eyes,
            "is_deletion_blocked": laya_res.is_deletion_blocked,
        }

        return {
            "fahas": fahas_report,
            "muwaffaq": muwaffaq_report,
            "mudaqqiq": mudaqqiq_report,
            "laya": laya_report,
        }

    # =========================================================================
    # 3. صناعة القرارات التنفيذية الأربعة
    # =========================================================================

    def _make_executive_decision(
        self,
        row: Dict[str, Any],
        validation_result: Dict[str, Any],
        consultation: Dict[str, Any],
        auto_repair: bool,
    ) -> MuslehDecisionResult:
        """
        صياغة القرار التنفيذي الحاسم: إصلاح فوري، عزل، تأسيس كيان، أو إحالة لسراج.
        """
        excel_row_number = row.get("excel_row_number", validation_result.get("excel_row_number", 0))
        fields = row.get("fields", {})
        name_val = fields.get("name", {}).get("value", "موظف")
        failure_code = validation_result.get("failure_code", "")
        original_status = validation_result.get("final_status", "needs_review")

        fahas = consultation["fahas"]
        muwaffaq = consultation["muwaffaq"]
        mudaqqiq = consultation["mudaqqiq"]
        laya = consultation["laya"]

        patched_fields: Dict[str, Any] = {}
        patches_to_apply = []
        overall_confidence = 1.0

        # خط أحمر: لا مساس بالهويات الوطنية أو التكرار الصريح للهويات
        if failure_code in (DUPLICATE_EXISTING_EMPLOYEE, DUPLICATE_IN_FILE):
            # يرفع لسراج فوراً للمسؤول البشري
            return self._build_escalate_decision(
                row=row,
                validation_result=validation_result,
                consultation=consultation,
                verdict_ar=f"رصد تشابه أو تكرار محتمل للموظف '{name_val}'. الهويات خط أحمر لا تُعدل آلياً.",
                options=[
                    ActionableOption(
                        option_id="confirm_new_hire",
                        title_ar="تأكيد أنه موظف جديد واعتماده",
                        action_type="override_accept",
                    ),
                    ActionableOption(
                        option_id="quarantine_row",
                        title_ar="عزل الصف واستبعاد الموظف من هذه الدفعة",
                        action_type="quarantine",
                    ),
                ],
            )

        # فحص إصلاح التواريخ
        hiring_date_val = fields.get("hiring_date", {}).get("value", "")
        if hiring_date_val:
            healed_date = self.heal_date_format(hiring_date_val)
            if healed_date and healed_date != hiring_date_val:
                patched_fields["hiring_date"] = healed_date
                patches_to_apply.append(("hiring_date", healed_date))

        # فحص إصلاح الهاتف
        mobile_val = fields.get("mobile_phone", {}).get("value", "")
        if mobile_val:
            healed_mobile = self.heal_phone_format(mobile_val)
            if healed_mobile and healed_mobile != mobile_val:
                patched_fields["mobile_phone"] = healed_mobile
                patches_to_apply.append(("mobile_phone", healed_mobile))

        # فحص إصلاح البريد الإلكتروني
        email_val = fields.get("work_email", {}).get("value", "")
        if email_val:
            healed_email = self.heal_email_format(email_val)
            if healed_email and healed_email != email_val:
                patched_fields["work_email"] = healed_email
                patches_to_apply.append(("work_email", healed_email))

        # فحص إصلاح القسم
        dept_val = fields.get("department", {}).get("value", "")
        if dept_val and not fahas["department_exists"]:
            sug_dept = muwaffaq["suggested_department"]
            dept_conf = muwaffaq["department_confidence"]
            overall_confidence = min(overall_confidence, dept_conf)
            if sug_dept and dept_conf >= 0.80:
                patched_fields["department"] = sug_dept
                patches_to_apply.append(("department", sug_dept))

        # فحص إصلاح المسمى
        job_val = fields.get("job", {}).get("value", "")
        if job_val and not fahas["job_exists"]:
            sug_job = muwaffaq["suggested_job"]
            job_conf = muwaffaq["job_confidence"]
            overall_confidence = min(overall_confidence, job_conf)
            if sug_job and job_conf >= 0.80:
                patched_fields["job"] = sug_job
                patches_to_apply.append(("job", sug_job))

        # -----------------------------------------------------------------
        # القرار 1: تطبيق الإصلاح التلقائي (APPLY_AUTO_PATCH)
        # -----------------------------------------------------------------
        can_auto_patch = (
            auto_repair
            and patched_fields
            and overall_confidence >= CONFIDENCE_THRESHOLD_AUTO_REPAIR
            and mudaqqiq["is_statutorily_compliant"]
        )

        if can_auto_patch:
            patched_row = copy.deepcopy(row)
            for f_name, f_val in patches_to_apply:
                if f_name in patched_row.get("fields", {}):
                    patched_row["fields"][f_name]["value"] = f_val
                    patched_row["fields"][f_name]["match_key"] = reference_match_key(str(f_val))

            return MuslehDecisionResult(
                excel_row_number=excel_row_number,
                original_status=original_status,
                final_status="accepted",
                decision=DECISION_APPLY_AUTO_PATCH,
                decision_ar="تطبيق الإصلاح والتمرير الفوري",
                verdict_ar=f"تم تصحيح الحقول {list(patched_fields.keys())} تلقائياً بثقة {int(overall_confidence*100)}%.",
                confidence=overall_confidence,
                patched_fields=patched_fields,
                patched_row=patched_row,
                consultation_log=consultation,
                is_auto_repaired=True,
            )

        # -----------------------------------------------------------------
        # القرار 3: اقتراح تأسيس كيان مفقود (PROPOSE_MISSING_ENTITY)
        # -----------------------------------------------------------------
        if (
            (dept_val and not fahas["department_exists"] and muwaffaq["department_confidence"] < 0.60)
            or (job_val and not fahas["job_exists"] and muwaffaq["job_confidence"] < 0.60)
        ):
            missing_name = dept_val if not fahas["department_exists"] else job_val
            entity_type = "قسم" if not fahas["department_exists"] else "مسمى وظيفي"
            return MuslehDecisionResult(
                excel_row_number=excel_row_number,
                original_status=original_status,
                final_status="needs_review",
                decision=DECISION_PROPOSE_MISSING_ENTITY,
                decision_ar="اقتراح تأسيس كيان مفقود في Odoo",
                verdict_ar=f"تم رصد {entity_type} جديد ('{missing_name}') غير مسجل في Odoo. يوصى بإنشائه أولاً.",
                confidence=0.95,
                patched_fields={"missing_entity": missing_name, "entity_type": entity_type},
                patched_row=None,
                consultation_log=consultation,
                escalation_packet=SerajEscalationPacket(
                    excel_row_number=excel_row_number,
                    employee_name=name_val,
                    failure_code="missing_entity_in_odoo",
                    verdict_ar=f"القسم/المسمى '{missing_name}' غير موجود ولا يوجد له بديل مقارب. هل تريد إضافته لـ Odoo؟",
                    consultation_summary=consultation,
                    actionable_options=[
                        ActionableOption(
                            option_id="create_entity_and_resume",
                            title_ar=f"إنشاء {entity_type} '{missing_name}' في Odoo واعتماد الموظف",
                            action_type="create_entity",
                            patch_payload={"entity": missing_name, "type": entity_type},
                        ),
                        ActionableOption(
                            option_id="quarantine_row",
                            title_ar="عزل الصف مؤقتاً ومتابعة الدفعة",
                            action_type="quarantine",
                        ),
                    ],
                ),
                is_auto_repaired=False,
            )

        # -----------------------------------------------------------------
        # القرار 4: الإحالة للمسؤول البشري — ترفع وترجع لسراج (ESCALATE_TO_HUMAN)
        # -----------------------------------------------------------------
        actionable_options = []
        if patched_fields:
            actionable_options.append(
                ActionableOption(
                    option_id="apply_musleh_proposal",
                    title_ar=f"اعتماد تصحيح مصلح المقترح: {patched_fields}",
                    action_type="apply_patch",
                    patch_payload=patched_fields,
                )
            )
        actionable_options.append(
            ActionableOption(
                option_id="quarantine_row",
                title_ar="عزل الصف المعطوب وتمرير بقية الموظفين",
                action_type="quarantine",
            )
        )

        return self._build_escalate_decision(
            row=row,
            validation_result=validation_result,
            consultation=consultation,
            verdict_ar=(
                f"الصف يحتاج مراجعة بشرية ({failure_code}). "
                + (f"اقتراح مصلح المتوفر: {patched_fields}" if patched_fields else "لم يُعثر على بديل آمن بنسبة كافية.")
            ),
            options=actionable_options,
            patched_fields=patched_fields,
            confidence=overall_confidence,
        )

    def _build_escalate_decision(
        self,
        row: Dict[str, Any],
        validation_result: Dict[str, Any],
        consultation: Dict[str, Any],
        verdict_ar: str,
        options: List[ActionableOption],
        patched_fields: Optional[Dict[str, Any]] = None,
        confidence: float = 0.5,
    ) -> MuslehDecisionResult:
        """بناء قرار الإحالة للمسؤول البشري المرفوع حصراً إلى سراج."""
        excel_row_number = row.get("excel_row_number", validation_result.get("excel_row_number", 0))
        fields = row.get("fields", {})
        name_val = fields.get("name", {}).get("value", "موظف")
        failure_code = validation_result.get("failure_code", "needs_review")
        original_status = validation_result.get("final_status", "needs_review")

        packet = SerajEscalationPacket(
            excel_row_number=excel_row_number,
            employee_name=name_val,
            failure_code=failure_code,
            verdict_ar=verdict_ar,
            consultation_summary=consultation,
            actionable_options=options,
            escalated_to="seraj_orchestrator",
        )

        return MuslehDecisionResult(
            excel_row_number=excel_row_number,
            original_status=original_status,
            final_status="needs_review",
            decision=DECISION_ESCALATE_TO_HUMAN,
            decision_ar="الإحالة للمسؤول البشري عبر سراج",
            verdict_ar=verdict_ar,
            confidence=confidence,
            patched_fields=patched_fields or {},
            patched_row=None,
            consultation_log=consultation,
            escalation_packet=packet,
            is_auto_repaired=False,
        )

    # =========================================================================
    # 4. المعالجة الاستباقية لتنسيقات البيانات (Data Normalization Healing)
    # =========================================================================

    @staticmethod
    def heal_date_format(val: Any) -> Optional[str]:
        """
        إصلاح وتحويل صيغ التواريخ المعطوبة إلى صيغة ISO YYYY-MM-DD المعتمدة في Odoo.
        
        يتحقق من صلاحية التاريخ باستخدام datetime.strptime لمنع تواريخ غير منطقية
        مثل 45/13/2026 (لا يوجد شهر 13 ولا يوم 45).
        
        P4: لا افتراض اليوم أولاً بصمت - يُطلب توضيح إذا كان التنسيق غامضاً.
        """
        from datetime import datetime
        
        if not val:
            return None
        text = clean_value_text(str(val))
        if not text:
            return None

        # 1. إذا كان التاريخ سليماً بصيغة YYYY-MM-DD
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            # التحقق من الصلاحية
            try:
                datetime.strptime(text, "%Y-%m-%d")
                return text
            except ValueError:
                return None

        # 2. صيغ مفصولة بـ / أو . مثل YYYY/MM/DD
        m = re.match(r"^(\d{4})[/.](\d{1,2})[/.](\d{1,2})$", text)
        if m:
            y, mm, d = m.groups()
            candidate = f"{y}-{int(mm):02d}-{int(d):02d}"
            # التحقق من الصلاحية
            try:
                datetime.strptime(candidate, "%Y-%m-%d")
                return candidate
            except ValueError:
                return None

        # 3. صيغ اليوم أولاً مثل DD-MM-YYYY أو DD/MM/YYYY
        # ملاحظة P4: عدم افتراض اليوم أولاً بصمت
        # نحاول فقط إذا كان اليوم > 12 (لا غموض)
        m2 = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", text)
        if m2:
            d, mm, y = m2.groups()
            d_int, mm_int = int(d), int(mm)
            
            # إذا كان اليوم > 12، فهو بالتأكيد يوم (لا غموض)
            if d_int > 12:
                candidate = f"{y}-{mm_int:02d}-{d_int:02d}"
                try:
                    datetime.strptime(candidate, "%Y-%m-%d")
                    return candidate
                except ValueError:
                    return None
            
            # إذا كان الشهر > 12 واليوم <= 12، فالترتيب عكسي (يوم شهر سنة)
            elif mm_int > 12 and d_int <= 12:
                candidate = f"{y}-{d_int:02d}-{mm_int:02d}"
                try:
                    datetime.strptime(candidate, "%Y-%m-%d")
                    return candidate
                except ValueError:
                    return None
            
            # الحالة الغامضة: كلاهما <= 12
            # P4: لا نخمّن، نرجع None ونطلب توضيح
            else:
                return None

        return None

    @staticmethod
    def heal_phone_format(val: Any) -> Optional[str]:
        """
        إصلاح وتنظيف أرقام الجوالات السعودية وتوحيدها إلى صيغة 05xxxxxxxx.
        
        P4: عدم إسقاط + من الأرقام غير السعودية - الاحتفاظ بالصيغة الدولية
        للأرقام التي لا تبدأ بـ 966.
        """
        if not val:
            return None
        raw = clean_value_text(str(val))
        
        # إذا كان الرقم يحتوي على + فهو بصيغة دولية
        has_plus = raw.startswith("+")
        
        # استخراج الأرقام فقط
        digits = re.sub(r"\D", "", raw)
        if not digits:
            return None

        # معالجة الأرقام السعودية فقط
        is_saudi = False
        
        # لو الرقم يبدأ بـ 00966
        if digits.startswith("00966"):
            digits = digits[5:]
            is_saudi = True
        # لو الرقم يبدأ بـ 966
        elif digits.startswith("966"):
            digits = digits[3:]
            is_saudi = True
        # لو يبدأ بـ 05 مباشرة
        elif digits.startswith("05") and len(digits) == 10:
            is_saudi = True
        # لو يبدأ بـ 5 وطوله 9
        elif digits.startswith("5") and len(digits) == 9:
            digits = "0" + digits
            is_saudi = True

        # إرجاع الرقم السعودي المنسق
        if is_saudi and digits.startswith("05") and len(digits) == 10:
            return digits
        
        # الأرقام غير السعودية: إعادة + إذا كان موجوداً
        if has_plus and not is_saudi:
            return "+" + digits
        
        return digits

    @staticmethod
    def heal_email_format(val: Any) -> Optional[str]:
        """
        تنظيف المسافات المخفية والأحرف الكبيرة في البريد الإلكتروني.
        """
        if not val:
            return None
        cleaned = clean_value_text(str(val)).strip().lower()
        # إزالة أي مسافات بالوسط
        cleaned = re.sub(r"\s+", "", cleaned)
        if is_valid_email_format(cleaned):
            return cleaned
        return None

    @staticmethod
    def _find_fuzzy_match(val: str, candidates: List[str]) -> Tuple[Optional[str], float]:
        """
        المطابقة الضبابية الذكية مع حساب نسبة الثقة.
        """
        if not val or not candidates:
            return None, 0.0

        val_key = reference_match_key(val)
        cand_map = {reference_match_key(c): c for c in candidates if c and reference_match_key(c)}
        if not cand_map:
            return None, 0.0

        # تطابق تام بعد التسوية
        if val_key in cand_map:
            return cand_map[val_key], 1.0

        # البحث عن أقرب تطابق
        close = get_close_matches(val_key, list(cand_map.keys()), n=1, cutoff=0.5)
        if not close:
            return None, 0.0

        best_key = close[0]
        score = SequenceMatcher(None, val_key, best_key).ratio()
        return cand_map[best_key], round(score, 2)

    # =========================================================================
    # 5. معالجة الدفعات وكشف الأسباب الجذرية (Batch Quarantine & Root Causes)
    # =========================================================================

    def heal_batch(
        self,
        rows: List[Dict[str, Any]],
        validation_results: List[Dict[str, Any]],
        live_snapshot: Optional[Dict[str, Any]] = None,
        auto_repair: bool = False,
    ) -> Dict[str, Any]:
        """
        معالجة دفعة كاملة من الصفوف مع عزل الصفوف غير القابلة للإصلاح.
        القرار: QUARANTINE_AND_PROCEED
        """
        accepted_rows: List[Dict[str, Any]] = []
        quarantined_rows: List[Dict[str, Any]] = []
        escalated_packets: List[SerajEscalationPacket] = []
        decisions: List[MuslehDecisionResult] = []

        val_map = {res.get("excel_row_number"): res for res in validation_results}

        for row in rows:
            rn = row.get("excel_row_number")
            val_res = val_map.get(rn, {})
            status = val_res.get("final_status")

            if status == "accepted":
                # الصف سليم، يمر فوراً
                accepted_rows.append(row)
                continue

            # الصف معطوب: يتدخل مصلح
            decision = self.diagnose_and_heal_row(
                row=row,
                validation_result=val_res,
                live_snapshot=live_snapshot,
                auto_repair=auto_repair,
            )

            if decision:
                decisions.append(decision)
                if decision.final_status == "accepted" and decision.patched_row:
                    accepted_rows.append(decision.patched_row)
                else:
                    # عزل الصف لمتابعة الدفعة (Quarantine)
                    quarantined_rows.append({
                        "row": row,
                        "decision": decision.to_dict(),
                    })
                    if decision.escalation_packet:
                        escalated_packets.append(decision.escalation_packet)
            else:
                quarantined_rows.append({"row": row, "validation": val_res})

        # كشف السبب الجذري المكرر في الدفعة
        root_causes = self.analyze_batch_root_causes(decisions)

        return {
            "total_rows": len(rows),
            "ready_to_create_count": len(accepted_rows),
            "quarantined_count": len(quarantined_rows),
            "accepted_rows": accepted_rows,
            "quarantined_rows": quarantined_rows,
            "escalated_to_seraj": [p.to_dict() for p in escalated_packets],
            "batch_root_causes": root_causes,
            "auto_repair_enabled": auto_repair,
        }

    def analyze_batch_root_causes(self, decisions: List[MuslehDecisionResult]) -> List[Dict[str, Any]]:
        """
        رصد الأخطاء الجماعية المكررة في الدفعة (مثلاً قسم مكرر مفقود في 5 صفوف).
        """
        missing_entities: Dict[str, int] = {}
        date_issues = 0

        for d in decisions:
            if d.decision == DECISION_PROPOSE_MISSING_ENTITY:
                ent = d.patched_fields.get("missing_entity", "unknown")
                missing_entities[ent] = missing_entities.get(ent, 0) + 1
            if "hiring_date" in d.patched_fields:
                date_issues += 1

        causes = []
        for ent, count in missing_entities.items():
            if count >= 2:
                causes.append({
                    "pattern": "repeated_missing_entity",
                    "entity_name": ent,
                    "affected_rows_count": count,
                    "recommendation_ar": f"الكيان '{ent}' مفقود في {count} صفوف. يوصى بإنشائه في Odoo دفعة واحدة لتفادي تعطيلها.",
                })

        if date_issues >= 3:
            causes.append({
                "pattern": "repeated_date_formatting_issue",
                "affected_rows_count": date_issues,
                "recommendation_ar": f"يوجد {date_issues} صفوف بصيغ تواريخ غير قياسية تم علاجها تلقائياً.",
            })

        return causes

    # =========================================================================
    # 6. التعافي ومنع التكرار عند انقطاع الاتصال (Idempotency & Network Recovery)
    # =========================================================================

    def verify_and_recover_submission(
        self,
        employee_name: str,
        company_id: int,
    ) -> Dict[str, Any]:
        """
        فحص قاعدة Odoo بعد انقطاع الشبكة: هل تم إنشاء الموظف فعلاً أم لا؟
        لمنع التكرار (Idempotency Guard).
        """
        if not self.repository:
            return {"recovered": False, "reason": "no_repository"}

        try:
            snapshot = self.repository.get_live_reference_snapshot()
            existing_employees = snapshot.get("existing_employees", [])
            target_key = reference_match_key(employee_name)

            for emp in existing_employees:
                emp_name = emp.get("name") or ""
                emp_cid = emp.get("company_id")
                cid = emp_cid[0] if isinstance(emp_cid, (list, tuple)) else emp_cid
                if cid == company_id and reference_match_key(emp_name) == target_key:
                    return {
                        "recovered": True,
                        "odoo_id": emp.get("id"),
                        "employee_name": emp_name,
                        "message_ar": f"الموظف '{emp_name}' موجود بالفعل في Odoo بمعرف ID: {emp.get('id')}. تم تفادي التكرار المزدوج.",
                    }

            return {
                "recovered": False,
                "message_ar": f"الموظف '{employee_name}' غير موجود في Odoo. العملية آمنة للإعادة.",
            }
        except Exception as e:
            return {"recovered": False, "error": str(e)}
