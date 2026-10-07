import os, sys, json, xmlrpc.client
from datetime import datetime, timezone

ODOO_URL = os.environ.get("ODOO_URL")
ODOO_DB = os.environ.get("ODOO_DB")
ODOO_USERNAME = os.environ.get("ODOO_USERNAME")
ODOO_API_KEY = os.environ.get("ODOO_API_KEY")

TEST_DEPARTMENT_NAME = os.environ.get("TEST_DEPARTMENT_NAME", "الموارد البشرية")
TEST_JOB_NAME = os.environ.get("TEST_JOB_NAME", "HR Officer")
TEST_COMPANY_ID = os.environ.get("TEST_COMPANY_ID")

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def log_event(event):
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    path = os.path.join(LOG_DIR, "02_test_lookup_department_job.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(json.dumps(event, ensure_ascii=False, indent=2))

def connect():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    log_event({"step": "server_version", "result": common.version()})
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_API_KEY, {})
    if not uid:
        log_event({"step": "authenticate", "result": "FAILED"})
        sys.exit(1)
    log_event({
        "step": "authenticate",
        "result": "SUCCESS",
        "uid": uid,
        "odoo_url": ODOO_URL,
        "odoo_db": ODOO_DB
    })
    return uid, xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

def exact_lookup(models, uid, model, name_value, company_id=None):
    domain = [["name", "=", name_value]]
    if company_id:
        domain.append(["company_id", "=", int(company_id)])

    rows = models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        model, "search_read",
        [domain],
        {"fields": ["id", "name", "company_id", "active"], "limit": 20}
    )

    status = "matched" if len(rows) == 1 else "needs_review"
    reason = None if len(rows) == 1 else ("no_exact_match" if len(rows) == 0 else "multiple_exact_matches")

    return {
        "model": model,
        "input_name": name_value,
        "company_id_filter": company_id,
        "status": status,
        "reason": reason,
        "matches": rows
    }

def main():
    uid, models = connect()
    log_event({
        "step": "start",
        "test_department_name": TEST_DEPARTMENT_NAME,
        "test_job_name": TEST_JOB_NAME,
        "test_company_id": TEST_COMPANY_ID
    })
    log_event({"step": "department_lookup", "result": exact_lookup(models, uid, "hr.department", TEST_DEPARTMENT_NAME, TEST_COMPANY_ID)})
    log_event({"step": "job_lookup", "result": exact_lookup(models, uid, "hr.job", TEST_JOB_NAME, TEST_COMPANY_ID)})
    log_event({"step": "end", "note": "No guessing. Any 0 or >1 result => needs_review"})

if __name__ == "__main__":
    main()