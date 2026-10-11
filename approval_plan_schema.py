"""
مخطط خطط الاعتماد الموحد (Unified Approval Plan Schema)
========================================================
P5: توحيد الاعتمادات لجميع عمليات الكتابة (إنشاء، تعديل، حذف، أرشفة)

كل خطة لها:
- TTL (5 دقائق)
- استهلاك واحد
- ربط بالمستخدم
- تفاصيل العملية
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


# ثوابت
PLAN_TTL_MINUTES = 5
PLANS_DIR = Path("approvals/plans")


class ApprovalPlanError(Exception):
    """خطأ في مخطط الخطة"""
    pass


@dataclass
class ApprovalPlan:
    """
    خطة اعتماد موحدة لجميع عمليات الكتابة.
    
    P5: استبدال WriteDecision بخطة منضبطة مع TTL واستهلاك واحد.
    """
    plan_id: str  # معرف فريد للخطة
    plan_type: Literal["create", "update", "archive", "delete"]  # نوع العملية
    target_model: str  # النموذج المستهدف (hr.employee, hr.contract, إلخ)
    target_records: List[int]  # معرفات السجلات المستهدفة
    operation_details: Dict[str, Any]  # تفاصيل العملية
    
    # ربط بالمستخدم
    created_by: str  # المستخدم الذي أنشأ الخطة
    approved_by: Optional[str]  # المستخدم الذي اعتمد الخطة (None = لم يُعتمد بعد)
    
    # TTL والاستهلاك
    created_at: str  # ISO 8601 timestamp
    expires_at: str  # ISO 8601 timestamp (TTL)
    is_consumed: bool  # هل تم استهلاك الخطة
    consumed_at: Optional[str]  # وقت الاستهلاك
    
    # الحالة
    status: Literal["pending", "approved", "rejected", "expired", "consumed"]
    
    @staticmethod
    def create(
        plan_type: Literal["create", "update", "archive", "delete"],
        target_model: str,
        target_records: List[int],
        operation_details: Dict[str, Any],
        created_by: str,
    ) -> "ApprovalPlan":
        """إنشاء خطة اعتماد جديدة"""
        import uuid
        import time
        
        plan_id = f"plan_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        expires = now + timedelta(minutes=PLAN_TTL_MINUTES)
        
        return ApprovalPlan(
            plan_id=plan_id,
            plan_type=plan_type,
            target_model=target_model,
            target_records=target_records,
            operation_details=operation_details,
            created_by=created_by,
            approved_by=None,
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
            is_consumed=False,
            consumed_at=None,
            status="pending",
        )
    
    def approve(self, approved_by: str) -> None:
        """اعتماد الخطة"""
        if self.is_expired():
            raise ApprovalPlanError(f"Plan {self.plan_id} has expired")
        
        if self.is_consumed:
            raise ApprovalPlanError(f"Plan {self.plan_id} has already been consumed")
        
        self.approved_by = approved_by
        self.status = "approved"
    
    def reject(self) -> None:
        """رفض الخطة"""
        self.status = "rejected"
    
    def consume(self) -> None:
        """استهلاك الخطة (تنفيذ لمرة واحدة)"""
        if self.is_expired():
            raise ApprovalPlanError(f"Plan {self.plan_id} has expired")
        
        if self.is_consumed:
            raise ApprovalPlanError(f"Plan {self.plan_id} has already been consumed")
        
        if self.status != "approved":
            raise ApprovalPlanError(f"Plan {self.plan_id} is not approved (status: {self.status})")
        
        self.is_consumed = True
        self.consumed_at = datetime.utcnow().isoformat()
        self.status = "consumed"
    
    def is_expired(self) -> bool:
        """فحص انتهاء صلاحية الخطة"""
        expires_dt = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        return datetime.utcnow() > expires_dt
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return {
            "plan_id": self.plan_id,
            "plan_type": self.plan_type,
            "target_model": self.target_model,
            "target_records": self.target_records,
            "operation_details": self.operation_details,
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "is_consumed": self.is_consumed,
            "consumed_at": self.consumed_at,
            "status": self.status,
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ApprovalPlan":
        """التحميل من قاموس"""
        return ApprovalPlan(
            plan_id=data["plan_id"],
            plan_type=data["plan_type"],
            target_model=data["target_model"],
            target_records=data["target_records"],
            operation_details=data["operation_details"],
            created_by=data["created_by"],
            approved_by=data.get("approved_by"),
            created_at=data["created_at"],
            expires_at=data["expires_at"],
            is_consumed=data.get("is_consumed", False),
            consumed_at=data.get("consumed_at"),
            status=data.get("status", "pending"),
        )
    
    def save(self) -> Path:
        """حفظ الخطة في ملف"""
        PLANS_DIR.mkdir(parents=True, exist_ok=True)
        plan_path = PLANS_DIR / f"{self.plan_id}.json"
        plan_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))
        return plan_path
    
    @staticmethod
    def load(plan_id: str) -> "ApprovalPlan":
        """تحميل خطة من ملف"""
        plan_path = PLANS_DIR / f"{plan_id}.json"
        
        if not plan_path.exists():
            raise ApprovalPlanError(f"Plan {plan_id} not found")
        
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        plan = ApprovalPlan.from_dict(data)
        
        # فحص انتهاء الصلاحية
        if plan.is_expired():
            plan.status = "expired"
            plan.save()
            raise ApprovalPlanError(f"Plan {plan_id} has expired")
        
        return plan


def validate_plan_for_execution(plan: ApprovalPlan) -> None:
    """
    التحقق من صلاحية الخطة للتنفيذ.
    
    P5: فحوص قبل التنفيذ:
    - الخطة معتمدة
    - لم تنته صلاحيتها
    - لم يتم استهلاكها
    """
    if plan.status != "approved":
        raise ApprovalPlanError(f"Plan {plan.plan_id} is not approved (status: {plan.status})")
    
    if plan.is_expired():
        raise ApprovalPlanError(f"Plan {plan.plan_id} has expired at {plan.expires_at}")
    
    if plan.is_consumed:
        raise ApprovalPlanError(f"Plan {plan.plan_id} has already been consumed at {plan.consumed_at}")
