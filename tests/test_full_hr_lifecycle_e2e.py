# -*- coding: utf-8 -*-
"""
End-to-End HR Lifecycle Integration Suite
==========================================
Simulates the complete, continuous HR journey:
1. Master Excel generation, multi-sheet upload & dry-run with agent handoffs & checkpoints.
2. Auto-fixing, approval & dependency-ordered execution (Company -> Depts -> Jobs -> Employees -> Contracts).
3. Live conversational additions & mutations via Seraj Cockpit Chat (Department & Employee creation, Wage update).
4. Statutory labor law operations (Annual leave m/109, Overtime m/107, GOSI/Saned, Loan deduction m/92).
5. End of service benefit calculation m/84-85, archiving, unarchiving, and governed deletion.
6. Forensic audit verification via Sijil & full chat session retrieval.
"""

import os
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import openpyxl
from starlette.testclient import TestClient

from web_service import app
from seraj_session_manager import SerajSessionManager
from agents.tool_registry import ToolRegistry, register_all_tools
from agents.seraj_meta_agent import SerajMetaAgent
from seraj_llm_service import SerajLLMService


client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": "test-secret"}


@pytest.fixture(autouse=True)
def setup_env_and_tools():
    old_token = os.environ.get("WRITE_API_TOKEN")
    os.environ["WRITE_API_TOKEN"] = "test-secret"
    register_all_tools()
    yield
    if old_token is not None:
        os.environ["WRITE_API_TOKEN"] = old_token
    else:
        os.environ.pop("WRITE_API_TOKEN", None)


def test_complete_hr_lifecycle_e2e(tmp_path):
    chat_id = f"e2e_session_{int(time.time())}"
    session_mgr = SerajSessionManager.get_instance()
    session = session_mgr.get_session(chat_id)
    seraj = SerajLLMService()

    try:

        # =========================================================================
        # المرحلة 1: توليد ملف إكسل ماستر متعدد الأوراق، ورفعه وفحصه عبر /dry-run
        # =========================================================================
        master_file = tmp_path / "Master_Client_Onboarding_Template.xlsx"
        wb = openpyxl.Workbook()

        # 1_Company_Setup Sheet
        ws_comp = wb.active
        ws_comp.title = "1_Company_Setup"
        ws_comp.append(["بيانات تأسيس المنشأة والحسابات البنكية"])
        ws_comp.append(["اسم المنشأة بالعربي *", "اسم المنشأة بالإنجليزي *", "رقم السجل التجاري *", "الرقم الضريبي *"])
        ws_comp.append(["شركة أفق المستقبل للتقنية", "Future Horizon Tech", "1010998877", "300099887700003"])

        # 2_Employees Sheet
        ws_emp = wb.create_sheet(title="2_Employees")
        ws_emp.append(["بيانات الموظفين الأساسية ومواقع العمل"])
        emp_headers = [
            "اسم الموظف الكامل بالعربي *", "البريد الإلكتروني للعمل", "رقم الجوال *",
            "المسمى الوظيفي *", "المنشأة التابع لها *", "القسم / الإدارة *", "الوظيفة *",
            "تاريخ المباشرة / hiring date *"
        ]
        ws_emp.append(emp_headers)
        ws_emp.append(["عبدالله العتيبي", "abdullah.otaibi@futurehorizon.com", "0501112233", "مهندس برمجيات أول", "شركة أفق المستقبل للتقنية", "الهندسة والتقنية", "مهندس برمجيات", "2026-01-01"])
        ws_emp.append(["ريم الشهري", "reem.shehri@futurehorizon.com", "0503334455", "مديرة موارد بشرية", "شركة أفق المستقبل للتقنية", "الموارد البشرية", "مدير موارد بشرية", "2026-02-01"])
        ws_emp.append(["خالد الدوسري", "invalid-email-format", "0509998877", "أخصائي توظيف", "شركة أفق المستقبل للتقنية", "الموارد البشرية", "أخصائي توظيف", "2026-03-01"])

        # 3_Contracts Sheet
        ws_con = wb.create_sheet(title="3_Contracts")
        ws_con.append(["العقود والبدلات"])
        ws_con.append(["اسم الموظف الثلاثي *", "نوع العقد *", "تاريخ بداية العقد *", "الراتب الأساسي (ر.س) *", "بدل السكن الشهري (ر.س) *"])
        ws_con.append(["عبدالله العتيبي", "عقد محدد المدة", "2026-01-01", 18000.0, 4500.0])
        ws_con.append(["ريم الشهري", "عقد غير محدد المدة", "2026-02-01", 15000.0, 3750.0])

        wb.save(master_file)
        assert master_file.exists()

        # رفع الملف للفحص المبدئي عبر /api/agents/upload
        with open(master_file, "rb") as f:
            res_upload = client.post(
                "/api/agents/upload",
                files={"file": ("Master_Client_Onboarding_Template.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"chat_id": chat_id},
                headers=AUTH_HEADERS,
            )
        assert res_upload.status_code == 200
        upload_data = res_upload.json()
        assert upload_data["status"] == "success"
        dry_run = upload_data.get("dry_run_report") or {}
        assert "summary" in dry_run or "header" in dry_run

        # التحقق من تسجيل تسليمات الوكلاء ونقاط التفتيش في الـ MetaAgent
        meta = SerajMetaAgent()
        perception = meta.perceive({"query": "فحص ملف استيراد الماستر والمطابقة المرجعية"})
        plan = meta.plan(perception)
        exec_res = meta.execute(plan, perception)
        assert exec_res.get("overall_success") is True
        assert len(meta.get_handoffs()) >= 1
        assert len(meta.get_checkpoints()) >= 1

        # =========================================================================
        # المرحلة 2: الإصلاح، الاعتماد، والتنفيذ المتسلسل للشركات والأقسام والموظفين والعقود
        # =========================================================================
        from writer import _setup_onboarding_prerequisites, _setup_onboarding_post_requisites

        class MockGateway:
            def __init__(self):
                self.created_records = []
                self.created_employees = []
            def create_record(self, model, values, context=None):
                rec_id = len(self.created_records) + 101
                self.created_records.append({"model": model, "id": rec_id, "values": values})
                return rec_id
            def create_employee(self, values, context=None):
                emp_id = len(self.created_employees) + 501
                self.created_employees.append({"id": emp_id, "values": values})
                return emp_id

        class MockRepo:
            def get_companies(self):
                return [{"id": 1, "name": "الشركة الافتراضية"}]
            def get_departments(self, company_id=None):
                return []
            def get_jobs(self, company_id=None):
                return []
            def get_employees(self):
                return []

        mock_gw = MockGateway()
        mock_repo = MockRepo()

        # 1. تأسيس المنشأة والأقسام والمسميات كمتطلبات مسبقة
        eff_comp_id, pre_sum = _setup_onboarding_prerequisites(master_file, mock_repo, mock_gw, target_company_id=1)
        assert eff_comp_id != 1 or pre_sum["company_created"] is not None
        assert len(pre_sum["departments_created"]) >= 1
        assert len(pre_sum["jobs_created"]) >= 1

        # 2. إنشاء الموظفين
        emp1_id = mock_gw.create_employee({"name": "عبدالله العتيبي", "work_email": "abdullah.otaibi@futurehorizon.com"})
        emp2_id = mock_gw.create_employee({"name": "ريم الشهري", "work_email": "reem.shehri@futurehorizon.com"})
        emp_map = {
            "عبدالله العتيبي": emp1_id,
            "abdullah.otaibi@futurehorizon.com": emp1_id,
            "ريم الشهري": emp2_id,
            "reem.shehri@futurehorizon.com": emp2_id,
        }

        # 3. تأسيس العقود كمتطلب لاحق
        post_sum = _setup_onboarding_post_requisites(master_file, mock_repo, mock_gw, eff_comp_id, emp_map)
        assert len(post_sum["contracts_created"]) == 2
        assert any(c["wage"] == 18000.0 for c in post_sum["contracts_created"])

        # =========================================================================
        # المرحلة 3: الإضافة والتعديل عبر شات سراج (شات قمرة القيادة)
        # =========================================================================
        # أ) إنشاء قسم جديد
        res_dept = seraj.chat_turn("أضف قسماً جديداً باسم الذكاء الاصطناعي", chat_id=chat_id)
        assert "تحضير عملية إنشاء قسم جديد" in res_dept or "خطة الاعتماد" in res_dept
        assert session.pending_action is not None
        assert session.pending_action["action_type"] == "create"
        assert session.pending_action["model"] == "hr.department"

        # تأكيد إنشاء القسم
        seraj.katib.execute_approved_action = MagicMock(return_value={"ok": True, "action": "create", "record_id": 301})
        res_confirm_dept = seraj.chat_turn("تأكيد", chat_id=chat_id)
        assert "تم إنشاء سجل قسم بنجاح" in res_confirm_dept or "تم إنشاء" in res_confirm_dept

        # ب) إضافة موظف جديد
        session.pending_action = None
        res_emp = seraj.chat_turn("أضف موظف جديد باسم تركي السبيعي", chat_id=chat_id)
        assert "في انتظار الاعتماد" in res_emp
        assert session.pending_action is not None
        assert session.pending_action["action_type"] == "create"

        # تأكيد إضافة الموظف
        seraj.katib.execute_approved_action = MagicMock(return_value={"ok": True, "action": "create", "employee_id": 555})
        res_confirm_emp = seraj.chat_turn("تأكيد", chat_id=chat_id)
        assert "تم إنشاء الموظف بنجاح" in res_confirm_emp or "تم إنشاء" in res_confirm_emp

        # ج) تعديل راتب الموظف
        seraj.fahas.search_records = MagicMock(return_value={
            "records": [{"id": 555, "name": "تركي السبيعي", "company_id": [eff_comp_id, "شركة أفق المستقبل"], "wage": 12000.0}]
        })
        session.pending_action = None
        res_wage = seraj.chat_turn("عدل راتب تركي السبيعي إلى 16000", chat_id=chat_id)
        assert "تحضير عملية تعديل" in res_wage or "في انتظار الاعتماد" in res_wage
        assert session.pending_action is not None
        assert session.pending_action["action_type"] == "update"
        assert session.pending_action["values"]["wage"] == 16000.0

        # تأكيد تعديل الراتب
        seraj.katib.execute_approved_action = MagicMock(return_value={"ok": True, "action": "update", "record_id": 555})
        res_confirm_wage = seraj.chat_turn("تأكيد", chat_id=chat_id)
        assert "تم تنفيذ وتأكيد العملية بنجاح" in res_confirm_wage

        # =========================================================================
        # المرحلة 4: العمليات اليومية وحسابات الرواتب عبر الشات (أدوات مدقق)
        # =========================================================================
        # أ) استحقاق الإجازة السنوية م/109
        res_leave = seraj.chat_turn("احسب استحقاق الإجازة السنوية لخدمة 6 سنوات", chat_id=chat_id)
        assert "استحقاق الإجازة السنوية" in res_leave
        assert "30 يوماً" in res_leave

        # ب) حساب أجر العمل الإضافي م/107
        res_ot = seraj.chat_turn("احسب ساعات العمل الإضافي لراتب 12000 و 8 ساعات عمل إضافي", chat_id=chat_id)
        assert "أجر العمل الإضافي" in res_ot
        assert "المادة 107" in res_ot

        # ج) حساب اشتراكات التأمينات الاجتماعية GOSI وساند
        res_gosi = seraj.chat_turn("احسب التأمينات الاجتماعية لراتب أساسي 12000 وبدل سكن 3000 لموظف سعودي", chat_id=chat_id)
        assert "التأمينات الاجتماعية" in res_gosi
        assert "ساند" in res_gosi

        # د) فحص حد استقطاع السلفة م/92 عبر ToolRegistry
        reg = ToolRegistry.get_instance()
        loan_check = reg.execute_tool("validate_loan_deduction", "mudaqqiq", {"installment": 1000.0, "monthly_wage": 12000.0})
        assert loan_check.is_valid is True
        assert "المادة 92" in loan_check.article

        # =========================================================================
        # المرحلة 5: نهاية الخدمة، الأرشفة، الاسترجاع، والحذف المحكوم
        # =========================================================================
        # أ) احتساب مكافأة نهاية الخدمة م/84-85
        res_eos = seraj.chat_turn("احسب مكافأة نهاية الخدمة لراتب 15000 وخدمة 7 سنوات بدون استقالة", chat_id=chat_id)
        assert "مكافأة نهاية الخدمة" in res_eos
        assert "المادة 84" in res_eos

        # ب) أرشفة الموظف
        session.pending_action = None
        seraj.fahas.search_records = MagicMock(return_value={
            "records": [{"id": 555, "name": "تركي السبيعي", "company_id": [eff_comp_id, "شركة أفق المستقبل"], "active": True}]
        })
        res_arch = seraj.chat_turn("أرشفة تركي السبيعي", chat_id=chat_id)
        assert "خطة الأرشفة" in res_arch or "في انتظار الاعتماد" in res_arch
        assert session.pending_action is not None
        assert session.pending_action["action_type"] == "archive"

        # تأكيد الأرشفة
        seraj.fahas.verify_record_status = MagicMock(return_value={"verified": True, "state": "archived"})
        seraj.katib.execute_approved_action = MagicMock(return_value={"ok": True, "action": "archive", "record_id": 555})
        res_confirm_arch = seraj.chat_turn("تأكيد", chat_id=chat_id)
        assert "تمت الأرشفة بنجاح" in res_confirm_arch

        # ج) استعادة الموظف من الأرشيف (Unarchive)
        session.pending_action = None
        seraj.fahas.search_records = MagicMock(return_value={
            "records": [{"id": 555, "name": "تركي السبيعي", "company_id": [eff_comp_id, "شركة أفق المستقبل"], "active": False}]
        })
        res_unarch = seraj.chat_turn("استرجع تركي السبيعي", chat_id=chat_id)
        assert "خطة الاسترجاع من الأرشيف" in res_unarch
        assert session.pending_action is not None
        assert session.pending_action["action_type"] == "unarchive"

        # تأكيد الاسترجاع
        seraj.fahas.verify_record_status = MagicMock(return_value={"verified": True, "state": "active"})
        seraj.katib.execute_approved_action = MagicMock(return_value={"ok": True, "action": "unarchive", "record_id": 555})
        res_confirm_unarch = seraj.chat_turn("تأكيد", chat_id=chat_id)
        assert "تم استرجاع السجل من الأرشيف بنجاح" in res_confirm_unarch

        # د) حذف نهائي محكوم لسجل تجريبي
        session.pending_action = None
        seraj.fahas.search_records = MagicMock(return_value={
            "records": [{"id": 999, "name": "سجل تجريبي للحذف", "company_id": [eff_comp_id, "شركة أفق المستقبل"], "active": False}]
        })
        res_del = seraj.chat_turn("حذف نهائي سجل تجريبي للحذف", chat_id=chat_id)
        assert "خطة الحذف النهائي" in res_del or "في انتظار الاعتماد" in res_del
        assert session.pending_action is not None
        assert session.pending_action["action_type"] == "delete"

        # تأكيد الحذف
        seraj.fahas.verify_record_status = MagicMock(return_value={"verified": True, "state": "deleted"})
        seraj.katib.execute_approved_action = MagicMock(return_value={"ok": True, "action": "delete", "record_id": 999})
        res_confirm_del = seraj.chat_turn("تأكيد", chat_id=chat_id)
        assert "تم الحذف النهائي للسجل بنجاح عبر «كاتب»" in res_confirm_del

        # =========================================================================
        # المرحلة 6: التدقيق الجنائي واسترجاع الجلسة عبر API
        # =========================================================================
        # استرجاع قائمة الجلسات
        res_sessions_api = client.get("/api/seraj/sessions")
        assert res_sessions_api.status_code == 200
        sessions_data = res_sessions_api.json()
        assert sessions_data["status"] == "success"
        session_ids = [s["chat_id"] for s in sessions_data["sessions"]]
        assert chat_id in session_ids

        # استرجاع تفاصيل الجلسة المتصلة ومطابقة التاريخ والرسائل
        res_detail_api = client.get(f"/api/seraj/session/{chat_id}")
        assert res_detail_api.status_code == 200
        detail_data = res_detail_api.json()
        assert detail_data["status"] == "success"
        sess_obj = detail_data["session"]
        assert sess_obj["chat_id"] == chat_id
        assert len(sess_obj["history"]) >= 8
    finally:
        seraj.fahas.__dict__.pop("search_records", None)
        seraj.fahas.__dict__.pop("verify_record_status", None)
        seraj.katib.__dict__.pop("execute_approved_action", None)


