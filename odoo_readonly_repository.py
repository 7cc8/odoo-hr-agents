from __future__ import annotations
import os
import xmlrpc.client
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class OdooReadonlyRepositoryError(Exception):
    pass


class OdooReadonlyRepository:
    def __init__(self, url=None, db=None, username=None, api_key=None, timeout=30):
        active_cfg: Dict[str, str] = {}
        try:
            from odoo_config_manager import get_active_odoo_config
            active_cfg = get_active_odoo_config()
        except ImportError:
            pass

        self.url = (url or active_cfg.get("url") or os.environ.get("ODOO_URL", "")).rstrip("/")
        self.db = db or active_cfg.get("db") or os.environ.get("ODOO_DB", "")
        self.username = username or active_cfg.get("username") or os.environ.get("ODOO_USER") or os.environ.get("ODOO_USERNAME", "")
        self.api_key = api_key or active_cfg.get("api_key") or os.environ.get("ODOO_API_KEY", "")
        self.timeout = timeout

        if not self.url or not self.db or not self.username or not self.api_key:
            raise OdooReadonlyRepositoryError(
                "Missing Odoo connection settings: ODOO_URL, ODOO_DB, ODOO_USER, ODOO_API_KEY"
            )

        self._uid: Optional[int] = None
        self._common = None
        self._models = None
        self._server_version_cache: Optional[Dict[str, Any]] = None
        self._company_ids_cache: Optional[List[int]] = None
        self._companies_cache: Optional[List[Dict[str, Any]]] = None

    @property
    def uid(self) -> int:
        if self._uid is None:
            raise OdooReadonlyRepositoryError("Not authenticated yet")
        return self._uid

    def connect(self) -> None:
        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        uid = common.authenticate(self.db, self.username, self.api_key, {})
        if not uid:
            raise OdooReadonlyRepositoryError("Authentication failed")
        self._common = common
        self._models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)
        self._uid = uid

    def version(self) -> Dict[str, Any]:
        if self._server_version_cache is None:
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
            self._server_version_cache = common.version()
        return self._server_version_cache

    def _ensure_connected(self) -> None:
        if self._models is None or self._uid is None:
            self.connect()

    def _execute_kw(self, model, method, args, kwargs=None):
        self._ensure_connected()
        kwargs = kwargs or {}
        return self._models.execute_kw(self.db, self.uid, self.api_key, model, method, args, kwargs)

    def _base_context(self) -> Dict[str, Any]:
        return {"active_test": False}

    def get_accessible_companies(self) -> List[Dict[str, Any]]:
        if self._companies_cache is None:
            self._companies_cache = self._execute_kw(
                "res.company", "search_read", [[]],
                {"fields": ["id", "name", "active"], "context": self._base_context(), "order": "id asc"},
            )
        return self._companies_cache

    def get_company_ids(self) -> List[int]:
        if self._company_ids_cache is None:
            self._company_ids_cache = [row["id"] for row in self.get_accessible_companies()]
        return self._company_ids_cache

    def get_default_company(self) -> Dict[str, Any]:
        """Returns the primary company of the authenticated Odoo user, or the first accessible company."""
        self._ensure_connected()
        try:
            user_data = self._execute_kw("res.users", "read", [[self.uid]], {"fields": ["company_id"]})
            if user_data and user_data[0].get("company_id"):
                cid = user_data[0]["company_id"]
                return {"id": cid[0], "name": cid[1]}
        except Exception:
            pass
        comps = self.get_accessible_companies()
        if comps:
            return {"id": comps[0]["id"], "name": comps[0]["name"]}
        return {"id": 1, "name": "Main Company"}

    def get_departments(self, company_ids=None) -> List[Dict[str, Any]]:
        domain: List[Any] = []
        if company_ids:
            domain.append(["company_id", "in", company_ids])
        return self._execute_kw(
            "hr.department", "search_read", [domain],
            {"fields": ["id", "name", "complete_name", "company_id", "active"],
             "context": self._base_context(), "order": "company_id, name, id"},
        )

    def get_jobs(self, company_ids=None) -> List[Dict[str, Any]]:
        domain: List[Any] = []
        if company_ids:
            domain.append(["company_id", "in", company_ids])
        return self._execute_kw(
            "hr.job", "search_read", [domain],
            {"fields": ["id", "name", "company_id", "department_id", "active"],
             "context": self._base_context(), "order": "company_id, name, id"},
        )

    def search_employee_candidates(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Searches employees comprehensively by name, email, identification ID, or numeric ID
        with full support for Arabic spelling and phonetic variations (Alef, Taa Marbuta, Al- prefix).
        """
        q = (query or "").strip()
        if not q:
            return []

        company_ids = self.get_company_ids()

        # Direct numeric ID lookup
        if q.isdigit():
            emp_id = int(q)
            domain_id: List[Any] = [["id", "=", emp_id]]
            if company_ids:
                domain_id.append(["company_id", "in", company_ids])
            try:
                rows = self._execute_kw(
                    "hr.employee", "search_read", [domain_id],
                    {"fields": ["id", "name", "work_email", "mobile_phone", "work_phone", "company_id", "department_id", "job_id", "identification_id", "active"],
                     "context": self._base_context(), "limit": 1},
                )
                if rows:
                    return rows
            except Exception:
                pass

        # Generate Arabic spelling variants
        variants = {q}
        for a in ("أ", "إ", "آ", "ا"):
            variants.add(q.replace("أ", a).replace("إ", a).replace("آ", a).replace("ا", a))
        variants.add(q.replace("ة", "ه"))
        variants.add(q.replace("ه", "ة"))
        variants.add(q.replace("ى", "ي"))
        variants.add(q.replace("ي", "ى"))
        if q.startswith("ال") and len(q) > 2:
            variants.add(q[2:])
        else:
            variants.add("ال" + q)

        conds: List[Any] = []
        if q.isdigit():
            conds.append(["identification_id", "ilike", q])

        for v in list(variants)[:8]:
            conds.append(["name", "ilike", v])
            conds.append(["work_email", "ilike", v])
            conds.append(["identification_id", "ilike", v])

        if not conds:
            return []

        or_domain = ["|"] * (len(conds) - 1) + conds
        final_domain: List[Any] = []
        if company_ids:
            final_domain = ["&", ["company_id", "in", company_ids]] + or_domain
        else:
            final_domain = or_domain

        try:
            return self._execute_kw(
                "hr.employee", "search_read", [final_domain],
                {"fields": ["id", "name", "work_email", "mobile_phone", "work_phone", "company_id", "department_id", "job_id", "identification_id", "active"],
                 "context": self._base_context(), "limit": limit, "order": "name asc, id asc"},
            )
        except Exception:
            return []

    def search_employee_email_candidates(self, email_fragment: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Backwards-compatible alias for comprehensive employee candidate search."""
        return self.search_employee_candidates(email_fragment, limit=limit)

    def get_live_reference_snapshot(self) -> Dict[str, Any]:
        companies = self.get_accessible_companies()
        company_ids = self.get_company_ids()
        departments = self.get_departments(company_ids=company_ids)
        jobs = self.get_jobs(company_ids=company_ids)
        return {"companies": companies, "departments": departments, "jobs": jobs}

    def get_session_info(self) -> Dict[str, Any]:
        self._ensure_connected()
        companies = self.get_accessible_companies()
        return {
            "odoo_url": self.url,
            "odoo_db": self.db,
            "uid": self.uid,
            "server_version": self.version(),
            "accessible_company_ids": self.get_company_ids(),
            "accessible_companies": [{"id": c["id"], "name": c["name"]} for c in companies],
        }

    def get_leave_types(self, active_only: bool = True) -> List[Dict[str, Any]]:
        domain: List[Any] = []
        if active_only:
            domain.append(["active", "=", True])
        return self._execute_kw(
            "hr.leave.type",
            "search_read",
            [domain],
            {"fields": ["id", "name", "request_unit", "requires_allocation", "active"],
             "context": self._base_context(), "order": "id asc"}
        )

    def get_employee(self, employee_id: int) -> Optional[Dict[str, Any]]:
        rows = self._execute_kw(
            "hr.employee",
            "read",
            [[employee_id]],
            {"fields": ["id", "name", "work_email", "department_id", "company_id", "sex", "country_id", "identification_id", "hiring_date", "create_date", "active"],
             "context": self._base_context()}
        )
        return rows[0] if rows else None

    def get_employee_leaves(self, employee_id: int, state: Optional[str] = None) -> List[Dict[str, Any]]:
        domain: List[Any] = [["employee_id", "=", employee_id]]
        if state:
            domain.append(["state", "=", state])
        return self._execute_kw(
            "hr.leave",
            "search_read",
            [domain],
            {"fields": ["id", "name", "holiday_status_id", "request_date_from", "request_date_to", "number_of_days", "state"],
             "context": self._base_context(), "order": "request_date_from desc, id desc"}
        )

    def get_employee_allocations(self, employee_id: int) -> List[Dict[str, Any]]:
        domain: List[Any] = [["employee_id", "=", employee_id], ["state", "=", "validate"]]
        return self._execute_kw(
            "hr.leave.allocation",
            "search_read",
            [domain],
            {"fields": ["id", "name", "holiday_status_id", "number_of_days", "state"],
             "context": self._base_context(), "order": "id asc"}
        )

    def get_employee_attendances(
        self,
        employee_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        domain: List[Any] = [["employee_id", "=", employee_id]]
        if date_from:
            domain.append(["date", ">=", date_from])
        if date_to:
            domain.append(["date", "<=", date_to])
        return self._execute_kw(
            "hr.attendance",
            "search_read",
            [domain],
            {"fields": ["id", "employee_id", "date", "check_in", "check_out", "worked_hours", "overtime_hours"],
             "context": self._base_context(), "limit": limit, "order": "check_in desc, id desc"}
        )

    def get_employee_current_attendance(self, employee_id: int) -> Optional[Dict[str, Any]]:
        domain: List[Any] = [["employee_id", "=", employee_id], ["check_out", "=", False]]
        rows = self._execute_kw(
            "hr.attendance",
            "search_read",
            [domain],
            {"fields": ["id", "employee_id", "date", "check_in", "check_out", "worked_hours"],
             "context": self._base_context(), "limit": 1, "order": "check_in desc"}
        )
        return rows[0] if rows else None

    def get_employee_disciplinary_actions(
        self,
        employee_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        domain: List[Any] = [["employee_name", "=", employee_id]]
        if date_from:
            domain.append(["discipline_date", ">=", date_from])
        if date_to:
            domain.append(["discipline_date", "<=", date_to])
        return self._execute_kw(
            "disciplinary.action",
            "search_read",
            [domain],
            {
                "fields": [
                    "id", "name", "employee_name", "department_name", "discipline_date",
                    "discipline_reason", "category_type", "number_of_days", "amount",
                    "occurrence", "state", "action_type_id", "explanation", "manager_response"
                ],
                "context": self._base_context(),
                "limit": limit,
                "order": "discipline_date desc, id desc"
            }
        )

    def get_disciplinary_action(self, action_id: int) -> Optional[Dict[str, Any]]:
        rows = self._execute_kw(
            "disciplinary.action",
            "search_read",
            [[["id", "=", action_id]]],
            {
                "fields": [
                    "id", "name", "employee_name", "department_name", "discipline_date",
                    "discipline_reason", "category_type", "number_of_days", "amount",
                    "occurrence", "state", "action_type_id", "explanation", "manager_response"
                ],
                "context": self._base_context(),
                "limit": 1
            }
        )
        return rows[0] if rows else None

    def get_discipline_categories(self) -> List[Dict[str, Any]]:
        return self._execute_kw(
            "discipline.category",
            "search_read",
            [[]],
            {
                "fields": ["id", "code", "name"],
                "context": self._base_context(),
                "order": "id asc"
            }
        )

    def get_employee_eos_records(
        self,
        employee_id: int,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        domain: List[Any] = [["employee_id", "=", employee_id]]
        return self._execute_kw(
            "hr.end.service.benefit",
            "search_read",
            [domain],
            {
                "fields": [
                    "id", "name", "employee_id", "department_id", "date", "hiring_date",
                    "type", "payment_type", "years", "months", "days", "service_period",
                    "total_deserved_amount", "total_holiday_deserved_amount",
                    "total_payslip_deserved_amount", "other_amount", "other_deduction",
                    "total_reward", "amount", "state", "notes"
                ],
                "context": self._base_context(),
                "limit": limit,
                "order": "date desc, id desc"
            }
        )

    def get_eos_record(self, eos_id: int) -> Optional[Dict[str, Any]]:
        rows = self._execute_kw(
            "hr.end.service.benefit",
            "search_read",
            [[["id", "=", eos_id]]],
            {
                "fields": [
                    "id", "name", "employee_id", "department_id", "date", "hiring_date",
                    "type", "payment_type", "years", "months", "days", "service_period",
                    "total_deserved_amount", "total_holiday_deserved_amount",
                    "total_payslip_deserved_amount", "other_amount", "other_deduction",
                    "total_reward", "amount", "state", "notes"
                ],
                "context": self._base_context(),
                "limit": 1
            }
        )
        return rows[0] if rows else None

    def get_eos_reasons(self) -> List[Dict[str, Any]]:
        try:
            return self._execute_kw(
                "hr.end.service.benefit.type",
                "search_read",
                [[]],
                {
                    "fields": ["id", "name"],
                    "context": self._base_context(),
                    "order": "id asc"
                }
            )
        except Exception:
            return []

    def get_employee_gr_transactions(
        self,
        employee_id: int,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        domain: List[Any] = [["employee_id", "=", employee_id]]
        return self._execute_kw(
            "gr.transaction",
            "search_read",
            [domain],
            {
                "fields": [
                    "id", "name", "employee_id", "transaction", "transaction_type",
                    "transaction_date", "responsible_party", "company_percentage",
                    "employee_percentage", "amount", "state", "description"
                ],
                "context": self._base_context(),
                "limit": limit,
                "order": "transaction_date desc, id desc"
            }
        )

    def get_gr_transaction(self, transaction_id: int) -> Optional[Dict[str, Any]]:
        rows = self._execute_kw(
            "gr.transaction",
            "search_read",
            [[["id", "=", transaction_id]]],
            {
                "fields": [
                    "id", "name", "employee_id", "transaction", "transaction_type",
                    "transaction_date", "responsible_party", "company_percentage",
                    "employee_percentage", "amount", "state", "description"
                ],
                "context": self._base_context(),
                "limit": 1
            }
        )
        return rows[0] if rows else None

    def get_employee_appraisals(
        self,
        employee_id: int,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        domain: List[Any] = [["employee_id", "=", employee_id]]
        try:
            return self._execute_kw(
                "appraisal.request",
                "search_read",
                [domain],
                {
                    "fields": [
                        "id", "name", "employee_id", "department_id", "job_id",
                        "manager_id", "start_date", "end_date", "evaluation_date",
                        "final_percentage", "total_points_earned", "max_possible_points",
                        "state", "manager_comments", "notes"
                    ],
                    "context": self._base_context(),
                    "limit": limit,
                    "order": "start_date desc, id desc"
                }
            )
        except Exception:
            return []

    def get_appraisal_request(self, appraisal_id: int) -> Optional[Dict[str, Any]]:
        try:
            rows = self._execute_kw(
                "appraisal.request",
                "search_read",
                [[["id", "=", appraisal_id]]],
                {
                    "fields": [
                        "id", "name", "employee_id", "department_id", "job_id",
                        "manager_id", "start_date", "end_date", "evaluation_date",
                        "final_percentage", "total_points_earned", "max_possible_points",
                        "state", "manager_comments", "notes"
                    ],
                    "context": self._base_context(),
                    "limit": 1
                }
            )
            return rows[0] if rows else None
        except Exception:
            return None

    def get_employee_loans(
        self,
        employee_id: int,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        domain: List[Any] = [["employee_id", "=", employee_id]]
        try:
            return self._execute_kw(
                "employee.loan",
                "search_read",
                [domain],
                {
                    "fields": [
                        "id", "name", "employee_id", "department_id", "job_id",
                        "manager_id", "loan_type_id", "payment_method", "loan_amount",
                        "installment_amount", "term", "start_date", "end_date",
                        "notes", "state"
                    ],
                    "context": self._base_context(),
                    "limit": limit,
                    "order": "start_date desc, id desc"
                }
            )
        except Exception:
            return []

    def get_employee_loan(self, loan_id: int) -> Optional[Dict[str, Any]]:
        try:
            rows = self._execute_kw(
                "employee.loan",
                "search_read",
                [[["id", "=", loan_id]]],
                {
                    "fields": [
                        "id", "name", "employee_id", "department_id", "job_id",
                        "manager_id", "loan_type_id", "payment_method", "loan_amount",
                        "installment_amount", "term", "start_date", "end_date",
                        "notes", "state"
                    ],
                    "context": self._base_context(),
                    "limit": 1
                }
            )
            return rows[0] if rows else None
        except Exception:
            return None

    def get_loan_types(self) -> List[Dict[str, Any]]:
        try:
            return self._execute_kw(
                "employee.loan.type",
                "search_read",
                [[]],
                {
                    "fields": ["id", "name", "loan_limit", "loan_term"],
                    "context": self._base_context(),
                    "order": "id asc"
                }
            )
        except Exception:
            return []

    def get_applicants(
        self,
        job_id: Optional[int] = None,
        stage_id: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        domain: List[Any] = []
        if job_id:
            domain.append(["job_id", "=", job_id])
        if stage_id:
            domain.append(["stage_id", "=", stage_id])
        try:
            return self._execute_kw(
                "hr.applicant",
                "search_read",
                [domain],
                {
                    "fields": [
                        "id", "partner_name", "job_id", "department_id", "is_saudi",
                        "nationality_id", "id_number", "passport_number", "email_from",
                        "partner_phone", "stage_id", "salary_expected", "salary_proposed",
                        "total_salary", "housing_allowance", "transportation_allowance",
                        "contract_status", "duration_of_contract", "approval_status",
                        "kanban_state", "availability"
                    ],
                    "context": self._base_context(),
                    "limit": limit,
                    "order": "id desc"
                }
            )
        except Exception:
            return []

    def get_applicant(self, applicant_id: int) -> Optional[Dict[str, Any]]:
        try:
            rows = self._execute_kw(
                "hr.applicant",
                "search_read",
                [[["id", "=", applicant_id]]],
                {
                    "fields": [
                        "id", "partner_name", "job_id", "department_id", "is_saudi",
                        "nationality_id", "id_number", "passport_number", "email_from",
                        "partner_phone", "stage_id", "salary_expected", "salary_proposed",
                        "total_salary", "housing_allowance", "transportation_allowance",
                        "contract_status", "duration_of_contract", "approval_status",
                        "kanban_state", "availability"
                    ],
                    "context": self._base_context(),
                    "limit": 1
                }
            )
            return rows[0] if rows else None
        except Exception:
            return None

    def get_recruitment_jobs(self) -> List[Dict[str, Any]]:
        try:
            return self._execute_kw(
                "hr.job",
                "search_read",
                [[]],
                {
                    "fields": ["id", "name", "department_id", "no_of_recruitment"],
                    "context": self._base_context(),
                    "order": "name asc"
                }
            )
        except Exception:
            return []

    def get_recruitment_stages(self) -> List[Dict[str, Any]]:
        try:
            return self._execute_kw(
                "hr.recruitment.stage",
                "search_read",
                [[]],
                {
                    "fields": ["id", "name", "sequence"],
                    "context": self._base_context(),
                    "order": "sequence asc"
                }
            )
        except Exception:
            return []

    def get_employee_contracts(self, employee_id: int) -> List[Dict[str, Any]]:
        try:
            return self._execute_kw(
                "hr.version",
                "search_read",
                [[["employee_id", "=", employee_id]]],
                {
                    "fields": [
                        "id", "name", "employee_id", "department_id", "job_id", "wage",
                        "l10n_sa_housing_allowance", "l10n_sa_transportation_allowance",
                        "l10n_sa_other_allowances", "total", "is_saudi", "date_start",
                        "date_end", "trial_date_end", "contract_type_id", "gosi_deduction",
                        "gosi_employee_deduction", "gosi_rate"
                    ],
                    "context": self._base_context(),
                    "order": "date_start desc, id desc"
                }
            )
        except Exception:
            return []

    def get_contract(self, contract_id: int) -> Optional[Dict[str, Any]]:
        try:
            rows = self._execute_kw(
                "hr.version",
                "search_read",
                [[["id", "=", contract_id]]],
                {
                    "fields": [
                        "id", "name", "employee_id", "department_id", "job_id", "wage",
                        "l10n_sa_housing_allowance", "l10n_sa_transportation_allowance",
                        "l10n_sa_other_allowances", "total", "is_saudi", "date_start",
                        "date_end", "trial_date_end", "contract_type_id", "gosi_deduction",
                        "gosi_employee_deduction", "gosi_rate"
                    ],
                    "context": self._base_context(),
                    "limit": 1
                }
            )
            return rows[0] if rows else None
        except Exception:
            return None

    def get_contract_types(self) -> List[Dict[str, Any]]:
        try:
            return self._execute_kw(
                "hr.contract.type",
                "search_read",
                [[]],
                {
                    "fields": ["id", "name"],
                    "context": self._base_context(),
                    "order": "id asc"
                }
            )
        except Exception:
            return []

    def get_employee_payslips(self, employee_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """جلب قسائم رواتب الموظف من hr.payslip."""
        try:
            return self._execute_kw(
                "hr.payslip",
                "search_read",
                [[["employee_id", "=", employee_id]]],
                {
                    "fields": [
                        "id", "name", "employee_id", "date_from", "date_to",
                        "basic_wage", "gross_wage", "net_wage", "discipline_amount",
                        "installment_employee_loan", "state", "struct_id"
                    ],
                    "context": self._base_context(),
                    "order": "date_to desc, id desc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_payslip(self, payslip_id: int) -> Optional[Dict[str, Any]]:
        """جلب تفاصيل قسيمة راتب محددة من hr.payslip."""
        try:
            rows = self._execute_kw(
                "hr.payslip",
                "search_read",
                [[["id", "=", payslip_id]]],
                {
                    "fields": [
                        "id", "name", "employee_id", "date_from", "date_to",
                        "basic_wage", "gross_wage", "net_wage", "discipline_amount",
                        "installment_employee_loan", "state", "struct_id"
                    ],
                    "context": self._base_context(),
                    "limit": 1
                }
            )
            return rows[0] if rows else None
        except Exception:
            return None

    def get_payroll_structures(self) -> List[Dict[str, Any]]:
        """جلب هياكل الرواتب المتاحة من hr.payroll.structure."""
        try:
            return self._execute_kw(
                "hr.payroll.structure",
                "search_read",
                [[]],
                {
                    "fields": ["id", "name", "code"],
                    "context": self._base_context(),
                    "order": "id asc"
                }
            )
        except Exception:
            return []

    def get_employees(self, limit: int = 500, active_only: bool = True) -> List[Dict[str, Any]]:
        """جلب قائمة موظفي المنشأة من hr.employee."""
        try:
            domain: List[Any] = []
            if active_only:
                domain.append(["active", "=", True])
            return self._execute_kw(
                "hr.employee",
                "search_read",
                [domain],
                {
                    "fields": [
                        "id", "name", "work_email", "department_id", "company_id",
                        "sex", "country_id", "identification_id", "hiring_date",
                        "create_date", "active", "job_id"
                    ],
                    "context": self._base_context(),
                    "order": "id asc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_all_employees(self, limit: int = 500, active_only: bool = True) -> List[Dict[str, Any]]:
        """الاسم البديل لجلب قائمة موظفي المنشأة."""
        return self.get_employees(limit=limit, active_only=active_only)

    def get_employees_for_expiry_monitoring(self, limit: int = 500, active_only: bool = True) -> List[Dict[str, Any]]:
        """جلب قائمة الموظفين مشمولة بحقول تواريخ انتهاء الهويات والوثائق وتصاريح العمل وفترة التجربة والعقود."""
        try:
            domain: List[Any] = []
            if active_only:
                domain.append(["active", "=", True])
            return self._execute_kw(
                "hr.employee",
                "search_read",
                [domain],
                {
                    "fields": [
                        "id", "name", "work_email", "department_id", "company_id",
                        "sex", "country_id", "identification_id", "hiring_date",
                        "active", "job_id",
                        "id_expiry_date", "passport_expiration_date", "visa_expire",
                        "work_permit_expiration_date", "trial_date_end", "contract_date_end"
                    ],
                    "context": self._base_context(),
                    "order": "id asc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_all_leaves(self, limit: int = 200, state: Optional[str] = None) -> List[Dict[str, Any]]:
        """جلب كل طلبات الإجازات من hr.leave."""
        try:
            domain: List[Any] = []
            if state:
                domain.append(["state", "=", state])
            return self._execute_kw(
                "hr.leave",
                "search_read",
                [domain],
                {
                    "fields": ["id", "employee_id", "holiday_status_id", "request_date_from", "request_date_to", "number_of_days", "state"],
                    "context": self._base_context(),
                    "order": "request_date_from desc, id desc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_all_attendances(self, date_str: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        """جلب حركات الحضور من hr.attendance."""
        try:
            domain: List[Any] = []
            if date_str:
                domain.append(["date", "=", date_str])
            return self._execute_kw(
                "hr.attendance",
                "search_read",
                [domain],
                {
                    "fields": ["id", "employee_id", "date", "check_in", "check_out", "worked_hours", "overtime_hours"],
                    "context": self._base_context(),
                    "order": "check_in desc, id desc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_all_loans(self, state: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        """جلب كل طلبات السلف والقروض من employee.loan."""
        try:
            domain: List[Any] = []
            if state:
                domain.append(["state", "=", state])
            return self._execute_kw(
                "employee.loan",
                "search_read",
                [domain],
                {
                    "fields": ["id", "employee_id", "loan_amount", "installment_amount", "term", "start_date", "end_date", "state"],
                    "context": self._base_context(),
                    "order": "id desc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_all_contracts(self, limit: int = 200) -> List[Dict[str, Any]]:
        """جلب كل عقود الموظفين من hr.version."""
        try:
            return self._execute_kw(
                "hr.version",
                "search_read",
                [[]],
                {
                    "fields": [
                        "id", "employee_id", "wage", "l10n_sa_housing_allowance",
                        "l10n_sa_transportation_allowance", "l10n_sa_other_allowances",
                        "total", "is_saudi", "date_start", "date_end", "trial_date_end"
                    ],
                    "context": self._base_context(),
                    "order": "id desc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_all_eos_records(self, limit: int = 200) -> List[Dict[str, Any]]:
        """جلب كل تسويات نهاية الخدمة من hr.end.service.benefit."""
        try:
            return self._execute_kw(
                "hr.end.service.benefit",
                "search_read",
                [[]],
                {
                    "fields": ["id", "employee_id", "amount", "total_reward", "state", "date"],
                    "context": self._base_context(),
                    "order": "date desc, id desc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_all_gr_transactions(self, limit: int = 200) -> List[Dict[str, Any]]:
        """جلب كل معاملات العلاقات الحكومية من gr.transaction."""
        try:
            return self._execute_kw(
                "gr.transaction",
                "search_read",
                [[]],
                {
                    "fields": ["id", "employee_id", "transaction", "transaction_type", "transaction_date", "amount", "state"],
                    "context": self._base_context(),
                    "order": "transaction_date desc, id desc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_all_appraisals(self, limit: int = 200) -> List[Dict[str, Any]]:
        """جلب كل تقييمات الأداء من appraisal.request."""
        try:
            return self._execute_kw(
                "appraisal.request",
                "search_read",
                [[]],
                {
                    "fields": ["id", "employee_id", "final_percentage", "state", "start_date", "end_date"],
                    "context": self._base_context(),
                    "order": "start_date desc, id desc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_approval_categories(self) -> List[Dict[str, Any]]:
        """جلب تصنيفات الموافقات والخطابات الرسمية من approval.category."""
        try:
            return self._execute_kw(
                "approval.category",
                "search_read",
                [[]],
                {
                    "fields": ["id", "name", "has_amount", "has_date", "has_period"],
                    "context": self._base_context(),
                    "order": "id asc"
                }
            )
        except Exception:
            return []

    def get_all_approval_requests(self, limit: int = 100) -> List[Dict[str, Any]]:
        """جلب كل طلبات الموافقات والخطابات من approval.request."""
        try:
            return self._execute_kw(
                "approval.request",
                "search_read",
                [[]],
                {
                    "fields": [
                        "id", "name", "category_id", "request_status", "request_employee_id",
                        "to", "purpose", "letter_language", "chamber_of_commerce_stamp",
                        "date", "create_date", "company_id"
                    ],
                    "context": self._base_context(),
                    "order": "id desc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_employee_approval_requests(self, employee_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """جلب طلبات الخطابات والموافقات لموظف محدد."""
        try:
            return self._execute_kw(
                "approval.request",
                "search_read",
                [[["request_employee_id", "=", employee_id]]],
                {
                    "fields": [
                        "id", "name", "category_id", "request_status", "request_employee_id",
                        "to", "purpose", "letter_language", "chamber_of_commerce_stamp",
                        "date", "create_date"
                    ],
                    "context": self._base_context(),
                    "order": "id desc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_approval_request_by_id(self, request_id: int) -> Optional[Dict[str, Any]]:
        """جلب تفاصيل طلب موافقة أو خطاب محدد."""
        try:
            res = self._execute_kw(
                "approval.request",
                "read",
                [[request_id]],
                {
                    "fields": [
                        "id", "name", "category_id", "request_status", "request_employee_id",
                        "to", "purpose", "letter_language", "chamber_of_commerce_stamp",
                        "bank_name", "bank_account_number", "reason", "date", "company_id", "create_date"
                    ],
                    "context": self._base_context()
                }
            )
            return res[0] if res else None
        except Exception:
            return None

    def get_warning_letters(self, employee_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """جلب خطابات الإنذار والمساءلات من warning.letter."""
        try:
            domain: List[Any] = []
            if employee_id:
                domain.append(["employee_id", "=", employee_id])
            return self._execute_kw(
                "warning.letter",
                "search_read",
                [domain],
                {
                    "fields": [
                        "id", "name", "employee_id", "department_id", "job_id",
                        "warning_type_id", "date_sent", "email_subject", "notes",
                        "state", "has_deduction", "deduction_amount", "deduction_date"
                    ],
                    "context": self._base_context(),
                    "order": "date_sent desc, id desc",
                    "limit": limit
                }
            )
        except Exception:
            return []

    def get_warning_types(self) -> List[Dict[str, Any]]:
        """جلب أنواع الإنذارات من warning.type."""
        try:
            return self._execute_kw(
                "warning.type",
                "search_read",
                [[]],
                {
                    "fields": ["id", "name"],
                    "context": self._base_context(),
                    "order": "id asc"
                }
            )
        except Exception:
            return []

    def get_hr_expenses(self, employee_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """جلب المصروفات من hr.expense."""
        try:
            domain: List[Any] = []
            if employee_id:
                domain.append(["employee_id", "=", employee_id])
            return self._execute_kw(
                "hr.expense",
                "search_read",
                [domain],
                {
                    "fields": [
                        "id", "name", "employee_id", "product_id", "total_amount",
                        "total_amount_currency", "state", "date", "description",
                        "company_id"
                    ],
                    "context": self._base_context(),
                    "order": "date desc, id desc",
                    "limit": limit
                }
            )
        except Exception:
            return []






