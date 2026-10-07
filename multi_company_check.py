import os
import time

from odoo_readonly_repository import OdooReadonlyRepository
from odoo_write_gateway import OdooWriteGateway


company_id = int(os.environ["TEST_COMPANY_ID"])
repository = OdooReadonlyRepository()
repository.connect()
gateway = OdooWriteGateway(
    url=repository.url,
    db=repository.db,
    login=repository.username,
    password=repository.api_key,
)

accessible_company_ids = {company["id"] for company in repository.get_accessible_companies()}
if company_id not in accessible_company_ids:
    raise RuntimeError(
        f"TEST_COMPANY_ID={company_id} is not accessible to the configured Odoo user."
    )

email = f"multicompany.test.{int(time.time())}@example.com"
vals = {
    "name": "MULTI COMPANY TEST TEMP",
    "work_email": email,
    "company_id": company_id,
}

emp_id = None
print("creating_with =", vals)

try:
    emp_id = gateway.create_employee(vals)
    print("created_id =", emp_id)

    row = gateway.read_employee(
        emp_id, ["id", "name", "work_email", "company_id", "active"]
    )
    print("read_after_create =", row)
    stored_company = (row or {}).get("company_id")
    if not isinstance(stored_company, (list, tuple)) or stored_company[0] != company_id:
        raise RuntimeError(
            f"Created employee company mismatch: expected {company_id}, got {stored_company!r}"
        )

finally:
    if emp_id:
        deleted = gateway.delete_employee_for_test_cleanup(emp_id)
        print("unlink_result =", deleted)

        after = repository._execute_kw(
            "hr.employee",
            "search_read",
            [[["id", "=", emp_id]]],
            {
                "fields": ["id", "name", "work_email", "company_id", "active"],
                "context": {"active_test": False},
            },
        )
        print("read_after_delete =", after)
        if after:
            raise RuntimeError(f"Employee {emp_id} still exists after cleanup: {after!r}")