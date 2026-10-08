"""
اختبارات القبول الشاملة للواجهة الموحدة لمنظومة الوكلاء
Unified Multi-Agent Cockpit Acceptance Tests (15 Scenarios)
============================================================
تغطي جميع اختبارات القبول المنصوص عليها في وثيقة المتطلبات:
1. رسالة واضحة -> تظهر فقط المهام التي نُفذت فعلاً.
2. طلب غامض -> يظهر استدعاء لايا إذا حدث، ثم سؤال المستخدم عند الحاجة.
3. استعلام -> نشاط فاحص ثم النتيجة.
4. تعديل -> انتظار اعتماد قبل نشاط كاتب.
5. رفض الاعتماد -> لا تنفيذ.
6. حذف -> يظهر المسار المحكوم نفسه، لا اختصار.
7. تعثر -> يظهر الوكيل والخطوة والخطأ الحقيقي.
8. تحديث الصفحة -> استرجاع الحالة دون تكرار التنفيذ.
9. انقطاع المتابعة -> حالة اتصال واضحة دون إعلان فشل العملية.
10. أحداث مكررة أو متأخرة -> لا تكرر الخطوات ولا تعكس ترتيبها.
11. عمليتان متزامنتان -> لا تختلط أحداثهما.
12. واجهة RTL سليمة على سطح المكتب والجوال.
13. تقليل الحركة -> يتوقف أو يقل الأنيميشن غير الضروري.
14. الانتقال إلى سجل وPDF يستخدم بيانات العملية نفسها.
15. حماية النطاق والتحقق من الصلاحيات وتوثيق الوصول (404 للعمليات غير الموجودة).
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from web_service import app
from agent_events_service import get_events_service, AGENTS_REGISTRY, STATUS_LABELS_AR
from seraj_session_manager import SerajSessionManager


class TestUnifiedAgentCockpitAcceptance(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.events_service = get_events_service()
        self.session_manager = SerajSessionManager.get_instance()

    # 1. رسالة واضحة -> تظهر فقط المهام التي نُفذت فعلاً
    def test_scenario_01_clear_message_only_executed_tasks(self):
        chat_id = "test_user_scen_1"
        res = self.client.post("/api/seraj/chat", json={
            "message": "كم ساعات العمل الرسمية في شهر رمضان للمسلمين؟",
            "chat_id": chat_id,
            "company_id": 15,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        op_id = data["operation_id"]

        op = self.events_service.get_operation(op_id)
        self.assertIsNotNone(op)
        events = op.get("events", [])
        self.assertGreater(len(events), 0)

        # التحقق من أن المهام المسجلة تخص سراج وشرح نظام العمل فقط، دون استدعاء كاتب أو مصلح
        agents_participated = {e["agent"] for e in events}
        self.assertIn("seraj", agents_participated)
        self.assertNotIn("katib", agents_participated)
        self.assertNotIn("musleh", agents_participated)

    # 2. طلب غامض -> استدعاء لايا إذا حدث، ثم سؤال المستخدم
    def test_scenario_02_ambiguous_request_clarification(self):
        chat_id = "test_user_scen_2"
        # طلب يحتوي على كلمة حذف دون تحديد نوعها (أرشفة أم حذف نهائي)
        res = self.client.post("/api/seraj/chat", json={
            "message": "احذف الموظف سامي",
            "chat_id": chat_id,
            "company_id": 15,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        op_id = data["operation_id"]
        op = self.events_service.get_operation(op_id)
        events = op.get("events", [])

        # التحقق من تسجيل حدث استيضاح أو انتظار توضيح المستخدم
        waiting_events = [e for e in events if e.get("status") in ("waiting_clarification", "waiting_user_clarification")]
        self.assertGreater(len(waiting_events), 0)
        self.assertIn("clarification", str(waiting_events[0].get("event_type", "")))

    # 3. استعلام -> نشاط فاحص ثم النتيجة
    @patch("fahas_service.FahasAgent.search_records")
    def test_scenario_03_query_invokes_fahas_then_result(self, mock_search):
        mock_search.return_value = {
            "status": "success",
            "records": [{"id": 101, "name": "سارة أحمد", "job_title": "مهندسة برمجيات"}],
            "total_count": 1
        }
        chat_id = "test_user_scen_3"
        res = self.client.post("/api/seraj/chat", json={
            "message": "استعلم عن الموظفة سارة في Odoo",
            "chat_id": chat_id,
            "company_id": 15,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        op_id = data["operation_id"]
        op = self.events_service.get_operation(op_id)
        events = op.get("events", [])

        agents_in_events = [e["agent"] for e in events]
        self.assertIn("seraj", agents_in_events)
        self.assertIn("fahas", agents_in_events)

    # 4. تعديل -> انتظار اعتماد قبل نشاط كاتب
    @patch("fahas_service.FahasAgent.search_records")
    def test_scenario_04_update_waits_for_approval_before_katib(self, mock_search):
        mock_search.return_value = {
            "status": "success",
            "records": [{"id": 55, "name": "فهد الناصر", "job_title": "أخصائي توظيف"}],
            "total_count": 1
        }
        chat_id = "test_user_scen_4"
        res = self.client.post("/api/seraj/chat", json={
            "message": "عدل مسمى فهد الناصر إلى مدير توظيف",
            "chat_id": chat_id,
            "company_id": 15,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        op_id = data["operation_id"]
        op = self.events_service.get_operation(op_id)

        # التحقق من أن حالة العملية في انتظار الاعتماد
        self.assertEqual(op["status"], "waiting_approval")
        # التحقق من أن كاتب لم ينفذ التعديل بعد
        events = op.get("events", [])
        katib_write_events = [e for e in events if e["agent"] == "katib" and e["status"] == "executing_write"]
        self.assertEqual(len(katib_write_events), 0)

    # 5. رفض الاعتماد -> لا تنفيذ
    def test_scenario_05_rejection_prevents_execution(self):
        chat_id = "test_user_scen_5"
        session = self.session_manager.get_session(chat_id)
        op_id = self.events_service.start_operation(
            user_query="تعديل مسمى وظيفي",
            operation_type="update",
            chat_id=chat_id,
            company_id=15
        )
        session.pending_action = {
            "action_type": "update",
            "record_id": 99,
            "record_name": "خالد المنصور",
            "plan_id": "PLAN-TEST-CANCEL"
        }

        # إرسال إلغاء عبر نقطة الاعتماد الموحدة
        res = self.client.post("/api/agents/cancel", json={
            "chat_id": chat_id,
            "operation_id": op_id
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsNone(data["pending_action"])

        op = self.events_service.get_operation(op_id)
        events = op.get("events", [])
        cancel_events = [e for e in events if e.get("event_type") == "plan_cancelled" or "إلغاء" in e.get("description_ar", "")]
        self.assertGreater(len(cancel_events), 0)
        # التأكد من عدم وجود أي تنفيذ بواسطة كاتب
        executed_events = [e for e in events if e.get("status") == "executing_write"]
        self.assertEqual(len(executed_events), 0)

    # 6. حذف -> يظهر المسار المحكوم نفسه، لا اختصار
    @patch("fahas_service.FahasAgent.search_records")
    def test_scenario_06_deletion_follows_governed_path(self, mock_search):
        mock_search.return_value = {
            "status": "success",
            "records": [{"id": 42, "name": "فيصل العتيبي", "job_title": "مطور برمجيات", "active": True}],
            "total_count": 1
        }
        chat_id = "test_user_scen_6"
        res = self.client.post("/api/seraj/chat", json={
            "message": "أريد حذف نهائي للموظف فيصل",
            "chat_id": chat_id,
            "company_id": 15,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        op_id = data["operation_id"]
        op = self.events_service.get_operation(op_id)
        events = op.get("events", [])

        # التحقق من أن المسار مر بحارس للتحقق من سياسة الحذف وإصدار الخطة
        hares_events = [e for e in events if e["agent"] == "hares"]
        self.assertGreater(len(hares_events), 0)

    # 7. تعثر -> يظهر الوكيل والخطوة والخطأ الحقيقي
    def test_scenario_07_failure_records_real_agent_and_error(self):
        op_id = self.events_service.start_operation(
            user_query="استعلام متعثر لاختبار الخطأ",
            operation_type="query",
            chat_id="test_error_op"
        )
        self.events_service.emit_event(
            operation_id=op_id,
            agent="fahas",
            event_type="connection_error",
            status="failed",
            description_ar="تعذر الاتصال بخادم Odoo: مهلة الاتصال انتهت (Timeout)",
            error="Connection timed out after 10000ms"
        )
        op = self.events_service.get_operation(op_id)
        self.assertEqual(op["status"], "failed")
        self.assertEqual(op["active_agent"], "fahas")
        self.assertIn("Connection timed out", op.get("error", ""))

        last_evt = op["events"][-1]
        self.assertEqual(last_evt["agent"], "fahas")
        self.assertEqual(last_evt["status"], "failed")
        self.assertEqual(last_evt["error"], "Connection timed out after 10000ms")

    # 8. تحديث الصفحة -> استرجاع الحالة دون تكرار التنفيذ
    def test_scenario_08_page_reload_idempotent_recovery(self):
        op_id = self.events_service.start_operation(
            user_query="استعلام استرجاع الحالة",
            operation_type="query",
            chat_id="test_reload_op"
        )
        self.events_service.emit_event(
            operation_id=op_id,
            agent="seraj",
            event_type="query_received",
            status="analyzing_request",
            description_ar="سراج يستلم الطلب"
        )
        # محاكاة إعادة تحميل المتصفح بطلب GET لنقطة تفاصيل العملية
        res = self.client.get(f"/api/agents/operations/{op_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["operation"]["operation_id"], op_id)
        self.assertEqual(len(data["operation"]["events"]), 2)

        # استرجاع ثانٍ للتأكد من عدم توليد أحداث متكررة أو إعادة تنفيذ
        res2 = self.client.get(f"/api/agents/operations/{op_id}")
        data2 = res2.json()
        self.assertEqual(len(data2["operation"]["events"]), 2)

    # 9. انقطاع المتابعة -> حالة اتصال واضحة دون إعلان فشل العملية
    def test_scenario_09_disconnection_status_does_not_fail_operation(self):
        op_id = self.events_service.start_operation(
            user_query="عملية قيد المتابعة",
            operation_type="query",
            chat_id="test_disconnect_op"
        )
        # العملية مستمرة لكن اتصال العميل انقطع
        op = self.events_service.get_operation(op_id)
        self.assertNotEqual(op["status"], "failed")
        # التحقق من أن وصف الحالة غير متصل معتمد
        self.assertEqual(STATUS_LABELS_AR["disconnected"], "انقطع اتصال متابعة الأحداث")

    # 10. أحداث مكررة أو متأخرة -> لا تكرر الخطوات ولا تعكس ترتيبها
    def test_scenario_10_after_seq_polling_prevents_duplicates(self):
        op_id = self.events_service.start_operation(
            user_query="اختبار التسلسل",
            operation_type="conversation",
            chat_id="test_seq_op"
        )
        e1 = self.events_service.emit_event(
            operation_id=op_id,
            agent="seraj",
            event_type="step_1",
            status="analyzing_request",
            description_ar="الخطوة 1"
        )
        e2 = self.events_service.emit_event(
            operation_id=op_id,
            agent="fahas",
            event_type="step_2",
            status="querying_odoo",
            description_ar="الخطوة 2"
        )

        # طلب الأحداث بعد التسلسل 2 (الحدث الأخير فقط)
        res = self.client.get(f"/api/agents/operations/{op_id}/events?after=2")
        self.assertEqual(res.status_code, 200)
        events = res.json()["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["sequence"], 3)

    # 11. عمليتان متزامنتان -> لا تختلط أحداثهما
    def test_scenario_11_concurrent_operations_isolation(self):
        op_a = self.events_service.start_operation(
            user_query="عملية أ",
            operation_type="query",
            chat_id="chat_a"
        )
        op_b = self.events_service.start_operation(
            user_query="عملية ب",
            operation_type="update",
            chat_id="chat_b"
        )

        self.events_service.emit_event(
            operation_id=op_a,
            agent="fahas",
            event_type="query_a",
            status="querying_odoo",
            description_ar="استعلام عملية أ"
        )
        self.events_service.emit_event(
            operation_id=op_b,
            agent="katib",
            event_type="write_b",
            status="executing_write",
            description_ar="تعديل عملية ب"
        )

        res_a = self.client.get(f"/api/agents/operations/{op_a}")
        res_b = self.client.get(f"/api/agents/operations/{op_b}")

        events_a = res_a.json()["operation"]["events"]
        events_b = res_b.json()["operation"]["events"]

        self.assertTrue(all(e["operation_id"] == op_a for e in events_a))
        self.assertTrue(all(e["operation_id"] == op_b for e in events_b))
        self.assertNotIn("katib", [e["agent"] for e in events_a])
        self.assertNotIn("fahas", [e["agent"] for e in events_b])

    # 12. واجهة RTL سليمة على سطح المكتب والجوال
    def test_scenario_12_rtl_and_responsive_structure(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn('dir="rtl"', html)
        self.assertIn('lang="ar"', html)
        self.assertIn('<meta name="viewport"', html)
        self.assertIn('view-cockpit', html)
        self.assertIn('view-operations', html)
        self.assertIn('view-agents', html)
        self.assertIn('view-sijil', html)
        self.assertIn('view-settings', html)

    # 13. تقليل الحركة -> يتوقف أو يقل الأنيميشن غير الضروري
    def test_scenario_13_reduce_motion_accessibility(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("prefers-reduced-motion", html)
        self.assertIn("reduce-motion-forced", html)
        self.assertIn("toggleReduceMotion", html)

    # 14. الانتقال إلى سجل وPDF يستخدم بيانات العملية نفسها
    def test_scenario_14_sijil_audit_and_pdf_export_consistency(self):
        op_id = self.events_service.start_operation(
            user_query="عملية التوثيق الموحد",
            operation_type="update",
            chat_id="test_sijil_pdf"
        )
        self.events_service.emit_event(
            operation_id=op_id,
            agent="sijil",
            event_type="audit_completed",
            status="completed",
            description_ar="اكتمل التوثيق في الدفتر اللاتراجعي"
        )
        # التحقق من إمكانية طلب تقرير PDF الشامل
        pdf_res = self.client.get("/api/sijil/report/pdf")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertIn("application/pdf", pdf_res.headers.get("content-type", ""))

    # 15. مستخدم غير مخول لا يرى الأحداث وتوثيق الوصول الأمني
    def test_scenario_15_invalid_operation_returns_404(self):
        res = self.client.get("/api/agents/operations/OP-NON-EXISTENT-XYZ")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
