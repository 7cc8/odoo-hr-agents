"""
خدمة إدارة المعاملات الحكومية والجوازات والتأشيرات (Government Relations Service)
====================================================================================
الطبقة التنفيذية لإدارة وتوثيق المعاملات الحكومية في Odoo (gr.transaction) بالتكامل التام مع
أنظمة مقيم وقوى والجوازات ونظام العمل السعودي (المادة 40):
1. المادة 40 فقرة (1): إلزام صاحب العمل بنفقات رخص العمل وتجديد الإقامة وما يترتب على التأخير.
2. التحقق الصارم من صفة الموظف (سعودي أم غير سعودي):
   - حظر معاملات الجوازات ومقيم (تجديد إقامة، خروج وعودة، رخص عمل وافدين، نقل كفالة) للمواطن السعودي.
   - قصر معاملات السعودي على (توثيق عقود قوى، التأمينات الاجتماعية GOSI، التراخيص المهنية).
3. تدقيق الرسوم والنسب وتحديد الطرف المسؤول (المنشأة، العامل، أو مناصفة/نسبة مئوية).
4. مبدأ التحقق المزدوج Four-Eyes والتحقق المستقل بعد الكتابة (Readback Verification).
"""

from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_gr_write_gateway import OdooGRWriteGateway
from eos_service import detect_employee_nationality


GR_AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "gr_audit_log.jsonl")

# المعاملات المحصورة بالعمالة الوافدة (غير السعوديين)
EXPAT_ONLY_TRANSACTIONS = frozenset({
    "تجديد إقامة",
    "تجديد اقامة",
    "إصدار إقامة",
    "اصدار اقامة",
    "إصدار إقامة جديدة",
    "اصدار اقامة جديدة",
    "تأشيرة خروج وعودة",
    "تاشيرة خروج وعودة",
    "إصدار تأشيرة خروج وعودة",
    "اصدار تاشيرة خروج وعودة",
    "خروج وعودة مفردة",
    "خروج وعودة متعددة",
    "تأشيرة خروج نهائي",
    "تاشيرة خروج نهائي",
    "إصدار تأشيرة نهائية",
    "اصدار تاشيرة نهائية",
    "خروج نهائي",
    "تجديد رخصة عمل",
    "رخصة عمل",
    "رخص عمل",
    "نقل كفالة",
    "نقل خدمات",
    "تعديل مهنة",
    "تعديل مهنة في قوى ومقيم",
    "فحص طبي إقامة",
})

# المعاملات الحكومية الشائعة ورسومها المعيارية (التقديرية) في المنصات الحكومية
STANDARD_GOV_FEES: Dict[str, float] = {
    "تجديد إقامة": 650.0,
    "إصدار إقامة جديدة": 650.0,
    "إصدار تأشيرة خروج وعودة": 200.0,
    "خروج وعودة مفردة": 200.0,
    "خروج وعودة متعددة": 500.0,
    "إصدار تأشيرة نهائية": 0.0,
    "خروج نهائي": 0.0,
    "تجديد رخصة عمل": 100.0,
    "تعديل مهنة في قوى ومقيم": 1000.0,
    "تعديل مهنة": 1000.0,
    "نقل كفالة": 2000.0,
    "نقل خدمات": 2000.0,
    "توثيق عقد عمل في قوى": 0.0,
    "تسجيل في التأمينات الاجتماعية": 0.0,
    "شهادة صحية مهنية": 150.0,
}


@dataclass
class GRTransactionSummary:
    employee_id: int
    employee_name: str
    department_name: str
    is_saudi: bool
    nationality_text_ar: str
    identification_id: str
    total_transactions_count: int
    recent_transactions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class GRDryRunResult:
    is_valid: bool
    employee_id: int
    employee_name: str
    department_id: int
    department_name: str
    is_saudi: bool
    nationality_text_ar: str
    transaction: str
    transaction_type: str  # "party" or "split"
    transaction_date: str
    responsible_party: str  # "company" or "employee"
    company_percentage: float
    employee_percentage: float
    amount_sar: float
    company_share_sar: float
    employee_share_sar: float
    statutory_article: str
    statutory_explanation_ar: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    approval_token: str = ""
    can_proceed: bool = False


@dataclass
class GRExecutionResult:
    success: bool
    transaction_id: Optional[int]
    reference: str
    employee_id: int
    employee_name: str
    transaction: str
    amount_sar: float
    state: str
    readback_verified: bool
    message_ar: str
    audit_logged: bool


class GRService:
    """
    خدمة إدارة وتدقيق المعاملات الحكومية والجوازات في Odoo.
    تلتزم بضوابط المادة 40 وتمنع معاملات الوافدين للمواطنين السعوديين تلقائياً.
    """
    _shared_pending_approvals: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        readonly_repo: Optional[OdooReadonlyRepository] = None,
        write_gateway: Optional[OdooGRWriteGateway] = None,
        audit_log_path: Optional[str] = None
    ):
        self.readonly_repo = readonly_repo or OdooReadonlyRepository()
        self.write_gateway = write_gateway
        self.audit_log_path = audit_log_path or GR_AUDIT_LOG_FILE
        self._pending_approvals: Dict[str, Dict[str, Any]] = GRService._shared_pending_approvals

    def get_employee_gr_summary(
        self,
        employee_id: int,
        explicit_is_saudi: Optional[bool] = None,
        limit: int = 15
    ) -> GRTransactionSummary:
        """
        جلب وتلخيص المعاملات الحكومية المسجلة للموظف وتصنيفه (سعودي أم غير سعودي).
        """
        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            raise ValueError(f"الموظف برقم المعرف #{employee_id} غير موجود في Odoo.")

        emp_name = emp.get("name", "غير معروف")
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"
        ident = str(emp.get("identification_id") or "غير مسجل")

        is_saudi = detect_employee_nationality(emp, explicit_is_saudi)
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        txs = self.readonly_repo.get_employee_gr_transactions(employee_id=employee_id, limit=limit)

        return GRTransactionSummary(
            employee_id=employee_id,
            employee_name=emp_name,
            department_name=dept_name,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            identification_id=ident,
            total_transactions_count=len(txs),
            recent_transactions=txs[:5]
        )

    def dry_run_gr_transaction(
        self,
        employee_id: int,
        transaction: str,
        amount: Optional[float] = None,
        transaction_type: str = "party",  # "party" or "split"
        responsible_party: str = "company",  # "company" or "employee"
        company_percentage: float = 100.0,
        employee_percentage: float = 0.0,
        transaction_date: Optional[str] = None,
        description: Optional[str] = None,
        explicit_is_saudi: Optional[bool] = None,
    ) -> GRDryRunResult:
        """
        الفحص التجريبي الاستباقي للمعاملة الحكومية وتدقيق الضوابط النظامية للمادة 40.
        """
        errors: List[str] = []
        warnings: List[str] = []

        emp = self.readonly_repo.get_employee(employee_id)
        if not emp:
            return GRDryRunResult(
                is_valid=False,
                employee_id=employee_id,
                employee_name="غير معروف",
                department_id=0,
                department_name="غير معروف",
                is_saudi=True,
                nationality_text_ar="غير معروف",
                transaction=transaction,
                transaction_type=transaction_type,
                transaction_date=transaction_date or date.today().isoformat(),
                responsible_party=responsible_party,
                company_percentage=company_percentage,
                employee_percentage=employee_percentage,
                amount_sar=0.0,
                company_share_sar=0.0,
                employee_share_sar=0.0,
                statutory_article="المادة 40",
                statutory_explanation_ar="الموظف غير موجود في Odoo.",
                errors=["الموظف برقم المعرف المحدد غير موجود."],
                can_proceed=False
            )

        emp_name = emp.get("name", "غير معروف")
        dept_id = emp["department_id"][0] if emp.get("department_id") else 1
        dept_name = emp["department_id"][1] if emp.get("department_id") else "بدون قسم"

        is_saudi = detect_employee_nationality(emp, explicit_is_saudi)
        nat_text = "مواطن سعودي" if is_saudi else "وافد غير سعودي (مقيم)"

        clean_tx = transaction.strip()
        if not clean_tx:
            errors.append("يجب تحديد نوع المعاملة الحكومية.")

        # 1. التدقيق الصارم لجنسية الموظف مقابل المعاملة
        is_expat_tx = any(expat_t in clean_tx for expat_t in EXPAT_ONLY_TRANSACTIONS)
        if is_saudi and is_expat_tx:
            errors.append(
                f"حظر نظامي: الموظف ({emp_name}) مواطن سعودي، ومعاملة '{clean_tx}' خاصة بالوافدين والمقيمين "
                f"(الجوازات ومقيم) ولا تجوز للمواطنين نظاماً."
            )

        # تحديد الرسوم
        calc_amount = amount if (amount is not None and amount >= 0) else STANDARD_GOV_FEES.get(clean_tx, 0.0)

        # حساب نسب التوزيع والمبالغ
        t_type = "split" if transaction_type == "split" else "party"
        if t_type == "split":
            total_pct = company_percentage + employee_percentage
            if total_pct <= 0:
                comp_pct, emp_pct = 100.0, 0.0
            else:
                comp_pct = round((company_percentage / total_pct) * 100.0, 2)
                emp_pct = round((employee_percentage / total_pct) * 100.0, 2)
            comp_share = round((comp_pct / 100.0) * calc_amount, 2)
            emp_share = round((emp_pct / 100.0) * calc_amount, 2)
            resp_party = "company" if comp_share >= emp_share else "employee"
        else:
            resp_party = "employee" if responsible_party == "employee" else "company"
            if resp_party == "company":
                comp_pct, emp_pct = 100.0, 0.0
                comp_share, emp_share = calc_amount, 0.0
            else:
                comp_pct, emp_pct = 0.0, 100.0
                comp_share, emp_share = 0.0, calc_amount

        # 2. المادة 40 من نظام العمل: التزامات صاحب العمل
        statutory_art = "المادة 40 من نظام العمل السعودي"
        if not is_saudi and clean_tx in ("تجديد إقامة", "تجديد رخصة عمل", "إصدار إقامة جديدة"):
            if resp_party == "employee" or emp_share > 0:
                warnings.append(
                    "المادة 40 فقرة (1): يلزم صاحب العمل نظاماً بتحمل رسوم رخص العمل والإقامة وتجديدهما؛ "
                    "تحميل العامل جزءاً من هذه الرسوم يتطلب موافقة كتابية صريحة أو سنداً تعاقدياً."
                )

        t_date = transaction_date or date.today().isoformat()
        expl_ar = (
            f"معاملة '{clean_tx}' للموظف {emp_name} ({nat_text}): "
            f"الرسوم الإجمالية {calc_amount:,.2f} ر.س. "
            f"حصة المنشأة: {comp_share:,.2f} ر.س ({comp_pct}%) | "
            f"حصة الموظف: {emp_share:,.2f} ر.س ({emp_pct}%)."
        )

        is_valid = len(errors) == 0
        token = ""
        ref_name = f"GR-{datetime.now(timezone.utc).strftime('%Y%m')}-{uuid.uuid4().hex[:4].upper()}"

        if is_valid:
            token = f"GR-{uuid.uuid4().hex[:8].upper()}"
            self._pending_approvals[token] = {
                "name": ref_name,
                "employee_id": employee_id,
                "employee_name": emp_name,
                "transaction": clean_tx,
                "transaction_type": t_type,
                "transaction_date": t_date,
                "responsible_party": resp_party,
                "company_percentage": comp_pct,
                "employee_percentage": emp_pct,
                "amount": calc_amount,
                "description": description or expl_ar,
                "is_saudi": is_saudi,
            }

        return GRDryRunResult(
            is_valid=is_valid,
            employee_id=employee_id,
            employee_name=emp_name,
            department_id=dept_id,
            department_name=dept_name,
            is_saudi=is_saudi,
            nationality_text_ar=nat_text,
            transaction=clean_tx,
            transaction_type=t_type,
            transaction_date=t_date,
            responsible_party=resp_party,
            company_percentage=comp_pct,
            employee_percentage=emp_pct,
            amount_sar=calc_amount,
            company_share_sar=comp_share,
            employee_share_sar=emp_share,
            statutory_article=statutory_art,
            statutory_explanation_ar=expl_ar,
            warnings=warnings,
            errors=errors,
            approval_token=token,
            can_proceed=is_valid
        )

    def apply_gr_transaction(
        self,
        approval_token: str,
        user_confirmation_text: str = "تأكيد",
        state: str = "confirmed"
    ) -> GRExecutionResult:
        """
        اعتماد وتسجيل المعاملة الحكومية فعلياً في Odoo مع إلزامية التأكيد الكتابي الصريح.
        """
        if user_confirmation_text != "تأكيد":
            return GRExecutionResult(
                success=False,
                transaction_id=None,
                reference="",
                employee_id=0,
                employee_name="",
                transaction="",
                amount_sar=0.0,
                state="",
                readback_verified=False,
                message_ar="مرفوض: يتطلب اعتماد المعاملة الحكومية كلمة 'تأكيد' صريحة من المستخدم.",
                audit_logged=False
            )

        payload = self._pending_approvals.pop(approval_token, None)
        if not payload:
            return GRExecutionResult(
                success=False,
                transaction_id=None,
                reference="",
                employee_id=0,
                employee_name="",
                transaction="",
                amount_sar=0.0,
                state="",
                readback_verified=False,
                message_ar=f"رمز الموافقة '{approval_token}' غير صالح أو منتهي الصلاحية.",
                audit_logged=False
            )

        if not self.write_gateway:
            return GRExecutionResult(
                success=False,
                transaction_id=None,
                reference=payload["name"],
                employee_id=payload["employee_id"],
                employee_name=payload["employee_name"],
                transaction=payload["transaction"],
                amount_sar=payload["amount"],
                state="dry_run_only",
                readback_verified=False,
                message_ar="بوابة الكتابة إلى Odoo غير مهيأة (وضع القراءة فقط).",
                audit_logged=False
            )

        try:
            created_id = self.write_gateway.create_gr_transaction(
                employee_id=payload["employee_id"],
                transaction=payload["transaction"],
                transaction_type=payload["transaction_type"],
                transaction_date=payload["transaction_date"],
                responsible_party=payload["responsible_party"],
                company_percentage=payload["company_percentage"],
                employee_percentage=payload["employee_percentage"],
                amount=payload["amount"],
                name=payload["name"],
                description=payload["description"],
                state="draft",
            )

            if state == "confirmed":
                self.write_gateway.confirm_gr_transaction(created_id)

            # التحقق المستقل بعد الكتابة (Readback Verification)
            read_back = self.write_gateway.read_gr_transaction(created_id)
            verified = bool(read_back and read_back.get("id") == created_id)

            # توثيق العملية في سجل التدقيق
            audit_entry = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event": "APPLY_GR_TRANSACTION",
                "transaction_id": created_id,
                "reference": payload["name"],
                "employee_id": payload["employee_id"],
                "employee_name": payload["employee_name"],
                "is_saudi": payload.get("is_saudi", True),
                "transaction": payload["transaction"],
                "amount": payload["amount"],
                "responsible_party": payload["responsible_party"],
                "state": state,
                "readback_verified": verified,
            }
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")

            msg = (
                f"تم اعتماد وتسجيل المعاملة الحكومية بنجاح في Odoo برقم #{created_id} "
                f"ومرجع ({payload['name']})، لنوع ({payload['transaction']}) بمبلغ {payload['amount']:,.2f} ر.س."
            )

            return GRExecutionResult(
                success=True,
                transaction_id=created_id,
                reference=payload["name"],
                employee_id=payload["employee_id"],
                employee_name=payload["employee_name"],
                transaction=payload["transaction"],
                amount_sar=payload["amount"],
                state=state,
                readback_verified=verified,
                message_ar=msg,
                audit_logged=True
            )
        except Exception as e:
            return GRExecutionResult(
                success=False,
                transaction_id=None,
                reference=payload["name"],
                employee_id=payload["employee_id"],
                employee_name=payload["employee_name"],
                transaction=payload["transaction"],
                amount_sar=payload["amount"],
                state="failed",
                readback_verified=False,
                message_ar=f"فشل تسجيل المعاملة الحكومية في Odoo: {str(e)}",
                audit_logged=False
            )
