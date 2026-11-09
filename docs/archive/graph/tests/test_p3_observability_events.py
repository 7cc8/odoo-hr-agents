"""
اختبار P3: الملاحظة والأحداث
===============================
يختبر تكامل أحداث الرسم مع نظام المراقبة:
- operation_id في الحالة
- emit_event من العقد 
- البحث في القرص عند عدم وجود العملية في الذاكرة
- إزالة company_id الافتراضية المثبتة
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from agent_events_service import AgentEventsService, get_events_service
from graph.state import SerajState


class TestAgentEventsServiceP3:
    """اختبار تحسينات P3 في agent_events_service"""
    
    def setup_method(self):
        """إعداد نسخة جديدة من الخدمة لكل اختبار"""
        # إعادة تعيين singleton
        AgentEventsService._instance = None
        
        # إنشاء ملف مؤقت للاختبار
        self.temp_dir = tempfile.mkdtemp()
        self.temp_log_file = Path(self.temp_dir) / "test_operations.jsonl"
        
        # mock ملف السجل
        with patch('agent_events_service.AGENT_OPS_LOG_FILE', self.temp_log_file):
            self.events_service = AgentEventsService.get_instance()
    
    def test_no_hardcoded_company_id(self):
        """P3: إزالة company_id الافتراضية المثبتة"""
        # بدء عملية بدون company_id
        op_id = self.events_service.start_operation(
            user_query="اختبار بدون شركة"
        )
        
        operation = self.events_service.get_operation(op_id)
        
        # يجب أن يكون company_id = None وليس 15
        assert operation["company_id"] is None
        assert operation["company_name"] is None
    
    def test_operation_id_in_state(self):
        """P3: operation_id موجود في حالة الرسم"""
        # محاكاة حالة الرسم
        state: SerajState = {
            "user_query": "كم موظف؟",
            "chat_id": "test_chat",
            "user_name": "اختبار",
            "connection_id": "test_conn"
        }
        
        # محاكاة ingest_user_message
        from graph.nodes import ingest_user_message
        
        result = ingest_user_message(state)
        
        # التحقق من وجود operation_id
        assert "operation_id" in result
        assert result["operation_id"] is not None
        assert result["operation_id"].startswith("op_")
    
    def test_emit_event_with_operation_id(self):
        """P3: العقد تستدعي emit_event مع operation_id"""
        # بدء عملية
        op_id = self.events_service.start_operation(
            user_query="اختبار الأحداث",
            company_id=1,
            company_name="شركة الاختبار"
        )
        
        # إصدار حدث من عقدة
        event = self.events_service.emit_event(
            operation_id=op_id,
            agent="fahas",
            event_type="query_started",
            status="querying_odoo",
            description_ar="فاحص يستعلم من Odoo",
            company_id=1,
            company_name="شركة الاختبار"
        )
        
        # التحقق من الحدث
        assert event["operation_id"] == op_id
        assert event["agent"] == "fahas"
        assert event["event_type"] == "query_started"
        assert event["status"] == "querying_odoo"
        
        # التحقق من أن الحدث مُسجل في العملية
        operation = self.events_service.get_operation(op_id)
        assert len(operation["events"]) >= 2  # بدء العملية + الحدث الجديد
        assert any(e["event_type"] == "query_started" for e in operation["events"])
    
    def test_disk_search_for_missing_operation(self):
        """P3: البحث في القرص عند عدم وجود العملية في الذاكرة"""
        # كتابة أحداث مباشرة في ملف السجل
        test_op_id = "op_test_123456"
        test_events = [
            {
                "operation_id": test_op_id,
                "event_id": "evt_1",
                "sequence": 1,
                "timestamp": "2024-01-01T12:00:00Z",
                "agent": "seraj",
                "event_type": "operation_started",
                "status": "analyzing_request",
                "description_ar": "بدء العملية",
                "user_query": "عملية اختبار",
                "operation_type": "test",
                "company_id": 1,
                "company_name": "شركة الاختبار"
            },
            {
                "operation_id": test_op_id,
                "event_id": "evt_2", 
                "sequence": 2,
                "timestamp": "2024-01-01T12:01:00Z",
                "agent": "fahas",
                "event_type": "query_completed",
                "status": "completed",
                "description_ar": "اكتملت العملية"
            }
        ]
        
        # كتابة الأحداث في الملف
        with open(self.temp_log_file, "w", encoding="utf-8") as f:
            for event in test_events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        
        # محاولة الحصول على العملية (غير موجودة في الذاكرة)
        with patch('agent_events_service.AGENT_OPS_LOG_FILE', self.temp_log_file):
            operation = self.events_service.get_operation(test_op_id)
        
        # التحقق من أن العملية تم العثور عليها من القرص
        assert operation is not None
        assert operation["operation_id"] == test_op_id
        assert operation["user_query"] == "عملية اختبار"
        assert operation["status"] == "completed"  # آخر حالة
        assert len(operation["events"]) == 2
    
    def test_improved_disk_loading(self):
        """P3: تحسين تحميل آخر 200 سطر بدلاً من 100"""
        # إنشاء 150 حدث في الملف
        events = []
        for i in range(150):
            event = {
                "operation_id": f"op_test_{i}",
                "event_id": f"evt_{i}",
                "sequence": 1,
                "timestamp": f"2024-01-01T12:{i:02d}:00Z",
                "agent": "seraj",
                "event_type": "test_event",
                "status": "completed",
                "description_ar": f"حدث اختبار {i}",
                "user_query": f"اختبار {i}"
            }
            events.append(event)
        
        # كتابة الأحداث في الملف
        with open(self.temp_log_file, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        
        # إنشاء نسخة جديدة من الخدمة لاختبار التحميل
        AgentEventsService._instance = None
        with patch('agent_events_service.AGENT_OPS_LOG_FILE', self.temp_log_file):
            new_service = AgentEventsService.get_instance()
        
        # التحقق من أن جميع العمليات تم تحميلها (يجب أن تكون 150، أقل من 200)
        assert len(new_service.operations) == 150


class TestGraphNodesP3:
    """اختبار إضافة operation_id في عقد الرسم"""
    
    def test_ingest_user_message_creates_operation_id(self):
        """ingest_user_message يُنشئ operation_id"""
        from graph.nodes import ingest_user_message
        
        state: SerajState = {
            "user_query": "كم موظف في الشركة؟",
            "chat_id": "test",
            "user_name": "مستخدم اختبار"
        }
        
        with patch('agent_events_service.get_events_service') as mock_service:
            mock_events_service = Mock()
            mock_service.return_value = mock_events_service
            
            result = ingest_user_message(state)
            
            # التحقق من وجود operation_id
            assert "operation_id" in result
            assert result["operation_id"] is not None
            
            # التحقق من استدعاء start_operation
            mock_events_service.start_operation.assert_called_once()
            call_args = mock_events_service.start_operation.call_args[1]
            assert call_args["user_query"] == "كم موظف في الشركة؟"
            assert call_args["operation_id"] == result["operation_id"]


class TestAgenticNodesP3:
    """اختبار إصدار الأحداث من العقد الذكية"""
    
    def setup_method(self):
        self.mock_events_service = Mock()
        self.mock_get_events_service = patch('graph.agentic_nodes.get_events_service', 
                                           return_value=self.mock_events_service)
        self.mock_get_events_service.start()
    
    def teardown_method(self):
        self.mock_get_events_service.stop()
    
    def test_musleh_emits_events(self):
        """musleh_agentic_heal يُصدر أحداث البداية والنهاية"""
        from graph.agentic_nodes import musleh_agentic_heal
        
        # إعداد mock لـ MuslehAgent
        with patch('graph.agentic_nodes.MuslehAgent') as mock_musleh_class:
            mock_musleh = Mock()
            mock_musleh_class.return_value = mock_musleh
            
            # إعداد نتائج mock
            mock_musleh.perceive.return_value = {"analysis": "test"}
            mock_musleh.plan.return_value = {"plan": "fix"}
            mock_musleh.execute.return_value = {"fixed": True, "fixed_row": {"name": "fixed"}}
            mock_musleh.reflect.return_value = {"confidence": 0.9}
            
            state: SerajState = {
                "operation_id": "op_test_123",
                "company_id": 1,
                "company_name": "شركة الاختبار",
                "rejected_data": [{"name": "test", "validation_errors": ["error1"]}]
            }
            
            result = musleh_agentic_heal(state)
            
            # التحقق من إصدار الأحداث
            assert self.mock_events_service.emit_event.call_count >= 2
            
            # التحقق من حدث البداية
            start_call = self.mock_events_service.emit_event.call_args_list[0][1]
            assert start_call["operation_id"] == "op_test_123"
            assert start_call["agent"] == "musleh"
            assert start_call["event_type"] == "healing_started"
            assert start_call["status"] == "executing_write"
            
            # التحقق من حدث النهاية
            end_call = self.mock_events_service.emit_event.call_args_list[1][1]
            assert end_call["operation_id"] == "op_test_123"
            assert end_call["agent"] == "musleh"
            assert end_call["event_type"] == "healing_completed"
            assert end_call["status"] == "completed"
            
            # التحقق من النتيجة
            assert result["healed_data"] == [{"name": "fixed"}]
    
    def test_hares_emits_security_events(self):
        """hares_agentic_guard يُصدر أحداث الأمان"""
        from graph.agentic_nodes import hares_agentic_guard
        
        with patch('graph.agentic_nodes.HaresAgent') as mock_hares_class:
            mock_hares = Mock()
            mock_hares_class.return_value = mock_hares
            
            # إعداد نتائج الأمان
            mock_hares.perceive.return_value = {"request": "test"}
            mock_hares.plan.return_value = {"security_plan": "check"}
            mock_hares.execute.return_value = {"decision": "approve"}
            mock_hares.reflect.return_value = {"risk_summary": "منخفض المخاطر"}
            
            state: SerajState = {
                "operation_id": "op_security_test",
                "company_id": 1,
                "company_name": "شركة الاختبار",
                "write_plan": {"action": "update", "data": {"name": "test"}}
            }
            
            result = hares_agentic_guard(state)
            
            # التحقق من إصدار أحداث الأمان
            assert self.mock_events_service.emit_event.call_count >= 2
            
            # التحقق من حدث بدء فحص الأمان
            start_call = self.mock_events_service.emit_event.call_args_list[0][1]
            assert start_call["agent"] == "hares"
            assert start_call["event_type"] == "security_check_started"
            assert start_call["status"] == "verifying_permissions"
            
            # التحقق من النتيجة
            assert result["security_approved"] is True
            assert result["security_decision"] == "approve"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])