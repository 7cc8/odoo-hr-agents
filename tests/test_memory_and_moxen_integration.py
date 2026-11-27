"""
اختبارات تكامل الذاكرة طويلة وقصيرة المدى وتحسينات Moxen وسير العمليات المباشر
=============================================================================
"""

import pytest
from fastapi.testclient import TestClient
from web_service import app
from memory.manager import MemoryManager
from seraj_session_manager import SerajSessionManager, ConversationSession
from agent_events_service import get_events_service


@pytest.fixture
def client():
    return TestClient(app)


class TestMemoryAndOperationsIntegration:
    def test_memory_manager_long_term_facts_crud(self):
        """اختبار عمليات CRUD للذاكرة طويلة المدى في MemoryManager."""
        mgr = MemoryManager.get_instance()
        mgr.clear_long_term_facts()

        # 1. Create
        fact = mgr.save_long_term_fact(
            content="أوقات العمل الرسمية من 8:00 ص إلى 4:00 م",
            key="ساعات الدوام",
            category="policy",
            importance=5,
        )
        assert fact["id"].startswith("fact_")
        assert fact["key"] == "ساعات الدوام"
        assert fact["importance"] == 5

        # 2. Read
        facts = mgr.get_long_term_facts()
        assert len(facts) == 1
        assert facts[0]["key"] == "ساعات الدوام"

        summary = mgr.get_long_term_summary()
        assert "ساعات الدوام" in summary
        assert "8:00 ص" in summary

        # 3. Update
        updated = mgr.update_long_term_fact(
            fact["id"],
            {"content": "أوقات العمل الرسمية المحدثة من 9:00 ص إلى 5:00 م"},
        )
        assert updated is not None
        assert "9:00 ص" in updated["content"]

        # 4. Delete
        ok = mgr.delete_long_term_fact(fact["id"])
        assert ok is True
        assert len(mgr.get_long_term_facts()) == 0

    def test_session_active_entities_and_pronoun_resolution(self):
        """اختبار الكيانات النشطة في الذاكرة قصيرة المدى وفض الضمائر."""
        sess_mgr = SerajSessionManager.get_instance()
        session = sess_mgr.get_session("test_chat_pronoun_1")

        session.update_active_entities(
            employee_name="سالم القحطاني",
            employee_id=42,
            department_name="المبيعات",
            job_title="مدير مبيعات",
        )
        summary = session.get_context_summary()
        assert "سالم القحطاني" in summary
        assert "المبيعات" in summary

        # فحص فض الضمير في seraj_llm_service
        from seraj_llm_service import SerajLLMService
        seraj = SerajLLMService()

        # عند إرسال «كم راتبه» يجب أن يتم فضها بسياق «سالم القحطاني»
        reply = seraj.chat_turn(
            user_query="كم راتبه",
            chat_id="test_chat_pronoun_1",
        )
        assert reply is not None

    def test_agent_events_auto_close_previous_steps(self):
        """اختبار إغلاق الخطوات السابقة المفتوحة وحساب duration_ms بدقة."""
        srv = get_events_service()
        op_id = srv.start_operation(user_query="استعلام تجريبي لإغلاق الخطوات")

        # الحدث الأول: تحليل الطلب
        srv.emit_event(
            operation_id=op_id,
            agent="seraj",
            event_type="intent_analysis",
            status="analyzing_request",
            description_ar="سراج يحلل الطلب",
        )

        events = srv.get_operation_events(op_id)
        assert len(events) >= 2  # operation_started + intent_analysis

        # الحدث الثاني: فاحص يستعلم (يجب أن يغلق الحدث السابق كـ completed مع duration_ms)
        srv.emit_event(
            operation_id=op_id,
            agent="fahas",
            event_type="odoo_query",
            status="completed",
            description_ar="فاحص ينهي الاستعلام",
        )

        updated_events = srv.get_operation_events(op_id)
        prev_event = updated_events[-2]
        assert prev_event["status"] == "completed"
        assert "duration_ms" in prev_event

    def test_memory_api_endpoints(self, client):
        """اختبار كافة نهايات API للذاكرة طويلة المدى."""
        # 1. Clear
        r_clear = client.delete("/api/memory/clear")
        assert r_clear.status_code == 200

        # 2. Create
        r_post = client.post(
            "/api/memory/items",
            json={
                "content": "الشركة تطبق نظام العمل السعودي واللوائح المعتمدة",
                "key": "مرجعية الامتثال",
                "category": "policy",
                "importance": 5,
            },
        )
        assert r_post.status_code == 200
        fact_id = r_post.json()["item"]["id"]

        # 3. Get list
        r_get = client.get("/api/memory/items")
        assert r_get.status_code == 200
        data = r_get.json()
        assert len(data["facts"]) == 1
        assert data["facts"][0]["key"] == "مرجعية الامتثال"

        # 4. Update
        r_put = client.put(
            f"/api/memory/items/{fact_id}",
            json={"importance": 4},
        )
        assert r_put.status_code == 200
        assert r_put.json()["item"]["importance"] == 4

        # 5. Delete
        r_del = client.delete(f"/api/memory/items/{fact_id}")
        assert r_del.status_code == 200

    def test_seraj_cancel_endpoint(self, client):
        """اختبار نهاية إلغاء واستيقاف العملية الجارية لسراج."""
        srv = get_events_service()
        op_id = srv.start_operation(user_query="عملية يتم إلغاؤها فوراً")

        res = client.post(f"/api/seraj/cancel/{op_id}")
        assert res.status_code == 200
        assert res.json()["status"] == "success"

        op = srv.get_operation(op_id)
        assert op["status"] == "cancelled"

