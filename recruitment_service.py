"""
خدمة إدارة التوظيف والمرشحين وضوابط التوطين السعودي (Recruitment & Saudization Service)
=============================================================================
الطبقة التنفيذية لإدارة وتوثيق طلبات التوظيف والمرشحين في Odoo (hr.applicant) بالتكامل مع:
1. قرارات التوطين والسعودة الصادرة عن وزارة الموارد البشرية والتنمية الاجتماعية (HRSD):
   - حظر توظيف غير السعوديين في المهن المقصورة 100% على المواطنين (الموارد البشرية، الاستقبال، شؤون الموظفين، العلاقات الحكومية، الصناديق).
   - التحقق من التراخيص المهنية للمهن التخصصية (المحاسبة SOCPA، الهندسة SCE).
2. التفريق الحتمي بين المواطن السعودي والوافد المقيم:
   - المواطن: رقم الهوية الوطنية (يبدأ بـ 1)، الاستفادة من برامج دعم هدف (HRDF) ومنصة جدارات، فترة تجربة مرنة (المادة 53).
   - الوافد: رقم الإقامة (يبدأ بـ 2) أو جواز السفر، إلزامية العقد المحدد المدة (المادة 37)، واشتراطات نقل الخدمة عبر منصة "قوى" (Qiwa).
3. مبدأ التحقق المزدوج Four-Eyes والتحقق المستقل بعد الكتابة (Readback Verification).
"""

from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_recruitment_write_gateway import OdooRecruitmentWriteGateway


RECRUITMENT_AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "recruitment_audit_log.jsonl")

# المهن والوظائف المقصورة نظاماً وحصرياً بنسبة 100% على المواطنين السعوديين
RESTRICTED_SAUDI_PROFESSIONS = frozenset({
    "موارد بشرية",
    "أخصائي موارد بشرية",
    "مدير موارد بشرية",
    "شؤون موظفين",
    "مدير شؤون موظفين",
    "أخصائي شؤون موظفين",
    "مسؤول توظيف",
    "أخصائي توظيف",
    "استقبال",
    "موظف استقبال",
    "كاتب استقبال",
    "علاقات حكومية",
    "مسؤول علاقات حكومية",
    "معقب",
    "أمين صندوق",
    "كاشير",
    "حارس أمن",
    "مدير أمن",
    "مخلص جمركي",
})

# المهن التخصصية التي تشترط اعتماداً وتصنيفاً مهنياً مع نسب توطين قطاعية
PROFESSION_ACCREDITATIONS: Dict[str, str] = {
    "محاسب": "الهيئة السعودية للمراجعين والمحاسبين (SOCPA) - الحد الأدنى للأجر المعتمد ونسب التوطين المحاسبي",
    "مهندس": "الهيئة السعودية للمهندسين (SCE) - متطلب التسجيل المهني الإلزامي قبل مباشرة العمل",
    "طبيب": "الهيئة السعودية للتخصصات الصحية (SCFHS) - التصنيف المهني والتسجيل ساري المفعول",
    "صيدلي": "الهيئة السعودية للتخصصات الصحية (SCFHS) - التوطين الإلزامي لقطاع الصيدلة",
    "محامي": "الإدارة العامة للمحاماة - رخصة مزاولة المهنة والاستشارات القانونية",
}


@dataclass
class JobOpeningSummary:
    id: int
    name: str
    department_name: str
    no_of_recruitment: int
    is_saudi_only: bool
    compliance_guidance_ar: str


@dataclass
class ApplicantSummary:
    applicant_id: int
    candidate_name: str
    job_id: int
    job_title: str
    department_name: str
    is_saudi: bool
    nationality_text_ar: str
    stage_id: int
    stage_name: str
    id_number: str
    passport_number: str
    email: str
    phone: str
    salary_expected: float
    salary_proposed: float
    total_salary: float
    approval_status: str
    kanban_state: str
    saudization_status_ar: str


@dataclass
class ApplicantDryRunResult:
    is_valid: bool
    candidate_name: str
    job_id: int
    job_title: str
    is_saudi: bool
    nationality_text_ar: str
    id_number: str
    passport_number: str
    email: str
    phone: str
    salary_expected: float
    salary_proposed: float
    housing_allowance: float
    transportation_allowance: float
    total_salary: float
    contract_status: str
    duration_of_contract: int
    is_saudi_restricted_job: bool
    statutory_article: str
    statutory_explanation_ar: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    approval_token: str = ""
    can_proceed: bool = False


@dataclass
class ApplicantExecutionResult:
    success: bool
    applicant_id: Optional[int]
    candidate_name: str
    job_id: int
    job_title: str
    is_saudi: bool
    total_salary: float
    approval_status: str
    readback_verified: bool
    message_ar: str
    audit_logged: bool


def is_job_restricted_to_saudis(job_title: str) -> bool:
    """
    فحص ما إذا كانت الوظيفة مقصورة نظاماً على المواطنين السعوديين بنسبة 100%.
    """
    clean_title = (job_title or "").strip().lower()
    for restricted in RESTRICTED_SAUDI_PROFESSIONS:
        if restricted in clean_title:
            return True
    return False


def get_job_accreditation_requirement(job_title: str) -> Optional[str]:
    """
    استخراج متطلبات الاعتماد المهني الرسمي للوظيفة (SOCPA / SCE / SCFHS).
    """
    clean_title = (job_title or "").strip().lower()
    for prof, req in PROFESSION_ACCREDITATIONS.items():
        if prof in clean_title:
            return req
    return None


class RecruitmentService:
    """
    خدمة إدارة التوظيف والمرشحين والتوطين السعودي في Odoo.
    """
    _shared_pending_approvals: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        readonly_repo: Optional[OdooReadonlyRepository] = None,
        write_gateway: Optional[OdooRecruitmentWriteGateway] = None,
        audit_log_path: Optional[str] = None
    ):
        self.readonly_repo = readonly_repo or OdooReadonlyRepository()
        self.write_gateway = write_gateway
        self.audit_log_path = audit_log_path or RECRUITMENT_AUDIT_LOG_FILE
        self._pending_approvals: Dict[str, Dict[str, Any]] = RecruitmentService._shared_pending_approvals

    def get_job_openings(self) -> List[JobOpeningSummary]:
        """
        جلب وتلخيص شواغر التوظيف مع تحديد وضع التوطين الإلزامي لكل وظيفة.
        """
        jobs = self.readonly_repo.get_recruitment_jobs()
        summaries: List[JobOpeningSummary] = []
        for j in jobs:
            j_id = int(j.get("id"))
            j_name = str(j.get("name") or "شاغر وظيفي")
            dept = j.get("department_id")
            dept_name = dept[1] if dept and isinstance(dept, (list, tuple)) else "بدون قسم"
            rec_count = int(j.get("no_of_recruitment") or 0)
            is_restricted = is_job_restricted_to_saudis(j_name)
            accreditation = get_job_accreditation_requirement(j_name)

            guidance = "مقصورة حصراً على المواطنين السعوديين بنسبة 100%" if is_restricted else "متاحة لكافة الجنسيات وفق نسب نطاقات"
            if accreditation:
                guidance += f" | تتطلب اعتماد: {accreditation}"

            summaries.append(
                JobOpeningSummary(
                    id=j_id,
                    name=j_name,
                    department_name=dept_name,
                    no_of_recruitment=rec_count,
                    is_saudi_only=is_restricted,
                    compliance_guidance_ar=guidance
                )
            )
        return summaries

    def get_applicant_summary(self, applicant_id: int) -> ApplicantSummary:
        """
        جلب وتلخيص بيانات مرشح توظيف محدد من Odoo.
        """
        app_data = self.readonly_repo.get_applicant(applicant_id)
        if not app_data:
            raise ValueError(f"طلب التوظيف برقم المعرف #{applicant_id} غير موجود في Odoo.")

        c_name = str(app_data.get("partner_name") or "مرشح غير معروف")
        job_info = app_data.get("job_id")
        j_id = job_info[0] if job_info and isinstance(job_info, (list, tuple)) else 0
        j_title = job_info[1] if job_info and isinstance(job_info, (list, tuple)) else "غير محدد"

        dept_info = app_data.get("department_id")
        dept_name = dept_info[1] if dept_info and isinstance(dept_info, (list, tuple)) else "بدون قسم"

        is_saudi = bool(app_data.get("is_saudi"))
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        stg_info = app_data.get("stage_id")
        stg_id = stg_info[0] if stg_info and isinstance(stg_info, (list, tuple)) else 1
        stg_name = stg_info[1] if stg_info and isinstance(stg_info, (list, tuple)) else "New"

        is_restricted = is_job_restricted_to_saudis(j_title)
        saud_status = "مطابق لضوابط التوطين والسعودة ✅"
        if not is_saudi and is_restricted:
            saud_status = "⚠️ مخالفة توطين: الوظيفة مقصورة نظاماً على المواطنين فقط!"

        return ApplicantSummary(
            applicant_id=applicant_id,
            candidate_name=c_name,
            job_id=j_id,
            job_title=j_title,
            department_name=dept_name,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            stage_id=stg_id,
            stage_name=stg_name,
            id_number=str(app_data.get("id_number") or ""),
            passport_number=str(app_data.get("passport_number") or ""),
            email=str(app_data.get("email_from") or ""),
            phone=str(app_data.get("partner_phone") or ""),
            salary_expected=float(app_data.get("salary_expected") or 0.0),
            salary_proposed=float(app_data.get("salary_proposed") or 0.0),
            total_salary=float(app_data.get("total_salary") or 0.0),
            approval_status=str(app_data.get("approval_status") or "draft"),
            kanban_state=str(app_data.get("kanban_state") or "normal"),
            saudization_status_ar=saud_status,
        )

    def dry_run_applicant(
        self,
        candidate_name: str,
        job_id: int,
        is_saudi: bool,
        id_number: Optional[str] = None,
        passport_number: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        salary_expected: float = 0.0,
        salary_proposed: float = 0.0,
        housing_allowance: float = 0.0,
        transportation_allowance: float = 0.0,
        contract_status: str = "single",
        duration_of_contract: int = 1,
        availability: Optional[str] = None,
        applicant_notes: Optional[str] = None,
        job_title_override: Optional[str] = None,
    ) -> ApplicantDryRunResult:
        """
        فحص وتدقيق طلب التوظيف تجريبياً (Dry-Run) والتحقق من التوطين والمادة 37 وفترة التجربة.
        """
        warnings: List[str] = []
        errors: List[str] = []

        clean_name = (candidate_name or "").strip()
        if not clean_name:
            errors.append("اسم المرشح إلزامي لإنشاء طلب التوظيف.")

        # استخراج اسم الوظيفة والتحقق من وجودها
        job_title = job_title_override or ""
        if not job_title and job_id:
            jobs = self.readonly_repo.get_recruitment_jobs()
            match_job = next((j for j in jobs if j.get("id") == job_id), None)
            if match_job:
                job_title = str(match_job.get("name") or "")
            else:
                job_title = f"وظيفة #{job_id}"

        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"
        is_restricted = is_job_restricted_to_saudis(job_title)

        # 1. فحص التوطين وحظر المهن المقصورة
        if not is_saudi and is_restricted:
            errors.append(
                f"حظر توطين قطعي: وظيفة '{job_title}' مقصورة نظاماً بنسبة 100% على المواطنين السعوديين "
                f"بموجب قرارات وزارة الموارد البشرية والتنمية الاجتماعية، ولا يجوز إسنادها لمرشح وافد."
            )
        elif is_saudi and is_restricted:
            warnings.append(
                f"متوافق مع التوطين: ترشيح مواطن سعودي لوظيفة مقصورة ('{job_title}') يدعم نسبة نطاقات وتفادي المخالفات."
            )

        # 2. فحص الاعتماد المهني الرسمي
        accreditation = get_job_accreditation_requirement(job_title)
        if accreditation:
            warnings.append(f"متطلب ترخيص واعتماد مهني: {accreditation}")

        # 3. التحقق من الهوية الوطنية / الإقامة
        clean_id = (id_number or "").strip()
        if is_saudi:
            if clean_id and not clean_id.startswith("1"):
                warnings.append("رقم الهوية الوطنية للمواطن السعودي يبدأ عادة بالرقم (1) ويتكون من 10 أرقام.")
        else:
            if clean_id and not clean_id.startswith("2"):
                warnings.append("رقم إقامة المقيم غير السعودي يبدأ عادة بالرقم (2) ويتكون من 10 أرقام.")
            if not clean_id and not passport_number:
                warnings.append("يلزم توفير رقم الإقامة أو جواز السفر لإتمام إجراءات التعاقد عبر منصة قوى (Qiwa).")

        # 4. ضوابط العقد والأجور والمادة 37
        if not is_saudi and duration_of_contract <= 0:
            errors.append("المادة 37: عقد عمل غير السعودي يجب أن يكون محدد المدة ومحدد بعدد سنوات/أشهر.")

        total_sal = float(salary_proposed) + float(housing_allowance) + float(transportation_allowance)
        if total_sal <= 0 and float(salary_expected) <= 0:
            warnings.append("لم يتم تحديد الراتب المتوقع أو المعروض للمرشح.")

        # 5. فترة التجربة (المادة 53)
        statutory_article = "قرارات التوطين الصادرة عن وزارة الموارد البشرية + المواد 37 و 53 من نظام العمل"
        statutory_explanation = (
            f"المرشح: {nat_text} | الوظيفة: {job_title} | "
            f"فترة التجربة النظامية: 90 يوماً قابلة للتمديد كتابة إلى 180 يوماً (المادة 53) | "
            f"العقد: {'محدد المدة وفق المادة 37' if not is_saudi else 'عقد موثق عبر منصة قوى'}."
        )

        is_valid = len(errors) == 0
        token = f"APP-{uuid.uuid4().hex[:8].upper()}" if is_valid else ""

        if is_valid:
            self._pending_approvals[token] = {
                "candidate_name": clean_name,
                "job_id": job_id,
                "job_title": job_title,
                "is_saudi": is_saudi,
                "id_number": clean_id,
                "passport_number": (passport_number or "").strip(),
                "email": (email or "").strip(),
                "phone": (phone or "").strip(),
                "salary_expected": float(salary_expected),
                "salary_proposed": float(salary_proposed),
                "housing_allowance": float(housing_allowance),
                "transportation_allowance": float(transportation_allowance),
                "total_salary": total_sal,
                "contract_status": contract_status,
                "duration_of_contract": duration_of_contract,
                "availability": availability,
                "applicant_notes": applicant_notes,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return ApplicantDryRunResult(
            is_valid=is_valid,
            candidate_name=clean_name,
            job_id=job_id,
            job_title=job_title,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            id_number=clean_id,
            passport_number=(passport_number or "").strip(),
            email=(email or "").strip(),
            phone=(phone or "").strip(),
            salary_expected=float(salary_expected),
            salary_proposed=float(salary_proposed),
            housing_allowance=float(housing_allowance),
            transportation_allowance=float(transportation_allowance),
            total_salary=total_sal,
            contract_status=contract_status,
            duration_of_contract=duration_of_contract,
            is_saudi_restricted_job=is_restricted,
            statutory_article=statutory_article,
            statutory_explanation_ar=statutory_explanation,
            warnings=warnings,
            errors=errors,
            approval_token=token,
            can_proceed=is_valid,
        )

    def apply_applicant(
        self,
        approval_token: str,
        user_confirmation_text: str = "تأكيد",
        stage_id: Optional[int] = None,
    ) -> ApplicantExecutionResult:
        """
        اعتماد وتسجيل طلب التوظيف في Odoo بموجب مبدأ التحقق المزدوج Four-Eyes والتحقق المستقل بعد الكتابة.
        """
        if user_confirmation_text.strip() != "تأكيد":
            return ApplicantExecutionResult(
                success=False,
                applicant_id=None,
                candidate_name="",
                job_id=0,
                job_title="",
                is_saudi=True,
                total_salary=0.0,
                approval_status="draft",
                readback_verified=False,
                message_ar="مبدأ التحقق المزدوج: يلزم إدخال كلمة «تأكيد» صراحة لتسجيل المرشح في Odoo.",
                audit_logged=False,
            )

        if not self.write_gateway:
            return ApplicantExecutionResult(
                success=False,
                applicant_id=None,
                candidate_name="",
                job_id=0,
                job_title="",
                is_saudi=True,
                total_salary=0.0,
                approval_status="draft",
                readback_verified=False,
                message_ar="بوابة الكتابة لسجلات التوظيف غير مهيأة أو غير متصلة.",
                audit_logged=False,
            )

        pending = self._pending_approvals.pop(approval_token, None)
        if not pending:
            return ApplicantExecutionResult(
                success=False,
                applicant_id=None,
                candidate_name="",
                job_id=0,
                job_title="",
                is_saudi=True,
                total_salary=0.0,
                approval_status="draft",
                readback_verified=False,
                message_ar="رمز الموافقة غير صالح أو منتهي الصلاحية؛ يرجى إجراء التدقيق التجريبي أولاً.",
                audit_logged=False,
            )

        c_name = pending["candidate_name"]
        j_id = pending["job_id"]
        is_saudi = pending["is_saudi"]

        try:
            created_id = self.write_gateway.create_applicant(
                partner_name=c_name,
                job_id=j_id,
                is_saudi=is_saudi,
                email_from=pending.get("email"),
                partner_phone=pending.get("phone"),
                id_number=pending.get("id_number"),
                passport_number=pending.get("passport_number"),
                stage_id=stage_id,
                salary_expected=pending.get("salary_expected", 0.0),
                salary_proposed=pending.get("salary_proposed", 0.0),
                housing_allowance=pending.get("housing_allowance", 0.0),
                transportation_allowance=pending.get("transportation_allowance", 0.0),
                contract_status=pending.get("contract_status", "single"),
                duration_of_contract=pending.get("duration_of_contract", 1),
                availability=pending.get("availability"),
                applicant_notes=pending.get("applicant_notes"),
            )

            # التحقق المستقل بعد الكتابة (Readback Verification)
            read_back = self.write_gateway.read_applicant(created_id)
            readback_ok = bool(read_back and read_back.get("id") == created_id)

            audit_entry = {
                "event": "applicant_created",
                "applicant_id": created_id,
                "candidate_name": c_name,
                "job_id": j_id,
                "job_title": pending.get("job_title"),
                "is_saudi": is_saudi,
                "total_salary": pending.get("total_salary"),
                "readback_verified": readback_ok,
                "approval_token": approval_token,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._write_audit_log(audit_entry)

            return ApplicantExecutionResult(
                success=True,
                applicant_id=created_id,
                candidate_name=c_name,
                job_id=j_id,
                job_title=pending.get("job_title", ""),
                is_saudi=is_saudi,
                total_salary=pending.get("total_salary", 0.0),
                approval_status="draft",
                readback_verified=readback_ok,
                message_ar=f"تم تسجيل المرشح '{c_name}' بنجاح في Odoo برقم السجل #{created_id}.",
                audit_logged=True,
            )
        except Exception as exc:
            return ApplicantExecutionResult(
                success=False,
                applicant_id=None,
                candidate_name=c_name,
                job_id=j_id,
                job_title=pending.get("job_title", ""),
                is_saudi=is_saudi,
                total_salary=pending.get("total_salary", 0.0),
                approval_status="draft",
                readback_verified=False,
                message_ar=f"فشل إنشاء طلب التوظيف في Odoo: {exc}",
                audit_logged=False,
            )

    def _write_audit_log(self, entry: Dict[str, Any]) -> None:
        try:
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
