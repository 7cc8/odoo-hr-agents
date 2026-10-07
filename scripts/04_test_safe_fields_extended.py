import os
import sys
import json
import xmlrpc.client
from datetime import datetime, timezone

ODOO_URL = os.environ.get("ODOO_URL")
ODOO_DB = os.environ.get("ODOO_DB")
ODOO_USERNAME = os.environ.get("ODOO_USERNAME")
ODOO_API_KEY = os.environ.get("ODOO_API_KEY")
ALLOWED_TEST_DBS = [x.strip() for x in os.environ.get("ALLOWED_TEST_DBS", "").split(",") if x.strip()]

TEST_COMPANY_ID = int(os.environ.get("TEST_COMPANY_ID", "15"))
TEST_DEPARTMENT_ID = int(os.environ.get("TEST_DEPARTMENT_ID", "8"))
TEST_JOB_ID = int(os.environ.get("TEST_JOB_ID", "22"))

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

REQUIRED_ENV = ["ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_API_KEY"]

def log_event(event: dict):
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    log_path = os.path.join(LOG_DIR, "04_test_safe_fields_extended.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(json.dumps(event, ensure_ascii=False, indent=2))

def fail(msg, code=1):
    log_event({"step": "fatal", "message": msg})
    sys.exit(code)

def check_env():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        fail(f"Missing env vars: {', '.join(missing)}")

    log_event({
        "step": "environment",
        "odoo_url": ODOO_URL,
        "odoo_db": ODOO_DB,
        "allowed_test_dbs": ALLOWED_TEST_DBS,
        "test_company_id": TEST_COMPANY_ID,
        "test_department_id": TEST_DEPARTMENT_ID,
        "test_job_id": TEST_JOB_ID,
    })

    if ODOO_DB not in ALLOWED_TEST_DBS:
        fail("Target DB is not in ALLOWED_TEST_DBS; refusing create/write/unlink", code=2)

def connect():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    version_info = common.version()
    log_event({"step": "server_version", "result": version_info})

    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_API_KEY, {})
    if not uid:
        fail("Authentication failed")

    log_event({"step": "authenticate", "result": "SUCCESS", "uid": uid})
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models

def search_read_one(models, uid, model, domain, fields):
    rows = models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        model, "search_read",
        [domain],
        {"fields": fields, "limit": 2}
    )
    return rows

def validate_reference_rows(models, uid):
    company = search_read_one(
        models, uid, "res.company",
        [["id", "=", TEST_COMPANY_ID], ["active", "=", True]],
        ["id", "name", "active"]
    )
    department = search_read_one(
        models, uid, "hr.department",
        [["id", "=", TEST_DEPARTMENT_ID], ["company_id", "=", TEST_COMPANY_ID], ["active", "=", True]],
        ["id", "name", "company_id", "complete_name", "active"]
    )
    job = search_read_one(
        models, uid, "hr.job",
        [["id", "=", TEST_JOB_ID], ["company_id", "=", TEST_COMPANY_ID], ["active", "=", True]],
        ["id", "name", "company_id", "department_id", "active"]
    )

    log_event({"step": "reference_company", "rows": company})
    log_event({"step": "reference_department", "rows": department})
    log_event({"step": "reference_job", "rows": job})

    if len(company) != 1:
        fail("Company reference is invalid or ambiguous")
    if len(department) != 1:
        fail("Department reference is invalid or ambiguous")
    if len(job) != 1:
        fail("Job reference is invalid or ambiguous")

    return company[0], department[0], job[0]

def duplicate_check(models, uid, work_email):
    rows = models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        "hr.employee", "search_read",
        [[["work_email", "=", work_email]]],
        {"fields": ["id", "name", "work_email", "company_id", "active"], "limit": 10}
    )
    log_event({"step": "pre_create_duplicate_check", "work_email": work_email, "matches": rows})
    if rows:
        fail("Duplicate employee found by work_email; refusing test create")

def create_employee(models, uid):
    payload = {
        "name": "موظف اختبار عربي موسع",
        "work_email": "test_safe_fields_extended@example.com",
        "work_phone": "+966500000002",
        "mobile_phone": "+966511111113",
        "job_title": "منسق موارد بشرية تجريبي",
        "company_id": TEST_COMPANY_ID,
        "department_id": TEST_DEPARTMENT_ID,
        "job_id": TEST_JOB_ID,
    }

    context = {
        "allowed_company_ids": [TEST_COMPANY_ID]
    }

    log_event({"step": "attempt_create", "payload": payload, "context": context})

    new_id = models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        "hr.employee", "create",
        [payload],
        {"context": context}
    )
    log_event({"step": "attempt_create", "result": "SUCCESS", "new_employee_id": new_id, "payload": payload})
    return new_id, payload, context

def read_employee(models, uid, employee_id, context):
    rows = models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        "hr.employee", "read",
        [[employee_id]],
        {
            "fields": [
                "name",
                "work_email",
                "work_phone",
                "mobile_phone",
                "job_title",
                "company_id",
                "department_id",
                "job_id",
                "resource_id",
                "version_id",
                "active",
            ],
            "context": context
        }
    )
    rec = rows[0] if rows else {}
    log_event({"step": "post_create_read", "record": rec})
    return rec

def compare_payload(payload, rec):
    comparison = {
        "name_match": rec.get("name") == payload["name"],
        "work_email_match": rec.get("work_email") == payload["work_email"],
        "work_phone_match": rec.get("work_phone") == payload["work_phone"],
        "mobile_phone_match": rec.get("mobile_phone") == payload["mobile_phone"],
        "job_title_match": rec.get("job_title") == payload["job_title"],
        "company_id_match": bool(rec.get("company_id")) and rec["company_id"][0] == payload["company_id"],
        "department_id_match": bool(rec.get("department_id")) and rec["department_id"][0] == payload["department_id"],
        "job_id_match": bool(rec.get("job_id")) and rec["job_id"][0] == payload["job_id"],
        "resource_id_auto_linked": bool(rec.get("resource_id")),
        "version_id_auto_linked": bool(rec.get("version_id")),
    }

    observations = {
        "job_title_after_create": rec.get("job_title"),
        "job_id_after_create": rec.get("job_id"),
        "job_title_affected_by_job_id": rec.get("job_title") != payload["job_title"],
        "job_id_missing_after_create": not bool(rec.get("job_id")),
    }

    log_event({"step": "comparison", "comparison": comparison, "observations": observations})

def cleanup(models, uid, employee_id, context):
    models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        "hr.employee", "unlink",
        [[employee_id]],
        {"context": context}
    )
    log_event({"step": "cleanup", "result": "SUCCESS", "employee_id": employee_id})

def main():
    check_env()
    log_event({"step": "start", "note": "Extended safe-fields create/read/compare test"})

    uid, models = connect()
    validate_reference_rows(models, uid)
    duplicate_check(models, uid, "test_safe_fields_extended@example.com")

    employee_id = None
    context = {"allowed_company_ids": [TEST_COMPANY_ID]}

    try:
        employee_id, payload, context = create_employee(models, uid)
        rec = read_employee(models, uid, employee_id, context)
        compare_payload(payload, rec)
    except xmlrpc.client.Fault as fault:
        log_event({
            "step": "xmlrpc_fault",
            "fault_code": fault.faultCode,
            "fault_string": fault.faultString
        })
        raise
    finally:
        if employee_id:
            try:
                cleanup(models, uid, employee_id, context)
            except xmlrpc.client.Fault as fault:
                log_event({
                    "step": "cleanup",
                    "result": "FAILED",
                    "fault_code": fault.faultCode,
                    "fault_string": fault.faultString
                })

    log_event({"step": "end", "note": "راجع logs/04_test_safe_fields_extended.jsonl"})

if __name__ == "__main__":
    main()