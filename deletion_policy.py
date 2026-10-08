"""
سياسة وضوابط الحذف والأرشفة المحكومة (Controlled Deletion & Archiving Policy)
=============================================================================
تحدد الشروط والسياسات الخاصة بكل نموذج مسموح، والمراجع، والآثار المعروفة،
وإنشاء خطة العملية الدقيقة مع رمز اعتماد ذي صلاحية زمنية (TTL) واستهلاك أحادي.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

ALLOWED_DELETION_MODELS = frozenset({"hr.employee"})
ALLOWED_ARCHIVE_MODELS = frozenset({
    "hr.employee",
    "hr.department",
    "hr.job",
    "hr.applicant",
    "hr.leave.type",
    "res.company",
})
ALLOWED_UNARCHIVE_MODELS = frozenset({
    "hr.employee",
    "hr.department",
    "hr.job",
    "hr.applicant",
    "hr.leave.type",
    "res.company",
})

APPROVAL_TTL_SECONDS = 300  # 5 دقائق صلاحية الاعتماد


class DeletionPolicyError(Exception):
    """خطأ في سياسة الحذف أو الأرشفة أو الاسترجاع."""


MODEL_LABELS = {
    "hr.employee": "سجل الموظفين (hr.employee)",
    "hr.department": "سجل الأقسام (hr.department)",
    "hr.job": "سجل الوظائف والمسميات (hr.job)",
    "hr.applicant": "سجل المتقدمين للتوظيف (hr.applicant)",
    "hr.leave.type": "سجل أنواع الإجازات (hr.leave.type)",
    "res.company": "سجل المنشآت والشركات (res.company)",
}


KNOWN_IMPACTS = {
    "hr.employee": {
        "archive": "إيقاف ظهور الموظف في القوائم النشطة مع حفظ كافة بياناته وعقوده وحركاته التاريخية.",
        "unarchive": "إعادة تنشيط الموظف وإظهاره في القوائم النشطة ونظام Odoo وإتاحة ربطه بالحركات الإدارية.",
        "delete": "إزالة السجل نهائياً من قاعدة بيانات Odoo. إذا كان الموظف مرتبطاً بعقود أو حركات مالية أو قيود مرجعية ملزمة، سيرفض خادم Odoo العملية لحماية التكامل المرجعي.",
    },
    "hr.department": {
        "archive": "أرشفة القسم وإخفاؤه من قوائم الاختيار النشطة مع بقاء تبعية الموظفين التاريخية.",
        "unarchive": "إعادة تنشيط القسم وإتاحته للاختيار وتعيين الموظفين فيه ونظام Odoo.",
    },
    "hr.job": {
        "archive": "أرشفة المسمى الوظيفي وإخفاؤه من قوائم الوظائف النشطة.",
        "unarchive": "إعادة تنشيط المسمى الوظيفي وإتاحته للاختيار في عقود وسجلات الموظفين.",
    },
    "hr.applicant": {
        "archive": "أرشفة ملف المتقدم للتوظيف مع حفظ كافة سجلات التقييم والملاحظات.",
        "unarchive": "إعادة تنشيط طلب التوظيف واستئناف إجراءات المتابعة والتقييم.",
    },
    "hr.leave.type": {
        "archive": "إيقاف إتاحة نوع الإجازة للتقديم المستقبلي مع حفظ السجلات السابقة.",
        "unarchive": "إعادة إتاحة نوع الإجازة للتقديم في طلبات الإجازات.",
    },
    "res.company": {
        "archive": "إيقاف تنشيط المنشأة/الشركة في النظام مع حفظ قيودها وسجلاتها.",
        "unarchive": "إعادة تنشيط المنشأة/الشركة وإتاحة العمليات عليها في Odoo.",
    },
}


def resolve_model_from_query(query: str) -> Tuple[str, str]:
    """تحديد النموذج والوصف العربي بناءً على الكلمات المفتاحية في الاستعلام."""
    q = query.lower()
    if any(w in q for w in ("قسم", "القسم", "اقسام", "أقسام", "department")):
        return "hr.department", MODEL_LABELS["hr.department"]
    if any(w in q for w in ("وظيفة", "الوظيفة", "وظائف", "مسمى", "المسمى", "job")):
        return "hr.job", MODEL_LABELS["hr.job"]
    if any(w in q for w in ("مرشح", "متقدم", "متقدمين", "توظيف", "applicant")):
        return "hr.applicant", MODEL_LABELS["hr.applicant"]
    if any(w in q for w in ("نوع إجازة", "نوع اجازه", "إجازات", "اجازات", "leave.type")):
        return "hr.leave.type", MODEL_LABELS["hr.leave.type"]
    if any(w in q for w in ("شركة", "الشركة", "منشأة", "المنشأة", "company")):
        return "res.company", MODEL_LABELS["res.company"]
    # الافتراضي سجل الموظفين
    return "hr.employee", MODEL_LABELS["hr.employee"]


@dataclass
class DeletionPlan:
    plan_id: str
    action_type: str  # "archive", "unarchive", or "delete"
    model: str
    model_label: str
    record_id: int
    record_name: str
    company_id: Optional[int]
    company_name: str
    connection_id: str
    count: int
    reason: str
    known_impact: str
    created_at: float
    expires_at: float
    user_id: str
    consumed: bool = False

    def is_valid(self, current_user_id: Optional[str] = None) -> Tuple[bool, str]:
        if self.consumed:
            return False, "⚠️ تم استهلاك هذا الاعتماد مسبقاً ولا يمكن إعادة تنفيذه."
        if time.time() > self.expires_at:
            return False, "⚠️ انتهت صلاحية هذا الاعتماد (تجاوزت مهلة الـ 5 دقائق). يرجى طلب اعتماد جديد."
        if current_user_id and str(self.user_id) != str(current_user_id):
            return False, "⚠️ لا يمكن تنفيذ هذه العملية: هوية صاحب التأكيد لا تطابق هوية مقدم الطلب الأصلية."
        return True, "صالح"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "action_type": self.action_type,
            "model": self.model,
            "model_label": self.model_label,
            "record_id": self.record_id,
            "record_name": self.record_name,
            "company_id": self.company_id,
            "company_name": self.company_name,
            "connection_id": self.connection_id,
            "count": self.count,
            "reason": self.reason,
            "known_impact": self.known_impact,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "user_id": str(self.user_id),
            "consumed": self.consumed,
        }


def create_deletion_plan(
    action_type: str,
    model: str,
    record_id: int,
    record_name: str,
    company_id: Optional[int] = None,
    company_name: str = "الشركة الافتراضية",
    connection_id: str = "default",
    reason: str = "طلب معتمد من المستخدم",
    user_id: str = "default_user",
) -> DeletionPlan:
    """إنشاء خطة دقيقة للأرشفة أو الاسترجاع أو الحذف لسجل مفرد بعد التحقق من السياسة."""
    action_norm = action_type.strip().lower()
    if action_norm not in ("archive", "unarchive", "delete"):
        raise DeletionPolicyError(f"نوع الإجراء «{action_type}» غير صالح؛ يجب أن يكون 'archive' أو 'unarchive' أو 'delete'.")

    if action_norm == "delete" and model not in ALLOWED_DELETION_MODELS:
        raise DeletionPolicyError(
            f"🚫 سياسة النماذج: النموذج «{model}» غير مصرح بحذفه نهائياً. النماذج المسموحة: {list(ALLOWED_DELETION_MODELS)}."
        )

    if action_norm == "archive" and model not in ALLOWED_ARCHIVE_MODELS:
        raise DeletionPolicyError(
            f"🚫 سياسة النماذج: النموذج «{model}» غير مصرح بأرشفته. النماذج المسموحة: {list(ALLOWED_ARCHIVE_MODELS)}."
        )

    if action_norm == "unarchive" and model not in ALLOWED_UNARCHIVE_MODELS:
        raise DeletionPolicyError(
            f"🚫 سياسة النماذج: النموذج «{model}» غير مصرح باسترجاعه من الأرشفة. النماذج المسموحة: {list(ALLOWED_UNARCHIVE_MODELS)}."
        )

    if not isinstance(record_id, int) or record_id <= 0:
        raise DeletionPolicyError("معرف السجل يجب أن يكون رقماً صحيحاً موجباً مفرداً.")

    impacts = KNOWN_IMPACTS.get(model, {})
    impact_text = impacts.get(action_norm)
    if not impact_text:
        raise DeletionPolicyError(
            f"⚠️ أثر العملية للنموذج «{model}» غير معروف أو غير موثق بالسياسة المعتمدة؛ تم إيقاف التنفيذ حمايةً للبيانات."
        )

    now = time.time()
    expires = now + APPROVAL_TTL_SECONDS
    plan_raw = f"{user_id}:{action_norm}:{model}:{record_id}:{company_id}:{now}"
    plan_id = hashlib.sha256(plan_raw.encode("utf-8")).hexdigest()[:12]

    model_label = MODEL_LABELS.get(model, model)

    return DeletionPlan(
        plan_id=plan_id,
        action_type=action_norm,
        model=model,
        model_label=model_label,
        record_id=record_id,
        record_name=record_name,
        company_id=company_id,
        company_name=company_name,
        connection_id=connection_id,
        count=1,
        reason=reason,
        known_impact=impact_text,
        created_at=now,
        expires_at=expires,
        user_id=str(user_id),
        consumed=False,
    )
