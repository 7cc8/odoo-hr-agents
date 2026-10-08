"""
مواصفات مهام وأدوات الاستعلام الحصرية لـ «فاحص» بتنسيق «سراج» (Strict Read-Only Odoo Agent Tools)
=================================================================================================
يوفر هذا الملف:
1. مواصفات استدعاء الأدوات (SERAJ_ODOO_TOOLS_SCHEMA) التي يستخدمها «سراج» لتنسيق مهام الاستعلام.
2. بوابة تفويض المهام المباشرة إلى وكيل الاستعلام والقراءة والتحقق المعتمد «فاحص» (FahasAgent).
3. لا ينفذ سراج أي استعلامات مباشرة أو مسار قراءة موازٍ، بل يفوّض المهام حصرياً إلى «فاحص».

المهام الـ 6 المعتمدة لدى «فاحص»:
1. list_connections: استعراض الاتصالات المتاحة والمصرح بها
2. list_companies: استعراض الشركات المصرح بها ضمن الاتصال المحدد
3. describe_model: فحص حقول الموديل وأنواعها والوصف عبر fields_get
4. count_records: حساب عدد السجلات المطابقة للشروط عبر search_count
5. search_records: استعلام السجلات وجلب حقول محددة عبر search_read
6. read_records: قراءة سجلات محددة بالمعرفات عبر read

الضوابط الأمنية:
- لا وجود لأي أداة كتابة (create) أو تعديل (write) أو حذف (unlink).
- لا وجود لـ execute_kw عام أو مفتوح.
- التحقق الصارم من أسماء الموديلات المصرح بقراءتها عبر فاحص.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fahas_service import (
    FahasAgent,
    FahasExecutionError,
    FahasSecurityError,
    FORBIDDEN_OPERATIONS,
    SAFE_MODEL_PREFIXES,
    get_fahas_agent,
    validate_model_name,
)
from odoo_readonly_repository import OdooReadonlyRepository, OdooReadonlyRepositoryError

logger = logging.getLogger("odoo_agent_tools")

# إعادة تصدير الأخطاء للتوافق البرمجي الكامل مع الاختبارات القديمة
OdooToolSecurityError = FahasSecurityError
OdooToolExecutionError = FahasExecutionError
_validate_model_name = validate_model_name


def _get_repository(connection_id: Optional[str] = None) -> OdooReadonlyRepository:
    """جلب مستودع القراءة الأساسي المستخدم لدى فاحص (يدعم التعديل أثناء الاختبارات mock)."""
    repo = OdooReadonlyRepository()
    repo.connect()
    return repo


# =============================================================================
# 1. دوال تفويض مهام الاستعلام والقراءة حصرياً إلى وكيل «فاحص»
# =============================================================================

def list_connections() -> List[Dict[str, Any]]:
    """استعراض الاتصالات المتاحة والمصرح بها بقاعدة بيانات Odoo عبر فاحص."""
    return get_fahas_agent().list_connections()


def list_companies(connection_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """استعراض الشركات المصرح بها للمستخدم ضمن الاتصال المحدد عبر فاحص دون تثبيت أي شركة."""
    return get_fahas_agent().list_companies(connection_id=connection_id)


def describe_model(
    model: str,
    fields: Optional[List[str]] = None,
    connection_id: Optional[str] = None,
) -> Dict[str, Any]:
    """فحص حقول الموديل وأنواعها وتسمياتها عبر فاحص للمساعدة في بناء الاستعلامات الصحيحة."""
    return get_fahas_agent().describe_model(
        model=model,
        fields=fields,
        connection_id=connection_id,
    )


def count_records(
    model: str,
    domain: Optional[List[Any]] = None,
    company_id: Optional[int] = None,
    include_archived: bool = False,
    connection_id: Optional[str] = None,
) -> Dict[str, Any]:
    """حساب عدد السجلات المطابقة للشروط عبر search_count بواسطة وكيل فاحص بدقة وأمان."""
    return get_fahas_agent().count_records(
        model=model,
        domain=domain,
        company_id=company_id,
        include_archived=include_archived,
        connection_id=connection_id,
    )


def search_records(
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
    """البحث في السجلات وجلب الحقول المطلوبة عبر search_read بواسطة فاحص ضمن سقف أمان أقصى 50 سجلاً."""
    return get_fahas_agent().search_records(
        model=model,
        domain=domain,
        fields=fields,
        limit=limit,
        offset=offset,
        order=order,
        company_id=company_id,
        include_archived=include_archived,
        connection_id=connection_id,
    )


def read_records(
    model: str,
    ids: List[int],
    fields: Optional[List[str]] = None,
    connection_id: Optional[str] = None,
) -> Dict[str, Any]:
    """قراءة تفاصيل سجلات محددة بأرقام معرفاتها عبر read بواسطة وكيل فاحص."""
    return get_fahas_agent().read_records(
        model=model,
        ids=ids,
        fields=fields,
        connection_id=connection_id,
    )


# =============================================================================
# 2. تعريف مواصفات المهام والأدوات بصيغة Tool Calling لسراج
# =============================================================================

SERAJ_ODOO_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_connections",
            "description": "طلب من فاحص: استعراض اتصالات Odoo المتاحة والمصرح بها حالياً في النظام.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_companies",
            "description": "طلب من فاحص: استعراض قائمة الشركات والمنشآت المتاحة والمصرح بها في قاعدة بيانات Odoo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "معرف الاتصال الاختياري (افتراضياً: default)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_model",
            "description": "طلب من فاحص: فحص حقول الموديل المعتمدة (مثل hr.employee أو res.company) ومعرفة أسمائها وأنواعها.",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "اسم الموديل المطلوب فحصه (مثل: hr.employee, hr.department, hr.job)",
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "قائمة اختيارية بأسماء حقول معينة لفحصها بدلاً من جلب كل الحقول",
                    },
                    "connection_id": {
                        "type": "string",
                        "description": "معرف الاتصال الاختياري",
                    },
                },
                "required": ["model"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_records",
            "description": "طلب من فاحص: حساب العدد الدقيق للسجلات في Odoo المطابقة لشروط معينة (مثل: كم عدد الموظفين؟). ممنوع البحث بالاسم عند طلب العدد.",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "اسم الموديل (مثل: hr.employee)",
                    },
                    "domain": {
                        "type": "array",
                        "description": "شروط التصفية بتنسيق Odoo Domain (مثل: [['active', '=', True]])",
                        "items": {"type": "array"},
                    },
                    "company_id": {
                        "type": "integer",
                        "description": "معرف المنشأة أو الشركة لتصفية السجلات بها حصراً إن طُلب ذلك",
                    },
                    "include_archived": {
                        "type": "boolean",
                        "description": "تفعيل البحث في السجلات غير النشطة والمؤرشفة (active=False)",
                    },
                    "connection_id": {
                        "type": "string",
                        "description": "معرف الاتصال الاختياري",
                    },
                },
                "required": ["model"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_records",
            "description": "طلب من فاحص: البحث والاستعلام في سجلات Odoo واستخراج حقول محددة (مثل: ابحث عن موظف اسمه أحمد، قائمة الأقسام، إلخ).",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "اسم الموديل (مثل: hr.employee, hr.department, hr.job)",
                    },
                    "domain": {
                        "type": "array",
                        "description": "شروط البحث كـ Odoo Domain (مثل: [['name', 'ilike', 'أحمد']])",
                        "items": {"type": "array"},
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "قائمة الحقول المحددة المراد جلبها (مثل: ['id', 'name', 'work_email', 'job_title'])",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "الحد الأقصى للسجلات المرجعة (الافتراضي 15، والحد الأقصى 50)",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "إزاحة النتائج للصفحات المتتالية",
                    },
                    "order": {
                        "type": "string",
                        "description": "ترتيب النتائج (مثل: 'name asc' أو 'id desc')",
                    },
                    "company_id": {
                        "type": "integer",
                        "description": "معرف الشركة لتصفية النتائج",
                    },
                    "include_archived": {
                        "type": "boolean",
                        "description": "البحث في السجلات المؤرشفة وغير النشطة",
                    },
                    "connection_id": {
                        "type": "string",
                        "description": "معرف الاتصال الاختياري",
                    },
                },
                "required": ["model"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_records",
            "description": "طلب من فاحص: قراءة وتفصيل سجلات محددة بأرقام معرّفاتها (IDs) المعروفة مسبقاً.",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "اسم الموديل (مثل: hr.employee)",
                    },
                    "ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "قائمة بأرقام معرّفات السجلات المراد قراءتها (مثال: [15, 147])",
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "قائمة الحقول المراد قراءتها",
                    },
                    "connection_id": {
                        "type": "string",
                        "description": "معرف الاتصال الاختياري",
                    },
                },
                "required": ["model", "ids"],
            },
        },
    },
]


def execute_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    تنفيذ استدعاء الأداة عبر تفويض المهمة حصرياً إلى وكيل «فاحص».
    سراج ينسق المهمة ويطلب من فاحص تنفيذها واسترجاع النتيجة المنظمة.
    """
    fahas = get_fahas_agent()
    return fahas.execute_query_task(tool_name, arguments)
