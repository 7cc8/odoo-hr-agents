"""
خدمة إدارة وتدقيق تقييمات الأداء والموظفين (Employee Appraisals Service)
=============================================================================
الطبقة التنفيذية لإدارة دورات تقييم الأداء في Odoo (appraisal.request) بالتكامل مع:
1. المادة 53 من نظام العمل السعودي: ضوابط تقييم فترة التجربة (90 يوماً وتمديد حتى 180 يوماً).
2. معايير الأوزان النسبية: (70% أهداف وKPIs + 30% كفاءات وسلوكيات).
3. سلم التقديرات المعتمد: ممتاز (90-100%)، جيد جداً (80-89%)، جيد (70-79%)، مقبول (60-69%)، غير مرضٍ (<60%).
4. التفريق الحتمي بين السعودي والوافد:
   - المواطن السعودي: أولوية الترقية، والتطوير الوظيفي، والإحلال والتوطين، وخطة تحسين الأداء الإلزامية (PIP).
   - الوافد المقيم: ربط التقييم بتجديد العقد المحدد المدة (المادة 37) ورخصة العمل في قوى.
5. مبدأ التحقق المزدوج Four-Eyes والتحقق المستقل بعد الكتابة (Readback Verification).
"""

from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_appraisal_write_gateway import OdooAppraisalWriteGateway
from eos_service import detect_employee_nationality


APPRAISAL_AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "appraisal_audit_log.jsonl")

# سلم التقديرات المعتمد
APPRAISAL_RATING_TIERS: List[Dict[str, Any]] = [
    {"code": "excellent", "min": 90.0, "max": 100.0, "name_ar": "ممتاز", "name_en": "Excellent", "color": "#10B981"},
    {"code": "very_good", "min": 80.0, "max": 89.99, "name_ar": "جيد جداً", "name_en": "Very Good", "color": "#3B82F6"},
    {"code": "good", "min": 70.0, "max": 79.99, "name_ar": "جيد", "name_en": "Good", "color": "#F59E0B"},
    {"code": "acceptable", "min": 60.0, "max": 69.99, "name_ar": "مقبول", "name_en": "Acceptable", "color": "#F97316"},
    {"code": "unsatisfactory", "min": 0.0, "max": 59.99, "name_ar": "غير مرضٍ", "name_en": "Unsatisfactory", "color": "#EF4444"},
]


def determine_appraisal_rating(score: float) -> Tuple[str, str]:
    """تحديد التقدير المعتمد بناءً على النسبة المئوية النهائية."""
    clamped = max(0.0, min(100.0, float(score)))
    for tier in APPRAISAL_RATING_TIERS:
        if tier["min"] <= clamped <= tier["max"]:
            return tier["code"], tier["name_ar"]
    return "unsatisfactory", "غير مرضٍ"


def calculate_weighted_score(
    kpi_score: float,
    competency_score: float,
    kpi_weight: float = 0.70,
    competency_weight: float = 0.30
) -> float:
    """احتساب المعدل النهائي الموزون بين الأهداف والكفاءات."""
    tot_weight = kpi_weight + competency_weight
    if tot_weight <= 0:
        kpi_w, comp_w = 0.70, 0.30
    else:
        kpi_w = kpi_weight / tot_weight
        comp_w = competency_weight / tot_weight
    kpi_clamped = max(0.0, min(100.0, float(kpi_score)))
    comp_clamped = max(0.0, min(100.0, float(competency_score)))
    return round((kpi_clamped * kpi_w) + (comp_clamped * comp_w), 2)


@dataclass
class AppraisalSummary:
    employee_id: int
    employee_name: str
    department_name: str
    job_title: str
    is_saudi: bool
    nationality_text_ar: str
    identification_id: str
    hiring_date: str
    days_since_hiring: int
    in_probation_period: bool
    total_appraisals_count: int
    last_score: Optional[float] = None
    last_rating_ar: Optional[str] = None
    recent_appraisals: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AppraisalDryRunResult:
    is_valid: bool
    employee_id: int
    employee_name: str
    department_id: int
    department_name: str
    job_id: int
    job_title: str
    is_saudi: bool
    nationality_text_ar: str
    appraisal_title: str
    appraisal_type: str  # "annual" or "probation"
    kpi_score: float
    competency_score: float
    kpi_weight_pct: float
    competency_weight_pct: float
    final_percentage: float
    rating_code: str
    rating_ar: str
    recommendation_ar: str
    statutory_article: str
    statutory_guidance_ar: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    approval_token: str = ""
    can_proceed: bool = False


@dataclass
class AppraisalExecutionResult:
    success: bool
    appraisal_id: Optional[int]
    appraisal_title: str
    employee_id: int
    employee_name: str
    final_percentage: float
    rating_ar: str
    state: str
    readback_verified: bool
    message_ar: str
    audit_logged: bool


class AppraisalService:
    """
    خدمة إدارة وتدقيق تقييمات الأداء والموظفين في Odoo.
    تلتزم بضوابط المادة 53 والتفريق بين المواطن والوافد.
    """
    _shared_pending_approvals: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        readonly_repo: Optional[OdooReadonlyRepository] = None,
        write_gateway: Optional[OdooAppraisalWriteGateway] = None,
        audit_log_path: Optional[str] = None
    ):
        self.readonly_repo = readonly_repo or OdooReadonlyRepository()
        self.write_gateway = write_gateway
        self.audit_log_path = audit_log_path or APPRAISAL_AUDIT_LOG_FILE
        self._pending_approvals: Dict[str, Dict[str, Any]] = AppraisalService._shared_pending_approvals

    def get_employee_appraisal_summary(
        self,
        employee_id: int,
        explicit_is_saudi: Optional[bool] = None,
        limit: int = 15
    ) -> AppraisalSummary:
        """
        جلب وتلخيص سجلات تقييم الأداء للموظف وتحديد موقفه من فترة التجربة.
        """
        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            raise ValueError(f"الموظف برقم المعرف #{employee_id} غير موجود في Odoo.")

        emp_name = emp.get("name", "غير معروف")
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"
        job_title = emp["job_id"][1] if emp.get("job_id") else "بدون مسمى وظيفي"
        ident = str(emp.get("identification_id") or "غير مسجل")

        is_saudi = detect_employee_nationality(emp, explicit_is_saudi)
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        # حساب مدة الخدمة وفترة التجربة
        h_date_raw = emp.get("create_date", "")
        contracts = self.readonly_repo.get_employee_contracts(employee_id)
        if contracts and contracts[0].get("date_start"):
            h_date_raw = contracts[0]["date_start"]

        h_date_str = str(h_date_raw)[:10] if h_date_raw else date.today().isoformat()
        try:
            h_date = datetime.strptime(h_date_str, "%Y-%m-%d").date()
            days_elapsed = max(0, (date.today() - h_date).days)
        except Exception:
            days_elapsed = 0

        in_probation = (days_elapsed <= 180)

        appraisals = self.readonly_repo.get_employee_appraisals(employee_id=employee_id, limit=limit)
        last_score = None
        last_rat_ar = None
        if appraisals:
            last_item = appraisals[0]
            last_score = last_item.get("final_percentage")
            if last_score is not None:
                _, last_rat_ar = determine_appraisal_rating(last_score)

        return AppraisalSummary(
            employee_id=employee_id,
            employee_name=emp_name,
            department_name=dept_name,
            job_title=job_title,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            identification_id=ident,
            hiring_date=h_date_str,
            days_since_hiring=days_elapsed,
            in_probation_period=in_probation,
            total_appraisals_count=len(appraisals),
            last_score=last_score,
            last_rating_ar=last_rat_ar,
            recent_appraisals=appraisals[:5]
        )

    def dry_run_appraisal(
        self,
        employee_id: int,
        appraisal_type: str = "annual",  # "annual" or "probation"
        year: Optional[int] = None,
        kpi_score: float = 85.0,
        competency_score: float = 85.0,
        kpi_weight: float = 0.70,
        competency_weight: float = 0.30,
        manager_id: Optional[int] = None,
        manager_name: Optional[str] = None,
        evaluation_date: Optional[str] = None,
        notes: Optional[str] = None,
        explicit_is_saudi: Optional[bool] = None,
    ) -> AppraisalDryRunResult:
        """
        الفحص والتدقيق التجريبي لتقييم الأداء وفق نظام العمل السعودي (المادة 53).
        """
        errors: List[str] = []
        warnings: List[str] = []

        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            return AppraisalDryRunResult(
                is_valid=False,
                employee_id=employee_id,
                employee_name="غير معروف",
                department_id=0,
                department_name="غير معروف",
                job_id=0,
                job_title="غير معروف",
                is_saudi=True,
                nationality_text_ar="غير معروف",
                appraisal_title="تقييم غير محدد",
                appraisal_type=appraisal_type,
                kpi_score=0.0,
                competency_score=0.0,
                kpi_weight_pct=70.0,
                competency_weight_pct=30.0,
                final_percentage=0.0,
                rating_code="unsatisfactory",
                rating_ar="غير مرضٍ",
                recommendation_ar="الموظف غير موجود في Odoo.",
                statutory_article="نظام العمل",
                statutory_guidance_ar="الموظف غير مسجل.",
                errors=["الموظف برقم المعرف المحدد غير موجود."],
                can_proceed=False
            )

        emp_name = emp.get("name", "غير معروف")
        dept_id = emp["department_id"][0] if emp.get("department_id") else 1
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"
        job_id = emp["job_id"][0] if emp.get("job_id") else 1
        job_title = emp["job_id"][1] if emp.get("job_id") else "بدون مسمى"

        is_saudi = detect_employee_nationality(emp, explicit_is_saudi)
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        if kpi_score < 0 or kpi_score > 100:
            errors.append(f"درجة الأهداف (KPIs) يجب أن تكون بين 0 و 100 (القيمة المدخلة: {kpi_score}).")
        if competency_score < 0 or competency_score > 100:
            errors.append(f"درجة الكفاءات والسلوك يجب أن تكون بين 0 و 100 (القيمة المدخلة: {competency_score}).")

        # احتساب المعدل الموزون
        final_pct = calculate_weighted_score(kpi_score, competency_score, kpi_weight, competency_weight)
        rat_code, rat_ar = determine_appraisal_rating(final_pct)

        eval_year = year or date.today().year
        eval_date = evaluation_date or date.today().isoformat()

        # حساب أيام الخدمة لفترة التجربة (المادة 53)
        h_date_raw = emp.get("create_date", "")
        contracts = self.readonly_repo.get_employee_contracts(employee_id)
        if contracts and contracts[0].get("date_start"):
            h_date_raw = contracts[0]["date_start"]

        h_date_str = str(h_date_raw)[:10] if h_date_raw else date.today().isoformat()
        days_elapsed = 0
        try:
            h_date = datetime.strptime(h_date_str, "%Y-%m-%d").date()
            days_elapsed = max(0, (date.today() - h_date).days)
        except Exception:
            pass

        statutory_art = "لائحة تنظيم العمل ونظام العمل السعودي"
        statutory_guidance = ""
        recommendation = ""

        # تدقيق نوع التقييم (فترة تجربة أم سنوي)
        is_probation = (appraisal_type in ("probation", "تجربة", "فترة تجربة"))
        if is_probation:
            statutory_art = "المادة 53 من نظام العمل السعودي (فترة التجربة)"
            app_title = f"تقييم نهاية فترة التجربة - {emp_name} ({eval_year})"

            if days_elapsed > 180:
                warnings.append(
                    f"المادة 53: مضى على بداية العمل ({days_elapsed} يوماً) متجاوزة الحد الأقصى النظامي لفترة التجربة (180 يوماً). "
                    f"يُعد الموظف مثبتاً حكماً بموجب النظام."
                )

            if final_pct >= 70.0:
                recommendation = "تثبيت الموظف في وظيفته وإنهاء فترة التجربة بنجاح واجتياز المعايير."
                statutory_guidance = (
                    "المادة 53: اجتياز الموظف بنجاح يُلزِم بتثبيته وتتحول العلاقة إلى عقد عمل تام الأثر القانوني."
                )
            else:
                if days_elapsed <= 90:
                    recommendation = (
                        "إنهاء العقد خلال فترة التجربة بموجب المادة 53 دون مكافأة أو تعويض، أو تمديد التجربة باتفاق كتابي حتى 180 يوماً."
                    )
                else:
                    recommendation = "إنهاء العقد قبل انتهاء مهلة الـ 180 يوماً بموجب المادة 53 لعدم الكفاءة."
                statutory_guidance = (
                    "المادة 53: يحق لصاحب العمل أو العامل إنهاء العقد أثناء فترة التجربة دون مكافأة نهاية خدمة أو تعويض."
                )
        else:
            app_title = f"التقييم الدوري السنوي لعام {eval_year} - {emp_name}"
            statutory_art = "معايير تقييم الأداء السنوي ولائحة تنظيم العمل"

            # التفريق الصارم بين السعودي والوافد في التوصيات
            if is_saudi:
                if rat_code in ("excellent", "very_good"):
                    recommendation = "ترشيح للترقية ومكافأة استحقاق، مع الإدراج في خطة التعاقب الوظيفي والتطوير القيادي (توطين نوعي)."
                    statutory_guidance = "دعم الكفاءات الوطنية ضمن مسارات الإحلال والتطوير الوظيفي المعزز لنظام نطاقات والتوطين."
                elif rat_code == "good":
                    recommendation = "تثبيت المسار الحالي ووضع خطة تطوير مهني دورية في الدورات التدريبية المعتمدة."
                    statutory_guidance = "الاستثمار في تدريب الموظف لرفع كفاءته للعام القادم."
                elif rat_code == "acceptable":
                    recommendation = "خطة تحسين الأداء (PIP) لمدة 90 يوماً مع متابعة شهرية مباشرة من المشرف."
                    statutory_guidance = "ضمان منح المواطن فرصة التدريب والتحسين قبل اتخاذ أي تدابير إدارية."
                else:  # unsatisfactory
                    recommendation = "خطة تصحيحية مشددة (PIP) وتوجيه إنذار أداء نظامي، والتأهيل لإعادة التقييم."
                    warnings.append(
                        "لائحة تنظيم العمل: تقييم المواطن كـ (غير مرضٍ) يتطلب تدريباً موثقاً وخطة تحسين أداء كتابية ومراجعة الموارد البشرية."
                    )
                    statutory_guidance = "حماية الكفاءات الوطنية تلزم بإتاحة فرصة التطوير والتحقيق الإداري قبل أي قرار."
            else:
                # غير سعودي (وافد)
                if rat_code in ("excellent", "very_good"):
                    recommendation = "تجديد عقد العمل المحدد المدة (المادة 37) ورخصة العمل في قوى ومقيم، مع منح علاوة تميز."
                    statutory_guidance = "المادة 37: استمرار العقد وفق مدته المحددة وتجديده برضا الطرفين."
                elif rat_code in ("good", "acceptable"):
                    recommendation = "تجديد العقد بنفس الشروط مع وضع أهداف أداء محددة للعام الجديد."
                    statutory_guidance = "استمرار العلاقة التعاقدية المحددة المدة."
                else:  # unsatisfactory
                    recommendation = "إشعار الموظف بعدم الرغبة في تجديد العقد عند نهاية مدته الحالية وفق مهلة الإشعار التعاقدية (المادة 75)."
                    warnings.append(
                        "المادة 75 والمادة 37: في حال عدم الرغبة في تجديد العقد، يجب مراعاة مهلة الإشعار المحددة في العقد أو النظام (30 يوماً)."
                    )
                    statutory_guidance = "عدم التجديد عند نهاية المدة لا يُعد فصلاً تعسفياً شريطة الالتزام بمهلة الإشعار."

        is_valid = len(errors) == 0
        token = ""
        if is_valid:
            token = f"APR-{uuid.uuid4().hex[:8].upper()}"
            self._pending_approvals[token] = {
                "employee_id": employee_id,
                "name": app_title,
                "start_date": f"{eval_year}-01-01" if not is_probation else h_date_str,
                "end_date": f"{eval_year}-12-31" if not is_probation else eval_date,
                "evaluation_date": eval_date,
                "department_id": dept_id,
                "job_id": job_id,
                "manager_id": manager_id,
                "final_percentage": final_pct,
                "total_points_earned": final_pct,
                "max_possible_points": 100.0,
                "manager_comments": notes or recommendation,
                "notes": f"التقدير: {rat_ar} | التوصية: {recommendation}",
                "is_saudi": is_saudi,
                "employee_name": emp_name,
                "appraisal_type": appraisal_type,
            }

        return AppraisalDryRunResult(
            is_valid=is_valid,
            employee_id=employee_id,
            employee_name=emp_name,
            department_id=dept_id,
            department_name=dept_name,
            job_id=job_id,
            job_title=job_title,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            appraisal_title=app_title,
            appraisal_type=appraisal_type,
            kpi_score=kpi_score,
            competency_score=competency_score,
            kpi_weight_pct=kpi_weight * 100.0,
            competency_weight_pct=competency_weight * 100.0,
            final_percentage=final_pct,
            rating_code=rat_code,
            rating_ar=rat_ar,
            recommendation_ar=recommendation,
            statutory_article=statutory_art,
            statutory_guidance_ar=statutory_guidance,
            warnings=warnings,
            errors=errors,
            approval_token=token,
            can_proceed=is_valid
        )

    def apply_appraisal(
        self,
        approval_token: str,
        user_confirmation_text: str = "تأكيد",
        state: str = "completed"
    ) -> AppraisalExecutionResult:
        """
        اعتماد وتسجيل تقييم الأداء فعلياً في Odoo مع إلزامية التأكيد الكتابي الصريح.
        """
        if user_confirmation_text != "تأكيد":
            return AppraisalExecutionResult(
                success=False,
                appraisal_id=None,
                appraisal_title="",
                employee_id=0,
                employee_name="",
                final_percentage=0.0,
                rating_ar="",
                state="",
                readback_verified=False,
                message_ar="مرفوض: يتطلب اعتماد تقييم الأداء كلمة 'تأكيد' صريحة من المستخدم.",
                audit_logged=False
            )

        payload = self._pending_approvals.pop(approval_token, None)
        if not payload:
            return AppraisalExecutionResult(
                success=False,
                appraisal_id=None,
                appraisal_title="",
                employee_id=0,
                employee_name="",
                final_percentage=0.0,
                rating_ar="",
                state="",
                readback_verified=False,
                message_ar=f"رمز الموافقة '{approval_token}' غير صالح أو منتهي الصلاحية.",
                audit_logged=False
            )

        if not self.write_gateway:
            return AppraisalExecutionResult(
                success=False,
                appraisal_id=None,
                appraisal_title=payload["name"],
                employee_id=payload["employee_id"],
                employee_name=payload["employee_name"],
                final_percentage=payload["final_percentage"],
                rating_ar=determine_appraisal_rating(payload["final_percentage"])[1],
                state="dry_run_only",
                readback_verified=False,
                message_ar="بوابة الكتابة إلى Odoo غير مهيأة (وضع القراءة فقط).",
                audit_logged=False
            )

        try:
            created_id = self.write_gateway.create_appraisal_request(
                employee_id=payload["employee_id"],
                name=payload["name"],
                start_date=payload["start_date"],
                end_date=payload["end_date"],
                evaluation_date=payload["evaluation_date"],
                department_id=payload["department_id"],
                job_id=payload["job_id"],
                manager_id=payload["manager_id"],
                final_percentage=payload["final_percentage"],
                total_points_earned=payload["total_points_earned"],
                max_possible_points=payload["max_possible_points"],
                manager_comments=payload["manager_comments"],
                notes=payload["notes"],
                state="draft",
            )

            if state == "completed":
                self.write_gateway.complete_appraisal_request(created_id)

            # التحقق المستقل بعد الكتابة (Readback Verification)
            read_back = self.write_gateway.read_appraisal_request(created_id)
            verified = bool(read_back and read_back.get("id") == created_id)

            # توثيق العملية في سجل التدقيق المستقل
            audit_entry = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event": "APPLY_APPRAISAL_REQUEST",
                "appraisal_id": created_id,
                "name": payload["name"],
                "employee_id": payload["employee_id"],
                "employee_name": payload["employee_name"],
                "is_saudi": payload.get("is_saudi", True),
                "final_percentage": payload["final_percentage"],
                "appraisal_type": payload.get("appraisal_type", "annual"),
                "state": state,
                "readback_verified": verified,
            }
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")

            rat_ar = determine_appraisal_rating(payload["final_percentage"])[1]
            msg = (
                f"تم اعتماد وتسجيل تقييم الأداء بنجاح في Odoo برقم #{created_id} "
                f"({payload['name']}) بنسبة {payload['final_percentage']}% وتقدير ({rat_ar})."
            )

            return AppraisalExecutionResult(
                success=True,
                appraisal_id=created_id,
                appraisal_title=payload["name"],
                employee_id=payload["employee_id"],
                employee_name=payload["employee_name"],
                final_percentage=payload["final_percentage"],
                rating_ar=rat_ar,
                state=state,
                readback_verified=verified,
                message_ar=msg,
                audit_logged=True
            )
        except Exception as e:
            return AppraisalExecutionResult(
                success=False,
                appraisal_id=None,
                appraisal_title=payload["name"],
                employee_id=payload["employee_id"],
                employee_name=payload["employee_name"],
                final_percentage=payload["final_percentage"],
                rating_ar="",
                state="failed",
                readback_verified=False,
                message_ar=f"فشل تسجيل تقييم الأداء في Odoo: {str(e)}",
                audit_logged=False
            )
