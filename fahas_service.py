"""
خدمة وكيل الاستعلام والقراءة والتحقق المعتمد «فاحص» (Fahas Inspection & Query Service)
====================================================================================
«فاحص» (Fahas) هو الوكيل الحصري المسؤول عن:
1. القراءة والاستعلام والتحقق من البيانات الفعلية في Odoo (سجلات حية ومؤرشفة).
2. تنفيذ مهام الاستعلام المحددة المرسلة إليه من وكيل التنسيق «سراج» (execute_query_task).
3. إرجاع نتائج منظمة وموثقة أو أخطاء تقنية واضحة وصريحة دون تخمين أو تضليل.
4. التحقق المرجعي من سجلات الموظفين والأقسام والشركات والوظائف.

حدود وضوابط «فاحص»:
- لا يدير المحادثة ولا يتعامل مع فهم سياق المستخدم باللغة الطبيعية (هذه مسؤولية سراج).
- لا يرد على المستخدم مباشرة بل يعيد البيانات المنظمة إلى سراج لعرضها وشرحها.
- لا يملك أي صلاحيات كتابة (create) أو تعديل (write) أو حذف (unlink) أو اعتماد (approve).
- محمي بحاجز أمني صارم يمنع الوصول لأي نماذج خارج نطاق الموارد البشرية والبيانات العامة.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository, OdooReadonlyRepositoryError

logger = logging.getLogger("fahas_service")

# النماذج المصرح لـ «فاحص» بقراءتها
SAFE_MODEL_PREFIXES = (
    "hr.",
    "res.",
    "resource.",
    "mail.",
    "ir.model",
    "ir.attachment",
)

# العمليات المحظورة قطعياً على فاحص وسراج (قراءة فقط)
FORBIDDEN_OPERATIONS = frozenset({
    "create", "write", "unlink", "delete", "drop", "update", "insert",
    "create_record", "unlink_records", "write_record", "delete_record",
})


class FahasSecurityError(PermissionError):
    """خطأ أمني عند محاولة طلب عملية كتابة أو موديل محظور لدى فاحص."""
    pass


class FahasExecutionError(RuntimeError):
    """خطأ تنفيذي أثناء استعلام فاحص لبيانات Odoo."""
    pass


def validate_model_name(model: str) -> str:
    """التحقق من سلامة اسم الموديل ومنع أي محاولة تجاوز لنطاق القراءة المعتمد لفاحص."""
    if not model or not isinstance(model, str):
        raise FahasSecurityError("اسم الموديل غير محدد أو غير صالح.")
    model_clean = model.strip()
    if not re.match(r"^[a-zA-Z0-9_\.]+$", model_clean):
        raise FahasSecurityError(f"اسم الموديل غير صالح أمنياً: {model_clean}")
    if not any(model_clean.startswith(prefix) for prefix in SAFE_MODEL_PREFIXES):
        raise FahasSecurityError(f"الموديل «{model_clean}» غير مصرح بقراءته عبر فاحص.")
    return model_clean


class FahasAgent:
    """
    وكيل الاستعلام والقراءة والتحقق المعتمد من Odoo (Strict Read-Only Inspection Agent).
    يستقبل المهام من «سراج»، وينفذها في Odoo، ويعيد نتائج منظمة خالية من التخمين.
    """

    _instance: Optional[FahasAgent] = None

    def __init__(self, repository: Optional[OdooReadonlyRepository] = None) -> None:
        self._custom_repo = repository

    @classmethod
    def get_instance(cls) -> FahasAgent:
        """الحصول على النسخة المشتركة من وكيل فاحص."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_repository(self, connection_id: Optional[str] = None) -> OdooReadonlyRepository:
        """الحصول على مستودع Odoo المعتمد للقراءة المباشرة."""
        if self._custom_repo is not None:
            return self._custom_repo
        
        # استخدام دالة الجلب المعتمدة أو إنشاء مستودع جديد
        try:
            from odoo_agent_tools import _get_repository
            return _get_repository(connection_id)
        except Exception:
            repo = OdooReadonlyRepository()
            repo.connect()
            return repo

    def execute_query_task(self, task_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        نقطة الدخول الرئيسية لتنفيذ المهام المحددة المرسلة من «سراج»:
        - يتحقق من أمان المهمة وخلوها من محاولات التعديل أو الحذف.
        - يوجه المهمة إلى طريقة الاستعلام المناسبة.
        - يرجع نتيجة منظمة أو يثير خطأً واضحاً.
        """
        clean_task = (task_type or "").strip()
        if any(forbid in clean_task.lower() for forbid in FORBIDDEN_OPERATIONS):
            raise FahasSecurityError(
                f"العملية «{clean_task}» محظورة على فاحص. اختصاص فاحص محصور في القراءة والاستعلام والتحقق فقط."
            )

        dispatch_map = {
            "list_connections": lambda p: self.list_connections(),
            "list_companies": lambda p: self.list_companies(connection_id=p.get("connection_id")),
            "describe_model": lambda p: self.describe_model(
                model=p.get("model", ""),
                fields=p.get("fields"),
                connection_id=p.get("connection_id"),
            ),
            "count_records": lambda p: self.count_records(
                model=p.get("model", ""),
                domain=p.get("domain"),
                company_id=p.get("company_id"),
                include_archived=p.get("include_archived", False),
                connection_id=p.get("connection_id"),
            ),
            "search_records": lambda p: self.search_records(
                model=p.get("model", ""),
                domain=p.get("domain"),
                fields=p.get("fields"),
                limit=p.get("limit", 15),
                offset=p.get("offset", 0),
                order=p.get("order"),
                company_id=p.get("company_id"),
                include_archived=p.get("include_archived", False),
                connection_id=p.get("connection_id"),
            ),
            "read_records": lambda p: self.read_records(
                model=p.get("model", ""),
                ids=p.get("ids", []),
                fields=p.get("fields"),
                connection_id=p.get("connection_id"),
            ),
            "inspect_employee": lambda p: self.inspect_employee(
                employee_query=p.get("query", ""),
                limit=p.get("limit", 20),
                connection_id=p.get("connection_id"),
            ),
            "inspect_references": lambda p: self.inspect_references(
                company_val=p.get("company"),
                department_val=p.get("department"),
                job_val=p.get("job"),
                connection_id=p.get("connection_id"),
            ),
        }

        handler = dispatch_map.get(clean_task)
        if not handler:
            raise FahasSecurityError(f"مهمة الاستعلام «{clean_task}» غير معروفة أو غير مصرح بها لدى فاحص.")

        return handler(params)

    # -------------------------------------------------------------------------
    # 1. استعراض الاتصالات والشركات والموديلات
    # -------------------------------------------------------------------------
    def list_connections(self) -> List[Dict[str, Any]]:
        """استعراض اتصالات Odoo المتاحة والمصرح بها."""
        try:
            repo = self.get_repository()
            return [
                {
                    "connection_id": "default",
                    "name": "الاتصال الأساسي بنظام Odoo",
                    "database": repo.db,
                    "url": repo.url,
                    "authenticated_user": repo.username,
                    "uid": repo.uid,
                    "state": "connected",
                }
            ]
        except Exception as exc:
            return [
                {
                    "connection_id": "default",
                    "name": "الاتصال الأساسي بنظام Odoo",
                    "state": "error",
                    "error": str(exc),
                }
            ]

    def list_companies(self, connection_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """استعراض المنشآت والشركات المصرح بها في النظام."""
        repo = self.get_repository(connection_id)
        try:
            return repo.get_accessible_companies()
        except Exception as exc:
            logger.error("فاحص: فشل جلب الشركات: %s", exc)
            raise FahasExecutionError(f"فشل جلب قائمة الشركات من Odoo عبر فاحص: {exc}")

    def describe_model(
        self,
        model: str,
        fields: Optional[List[str]] = None,
        connection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """فحص حقول الموديل وأنواعها وتسمياتها للمساعدة في بناء الاستعلامات الصحيحة."""
        model_clean = validate_model_name(model)
        repo = self.get_repository(connection_id)
        try:
            attrs = ["string", "type", "help", "relation", "required", "readonly"]
            fields_arg = fields if fields and isinstance(fields, list) else []
            meta = repo._models.execute_kw(
                repo.db,
                repo.uid,
                repo.api_key,
                model_clean,
                "fields_get",
                [fields_arg],
                {"attributes": attrs},
            )
            return {
                "model": model_clean,
                "fields_count": len(meta),
                "fields": meta,
            }
        except Exception as exc:
            logger.error("فاحص: فشل فحص حقول الموديل %s: %s", model_clean, exc)
            raise FahasExecutionError(f"فشل فحص حقول الموديل «{model_clean}» عبر فاحص: {exc}")

    # -------------------------------------------------------------------------
    # 2. حساب السجلات والبحث والقراءة
    # -------------------------------------------------------------------------
    def count_records(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        company_id: Optional[int] = None,
        include_archived: bool = False,
        connection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """حساب عدد السجلات الفعلية المطابقة للشروط عبر search_count."""
        model_clean = validate_model_name(model)
        repo = self.get_repository(connection_id)

        query_domain = list(domain) if domain and isinstance(domain, list) else []

        # تصفية الشركة إن حددها سراج
        if company_id is not None:
            has_company_filter = any(
                isinstance(cond, (list, tuple)) and len(cond) >= 1 and cond[0] == "company_id"
                for cond in query_domain
            )
            if not has_company_filter:
                query_domain.append(("company_id", "=", company_id))

        # معالجة المؤرشفين
        context: Dict[str, Any] = {}
        is_archived_query = include_archived or any(
            isinstance(cond, (list, tuple)) and len(cond) >= 1 and cond[0] == "active"
            for cond in query_domain
        )
        if is_archived_query:
            context["active_test"] = False

        try:
            kwargs: Dict[str, Any] = {}
            if context:
                kwargs["context"] = context

            count = repo._models.execute_kw(
                repo.db,
                repo.uid,
                repo.api_key,
                model_clean,
                "search_count",
                [query_domain],
                kwargs,
            )
            return {
                "model": model_clean,
                "count": int(count),
                "domain": query_domain,
                "company_id": company_id,
                "context": context,
            }
        except Exception as exc:
            logger.error("فاحص: فشل حساب عدد السجلات في %s: %s", model_clean, exc)
            raise FahasExecutionError(f"فشل حساب عدد السجلات في «{model_clean}» عبر فاحص: {exc}")

    def search_records(
        self,
        model: str,
        domain: Optional[List[Any]] = None,
        fields: Optional[List[str]] = None,
        limit: int = 15,
        offset: int = 0,
        order: Optional[str] = None,
        company_id: Optional[int] = None,
        include_archived: bool = False,
        connection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """البحث في السجلات وجلب حقول محددة عبر search_read ضمن سقف أمان أقصى 50 سجلاً."""
        model_clean = validate_model_name(model)
        repo = self.get_repository(connection_id)

        safe_limit = max(1, min(int(limit), 50))
        query_domain = list(domain) if domain and isinstance(domain, list) else []

        if company_id is not None:
            has_company_filter = any(
                isinstance(cond, (list, tuple)) and len(cond) >= 1 and cond[0] == "company_id"
                for cond in query_domain
            )
            if not has_company_filter:
                query_domain.append(("company_id", "=", company_id))

        context: Dict[str, Any] = {}
        if include_archived or any(isinstance(cond, (list, tuple)) and len(cond) >= 1 and cond[0] == "active" for cond in query_domain):
            context["active_test"] = False

        safe_fields = fields if fields and isinstance(fields, list) else ["id", "name"]
        if model_clean == "hr.employee" and not fields:
            safe_fields = ["id", "name", "work_email", "job_title", "department_id", "company_id", "active"]

        try:
            kwargs: Dict[str, Any] = {
                "fields": safe_fields,
                "limit": safe_limit,
                "offset": max(0, int(offset)),
            }
            if order:
                kwargs["order"] = str(order)
            if context:
                kwargs["context"] = context

            records = repo._models.execute_kw(
                repo.db,
                repo.uid,
                repo.api_key,
                model_clean,
                "search_read",
                [query_domain],
                kwargs,
            )
            return {
                "model": model_clean,
                "records_count": len(records),
                "records": records,
                "company_id": company_id,
                "domain": query_domain,
            }
        except Exception as exc:
            logger.error("فاحص: فشل البحث في سجلات %s: %s", model_clean, exc)
            raise FahasExecutionError(f"فشل البحث في سجلات «{model_clean}» عبر فاحص: {exc}")

    def read_records(
        self,
        model: str,
        ids: List[int],
        fields: Optional[List[str]] = None,
        connection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """قراءة تفاصيل سجلات محددة بأرقام معرفاتها عبر read."""
        model_clean = validate_model_name(model)
        repo = self.get_repository(connection_id)

        if not ids or not isinstance(ids, list):
            raise FahasExecutionError("يلزم تمرير قائمة معرّفات (ids) صحيحة لقراءتها.")

        clean_ids = [int(i) for i in ids[:50]]
        safe_fields = fields if fields and isinstance(fields, list) else []

        try:
            records = repo._models.execute_kw(
                repo.db,
                repo.uid,
                repo.api_key,
                model_clean,
                "read",
                [clean_ids],
                {"fields": safe_fields} if safe_fields else {},
            )
            return {
                "model": model_clean,
                "records_count": len(records),
                "records": records,
            }
        except Exception as exc:
            logger.error("فاحص: فشل قراءة سجلات %s: %s", model_clean, exc)
            raise FahasExecutionError(f"فشل قراءة السجلات في «{model_clean}» عبر فاحص: {exc}")

    # -------------------------------------------------------------------------
    # 3. التحقق المرجعي وفحص الموظفين والأقسام
    # -------------------------------------------------------------------------
    def inspect_employee(
        self,
        employee_query: str,
        limit: int = 20,
        connection_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """البحث الشامل والتحقق من سجل الموظف في Odoo بالاسم أو المعرف أو البريد."""
        repo = self.get_repository(connection_id)
        try:
            return repo.search_employee_candidates(employee_query, limit=limit)
        except Exception as exc:
            logger.error("فاحص: فشل فحص الموظف: %s", exc)
            raise FahasExecutionError(f"فشل فحص بيانات الموظف عبر فاحص: {exc}")

    def inspect_references(
        self,
        company_val: Optional[str] = None,
        department_val: Optional[str] = None,
        job_val: Optional[str] = None,
        connection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        فحص السجلات المباشرة والمؤرشفة لمطابقة المراجع (الشركة، القسم، المسمى)،
        وفق تنفيذ فاحص المعتمد في منظومة المعالجة والاستشارة التشخيصية.
        """
        repo = self.get_repository(connection_id)
        try:
            companies = repo.get_accessible_companies()
            company_ids = repo.get_company_ids()
            departments = repo.get_departments(company_ids=company_ids)
            jobs = repo.get_jobs(company_ids=company_ids)

            def match_key(s: str) -> str:
                return re.sub(r"\s+", "", (s or "").strip().lower())

            report: Dict[str, Any] = {
                "company_exists": False,
                "company_archived": False,
                "matched_company_id": None,
                "department_exists": False,
                "department_archived": False,
                "job_exists": False,
                "job_archived": False,
            }

            if company_val:
                for c in companies:
                    if match_key(c.get("name") or "") == match_key(company_val):
                        report["company_exists"] = True
                        report["company_archived"] = (c.get("active") is False)
                        report["matched_company_id"] = c.get("id")
                        break

            comp_id = report["matched_company_id"]

            if department_val:
                for d in departments:
                    d_comp = d.get("company_id")
                    d_cid = d_comp[0] if isinstance(d_comp, (list, tuple)) else d_comp
                    if comp_id and d_cid and d_cid != comp_id:
                        continue
                    if match_key(d.get("complete_name") or "") == match_key(department_val) or match_key(d.get("name") or "") == match_key(department_val):
                        report["department_exists"] = True
                        report["department_archived"] = (d.get("active") is False)
                        break

            if job_val:
                for j in jobs:
                    j_comp = j.get("company_id")
                    j_cid = j_comp[0] if isinstance(j_comp, (list, tuple)) else j_comp
                    if comp_id and j_cid and j_cid != comp_id:
                        continue
                    if match_key(j.get("name") or "") == match_key(job_val):
                        report["job_exists"] = True
                        report["job_archived"] = (j.get("active") is False)
                        break

            return report
        except Exception as exc:
            logger.error("فاحص: فشل فحص المراجع: %s", exc)
            raise FahasExecutionError(f"فشل فحص المراجع عبر فاحص: {exc}")

    def get_departments(
        self,
        company_ids: Optional[List[int]] = None,
        connection_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """استرجاع قائمة الأقسام من Odoo."""
        repo = self.get_repository(connection_id)
        return repo.get_departments(company_ids=company_ids)

    def get_jobs(
        self,
        company_ids: Optional[List[int]] = None,
        connection_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """استرجاع قائمة الوظائف من Odoo."""
        repo = self.get_repository(connection_id)
        return repo.get_jobs(company_ids=company_ids)

    def verify_record_status(
        self,
        model: str,
        record_id: int,
        expected_state: str,
        connection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        التحقق المستقل بعد التنفيذ بواسطة فاحص:
        - للأرشفة (archived): التحقق من وجود السجل مع حالة active=False.
        - للحذف (deleted): التحقق من غياب السجل تماماً حتى مع active_test=False (include_archived=True).
        - أخطاء الاتصال أو الصلاحيات لا تعتبر دليلاً على غياب السجل؛ تعيد state="inconclusive".
        """
        model_clean = validate_model_name(model)
        try:
            if expected_state == "archived":
                res = self.search_records(
                    model=model_clean,
                    domain=[("id", "=", record_id)],
                    fields=["id", "name", "active"],
                    include_archived=True,
                    connection_id=connection_id,
                )
                records = res.get("records", [])
                if not records:
                    return {"verified": False, "state": "not_found", "message": "لم يتم العثور على السجل في Odoo."}
                rec = records[0]
                is_active = rec.get("active", True)
                if not is_active:
                    return {"verified": True, "state": "archived", "record": rec}
                return {"verified": False, "state": "still_active", "record": rec}

            elif expected_state in ("active", "unarchived"):
                res = self.search_records(
                    model=model_clean,
                    domain=[("id", "=", record_id)],
                    fields=["id", "name", "active"],
                    include_archived=True,
                    connection_id=connection_id,
                )
                records = res.get("records", [])
                if not records:
                    return {"verified": False, "state": "not_found", "message": "لم يتم العثور على السجل في Odoo."}
                rec = records[0]
                is_active = rec.get("active", False)
                if is_active:
                    return {"verified": True, "state": "active", "record": rec}
                return {"verified": False, "state": "still_archived", "record": rec}

            elif expected_state == "deleted":
                res = self.count_records(
                    model=model_clean,
                    domain=[("id", "=", record_id)],
                    include_archived=True,
                    connection_id=connection_id,
                )
                count = res.get("count", -1)
                if count == 0:
                    return {"verified": True, "state": "deleted"}
                return {"verified": False, "state": "still_exists", "count": count}

            return {"verified": False, "state": "unknown_expected_state"}

        except Exception as exc:
            logger.warning("فاحص: تعذر التحقق المستقل من حالة السجل %s: %s", record_id, exc)
            return {
                "verified": False,
                "state": "inconclusive",
                "error": str(exc),
                "message": "نتيجة التحقق غير محسومة بسبب تعذر الاتصال أو نقص الصلاحيات؛ لا يمكن إعلان النجاح.",
            }


# توفير اسم مرادف للتوافق
FahasService = FahasAgent


def get_fahas_agent() -> FahasAgent:
    """الحصول على النسخة الحالية لوكيل فاحص."""
    return FahasAgent.get_instance()
