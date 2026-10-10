"""
مستودع Odoo مزيّف للاختبارات
================================
يحاكي Odoo XML-RPC بدون اتصال حقيقي
"""
from typing import Any, Dict, List, Optional


class FakeOdooRepository:
    """مستودع مزيّف يحتوي على بيانات ثابتة للاختبار"""
    
    def __init__(self):
        # الشركات
        self.companies = [
            {"id": 1, "name": "My Company", "active": True, "child_ids": []},
            {"id": 15, "name": "شركة النخبة الذكية للتقنية", "active": True, "child_ids": []},
            {"id": 16, "name": "شركة توركين للتجزئة", "active": True, "child_ids": []},
            {"id": 17, "name": "شركة العقار الموحدة", "active": True, "child_ids": []},
        ]
        
        # الموظفون (1 في My Company + 13 في النخبة + 0 في توركين + 0 في العقار = 14)
        self.employees = [
            {
                "id": 1,
                "name": "Administrator",
                "company_id": [1, "My Company"],
                "job_id": False,
                "department_id": [1, "Administration"],
            },
        ] + [
            {
                "id": 10 + i,
                "name": f"موظف {i}",
                "company_id": [15, "شركة النخبة الذكية للتقنية"],
                "job_id": [20 + (i % 5), f"وظيفة {i % 5}"],
                "department_id": [10 + (i % 3), f"قسم {i % 3}"],
            }
            for i in range(1, 14)  # 13 موظف
        ]
        
        # الأقسام
        self.departments = [
            {"id": 1, "name": "Administration", "company_id": [1, "My Company"]},
            {"id": 10, "name": "قسم 0", "company_id": [15, "شركة النخبة الذكية للتقنية"]},
            {"id": 11, "name": "قسم 1", "company_id": [15, "شركة النخبة الذكية للتقنية"]},
            {"id": 12, "name": "قسم 2", "company_id": [15, "شركة النخبة الذكية للتقنية"]},
        ]
        
        # الوظائف
        self.jobs = [
            {"id": 20 + i, "name": f"وظيفة {i}"} for i in range(5)
        ]
    
    def search_read(self, model: str, domain: List, fields: List[str], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """محاكاة search_read"""
        if model == "res.company":
            results = self.companies
        elif model == "hr.employee":
            results = self._filter_employees(domain)
        elif model == "hr.department":
            results = self._filter_departments(domain)
        elif model == "hr.job":
            results = self.jobs
        else:
            return []
        
        # تطبيق الحقول المطلوبة
        if fields and fields != ["id"]:
            filtered_results = []
            for item in results:
                filtered_item = {field: item.get(field) for field in fields if field in item}
                if "id" not in fields:
                    filtered_item["id"] = item["id"]  # دائماً نضيف id
                filtered_results.append(filtered_item)
            results = filtered_results
        
        # تطبيق limit
        if limit and limit > 0:
            results = results[:limit]
        
        return results
    
    def search_count(self, model: str, domain: List) -> int:
        """محاكاة search_count"""
        if model == "res.company":
            return len(self.companies)
        elif model == "hr.employee":
            return len(self._filter_employees(domain))
        elif model == "hr.department":
            return len(self._filter_departments(domain))
        elif model == "hr.job":
            return len(self.jobs)
        return 0
    
    def _filter_employees(self, domain: List) -> List[Dict[str, Any]]:
        """تصفية الموظفين بناءً على domain"""
        if not domain:
            return self.employees
        
        results = self.employees
        for condition in domain:
            if len(condition) != 3:
                continue
            
            field, operator, value = condition
            
            if field == "company_id" and operator == "=":
                results = [e for e in results if e["company_id"][0] == value]
            elif field == "company_id.name" and operator in ("=", "ilike"):
                if operator == "=":
                    results = [e for e in results if e["company_id"][1] == value]
                else:  # ilike
                    results = [e for e in results if value.lower() in e["company_id"][1].lower()]
            elif field == "name" and operator == "ilike":
                results = [e for e in results if value.lower() in e["name"].lower()]
        
        return results
    
    def _filter_departments(self, domain: List) -> List[Dict[str, Any]]:
        """تصفية الأقسام بناءً على domain"""
        if not domain:
            return self.departments
        
        results = self.departments
        for condition in domain:
            if len(condition) != 3:
                continue
            
            field, operator, value = condition
            
            if field == "company_id" and operator == "=":
                results = [d for d in results if d["company_id"][0] == value]
        
        return results
    
    def execute_kw(self, db: str, uid: int, password: str, model: str, method: str, args: List, kwargs: Dict = None) -> Any:
        """محاكاة execute_kw (الواجهة الرئيسية)"""
        kwargs = kwargs or {}
        
        if method == "search_read":
            domain = args[0] if args else []
            fields = kwargs.get("fields", [])
            limit = kwargs.get("limit")
            return self.search_read(model, domain, fields, limit)
        
        elif method == "search_count":
            domain = args[0] if args else []
            return self.search_count(model, domain)
        
        elif method == "read":
            ids = args[0] if args else []
            fields = kwargs.get("fields", [])
            if model == "hr.employee":
                return [e for e in self.employees if e["id"] in ids]
            elif model == "res.company":
                return [c for c in self.companies if c["id"] in ids]
        
        return []


# Instance عامة للاستخدام في الاختبارات
fake_odoo = FakeOdooRepository()
