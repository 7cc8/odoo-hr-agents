"""
Smoke Test اختياري لمحرك Laya Neural Consultant مع النموذج الحقيقي
===================================================================
هذا الملف لا يعمل ضمن pytest العادي.
التشغيل يدوياً من PowerShell:
    .\.venv\Scripts\python.exe tests\smoke_laya_neural.py

المتطلبات:
- LAYA_ENABLED=true في .env أو يدوياً قبل التشغيل
- الأوزان موجودة في laya-models/multilingual/ (~600MB)
- لا يقرأ أو يكتب في Odoo
- يطبع النتيجة الحقيقية من النموذج

ملاحظة: هذا smoke test على أمثلة synthetic لا تمثل تقييماً للدقة الكاملة.
"""
from __future__ import annotations

import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# تفعيل الاستشارة العصبية لهذا الاختبار فقط
os.environ["LAYA_ENABLED"] = "true"
os.environ["LAYA_MODE"] = "shadow"

# إضافة مسار المشروع
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from laya_neural_consultant import (
    ConsultationRequest,
    ConsultationResult,
    consult_decision,
    get_engine_status,
    _load_engine,
)


def print_sep(title=""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def print_result(label: str, result: ConsultationResult):
    print(f"\n[{label}]")
    print(f"  status:               {result.status}")
    print(f"  mode:                 {result.mode}")
    print(f"  suggested_choice:     {result.suggested_choice}")
    print(f"  answer_probability:   {result.answer_probability}")
    print(f"  dist_confidence:      {result.distribution_confidence}")
    print(f"  probabilities:        {result.probabilities}")
    print(f"  model_id:             {result.model_id}")
    print(f"  latency_ms:           {result.latency_ms:.1f}" if result.latency_ms else "  latency_ms: N/A")
    print(f"  truncation_warning:   {result.truncation_warning}")
    print(f"  execution_authorized: {result.execution_authorized}")
    if result.error_code:
        print(f"  error_code:           {result.error_code}")


def main():
    print_sep("بيانات البيئة والنموذج")
    status = get_engine_status()
    for k, v in status.items():
        print(f"  {k}: {v}")

    print_sep("تحميل المحرك (قياس زمن التهيئة)")
    t0 = time.monotonic()
    engine = _load_engine()
    init_time = (time.monotonic() - t0) * 1000
    print(f"  Engine loaded: {engine is not None}")
    print(f"  Init time: {init_time:.0f} ms")
    print(f"  (ملاحظة: زمن التهيئة ≠ زمن الاستدلال)")

    print_sep("الأمثلة الاختبارية (Synthetic Smoke Tests)")

    cases = [
        {
            "label": "1. غموض يحتاج توضيحاً (تحضير طلب إجازة بدون تفاصيل)",
            "verified_facts": None,
            "user_claims": "أريد إجازة",
            "agent_inferences": "domain=leaves, action=query",
            "missing_information": "عدد الأيام وتاريخ البداية غير معروفان",
        },
        {
            "label": "2. معلومات متعارضة تحتاج إعادة استعلام",
            "verified_facts": "رصيد الإجازة: 5 أيام",
            "user_claims": "لدي 15 يوم إجازة متبقية وأريد أخذ 10",
            "agent_inferences": "domain=leaves, action=query",
            "conflicts": "المستخدم يدّعي 15 يوماً لكن السجل يُظهر 5 أيام فقط",
        },
        {
            "label": "3. أدلة غير كافية (لا معلومات)",
            "verified_facts": None,
            "user_claims": "ساعدني",
            "agent_inferences": "domain=general, action=query",
            "missing_information": "الطلب غير محدد بالكامل",
        },
        {
            "label": "4. خطوة واضحة لا تستلزم نموذجاً (لإثبات bypass — disabled في هذا الاختبار)",
            "verified_facts": "الموظف موجود بـ ID=42، يطلب عرض رصيد إجازته",
            "user_claims": "كم رصيدي من الإجازات؟",
            "agent_inferences": "domain=leaves, action=query",
        },
        {
            "label": "5. خطأ تشخيصي له أكثر من مسار مسموح",
            "verified_facts": "سجل حضور الموظف يُظهر تأخيراً متكرراً",
            "user_claims": "الموظف يتأخر دائماً، ماذا أفعل؟",
            "agent_inferences": "domain=disciplinary, action=query",
            "missing_information": "لم يتم تحديد إن كان مطلوباً تقرير فقط أم تطبيق جزاء",
        },
    ]

    for case in cases:
        req = ConsultationRequest(
            caller_agent="smoke_test",
            stage="test",
            question_id="next_handling_step",
            instructions="بناءً على الأدلة، ما هي الخطوة التالية الأنسب لسراج؟",
            allowed_choices={
                "route_read":   "توجيه لوكيل القراءة (فاحص) للاستعلام",
                "clarify_user": "طلب توضيح إضافي من المستخدم",
                "route_write":  "تحضير مسودة كتابة وطلب اعتماد",
            },
            verified_facts=case.get("verified_facts"),
            user_claims=case.get("user_claims"),
            agent_inferences=case.get("agent_inferences"),
            missing_information=case.get("missing_information"),
            conflicts=case.get("conflicts"),
        )
        result = consult_decision(req)
        print_result(case["label"], result)

    print_sep("تحذيرات مهمة")
    print("  ⚠️  الاحتمالات ليست معايَرة — لا تُثبت صحة الاختيار.")
    print("  ⚠️  هذه أمثلة synthetic، ليست تقييماً فعلياً على بيانات المشروع.")
    print("  ⚠️  execution_authorized = False في جميع النتائج دائماً.")
    print("  ⚠️  وضع shadow: الاقتراح مُسجَّل للمقارنة فقط، لا يدخل للسياق.")
    print("\nانتهى smoke test بنجاح.")


if __name__ == "__main__":
    main()
