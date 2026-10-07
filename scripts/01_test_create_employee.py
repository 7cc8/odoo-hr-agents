"""
01_test_create_employee.py

بروتوكول التجربة الواحدة: إنشاء موظف تجريبي واحد فعلياً على sandbox عبر XML-RPC،
لاكتشاف السلوك الحقيقي لبيئة Odoo (multi-source customized) قبل بناء وثيقة المسار A.

لا يُنفذ هذا السكربت على بيئة إنتاج (production). استخدم قاعدة sandbox/staging فقط.

الأسئلة الثلاث التي نريد إجابتها:
1) هل create() ينجح بالحد الأدنى من الحقول، أو نحتاج hr.version / resource_id صراحة؟
2) هل تتفعّل قيود/onchange من موديولات مخصصة ترث hr.employee.form
   (مثل nthub_hr_disciplinary, prosys_hr_contract_total, hr_employee_profile)؟
3) هل تظهر حقول "مطلوبة فعلياً" رغم أنها required: False في الـ schema الأساسي؟
"""

import os
import sys
import json
import xmlrpc.client
from datetime import datetime, timezone

ODOO_URL = os.environ.get("ODOO_URL")
ODOO_DB = os.environ.get("ODOO_DB")
ODOO_USERNAME = os.environ.get("ODOO_USERNAME")
ODOO_API_KEY = os.environ.get("ODOO_API_KEY")

REQUIRED_ENV = ["ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_API_KEY"]

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def log_event(event: dict):
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    log_path = os.path.join(LOG_DIR, "01_test_create_employee.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(json.dumps(event, ensure_ascii=False, indent=2))


def check_env():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(f"[ERROR] متغيرات البيئة الناقصة: {', '.join(missing)}")
        print("راجع README.md لطريقة الإعداد على PowerShell.")
        sys.exit(1)


def connect():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    version_info = common.version()
    log_event({"step": "server_version", "result": version_info})

    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_API_KEY, {})
    if not uid:
        log_event({"step": "authenticate", "result": "FAILED"})
        sys.exit(1)

    log_event({"step": "authenticate", "result": "SUCCESS", "uid": uid})
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models


def inspect_employee_fields(models, uid):
    """السؤال 3: نتحقق من fields_get على hr.employee لمعرفة أي حقول required فعلياً
    في الـ schema، ونطبع أي حقول غير قياسية (مضافة من موديولات مخصصة)."""
    fields = models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        "hr.employee", "fields_get",
        [], {"attributes": ["string", "type", "required", "help"]}
    )
    required_fields = {k: v for k, v in fields.items() if v.get("required")}
    log_event({
        "step": "fields_get_hr_employee",
        "total_fields": len(fields),
        "required_fields": list(required_fields.keys()),
    })
    return fields


def inspect_module_exclusions(models, uid):
    """تحقق مستقل: هل exclusion_ids حقل موجود فعلياً على ir.module.module،
    وهل قراءته تُرجع True/False بدل فراغ تام (يفيد لتصحيح ملاحظة الكتالوج)."""
    try:
        fields = models.execute_kw(
            ODOO_DB, uid, ODOO_API_KEY,
            "ir.module.module", "fields_get",
            [], {"attributes": ["string", "type"]}
        )
        has_exclusion_field = "exclusion_ids" in fields
        log_event({
            "step": "fields_get_ir_module_module",
            "has_exclusion_ids_field": has_exclusion_field,
        })

        if has_exclusion_field:
            sample = models.execute_kw(
                ODOO_DB, uid, ODOO_API_KEY,
                "ir.module.module", "search_read",
                [[["exclusion_ids", "!=", False]]],
                {"fields": ["name", "exclusion_ids"], "limit": 5}
            )
            log_event({"step": "sample_modules_with_exclusions", "result": sample})
    except Exception as e:
        log_event({"step": "inspect_module_exclusions", "error": str(e)})


def attempt_minimal_create(models, uid):
    """السؤال 1 و2: نحاول create() بأقل عدد ممكن من الحقول،
    ونرصد استجابة الخادم بالتفصيل (نجاح أو استثناء كامل)."""
    minimal_payload = {
        "name": "TEST_MVP_DryRun_DoNotUse",
    }
    log_event({"step": "attempt_minimal_create", "payload": minimal_payload})

    try:
        new_id = models.execute_kw(
            ODOO_DB, uid, ODOO_API_KEY,
            "hr.employee", "create",
            [minimal_payload]
        )
        log_event({
            "step": "attempt_minimal_create",
            "result": "SUCCESS",
            "new_employee_id": new_id,
        })
        return new_id
    except xmlrpc.client.Fault as fault:
        log_event({
            "step": "attempt_minimal_create",
            "result": "FAILED",
            "fault_code": fault.faultCode,
            "fault_string": fault.faultString,
        })
        return None


def cleanup_test_record(models, uid, employee_id):
    """إزالة السجل التجريبي بعد التحقق، لتجنب تلويث بيانات الـ sandbox."""
    if not employee_id:
        return
    try:
        models.execute_kw(
            ODOO_DB, uid, ODOO_API_KEY,
            "hr.employee", "unlink",
            [[employee_id]]
        )
        log_event({"step": "cleanup", "result": "SUCCESS", "employee_id": employee_id})
    except xmlrpc.client.Fault as fault:
        log_event({
            "step": "cleanup",
            "result": "FAILED",
            "fault_string": fault.faultString,
            "note": "قد تحتاج حذف السجل يدوياً من الواجهة.",
        })


def main():
    check_env()
    log_event({"step": "start", "note": "بروتوكول تجربة create() الواحدة - المسار A تمهيدي"})

    uid, models = connect()
    inspect_employee_fields(models, uid)
    inspect_module_exclusions(models, uid)
    new_id = attempt_minimal_create(models, uid)
    cleanup_test_record(models, uid, new_id)

    log_event({"step": "end", "note": "راجع logs/01_test_create_employee.jsonl للتفاصيل الكاملة"})


if __name__ == "__main__":
    main()
